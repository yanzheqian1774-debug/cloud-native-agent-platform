"""Real isolated PostgreSQL storage checks; not API authorization acceptance."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from agent_console.business_capability import BusinessCapabilityError
from agent_console.business_capability_postgres import (
    PostgresBusinessCapabilityRepository,
)
from agent_console.execution_domain import ScopeIdentity
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from test_business_capability import capability

URL = os.environ.get("CAPABILITY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
MIGRATION = Path(__file__).parents[1] / "migrations/0052_business_capability.sql"


@pytest.fixture
def store():
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        repo = PostgresBusinessCapabilityRepository(pool)
        repo.migrate(MIGRATION)
        repo.compatibility(MIGRATION)
        yield repo


def save(store, revision, command="command:1", expected=0):
    with store.pool.connection() as conn, conn.transaction():
        return store.save(
            conn,
            revision,
            expected_version=expected,
            command_id=command,
            actor_id="human:test",
            decision_id="decision:test",
        )


def fresh():
    return replace(capability(), scope=ScopeIdentity("test-" + uuid4().hex, "isolated"))


def test_restart_replay_and_scope_isolation(store):
    revision = fresh()
    first = save(store, revision)
    assert first["aggregateVersion"] == 1
    # New connection/pool models service repository reconstruction.
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        restarted = PostgresBusinessCapabilityRepository(pool)
        assert save(restarted, revision)["replayed"]
        with pool.connection() as conn:
            assert (
                restarted.read(
                    conn, revision.scope, revision.capability_id, revision.revision_id
                )
                == revision
            )
            with pytest.raises(BusinessCapabilityError, match="CAPABILITY_NOT_FOUND"):
                restarted.read(
                    conn,
                    ScopeIdentity("other", "isolated"),
                    revision.capability_id,
                    revision.revision_id,
                )
    with pytest.raises(BusinessCapabilityError, match="CAPABILITY_COMMAND_CONFLICT"):
        save(store, replace(revision, title="不同内容"))


def test_concurrent_successors_preserve_history(store):
    revision = fresh()
    save(store, revision)

    def edit(n):
        successor = replace(
            revision,
            revision_id=f"capability-revision:{n}",
            predecessor_revision_id=revision.revision_id,
            title=f"能力 {n}",
        )
        try:
            return save(store, successor, f"command:{n}", 1)["aggregateVersion"]
        except BusinessCapabilityError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, [2, 3]))
    assert sorted(map(str, results)) == ["2", "CAPABILITY_VERSION_CONFLICT"]
    with store.pool.connection() as conn:
        assert (
            store.read(
                conn, revision.scope, revision.capability_id, revision.revision_id
            )
            == revision
        )
        rows = conn.execute(
            "SELECT * FROM business_capability.receipts WHERE namespace=%s",
            (revision.scope.namespace,),
        ).fetchall()
        assert len(rows) == 2


def test_transaction_rollback_and_immutable_audit(store):
    revision = fresh()
    with (
        pytest.raises(RuntimeError),
        store.pool.connection() as conn,
        conn.transaction(),
    ):
        store.save(
            conn,
            revision,
            expected_version=0,
            command_id="command:1",
            actor_id="human:test",
            decision_id="decision:test",
        )
        raise RuntimeError("later authorization unit failed")
    assert not save(store, revision)["replayed"]
    for table in ("revisions", "receipts"):
        with (
            pytest.raises(psycopg.Error, match="CAPABILITY_IMMUTABLE_RECORD"),
            store.pool.connection() as conn,
            conn.transaction(),
        ):
            conn.execute(
                f"DELETE FROM business_capability.{table} WHERE namespace=%s",
                (revision.scope.namespace,),
            )


def test_same_command_concurrency_creates_one_receipt(store):
    revision = fresh()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: save(store, revision), range(2)))
    assert sorted(result["replayed"] for result in results) == [False, True]
    with pytest.raises(BusinessCapabilityError, match="CAPABILITY_COMMAND_CONFLICT"):
        save(store, replace(revision, capability_id="business-capability:another"))
    with store.pool.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM business_capability.receipts WHERE namespace=%s",
            (revision.scope.namespace,),
        ).fetchone()["n"]
        assert count == 1
