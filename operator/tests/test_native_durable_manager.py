"""Controlled local children only; no DB, model or actual service process."""

# ruff: noqa: F401,F811 -- Reuse the isolated local process fixture.
import time
from datetime import datetime
from types import SimpleNamespace

from agent_operator.native_host_service_state import read
from agent_operator.native_host_startup import digest
from test_native_host_service import item, service


def ended(service, child):
    service.candidates.clear()
    service.tick()
    deadline = time.monotonic() + 3
    while child.process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert child.process.poll() is not None


def proof(cp_record, startup, receipt):
    cp = SimpleNamespace(
        worker_id=cp_record["workerId"], startup_record_digest=startup["digest"]
    )
    observation = SimpleNamespace(
        process_identity_digest=digest(
            {
                k: cp_record.get(k)
                for k in ("pid", "processBirth", "boot", "startupDigest", "workerId")
            }
        ),
        exit_receipt_digest=digest(receipt),
        stopped_at=datetime.fromisoformat(receipt["stoppedAt"]),
    )
    return cp, observation


def test_exact_exit_confirmation_retries_same_receipt_without_restart(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    service.discovery.wait_access = object()
    calls = []

    def stopped(actual, record, startup, receipt, verify):
        assert actual == candidate
        verify(None, *proof(record, startup, receipt))
        calls.append(dict(receipt))
        if len(calls) == 1:
            raise RuntimeError("CONTROLLED_OBSERVER_UNAVAILABLE")

    service.discovery.stopped = stopped
    ended(service, child)
    service.tick()
    assert not service.children
    assert read(child.status_path)["exitProof"]["record"]["exitReceipt"] == calls[0]
    service.recover_wait_exit(candidate)
    assert not service.children
    assert len(service.spawned) == 1
    assert len(calls) == 2 and calls[0] == calls[1]
    from agent_operator.native_host_service import HostService

    restored = HostService(service.config, service.discovery)
    restored.recover_wait_exit(candidate)
    assert len(calls) == 3 and calls[0] == calls[2]
    assert not restored.children


def test_missing_startup_never_generates_stop_confirmation(service):
    service.candidates.append(item())
    service.tick()
    child = next(iter(service.children.values()))
    service.discovery.wait_access = object()
    calls = []
    service.discovery.stopped = lambda *args: calls.append(args)
    ended(service, child)
    from pathlib import Path

    Path(child.status["recordPath"]).unlink()
    service.tick()
    assert not calls and not service.children
    assert "exitProof" in child.status
    assert service.last_error == "WAIT_STOP_UNCONFIRMED"


def test_live_advancing_child_uses_maintenance_not_launch_eligibility(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    service.discovery.current = lambda _: None
    calls = []

    def maintain(value, record):
        calls.append((value, record["startupDigest"]))
        return value

    service.discovery.maintain = maintain
    service.tick()
    assert calls and child.control_fd >= 0 and child.process.poll() is None
    assert len(service.spawned) == 1


def discovery(waiting):
    from contextlib import contextmanager

    from agent_operator.native_host_service_discovery import Discovery

    class Connection:
        def execute(self, sql, params):
            self.sql = sql
            return self

        def fetchone(self):
            return {"record": {"state": "RUNNING"}}

        def fetchall(self):
            return [{"state": "EFFECT_STARTED", "worker_id": "worker"}]

    @contextmanager
    def connection():
        yield Connection()

    access = SimpleNamespace(inspect=lambda c, candidate: waiting)
    work = SimpleNamespace(
        owned_business=object(),
        policy=SimpleNamespace(enabled=True, digest="policy"),
        _owned_receipt=lambda row, now: True,
    )
    assembly = SimpleNamespace(
        worker=SimpleNamespace(
            repository=SimpleNamespace(work=work),
            transport=SimpleNamespace(caller=SimpleNamespace(wait_access=access)),
        ),
        execution_repository=SimpleNamespace(
            pool=SimpleNamespace(connection=connection)
        ),
    )
    reader = Discovery(assembly, ("ns", "domain", "human:a"), "db-a")
    row = {
        "command_key": "command",
        "result": {
            "executionAuthorizationDigest": "policy",
            "subject": "human:a",
            "preparationDigest": "a" * 64,
            "runId": "run:a",
        },
    }
    return reader, row


def test_wait_discovery_requires_answer_and_stop_but_preserves_live_advancement():
    waiting = {
        "state": "QUIESCING",
        "resumable": False,
        "activeWorkerId": "worker",
        "startupRecordDigest": "startup",
    }
    reader, row = discovery(waiting)
    for state in (
        "QUIESCING",
        "WAITING_FOR_USER",
        "CONTINUATION_CLAIMED",
        "ADVANCING",
        "ANSWER_SAVED",
    ):
        waiting["state"] = state
        assert reader.inspect(row) is None
    waiting["resumable"] = True
    assert reader.inspect(row) is not None
    waiting["state"] = "ADVANCING"
    active = {"workerId": "worker", "startupDigest": "startup", "released": True}
    assert reader.inspect(row, active_process=active) is not None
    waiting["state"] = "CONTINUATION_CLAIMED"
    assert reader.inspect(row, active_process=active) is not None
    assert reader.inspect(row) is None
    assert (
        reader.inspect(row, active_process={**active, "startupDigest": "another"})
        is None
    )
    assert reader.inspect(row) is None
    reader.wait_access.inspect = lambda c, candidate: None
    assert reader.inspect(row) is not None


def test_stop_observation_precedes_launch_filter_and_read_failure_does_not_spawn():
    import pytest

    waiting = {"state": "ANSWER_SAVED", "resumable": False}
    reader, row = discovery(waiting)
    calls = []

    def observed(candidate):
        calls.append(candidate)
        waiting["resumable"] = True

    reader.observe_stopped = observed
    assert reader.inspect(row, observe_stopped=True) is not None
    assert len(calls) == 1
    reader.wait_access.inspect = lambda c, candidate: (_ for _ in ()).throw(
        RuntimeError("READ_FAILED")
    )
    with pytest.raises(RuntimeError, match="READ_FAILED"):
        reader.inspect(row, observe_stopped=True)
    assert len(calls) == 1


def test_shutdown_records_exit_proof_for_owner_observation_after_manager_restart(
    service,
):
    from agent_operator.native_host_service import HostService

    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    service.discovery.wait_access = object()
    service.discovery.stopped = lambda *args: (_ for _ in ()).throw(
        RuntimeError("OFFLINE")
    )
    service.close()
    saved = read(child.status_path)
    assert saved["state"] == "EXIT_CONFIRMED" and saved["exitProof"]
    calls = []

    def stopped(candidate, record, startup, receipt, verify):
        verify(None, *proof(record, startup, receipt))
        calls.append(receipt)

    service.discovery.stopped = stopped
    restored = HostService(service.config, service.discovery)
    restored.recover_wait_exit(candidate)
    assert calls == [saved["exitProof"]["record"]["exitReceipt"]]
    assert not restored.children and len(service.spawned) == 1


def test_missing_pid_without_prior_exit_proof_cannot_create_stop_fact(service):
    candidate = item()
    service.candidates.append(candidate)
    service.tick()
    child = next(iter(service.children.values()))
    ended(service, child)
    service.tick()
    assert not service.children and "exitProof" not in read(child.status_path)
    service.discovery.wait_access = object()
    calls = []
    service.discovery.stopped = lambda *args: calls.append(args)
    service.recover_wait_exit(candidate)
    assert not calls and "exitProof" not in read(child.status_path)


def test_owner_stop_failure_releases_dead_capacity_but_never_restarts_wait(service):
    service.config.value["maxHosts"] = 1
    first, second = item(), item("b")
    service.candidates.append(first)
    service.tick()
    child = next(iter(service.children.values()))
    service.discovery.wait_access = object()
    service.discovery.stopped = lambda *args: (_ for _ in ()).throw(
        RuntimeError("EXPIRED")
    )
    ended(service, child)
    service.candidates.append(second)
    service.tick()
    assert len(service.children) == 1 and len(service.spawned) == 2
    assert next(iter(service.children.values())).candidate == second
    before = read(child.status_path)["exitProof"]
    assert service.recover_wait_exit(first) is False
    assert read(child.status_path)["exitProof"] == before
    assert len(service.spawned) == 2


def test_failed_wait_observation_prevents_launch_even_if_old_reader_says_resumable():
    reader, row = discovery({"state": "ANSWER_SAVED", "resumable": True})
    reader.observe_stopped = lambda candidate: False
    assert reader.inspect(row, observe_stopped=True) is None
