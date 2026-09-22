"""Bounded process tests; phase substitutes are labelled, not TLS evidence."""

import multiprocessing
import threading
from types import SimpleNamespace as NS

import pytest
from agent_console import responses_deadline as boundary
from responses_deadline_test_jobs import (
    ResultJob,
    StalledJob,
    UnreapableProcess,
    stalled_startup,
)


def config(total=1, connect=1):
    return NS(
        total_timeout_seconds=total,
        connect_timeout_seconds=connect,
        maximum_response_bytes=64000,
    )


def assert_reaped(d):
    assert d["reaped"]
    assert d["cleanup_seconds"] <= 2
    assert d["worker_pid"] not in [p.pid for p in multiprocessing.active_children()]


@pytest.mark.parametrize(
    "phase",
    [
        "PREPARE",
        "CREDENTIAL",
        "CONNECT",
        "SEND_REQUEST",
        "WAIT_HEADERS",
        "READ_BODY",
        "VALIDATE_RESPONSE",
        "CLOSE",
    ],
)
def test_phase_substitute_has_total_bound_and_reaps(phase, record_property):
    with pytest.raises(boundary.ResponsesBoundaryError) as raised:
        boundary.supervise(StalledJob(phase), config())
    d = raised.value.diagnostic
    record_property("deadline", d)
    assert d["stage"] == phase  # prove fixture reached the intended phase
    assert d["reason"] == "TOTAL_DEADLINE"
    assert 0.9 <= d["decision_seconds"] < 1.5
    assert_reaped(d)


def test_worker_import_startup_is_in_total_budget():
    with pytest.raises(boundary.ResponsesBoundaryError) as raised:
        boundary.supervise(None, config(), worker=stalled_startup)
    d = raised.value.diagnostic
    assert d["stage"] == "STARTUP"
    assert d["reason"] == "TOTAL_DEADLINE"
    assert_reaped(d)


def test_connect_subdeadline_starts_at_explicit_connect_stage():
    with pytest.raises(boundary.ResponsesBoundaryError) as raised:
        boundary.supervise(StalledJob("CONNECT"), config(total=3, connect=1))
    d = raised.value.diagnostic
    assert d["reason"] == "CONNECT_DEADLINE"
    assert 0.9 <= d["decision_seconds"] - d["stage_seconds"]["CONNECT"] < 1.5
    assert_reaped(d)


def test_active_cancel_never_accepts_late_success():
    signal = threading.Event()
    timer = threading.Timer(0.7, signal.set)
    timer.start()
    try:
        with pytest.raises(boundary.ResponsesBoundaryError) as raised:
            boundary.supervise(ResultJob(2), config(5), cancel=signal)
        assert raised.value.diagnostic["reason"] == "CANCELLED"
        assert_reaped(raised.value.diagnostic)
    finally:
        timer.cancel()
        timer.join()


def test_success_also_reaps_before_return():
    result, diagnostic = boundary.supervise(ResultJob(), config(3))
    assert result == {"accepted": True}
    assert diagnostic["reason"] == "RESULT_ACCEPTED"
    assert_reaped(diagnostic)


def test_unreapable_worker_is_observable_not_success(monkeypatch):
    monkeypatch.setattr(
        boundary.multiprocessing,
        "get_context",
        lambda _: NS(Process=lambda **kwargs: UnreapableProcess()),
    )
    with pytest.raises(boundary.ResponsesBoundaryError) as raised:
        boundary.supervise(ResultJob(), config(total=0.05))
    assert raised.value.diagnostic["reason"] == "CLEANUP_FAILURE"
    assert not raised.value.diagnostic["reaped"]


def test_external_cancel_consumed_by_disconnect_probe_is_still_propagated():
    """A disconnect CancelScope can consume delivery, but not cancel intent."""
    import asyncio
    import threading
    from contextlib import suppress

    from agent_console.responses_deadline import CANCEL, cancellable_request

    persisted = threading.Event()

    class Request:
        async def is_disconnected(self):
            asyncio.current_task().cancel()
            # Simulate the probe consuming cancellation delivery.
            with suppress(asyncio.CancelledError):
                await asyncio.sleep(0)
            return False

    def action():
        cancelled = CANCEL.get().wait(0.5)
        persisted.set()
        return cancelled

    async def exercise():
        with pytest.raises(asyncio.CancelledError):
            await cancellable_request(Request(), action)
        assert persisted.is_set()

    asyncio.run(exercise())
