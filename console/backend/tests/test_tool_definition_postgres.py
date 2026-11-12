# ruff: noqa: F811 -- Existing disposable PostgreSQL fixture.
"""Real database draft ownership, idempotency and exact historical reads."""

import json
from pathlib import Path

import psycopg
import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.tool_definition_postgres import (
    PostgresToolDefinitionRepository,
    ToolStorageError,
)
from test_tool_import import api
from test_workbench_authorization_postgres import repository  # noqa: F401


@pytest.fixture
def owner(repository):
    owner = PostgresToolDefinitionRepository(repository.pool)
    path = Path(__file__).parents[1] / "migrations/0061_tool_definitions.sql"
    owner.migrate(path)
    owner.compatibility(path)
    return owner


def save(
    owner,
    scope,
    value=None,
    *,
    command="import:1",
    selected=None,
    expected=None,
    actor="human:test",
    effects=None,
):
    payload = json.dumps(value or api()).encode()
    with owner.pool.connection() as conn, conn.transaction():
        return owner.import_drafts(
            conn,
            scope,
            "API",
            payload,
            selected or ["orders"],
            expected or {},
            effects=effects,
            command_id=command,
            actor_id=actor,
            decision_id="decision:fixture",
        )


def read(owner, scope, tool, revision=None):
    with owner.pool.connection() as conn:
        return owner.read(conn, scope, tool, revision)


def test_persistent_import_duplicate_replay_and_stale_revision(owner):
    scope = ScopeIdentity("tools-a", "test")
    first = save(owner, scope)
    item = first["items"][0]
    assert item["changed"] and item["state"] == "DRAFT"
    restarted = PostgresToolDefinitionRepository(owner.pool)
    original = read(restarted, scope, item["toolId"])
    assert original["record"]["operation"]["sideEffect"] == "UNCONFIRMED"
    assert (
        original["publishedRevisionId"] is None and not original["executionAuthorized"]
    )
    replay = save(restarted, scope)
    assert replay["replayed"] and replay["items"] == first["items"]
    duplicate = save(owner, scope, command="import:duplicate")
    assert (
        duplicate["items"][0]["changed"] is False and duplicate["items"][0]["existing"]
    )
    assert read(owner, scope, item["toolId"]) == original
    value = api()
    value["paths"]["/orders"]["get"]["summary"] = "Revised purpose"
    with pytest.raises(ToolStorageError, match="TOOL_COMMAND_CONFLICT"):
        save(owner, scope, value)
    changed = save(owner, scope, value, command="import:2", expected={"orders": 1})[
        "items"
    ][0]
    assert (
        changed["revisionId"] != item["revisionId"] and changed["aggregateVersion"] == 2
    )
    assert (
        read(owner, scope, item["toolId"], item["revisionId"])["record"]
        == original["record"]
    )
    assert read(owner, scope, item["toolId"])["record"]["purpose"] == "Revised purpose"
    with pytest.raises(ToolStorageError, match="TOOL_VERSION_CONFLICT"):
        save(owner, scope, value, command="import:stale", expected={"orders": 1})
    with owner.pool.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM tool_definition.revisions WHERE "
                "namespace='tools-a'"
            ).fetchone()["n"]
            == 2
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM tool_definition.definitions WHERE "
                "namespace='tools-a' AND draft_revision_id IS NOT NULL"
            ).fetchone()["n"]
            == 1
        )


def test_scope_actor_isolation_and_atomic_selection(owner):
    scope = ScopeIdentity("tools-a", "test")
    other = ScopeIdentity("tools-b", "test")
    first = save(owner, scope)["items"][0]
    with pytest.raises(ToolStorageError, match="TOOL_NOT_FOUND"):
        read(owner, other, first["toolId"])
    with pytest.raises(ToolStorageError, match="TOOL_COMMAND_CONFLICT"):
        save(owner, scope, actor="human:other")
    assert save(owner, other)["items"][0]["changed"]
    value = api()
    value["paths"]["/new"] = {"get": {"operationId": "new", "responses": {}}}
    with pytest.raises(ToolStorageError, match="TOOL_VERSION_CONFLICT"):
        save(
            owner,
            scope,
            value,
            command="import:atomic",
            selected=["new", "orders"],
            expected={"orders": 88},
        )
    with owner.pool.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM tool_definition.definitions WHERE "
                "namespace='tools-a'"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM tool_definition.receipts WHERE "
                "namespace='tools-a' AND command_id='import:atomic'"
            ).fetchone()["n"]
            == 0
        )


def test_artifact_and_revision_receipts_cannot_be_rewritten(owner):
    scope = ScopeIdentity("tools-a", "test")
    first = save(owner, scope)
    with owner.pool.connection() as conn:
        kind, payload = owner.source(conn, scope, first["sourceDigest"])
        assert kind == "API" and json.loads(payload) == api()
    for table in ["sources", "revisions", "receipts"]:
        with (
            pytest.raises(psycopg.errors.RaiseException, match="TOOL_IMMUTABLE_RECORD"),
            owner.pool.connection() as conn,
            conn.transaction(),
        ):
            conn.execute("DELETE FROM tool_definition." + table)


def test_schema_check_rejects_missing_nullable_head_column(owner):
    with owner.pool.connection() as conn, conn.transaction():
        conn.execute(
            "ALTER TABLE tool_definition.definitions DROP COLUMN published_revision_id"
        )
    with pytest.raises(ToolStorageError, match="TOOL_SCHEMA_INCOMPATIBLE"):
        owner.compatibility(
            Path(__file__).parents[1] / "migrations/0061_tool_definitions.sql"
        )


def test_import_effect_declaration_is_persisted_and_never_overwrites_duplicate(owner):
    scope = ScopeIdentity("effect-scope", "test")
    first = save(owner, scope, effects={"orders": "read-only"})["items"][0]
    original = read(owner, scope, first["toolId"])
    assert original["record"]["operation"]["sideEffect"] == "read-only"
    assert original["record"]["validation"] is None
    assert not original["executionAuthorized"]
    assert save(owner, scope, effects={"orders": "read-only"})["replayed"]
    with pytest.raises(ToolStorageError, match="TOOL_COMMAND_CONFLICT"):
        save(owner, scope, effects={"orders": "external-write"})
    duplicate = save(
        owner, scope, command="duplicate", effects={"orders": "external-write"}
    )
    assert not duplicate["items"][0]["changed"]
    assert read(owner, scope, first["toolId"]) == original
    with pytest.raises(ToolStorageError, match="TOOL_IMPORT_EFFECT_INVALID"):
        save(owner, scope, command="invalid", effects={"not-selected": "read-only"})
