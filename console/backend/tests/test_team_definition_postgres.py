"""Real isolated PostgreSQL storage checks; not API authorization acceptance."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.team_definition import TeamDefinitionError
from agent_console.team_definition_postgres import PostgresTeamDefinitionRepository
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from test_team_definition import team

URL = os.environ.get("TEAM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
MIGRATION = Path(__file__).parents[1] / "migrations/0051_team_definition.sql"


@pytest.fixture
def store():
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        repo = PostgresTeamDefinitionRepository(pool)
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
    return replace(team(), scope=ScopeIdentity("test-" + uuid4().hex, "isolated"))


def test_restart_replay_and_scope_isolation(store):
    revision = fresh()
    first = save(store, revision)
    assert first["aggregateVersion"] == 1
    # New connection/pool models service repository reconstruction.
    with ConnectionPool(URL, kwargs={"row_factory": dict_row}) as pool:
        restarted = PostgresTeamDefinitionRepository(pool)
        assert save(restarted, revision)["replayed"]
        with pool.connection() as conn:
            assert (
                restarted.read(
                    conn, revision.scope, revision.team_id, revision.revision_id
                )
                == revision
            )
            with pytest.raises(TeamDefinitionError, match="TEAM_NOT_FOUND"):
                restarted.read(
                    conn,
                    ScopeIdentity("other", "isolated"),
                    revision.team_id,
                    revision.revision_id,
                )
    with pytest.raises(TeamDefinitionError, match="TEAM_COMMAND_CONFLICT"):
        save(store, replace(revision, title="不同内容"))


def test_concurrent_successors_preserve_history(store):
    revision = fresh()
    save(store, revision)

    def edit(n):
        successor = replace(
            revision,
            revision_id=f"team-revision:{n}",
            predecessor_revision_id=revision.revision_id,
            title=f"团队 {n}",
        )
        try:
            return save(store, successor, f"command:{n}", 1)["aggregateVersion"]
        except TeamDefinitionError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, [2, 3]))
    assert sorted(map(str, results)) == ["2", "TEAM_VERSION_CONFLICT"]
    with store.pool.connection() as conn:
        assert (
            store.read(conn, revision.scope, revision.team_id, revision.revision_id)
            == revision
        )
        rows = conn.execute(
            "SELECT * FROM team_definition.receipts WHERE namespace=%s",
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
            pytest.raises(psycopg.Error, match="TEAM_IMMUTABLE_RECORD"),
            store.pool.connection() as conn,
            conn.transaction(),
        ):
            conn.execute(
                f"DELETE FROM team_definition.{table} WHERE namespace=%s",
                (revision.scope.namespace,),
            )


def test_same_command_concurrency_creates_one_receipt(store):
    revision = fresh()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: save(store, revision), range(2)))
    assert sorted(result["replayed"] for result in results) == [False, True]
    with pytest.raises(TeamDefinitionError, match="TEAM_COMMAND_CONFLICT"):
        save(store, replace(revision, team_id="team:another"))
    with store.pool.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM team_definition.receipts WHERE namespace=%s",
            (revision.scope.namespace,),
        ).fetchone()["n"]
        assert count == 1


def test_linked_successor_requires_explicit_retention_or_removal(store):
    from agent_console.team_definition import TeamWorkReference

    original = replace(
        fresh(),
        work_links=(
            TeamWorkReference("run:1", "a" * 64, "problem:1", "revision:1", "b" * 64),
        ),
    )
    save(store, original)
    successor = replace(
        original,
        revision_id="team-revision:2",
        predecessor_revision_id=original.revision_id,
        work_links=None,
    )
    with pytest.raises(TeamDefinitionError, match="TEAM_WORK_CONFIRMATION_REQUIRED"):
        save(store, successor, "command:2", 1)
    removed = replace(successor, work_links=())
    assert save(store, removed, "command:2", 1)["aggregateVersion"] == 2
    with store.pool.connection() as conn:
        assert (
            store.read(
                conn, original.scope, original.team_id, original.revision_id
            ).work_links
            == original.work_links
        )
        assert not store.read(
            conn, removed.scope, removed.team_id, removed.revision_id
        ).work_links
        assert (
            conn.execute(
                "SELECT count(*) n FROM team_definition.receipts WHERE namespace=%s",
                (original.scope.namespace,),
            ).fetchone()["n"]
            == 2
        )
