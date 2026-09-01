import os
import uuid
from pathlib import Path

import pytest
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_repository import (
    WorkflowDefinitionConflict,
    WorkflowDefinitionRepositoryError,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService

DATABASE_URL = os.environ.get("WORKFLOW_RUNTIME_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0007_workflow_runtime_profiles.sql"
)


def test_real_postgresql_migration_scope_and_optimistic_concurrency():
    store = PostgresWorkflowDefinitionRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    store.migrate()
    store.compatibility()
    service = WorkflowDefinitionService(store)
    scope = service.scope(f"workflow-postgres-{uuid.uuid4()}", "quality")
    record = service.create(
        scope,
        "human:owner",
        "Flow",
        {
            "description": "",
            "tasks": [{"taskId": "one", "name": "One", "dependsOn": []}],
            "inputs": [],
            "outputs": [],
            "runtimeProfile": {
                "kind": "RUNTIME_PROFILE",
                "resourceId": "runtime-profile:one",
                "revisionId": "runtime-profile-revision:one",
            },
        },
    )
    changed = {**record, "aggregateVersion": 2}
    store.replace(
        changed,
        expected_version=1,
        fact={"factId": f"workflow-fact:{uuid.uuid4()}", "event": "CONFORMANCE"},
    )
    with pytest.raises(WorkflowDefinitionConflict):
        store.replace(
            changed,
            expected_version=1,
            fact={"factId": f"workflow-fact:{uuid.uuid4()}", "event": "STALE"},
        )
    store.pool.close()


def test_migration_0007_checksum_mismatch_fails_closed():
    store = PostgresWorkflowDefinitionRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    store.migrate()
    try:
        with store.pool.connection() as connection:
            connection.execute(
                "UPDATE workflow_definition.schema_migrations "
                "SET checksum=%s WHERE version=1",
                ("0" * 64,),
            )
            connection.commit()
        with pytest.raises(
            WorkflowDefinitionRepositoryError,
            match="WORKFLOW_DEFINITION_SCHEMA_INCOMPATIBLE",
        ):
            store.compatibility()
    finally:
        with store.pool.connection() as connection:
            connection.execute(
                "UPDATE workflow_definition.schema_migrations "
                "SET checksum=%s WHERE version=1",
                (store.migration_checksum,),
            )
            connection.commit()
        store.pool.close()
