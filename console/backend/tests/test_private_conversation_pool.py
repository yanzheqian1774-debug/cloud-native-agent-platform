"""Connection reuse through the real application lifecycle and isolated PostgreSQL."""

# ruff: noqa: F401,F811
from contextlib import contextmanager

import psycopg
import pytest
from agent_console.private_conversation import ConversationError
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from fastapi.testclient import TestClient
from psycopg.pq import TransactionStatus
from psycopg_pool import PoolTimeout
from test_private_conversation import ctx, database, new, service
from test_workbench_bff import SessionStub


def test_pool_reuses_connection_with_rollback_and_owner_isolation(service):
    service.start_pool()
    pool = service._connection_pool
    try:
        identity = new(service)
        with service.connect() as c:
            first_pid = c.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            original_name = c.execute("SHOW application_name").fetchone()[
                "application_name"
            ]
        with pytest.raises(ValueError, match="rollback"), service.connect() as c:
            c.execute("SET LOCAL application_name = 'temporary-test-scope'")
            c.execute("CREATE TEMP TABLE conversation_pool_rollback_probe (value int)")
            raise ValueError("rollback")
        with pytest.raises(ConversationError, match="CONVERSATION_NOT_FOUND"):
            service.head(ctx("other-owner"), identity)
        assert (
            service.head(ctx(), identity)["conversation"]["conversation_id"] == identity
        )
        with service.connect() as c:
            assert c.info.transaction_status == TransactionStatus.IDLE
            assert (
                c.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
                == first_pid
            )
            assert (
                c.execute("SHOW application_name").fetchone()["application_name"]
                == original_name
            )
            assert (
                c.execute(
                    "SELECT to_regclass('pg_temp.conversation_pool_rollback_probe') "
                    "AS relation"
                ).fetchone()["relation"]
                is None
            )
        assert pool.get_stats()["connections_num"] == 1
        assert pool.max_size == 4
    finally:
        service.close_pool()
    assert pool.closed and service._connection_pool is None


def test_pool_acquisition_failure_has_no_fallback_connection_or_retry(
    service, monkeypatch
):
    class Exhausted:
        calls = 0

        @contextmanager
        def connection(self, *, timeout):
            self.calls += 1
            assert timeout == 5
            raise PoolTimeout("PRIVATE_POOL_DETAILS")
            yield  # pragma: no cover

    pool = Exhausted()
    service._connection_pool = pool
    monkeypatch.setattr(
        psycopg, "connect", lambda *a, **kw: pytest.fail("unexpected fallback")
    )
    with pytest.raises(PoolTimeout) as caught, service.connect():
        pytest.fail("unexpected query")
    assert caught.value._conversation_storage_phase == "POOL_ACQUIRE"
    assert pool.calls == 1
    service._connection_pool = None


def test_bff_lifespan_opens_and_closes_its_owned_pool(database):
    app = create_workbench_bff(
        SessionStub(),
        object(),
        WorkbenchBffPolicy("testserver", "https://testserver"),
        conversation_database_url=database,
    )
    records = app.state.conversation_actions.records
    assert records._connection_pool is None
    with TestClient(app, base_url="https://testserver"):
        pool = records._connection_pool
        assert pool is not None and not pool.closed
        with records.connect() as c:
            pid = c.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        with records.connect() as c:
            assert c.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"] == pid
    assert pool.closed and records._connection_pool is None
