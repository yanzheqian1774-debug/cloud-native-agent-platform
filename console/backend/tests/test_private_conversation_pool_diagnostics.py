"""Bounded storage diagnostics, without exception content or retries."""

# ruff: noqa: F401,F811
import psycopg
import pytest
from agent_console.private_conversation import PrivateConversations
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
from test_private_conversation import database
from test_workbench_bff import SessionStub


@pytest.mark.parametrize(
    "error,category,state",
    [
        (psycopg.OperationalError, "OPERATIONAL", "UNKNOWN"),
        (psycopg.errors.ConnectionTimeout, "CONNECTION_TIMEOUT", "UNKNOWN"),
        (PoolTimeout, "POOL_TIMEOUT", "UNKNOWN"),
        (psycopg.errors.SerializationFailure, "OPERATIONAL", "40001"),
        (psycopg.errors.UniqueViolation, "INTEGRITY", "23505"),
    ],
)
def test_storage_failure_diagnostic_is_safe_and_never_retries(
    database, monkeypatch, caplog, error, category, state
):
    from agent_console.workbench_bff import SESSION_COOKIE

    sessions = SessionStub()
    app = create_workbench_bff(
        sessions,
        object(),
        WorkbenchBffPolicy("testserver", "https://testserver"),
        conversation_database_url=database,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, sessions.secret)
    calls = []

    def fail(*args):
        calls.append(1)
        failure = error("PRIVATE_SQL_PASSWORD_AND_USER_CONTENT")
        if error is psycopg.errors.ConnectionTimeout:
            failure._conversation_storage_phase = "CONNECT"
        elif error is PoolTimeout:
            failure._conversation_storage_phase = "POOL_ACQUIRE"
        raise failure

    monkeypatch.setattr(PrivateConversations, "mutate", fail)
    response = client.post(
        "/api/workbench/v1/conversations/private-identity/messages",
        json={
            "idempotencyKey": "private-key",
            "expectedVersion": 0,
            "content": "PRIVATE_MESSAGE",
        },
        headers={"origin": "https://testserver", "x-csrf-token": "csrf-token"},
    )
    assert response.status_code == 503
    assert response.json() == {"reasonCode": "CONVERSATION_STORAGE_UNAVAILABLE"}
    assert calls == [1]
    records = [r for r in caplog.records if "conversation_storage_failure" in r.message]
    assert len(records) == 1
    record = records[0]
    assert response.headers["X-Diagnostic-ID"] in record.message
    assert "category=" + category in record.message
    assert "sqlstate=" + state in record.message
    assert (
        "phase="
        + (
            "CONNECT"
            if error is psycopg.errors.ConnectionTimeout
            else "POOL_ACQUIRE"
            if error is PoolTimeout
            else "UNKNOWN"
        )
        in record.message
    )
    assert "/conversations/{identity}/messages" in record.message
    assert "PRIVATE" not in record.message
    assert "private-identity" not in record.message
    assert record.exc_info is None


def test_connection_failure_marks_phase_without_retry(monkeypatch):
    calls = []
    failure = psycopg.errors.ConnectionTimeout("PRIVATE_CONNECTION_DETAILS")

    def fail(*args, **kwargs):
        calls.append(1)
        raise failure

    monkeypatch.setattr(psycopg, "connect", fail)
    records = PrivateConversations("unused", lambda *_: None)
    with pytest.raises(psycopg.errors.ConnectionTimeout) as raised:
        records.connect()
    assert raised.value is failure
    assert failure._conversation_storage_phase == "CONNECT"
    assert calls == [1]
