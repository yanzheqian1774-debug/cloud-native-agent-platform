import os
import uuid
from pathlib import Path

import pytest
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService

DATABASE_URL = os.environ.get("WORKFLOW_RUNTIME_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0007_workflow_runtime_profiles.sql"
)
CONTENT = {
    "provider": "OPENCLAW",
    "resources": {
        "cpuRequest": "250m",
        "cpuLimit": "500m",
        "memoryRequest": "256Mi",
        "memoryLimit": "1Gi",
    },
    "isolation": "DEDICATED_RUNTIME",
    "stateMode": "EXTERNAL_REFERENCE",
    "sessionAffinity": "REQUIRED",
    "secretReferences": [],
    "openClawPackageRef": "oci://openclaw@sha256:abc",
}


def test_restart_recovers_profile_without_claiming_runtime_liveness():
    first = PostgresRuntimeProfileRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    first.migrate()
    service = RuntimeProfileService(first)
    scope = service.scope(f"runtime-restart-{uuid.uuid4()}", "quality")
    created = service.create(scope, "human:owner", "OpenClaw", CONTENT)
    rid = created["runtimeProfileId"]
    digest = created["revisions"][0]["digest"]
    first.pool.close()
    second = PostgresRuntimeProfileRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    second.compatibility()
    recovered = second.get(scope, rid)
    assert recovered["revisions"][0]["digest"] == digest
    assert (
        service.project(recovered)["technicalProjection"]["executionAuthority"] is False
    )
    second.pool.close()
