import os
import uuid
from pathlib import Path

import psycopg
import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_repository import AgentDefinitionConflict
from agent_console.agent_definition_service import AgentDefinitionService

DATABASE_URL = os.environ.get("AGENT_DEFINITION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0001_agent_definition_lifecycle.sql"
)
GOVERNED_MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0006_agent_governed_bindings.sql"
)


def apply_prerequisite_chain() -> None:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 6):
            path = next(
                (Path(__file__).parents[1] / "migrations").glob(f"{version:04d}_*.sql")
            )
            connection.execute(path.read_text())


def repository() -> PostgresAgentDefinitionRepository:
    apply_prerequisite_chain()
    value = PostgresAgentDefinitionRepository(
        DATABASE_URL or "",
        migration_path=MIGRATION,
        governed_bindings_migration_path=GOVERNED_MIGRATION,
    )
    value.migrate()
    return value


def test_migration_checksum_and_optimistic_concurrency() -> None:
    store = repository()
    service = AgentDefinitionService(store)
    scope = service.scope(f"postgres-conformance-{uuid.uuid4()}", "quality")
    created = service.create(
        scope,
        "human:owner",
        "Postgres Agent",
        {
            "title": "Quality Analyst",
            "duties": ["analyze quality"],
            "capabilities": ["supplier-quality-analysis"],
            "bindings": {
                "skills": [
                    {
                        "resourceId": "skill-definition:exact",
                        "revisionId": "skill-revision:exact",
                        "digest": "a" * 64,
                    }
                ]
            },
        },
    )
    with store.pool.connection() as connection:
        binding = connection.execute(
            "SELECT resource_id,resource_revision_id,resource_digest "
            "FROM agent_definition.revision_bindings "
            "WHERE definition_id=%s",
            (created["definitionId"],),
        ).fetchone()
    assert binding == {
        "resource_id": "skill-definition:exact",
        "resource_revision_id": "skill-revision:exact",
        "resource_digest": "a" * 64,
    }
    changed = {**created, "aggregateVersion": 2}
    store.replace(
        changed,
        expected_version=1,
        fact={
            "factId": "agent-fact:postgres-conformance",
            "event": "CONFORMANCE",
        },
    )
    with pytest.raises(AgentDefinitionConflict):
        store.replace(
            changed,
            expected_version=1,
            fact={"factId": "agent-fact:stale", "event": "STALE"},
        )
    store.pool.close()


def test_migration_0006_is_checksum_bound_and_rejects_newer_schema() -> None:
    store = repository()
    assert store.governed_bindings_checksum
    with store.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO agent_definition.schema_migrations"
            "(version,checksum,adapter) VALUES (7,%s,%s)",
            ("future", "agent-definition-postgresql-v1"),
        )
    with pytest.raises(Exception, match="AGENT_DEFINITION_SCHEMA_INCOMPATIBLE"):
        store.compatibility()
    with store.pool.connection() as connection, connection.transaction():
        connection.execute(
            "DELETE FROM agent_definition.schema_migrations WHERE version = 7"
        )
    store.pool.close()
