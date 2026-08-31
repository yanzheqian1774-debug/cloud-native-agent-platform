import os
import uuid
from pathlib import Path

import pytest
from agent_console.skill_mcp_postgres import (
    ADAPTER,
    PROFESSIONAL_ADAPTER,
    PROFESSIONAL_SCHEMA_VERSION,
    SCHEMA_VERSION,
    PostgresSkillMcpRepository,
)
from agent_console.skill_mcp_service import SkillMcpService

DATABASE_URL = os.environ.get("SKILL_MCP_TEST_DATABASE_URL")
MIGRATION = Path(__file__).parents[1] / "migrations" / "0002_skill_mcp_lifecycle.sql"
PROFESSIONAL_MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "0004_skill_mcp_professional_experience.sql"
)


def test_migration_has_scoped_keys_constraints_and_adapter_identity() -> None:
    sql = MIGRATION.read_text()
    assert "PRIMARY KEY (namespace, security_domain, kind, resource_id)" in sql
    assert "REFERENCES skill_mcp_resource.resources" in sql
    assert ADAPTER == "skill-mcp-resource-postgresql-v1" and SCHEMA_VERSION == 1
    professional = PROFESSIONAL_MIGRATION.read_text()
    assert "skill_mcp_resource.professional_facts" in professional
    assert "safe_fact jsonb NOT NULL" in professional
    assert PROFESSIONAL_ADAPTER == "skill-mcp-professional-postgresql-v1"
    assert PROFESSIONAL_SCHEMA_VERSION == 2


@pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
def test_real_postgres_migration_persistence_and_optimistic_concurrency() -> None:
    repository = PostgresSkillMcpRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    service = SkillMcpService(repository)
    scope = service.scope(f"skill-mcp-{uuid.uuid4()}", "quality")
    created = service.create(
        scope,
        "skill",
        "human:owner",
        "Persistent Skill",
        {
            "description": "Persistent skill",
            "capabilities": ["quality.lookup"],
            "instructions": "Perform bounded lookup",
        },
    )
    recovered = SkillMcpService(repository).get(scope, "skill", created["resourceId"])[
        "resource"
    ]
    assert recovered["revisions"][0]["digest"] == created["revisions"][0]["digest"]
    tested = service.save_test(
        scope,
        created["resourceId"],
        "human:owner",
        1,
        "Restart-safe regression",
        {"supplier": "ACME"},
        {"status": "healthy"},
    )
    restarted = SkillMcpService(repository).get(scope, "skill", created["resourceId"])[
        "resource"
    ]
    assert restarted["savedTests"] == tested["resource"]["savedTests"]
    with repository.pool.connection() as connection:
        fact = connection.execute(
            "SELECT fact_type FROM skill_mcp_resource.professional_facts "
            "WHERE namespace=%s AND security_domain=%s AND resource_id=%s",
            (scope.namespace, scope.security_domain, created["resourceId"]),
        ).fetchone()
    assert fact["fact_type"] == "TEST_CASE_SAVED"
    repository.pool.close()
