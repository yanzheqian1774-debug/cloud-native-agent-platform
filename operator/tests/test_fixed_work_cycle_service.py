"""Local cycle controls; real owner integration is in backend PG tests."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_operator.fixed_work_cycle_service import FixedWorkCycleService


@contextmanager
def value(v):
    yield v


def setup_service(saved=()):
    now = datetime.now(UTC)
    policy = N(
        tenantId="t",
        securityDomain="d",
        work=N(resource_id="w"),
        digest="p",
        allowedEventIds=("old", "current", "future"),
        eventWindows={
            "old": (now - timedelta(hours=2), now - timedelta(hours=1)),
            "current": (now - timedelta(seconds=1), now + timedelta(hours=1)),
            "future": (now + timedelta(hours=1), now + timedelta(hours=2)),
        },
    )
    c = N(
        transaction=lambda: value(None),
        execute=Mock(return_value=N(fetchall=lambda: [{"event_id": e} for e in saved])),
    )
    registry = N(
        _policy=lambda: policy,
        _check=Mock(return_value=now),
        repository=N(pool=N(connection=lambda: value(c))),
    )
    host = N(
        runtime=N(registry=registry),
        step=Mock(return_value={"stage": "START_COMMITTED"}),
    )
    service = FixedWorkCycleService(
        host, lambda: N(principal_id="service:s"), "db", enabled=True
    )
    return service, host


def test_default_off_never_observes_identity_or_database():
    service, host = setup_service()
    service.enabled = False
    with pytest.raises(ValueError, match="DISABLED"):
        service.step()
    host.runtime.registry._check.assert_not_called()


def test_no_backfill_or_early_dispatch_but_saved_old_event_is_read():
    service, _host = setup_service()
    assert [r["eventId"] for r in service.step()] == ["current"]
    service, _host = setup_service(("old",))
    assert [r["eventId"] for r in service.step()] == ["old", "current"]


def test_unknown_stops_later_slots_and_known_pending_guard_is_readable():
    service, host = setup_service(("old",))
    host.step.return_value = {
        "stage": "PLANNING_OBSERVATION",
        "result": {"technical_status": "OUTCOME_UNKNOWN"},
    }
    assert len(service.step()) == 1
    host.step.assert_called_once()
    host.step.side_effect = AuthorityError("FIXED_WORK_SERVICE_PREVIOUS_RUN_UNRESOLVED")
    assert service.step() == ({"eventId": "old", "stage": "WAITING_PREVIOUS_WORK"},)


def test_unrelated_failure_not_retried_or_reclassified():
    service, host = setup_service()
    host.step.side_effect = AuthorityError("SERVICE_CREDENTIAL_REVOKED")
    with pytest.raises(AuthorityError, match="REVOKED"):
        service.step()
    host.step.assert_called_once()


def test_run_uses_existing_private_singleton_and_stops_without_effect_cancel(
    monkeypatch, tmp_path
):
    service, host = setup_service()
    stop = Event()
    closed = []
    locks = []
    monkeypatch.setattr(
        "agent_operator.fixed_work_cycle_service.machine_lock_directory",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "agent_operator.fixed_work_cycle_service.lock", lambda p: locks.append(p) or 9
    )
    monkeypatch.setattr(
        "agent_operator.fixed_work_cycle_service.os.close", closed.append
    )

    def observed(rows):
        assert len(rows) == 1
        stop.set()

    service.run(stop, observed)
    assert len(locks) == 1 and locks[0].name.startswith("fixed-cycle-")
    assert closed == [9]
    host.step.assert_called_once()


def test_failed_prior_event_does_not_skip_next_event_budget_guard():
    service, host = setup_service(("old",))
    host.step.side_effect = [
        {"stage": "PLANNING_OBSERVATION", "result": {"technical_status": "FAILED"}},
        AuthorityError("FIXED_WORK_SERVICE_PREVIOUS_BUDGET_UNRESOLVED"),
    ]
    result = service.step()
    assert [r["eventId"] for r in result] == ["old", "current"]
    assert result[-1]["stage"] == "WAITING_PREVIOUS_WORK"
    assert host.step.call_count == 2
