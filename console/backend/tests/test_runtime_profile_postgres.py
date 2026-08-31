import os
import uuid
from pathlib import Path

import pytest
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_repository import RuntimeProfileConflict
from agent_console.runtime_profile_service import RuntimeProfileService

DATABASE_URL = os.environ.get("WORKFLOW_RUNTIME_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0007_workflow_runtime_profiles.sql"
)
CONTENT = {
    "provider": "NATIVE_KUBERNETES",
    "resources": {
        "cpuRequest": "250m",
        "cpuLimit": "500m",
        "memoryRequest": "256Mi",
        "memoryLimit": "1Gi",
    },
    "isolation": "NAMESPACE",
    "stateMode": "STATELESS",
    "sessionAffinity": "NONE",
    "secretReferences": [],
    "openClawPackageRef": None,
}


def test_real_postgresql_migration_scope_and_optimistic_concurrency():
    store = PostgresRuntimeProfileRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    store.migrate()
    store.compatibility()
    service = RuntimeProfileService(store)
    scope = service.scope(f"runtime-postgres-{uuid.uuid4()}", "quality")
    record = service.create(scope, "human:owner", "Native", CONTENT)
    changed = {**record, "aggregateVersion": 2}
    store.replace(
        changed,
        expected_version=1,
        fact={"factId": f"runtime-profile-fact:{uuid.uuid4()}", "event": "CONFORMANCE"},
    )
    with pytest.raises(RuntimeProfileConflict):
        store.replace(
            changed,
            expected_version=1,
            fact={"factId": f"runtime-profile-fact:{uuid.uuid4()}", "event": "STALE"},
        )
    store.pool.close()
