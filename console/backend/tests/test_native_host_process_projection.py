"""Optional safe projection; original progress authority remains upstream."""

import hashlib
import json
import time
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from agent_console.native_host_process_projection import process_projection


@pytest.fixture
def projection(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    monkeypatch.setenv("NATIVE_EXACT_HOST_SERVICE_STATUS_DIRECTORY", str(tmp_path))

    class Connection:
        def __init__(self):
            self.subjects = [{"principal_id": "human:a"}]

        def transaction(self):
            return nullcontext()

        def execute(self, query, params):
            assert "JOIN execution_authority.attempts" in query
            assert "JOIN execution_authority.prepared_task_bindings" in query
            assert "DISTINCT n.principal_id" in query and "LIMIT 2" in query
            assert params == (
                "ns",
                "d",
                "run:a",
                "governed-execution:prepared:" + "a" * 64,
            )
            return SimpleNamespace(fetchall=lambda: self.subjects)

    call = SimpleNamespace(
        context=SimpleNamespace(principal_id="human:a"), connection=Connection()
    )
    p = SimpleNamespace(
        namespace="ns", security_domain="d", digest="a" * 64, run_id="run:a"
    )
    identity = [p.namespace, p.security_domain, call.context.principal_id, p.digest]
    key = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / ("view-" + key + ".json")
    value = {
        "schema": "native-exact-host-view.v1",
        "identity": identity,
        "runId": p.run_id,
        "observedAt": time.time(),
        "validForSeconds": 30,
        "state": "READY",
        "reasonCode": None,
    }
    return call, p, path, value


def save(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)


def test_default_off_preserves_absence(projection, monkeypatch):
    call, p, _, _ = projection
    monkeypatch.delenv("NATIVE_EXACT_HOST_SERVICE_STATUS_DIRECTORY")
    assert process_projection(call, p) is None


@pytest.mark.parametrize(
    "state", ["QUEUED", "STARTING", "READY", "BLOCKED", "STOPPING", "UNKNOWN"]
)
def test_current_exact_safe_fields_only(projection, state):
    call, p, path, value = projection
    value.update(state=state, pid=123, path="/secret", token="not-returned")
    save(path, value)
    result = process_projection(call, p)
    assert result["state"] == state
    assert set(result) == {
        "state",
        "preparationDigest",
        "runId",
        "observedAt",
        "reasonCode",
    }


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "subject",
        "domain",
        "preparation",
        "run",
        "expired",
        "future",
        "state",
        "reason",
        "permission",
        "symlink",
    ],
)
def test_unreadable_or_wrong_binding_never_claims_queue_or_success(projection, change):
    call, p, path, value = projection
    if change == "missing":
        pass
    else:
        if change in {"subject", "domain", "preparation"}:
            value["identity"][{"domain": 1, "subject": 2, "preparation": 3}[change]] = (
                "other"
            )
        elif change == "run":
            value["runId"] = "other"
        elif change in {"expired", "future"}:
            value["observedAt"] += -31 if change == "expired" else 100
        elif change in {"state", "reason"}:
            value["state" if change == "state" else "reasonCode"] = "SECRET_EXCEPTION"
        save(path, value)
        if change == "permission":
            path.chmod(0o644)
        if change == "symlink":
            moved = path.with_suffix(".other")
            path.rename(moved)
            path.symlink_to(moved)
    result = process_projection(call, p)
    assert result["state"] == "UNKNOWN"
    assert result["observedAt"] is None


def test_fifo_is_unknown_without_blocking_read(projection):
    import os

    call, p, path, _ = projection
    os.mkfifo(path, 0o600)
    assert process_projection(call, p)["state"] == "UNKNOWN"


def test_native_authorization_precedes_local_projection(monkeypatch):
    from agent_console import native_host_process_projection, native_interaction
    from agent_console.authority_contracts import AuthorityError

    def denied(*_):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    observed = []
    monkeypatch.setattr(native_interaction, "records", denied)
    monkeypatch.setattr(
        native_host_process_projection,
        "process_projection",
        lambda *_: observed.append(True),
    )
    with pytest.raises(AuthorityError):
        native_interaction.progress(None, None, None)
    assert observed == []


def test_authorized_different_reader_uses_original_execution_subject(
    projection, monkeypatch
):
    from agent_console import native_interaction

    call, p, path, value = projection
    call.context.principal_id = "human:development-admin"
    save(path, value)
    checked = []

    def permitted(call, app, preparation):
        checked.append(call.context.principal_id)
        return []

    monkeypatch.setattr(native_interaction, "records", permitted)
    result = native_interaction.progress(call, None, p)
    assert checked == ["human:development-admin"]
    assert result["hostDispatch"]["state"] == "READY"
    assert "principal" not in json.dumps(result["hostDispatch"])


@pytest.mark.parametrize(
    "subjects",
    [
        [],
        [{"principal_id": "a"}, {"principal_id": "b"}],
        [{"principal_id": ""}],
        [{"principal_id": None}],
    ],
)
def test_absent_or_ambiguous_execution_subject_remains_unknown(projection, subjects):
    call, p, path, value = projection
    save(path, value)
    call.connection.subjects = subjects
    assert process_projection(call, p)["state"] == "UNKNOWN"


def test_subject_storage_failure_is_unknown_not_reader_identity_fallback(projection):
    from psycopg import OperationalError

    call, p, path, value = projection
    save(path, value)

    def unavailable(*_):
        raise OperationalError("controlled read failure")

    call.connection.execute = unavailable
    assert process_projection(call, p)["state"] == "UNKNOWN"
