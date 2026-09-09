"""Destructive restart checks against a task-owned PostgreSQL database."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_repository import AgentDefinitionRepositoryError
from agent_console.digital_employee_definition import EmployeeDefinitionError
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_repository import KnowledgeRepositoryError
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_repository import RuntimeProfileRepositoryError
from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
from agent_console.skill_mcp_repository import SkillMcpRepositoryError
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_repository import (
    WorkflowDefinitionRepositoryError,
)
from psycopg.conninfo import conninfo_to_dict, make_conninfo

MIGRATIONS = Path(__file__).parents[1] / "migrations"
DATABASE_URL = os.environ.get("RESTART_SCHEMA_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real task-owned PostgreSQL 15 required"
)


_OWNED_SCHEMAS = (
    "digital_employee_definition",
    "execution_authority",
    "agent_definition",
    "skill_mcp_resource",
    "knowledge_quality",
    "knowledge_operation",
    "workflow_definition",
    "runtime_profile",
)


@pytest.fixture(scope="session")
def task_database() -> Iterator[str]:
    parameters = conninfo_to_dict(DATABASE_URL or "")
    database_name = f"restart_schema_{uuid.uuid4().hex}"
    admin_parameters = {**parameters, "dbname": "postgres"}
    admin_url = make_conninfo(**admin_parameters)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{database_name}"')
    database_url = make_conninfo(**{**parameters, "dbname": database_name})
    try:
        yield database_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')


@pytest.fixture
def isolated_database(task_database: str) -> Iterator[str]:
    def reset() -> None:
        with psycopg.connect(task_database, autocommit=True) as connection:
            for schema in _OWNED_SCHEMAS:
                connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

    reset()
    try:
        yield task_database
    finally:
        reset()


def _knowledge(database_url: str):
    repository = PostgresKnowledgeRepository(
        database_url,
        migration_path=MIGRATIONS / "0003_knowledge_operations.sql",
        quality_migration_path=MIGRATIONS / "0005_knowledge_quality_operations.sql",
        min_pool_size=1,
        max_pool_size=1,
    )
    repository.migrate()
    repository.migrate_quality()
    return repository, repository.compatibility, KnowledgeRepositoryError


def _knowledge_quality(database_url: str):
    repository, _, error = _knowledge(database_url)
    return repository, repository.quality_compatibility, error


def _runtime_profile(database_url: str):
    repository = PostgresRuntimeProfileRepository(
        database_url,
        migration_path=MIGRATIONS / "0007_workflow_runtime_profiles.sql",
        min_pool_size=1,
        max_pool_size=1,
    )
    repository.migrate()
    return repository, repository.compatibility, RuntimeProfileRepositoryError


def _workflow_definition(database_url: str):
    repository = PostgresWorkflowDefinitionRepository(
        database_url,
        migration_path=MIGRATIONS / "0007_workflow_runtime_profiles.sql",
        min_pool_size=1,
        max_pool_size=1,
    )
    repository.migrate()
    return repository, repository.compatibility, WorkflowDefinitionRepositoryError


def _skill_mcp(database_url: str):
    repository = PostgresSkillMcpRepository(
        database_url,
        migration_path=MIGRATIONS / "0002_skill_mcp_lifecycle.sql",
        min_pool_size=1,
        max_pool_size=1,
    )
    repository.migrate()
    return repository, repository.compatibility, SkillMcpRepositoryError


def _agent_definition(database_url: str):
    skill, _, _ = _skill_mcp(database_url)
    knowledge, _, _ = _knowledge(database_url)
    repository = PostgresAgentDefinitionRepository(
        database_url,
        migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
        governed_bindings_migration_path=MIGRATIONS
        / "0006_agent_governed_bindings.sql",
        min_pool_size=1,
        max_pool_size=1,
    )
    repository.migrate()
    skill.pool.close()
    knowledge.pool.close()
    return repository, repository.compatibility, AgentDefinitionRepositoryError


def _employee_definition(database_url: str):
    authority = PostgresExecutionAuthorityRepository(
        database_url,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
        min_pool_size=1,
        max_pool_size=1,
    )
    authority.migrate()
    repository = PostgresEmployeeDefinitionRepository(authority)
    migration = MIGRATIONS / "0014_digital_employee_identity.sql"
    repository.migrate(migration)
    return (
        repository,
        lambda: repository.compatibility(migration),
        EmployeeDefinitionError,
    )


OwnerFactory = Callable[[str], tuple[object, Callable[[], None], type[Exception]]]


@pytest.mark.parametrize(
    ("factory", "damage"),
    (
        (_knowledge, "DROP TABLE knowledge_operation.purge_tombstones"),
        (_knowledge_quality, "DROP TABLE knowledge_quality.entities"),
        (_runtime_profile, "DROP TABLE runtime_profile.profiles CASCADE"),
        (_workflow_definition, "DROP TABLE workflow_definition.definitions CASCADE"),
        (_skill_mcp, "DROP TABLE skill_mcp_resource.professional_facts"),
        (_agent_definition, "DROP TABLE agent_definition.tombstones"),
        (
            _employee_definition,
            "DROP TABLE digital_employee_definition.execution_bindings",
        ),
    ),
)
def test_correct_ledger_rejects_missing_owner_structure(
    isolated_database: str, factory: OwnerFactory, damage: str
) -> None:
    repository, compatibility, error = factory(isolated_database)
    try:
        compatibility()
        with psycopg.connect(isolated_database) as connection:
            connection.execute(damage)
        with pytest.raises(error, match="SCHEMA_INCOMPATIBLE"):
            compatibility()
    finally:
        repository.pool.close()


@pytest.mark.parametrize(
    "damage",
    (
        "ALTER TABLE knowledge_operation.purge_tombstones DROP COLUMN tombstone",
        "ALTER TABLE knowledge_operation.purge_tombstones "
        "ALTER COLUMN knowledge_id TYPE varchar(255)",
        "ALTER TABLE knowledge_operation.purge_tombstones "
        "DROP CONSTRAINT purge_tombstones_pkey",
    ),
)
def test_correct_ledger_rejects_missing_column_wrong_type_or_constraint(
    isolated_database: str, damage: str
) -> None:
    repository, compatibility, error = _knowledge(isolated_database)
    try:
        compatibility()
        with psycopg.connect(isolated_database) as connection:
            connection.execute(damage)
        with pytest.raises(error, match="KNOWLEDGE_SCHEMA_INCOMPATIBLE"):
            compatibility()
    finally:
        repository.pool.close()


def test_employee_version_14_adapter_mismatch_fails_closed(
    isolated_database: str,
) -> None:
    repository, compatibility, error = _employee_definition(isolated_database)
    try:
        compatibility()
        with psycopg.connect(isolated_database) as connection:
            connection.execute(
                "UPDATE digital_employee_definition.schema_migrations "
                "SET adapter='wrong-adapter' WHERE version=14"
            )
        with pytest.raises(error, match="EMPLOYEE_SCHEMA_INCOMPATIBLE"):
            compatibility()
    finally:
        repository.pool.close()
