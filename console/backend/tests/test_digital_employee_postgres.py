import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    DigitalEmployeeApplicationService,
    DigitalEmployeeError,
)
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.execution_postgres import (
    AppendDisposition,
    AssignmentId,
    DigitalEmployeeInstanceId,
    PostgresExecutionAuthorityRepository,
    ScopeIdentity,
)

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION = MIGRATIONS / "0008_execution_runtime_authority.sql"


class Definitions:
    def resolve(self, scope, definition_id, revision_id):
        return DefinitionReference(definition_id, revision_id, "d" * 64, True, True)


def authority():
    value = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    value.migrate()
    return value


def test_restart_readback_replay_history_conflict_and_isolation():
    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"tenant-{suffix}", "domain")
    raw = authority()
    repository = PostgresDigitalEmployeeRepository(raw)
    service = DigitalEmployeeApplicationService(repository, Definitions())
    instance, disposition = service.create_instance(
        scope=scope,
        instance_id=DigitalEmployeeInstanceId(f"employee-{suffix}"),
        definition_id="definition",
        definition_revision_id="revision-1",
        owner_id="owner",
        organization_id="org",
        command_id=f"create-{suffix}",
    )
    assert disposition is AppendDisposition.APPENDED
    assert (
        service.create_instance(
            scope=scope,
            instance_id=instance.instance_id,
            definition_id="definition",
            definition_revision_id="revision-1",
            owner_id="owner",
            organization_id="org",
            command_id=f"create-{suffix}",
            now=instance.created_at,
        )[1]
        is AppendDisposition.REPLAYED
    )
    assignment = AssignmentRecord(
        scope,
        AssignmentId(f"assignment-{suffix}"),
        instance.instance_id,
        "assignee",
        "operator",
        AssignmentLifecycle.ACTIVE,
        datetime.now(UTC),
        None,
        1,
        f"assign-{suffix}",
    )
    assert service.assign(assignment) is AppendDisposition.APPENDED
    assert service.assign(assignment) is AppendDisposition.REPLAYED
    with pytest.raises(DigitalEmployeeError, match="ACTIVE_ASSIGNMENT_CONFLICT"):
        service.assign(
            AssignmentRecord(
                scope,
                AssignmentId(f"assignment-2-{suffix}"),
                instance.instance_id,
                "other",
                "operator",
                AssignmentLifecycle.ACTIVE,
                datetime.now(UTC),
                None,
                1,
                f"assign-2-{suffix}",
            )
        )
    raw.pool.close()
    restarted = authority()
    recovered = PostgresDigitalEmployeeRepository(restarted)
    assert recovered.get_instance(scope, instance.instance_id) == instance
    assert recovered.assignments_for_instance(scope, instance.instance_id) == (
        assignment,
    )
    assert (
        recovered.get_instance(ScopeIdentity("other", "domain"), instance.instance_id)
        is None
    )
    restarted.pool.close()
