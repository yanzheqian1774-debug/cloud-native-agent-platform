"""Real dedicated PostgreSQL checks, not API authorization acceptance."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from agent_console.business_process_definition import BusinessArchitecture
from agent_console.business_process_postgres import (
    BusinessProcessStorageError,
    PostgresBusinessProcessRepository,
)
from agent_console.execution_domain import ScopeIdentity
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from test_business_process_definition import architecture, content

URL = os.environ.get("BUSINESS_PROCESS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
MIGRATION = Path(__file__).parents[1] / "migrations/0056_business_process.sql"


@pytest.fixture
def store():
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        repo = PostgresBusinessProcessRepository(pool)
        repo.migrate(MIGRATION)
        repo.compatibility(MIGRATION)
        scope = ScopeIdentity("process-test-" + uuid4().hex, "isolated")
        with pool.connection() as conn, conn.transaction():
            repo.save_architecture(
                conn,
                scope,
                architecture(),
                expected_version=0,
                command_id="architecture:create",
                actor_id="human:test",
                decision_id="decision:test",
            )
        yield repo, scope


def save(store, value=None, command="process:create", expected=0, actor="human:test"):
    repo, scope = store
    with repo.pool.connection() as conn, conn.transaction():
        return repo.save_process(
            conn,
            scope,
            "process:1",
            value or content(),
            expected_version=expected,
            command_id=command,
            actor_id=actor,
            decision_id="decision:test",
        )


def test_reconnect_receipt_replay_and_fixed_architecture_history(store):
    _repo, scope = store
    first = save(store)
    assert first["state"] == "DRAFT" and first["executionAuthorized"] is False
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        restarted = PostgresBusinessProcessRepository(pool)
        replay = save((restarted, scope))
        assert replay["replayed"] and replay["revisionId"] == first["revisionId"]
        with pool.connection() as conn, conn.transaction():
            original = restarted.read(conn, scope, "PROCESS", "process:1")
            changed = architecture().model_dump()
            changed["domains"][0]["name"] = "采购新名称"
            restarted.save_architecture(
                conn,
                scope,
                BusinessArchitecture.model_validate(changed),
                expected_version=1,
                command_id="architecture:rename",
                actor_id="human:test",
                decision_id="decision:test",
            )
            assert restarted.read(conn, scope, "PROCESS", "process:1") == original
            reference = original["record"]["architectureReference"]
            old_architecture = restarted.read(
                conn, scope, "ARCHITECTURE", "architecture", reference["revisionId"]
            )
            assert old_architecture["digest"] == reference["digest"]
            assert (
                old_architecture["record"]["content"]["domains"][0]["name"]
                == "采购管理"
            )


def test_changed_payload_or_actor_cannot_reuse_receipt(store):
    save(store)
    changed = content().model_copy(update={"purpose": "另一目的"})
    with pytest.raises(BusinessProcessStorageError, match="COMMAND_CONFLICT"):
        save(store, changed)
    with pytest.raises(BusinessProcessStorageError, match="COMMAND_CONFLICT"):
        save(store, actor="human:other")


def test_concurrent_edits_keep_one_successor_and_original_revision(store):
    repo, scope = store
    first = save(store)

    def edit(index):
        try:
            value = content().model_copy(update={"purpose": f"修改{index}"})
            return save(store, value, f"edit:{index}", 1)["aggregateVersion"]
        except BusinessProcessStorageError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as executor:
        result = list(executor.map(edit, [1, 2]))
    assert sorted(map(str, result)) == ["2", "BUSINESS_PROCESS_VERSION_CONFLICT"]
    with repo.pool.connection() as conn:
        old = repo.read(conn, scope, "PROCESS", "process:1", first["revisionId"])
        assert old["record"]["content"] == content().model_dump(mode="json")


def test_scope_isolation_and_transaction_rollback(store):
    repo, scope = store
    with (
        pytest.raises(RuntimeError, match="abort transaction"),
        repo.pool.connection() as conn,
        conn.transaction(),
    ):
        repo.save_process(
            conn,
            scope,
            "process:1",
            content(),
            expected_version=0,
            command_id="rolled-back",
            actor_id="human:test",
            decision_id="decision:test",
        )
        raise RuntimeError("abort transaction")
    with repo.pool.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM business_process.receipts WHERE "
                "namespace=%s AND command_id=%s",
                (scope.namespace, "rolled-back"),
            ).fetchone()["n"]
            == 0
        )
        with pytest.raises(BusinessProcessStorageError, match="NOT_FOUND"):
            repo.read(conn, scope, "PROCESS", "process:1")
    save(store)
    with (
        repo.pool.connection() as conn,
        pytest.raises(BusinessProcessStorageError, match="NOT_FOUND"),
    ):
        repo.read(conn, ScopeIdentity(scope.namespace, "other"), "PROCESS", "process:1")


def test_invalid_architecture_reference_writes_neither_revision_nor_receipt(store):
    repo, scope = store
    changed = content().model_copy(update={"group_id": "wrong-group"})
    with pytest.raises(BusinessProcessStorageError, match="ARCHITECTURE_MISMATCH"):
        save(store, changed)
    with repo.pool.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM business_process.definitions WHERE "
                "namespace=%s AND kind='PROCESS'",
                (scope.namespace,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM business_process.receipts WHERE "
                "namespace=%s AND kind='PROCESS'",
                (scope.namespace,),
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("table", ["revisions", "receipts"])
def test_history_cannot_be_rewritten(store, table):
    repo, scope = store
    save(store)
    from psycopg import sql

    with (
        pytest.raises(psycopg.Error, match="BUSINESS_PROCESS_IMMUTABLE_RECORD"),
        repo.pool.connection() as conn,
        conn.transaction(),
    ):
        conn.execute(
            sql.SQL("DELETE FROM business_process.{} WHERE namespace=%s").format(
                sql.Identifier(table)
            ),
            (scope.namespace,),
        )
