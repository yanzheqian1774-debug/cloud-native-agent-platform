import os
import uuid
from pathlib import Path

import pytest
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService

DATABASE_URL = os.environ.get("WORKFLOW_RUNTIME_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0007_workflow_runtime_profiles.sql"
)


def test_restart_recovers_exact_identity_revision_digest_and_history():
    first = PostgresWorkflowDefinitionRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    first.migrate()
    service = WorkflowDefinitionService(first, lambda _s, _r: True)
    scope = service.scope(f"workflow-restart-{uuid.uuid4()}", "quality")
    created = service.create(
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
    rid = created["workflowDefinitionId"]
    digest = created["revisions"][0]["digest"]
    first.pool.close()
    second = PostgresWorkflowDefinitionRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    second.compatibility()
    recovered = second.get(scope, rid)
    assert recovered["workflowDefinitionId"] == rid
    assert recovered["revisions"][0]["digest"] == digest
    assert recovered["facts"][0]["event"] == "DRAFT_CREATED"
    second.pool.close()
