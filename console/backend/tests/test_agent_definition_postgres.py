import os
import uuid
from pathlib import Path

import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_repository import AgentDefinitionConflict
from agent_console.agent_definition_service import AgentDefinitionService

DATABASE_URL = os.environ.get("AGENT_DEFINITION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0001_agent_definition_lifecycle.sql"
)


def repository() -> PostgresAgentDefinitionRepository:
    value = PostgresAgentDefinitionRepository(
        DATABASE_URL or "", migration_path=MIGRATION
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
        },
    )
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
