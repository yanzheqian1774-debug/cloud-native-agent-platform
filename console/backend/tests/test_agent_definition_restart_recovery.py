import os
from pathlib import Path

import psycopg
import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
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


def test_restart_recovers_exact_published_identity_revision_and_digest() -> None:
    apply_prerequisite_chain()
    first_repository = PostgresAgentDefinitionRepository(
        DATABASE_URL or "",
        migration_path=MIGRATION,
        governed_bindings_migration_path=GOVERNED_MIGRATION,
    )
    first_repository.migrate()
    first = AgentDefinitionService(first_repository)
    scope = first.scope("restart-recovery", "quality")
    created = first.create(
        scope,
        "human:owner",
        "Recovery Agent",
        {
            "title": "Quality Analyst",
            "duties": ["analyze quality"],
            "capabilities": ["supplier-quality-analysis"],
        },
    )
    definition_id = created["definitionId"]
    validated = first.validate(scope, definition_id, "human:owner", 1)["definition"]
    revision = validated["revisions"][-1]
    reviewed = first.review(
        scope,
        definition_id,
        "human:reviewer",
        2,
        revision["digest"],
        "APPROVE",
        "exact digest verified",
    )["definition"]
    first.publish(
        scope,
        definition_id,
        "human:publisher",
        3,
        revision["digest"],
        reviewed["reviews"][-1]["reviewId"],
    )
    first_repository.pool.close()

    recovered_repository = PostgresAgentDefinitionRepository(
        DATABASE_URL or "",
        migration_path=MIGRATION,
        governed_bindings_migration_path=GOVERNED_MIGRATION,
    )
    recovered_repository.migrate()
    recovered = AgentDefinitionService(recovered_repository).get(scope, definition_id)
    assert recovered["definition"]["definitionId"] == definition_id
    assert recovered["definition"]["publishedRevisionId"] == revision["revisionId"]
    assert recovered["definition"]["revisions"][-1]["digest"] == revision["digest"]
    recovered_repository.pool.close()
