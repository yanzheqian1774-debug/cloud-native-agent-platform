import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.agent_binding_validation import BindingResolution
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.digital_employee_application import DigitalEmployeeError
from agent_console.digital_employee_bootstrap import build_digital_employee_assembly
from agent_console.digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
    CreateDigitalEmployeePlacement,
)
from agent_console.execution_domain import VersionedAggregate
from agent_console.execution_postgres import (
    AgentInstanceId,
    AssignmentId,
    AssignmentIdentity,
    AttemptId,
    AttemptIdentity,
    DigitalEmployeeInstanceId,
    ExecutionIdentityAggregate,
    RuntimeInstanceId,
    ScopeIdentity,
    TaskRunId,
    TaskRunIdentity,
    WorkflowRunId,
    WorkflowRunIdentity,
    canonical_bytes,
)

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
NOW = datetime(2026, 9, 3, tzinfo=UTC)


class Bindings:
    def resolve(self, scope, kind, resource_id):
        values = {
            "knowledge": ("knowledge-r1", "a" * 64),
            "workflow": ("workflow-r1", "c" * 64),
            "runtime-profile": ("runtime-profile-r1", "d" * 64),
        }
        revision_id, digest = values[kind]
        return BindingResolution(resource_id, revision_id, digest, True, True)


def definitions():
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 6):
            path = next(MIGRATIONS.glob(f"{version:04d}_*.sql"))
            connection.execute(path.read_text())
    repository = PostgresAgentDefinitionRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
        governed_bindings_migration_path=MIGRATIONS
        / "0006_agent_governed_bindings.sql",
    )
    repository.migrate()
    with psycopg.connect(DATABASE_URL or "") as connection:
        connection.execute(
            (MIGRATIONS / "0007_workflow_runtime_profiles.sql").read_text()
        )
    return AgentDefinitionService(repository, binding_resolver=Bindings())


def publish(service, scope):
    record = service.create(
        service.scope(scope.namespace, scope.security_domain),
        "owner-a",
        "Quality reviewer",
        {
            "title": "Quality reviewer",
            "duties": ["Review supplier quality"],
            "capabilities": ["supplier-quality-review"],
            "bindings": {
                "skills": [],
                "mcpTools": [],
                "knowledge": [
                    {
                        "resourceId": "knowledge-1",
                        "revisionId": "knowledge-r1",
                        "digest": "a" * 64,
                    }
                ],
                "workflow": {
                    "kind": "workflow",
                    "resourceId": "workflow-1",
                    "revisionId": "workflow-r1",
                    "digest": "c" * 64,
                },
                "runtimeProfile": {
                    "kind": "runtime-profile",
                    "resourceId": "runtime-profile-1",
                    "revisionId": "runtime-profile-r1",
                    "digest": "d" * 64,
                },
            },
        },
    )
    definition_id = record["definitionId"]
    record = service.validate(scope, definition_id, "owner-a", 1)
    revision = record["definition"]["revisions"][0]
    record = service.review(
        scope,
        definition_id,
        "reviewer-a",
        2,
        revision["digest"],
        "APPROVE",
        "approved",
    )
    review_id = record["definition"]["reviews"][0]["reviewId"]
    record = service.publish(
        scope, definition_id, "publisher-a", 3, revision["digest"], review_id
    )
    return definition_id, revision["revisionId"], revision["digest"]


def seed_execution_chain(assembly, scope, instance_id, assignment_id, revision_id):
    suffix = instance_id.rsplit("-", 1)[-1]
    authority = assembly.repository.authority
    runtime_id = RuntimeInstanceId(f"runtime-{suffix}")
    agent_id = AgentInstanceId(f"agent-{suffix}")
    authority.create_aggregate(
        "runtime_instance",
        VersionedAggregate(
            scope,
            str(runtime_id),
            1,
            {"current_generation": 1, "runtime_type": "native"},
        ),
    )
    authority.create_aggregate(
        "agent_instance",
        VersionedAggregate(
            scope,
            str(agent_id),
            1,
            {
                "agent_revision_id": revision_id,
                "runtime_instance_id": str(runtime_id),
            },
        ),
    )
    aggregate = ExecutionIdentityAggregate(
        scope,
        AssignmentIdentity(
            AssignmentId(assignment_id), DigitalEmployeeInstanceId(instance_id)
        ),
        WorkflowRunIdentity(
            WorkflowRunId(f"workflow-{suffix}"),
            AssignmentId(assignment_id),
            "approved-plan-r1",
        ),
        TaskRunIdentity(
            TaskRunId(f"task-{suffix}"), WorkflowRunId(f"workflow-{suffix}")
        ),
        AttemptIdentity(
            AttemptId(f"attempt-{suffix}"), TaskRunId(f"task-{suffix}"), None
        ),
    )
    payload = json.loads(canonical_bytes(aggregate))["payload"]
    with authority.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO execution_authority.workflow_runs("
            "namespace,security_domain,workflow_run_id,assignment_id,"
            "approved_plan_revision_id,record) "
            "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                scope.namespace,
                scope.security_domain,
                str(aggregate.workflow_run.workflow_run_id),
                assignment_id,
                aggregate.workflow_run.approved_plan_revision_id,
                json.dumps(payload["workflow_run"]),
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.task_runs("
            "namespace,security_domain,task_run_id,workflow_run_id,record) "
            "VALUES (%s,%s,%s,%s,%s::jsonb)",
            (
                scope.namespace,
                scope.security_domain,
                str(aggregate.task_run.task_run_id),
                str(aggregate.workflow_run.workflow_run_id),
                json.dumps(payload["task_run"]),
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.attempts("
            "namespace,security_domain,attempt_id,task_run_id,aggregate_digest,record) "
            "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                scope.namespace,
                scope.security_domain,
                str(aggregate.attempt.attempt_id),
                str(aggregate.task_run.task_run_id),
                "b" * 64,
                json.dumps(payload),
            ),
        )
    return aggregate, agent_id, runtime_id


def test_real_postgres_exact_chain_restart_and_scope_isolation():
    suffix = uuid.uuid4().hex
    definition_service = definitions()
    definition_scope = definition_service.scope(f"tenant-{suffix}", "domain-a")
    scope = ScopeIdentity(definition_scope.namespace, definition_scope.security_domain)
    definition_id, revision_id, digest = publish(definition_service, definition_scope)
    assembly = build_digital_employee_assembly(
        DATABASE_URL or "",
        definition_service,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    instance_id = f"employee-{suffix}"
    assignment_id = f"assignment-{suffix}"
    created = assembly.create_instance(
        scope,
        "owner-a",
        CreateDigitalEmployeeInstance(
            instanceId=instance_id,
            definitionId=definition_id,
            definitionRevisionId=revision_id,
            commandId=f"create-{suffix}",
        ),
    )
    assert created["definition"] == {
        "definitionId": definition_id,
        "revisionId": revision_id,
        "digest": digest,
    }
    assert created["relationships"]["capabilities"] == ["supplier-quality-review"]
    assert created["relationships"]["knowledge"][0]["resourceId"] == "knowledge-1"
    assert created["execution"]["state"] == "UNAVAILABLE"

    with pytest.raises(DigitalEmployeeError, match="DEFINITION_NOT_FOUND"):
        assembly.create_instance(
            scope,
            "owner-a",
            CreateDigitalEmployeeInstance(
                instanceId=f"wrong-{suffix}",
                definitionId=definition_id,
                definitionRevisionId="not-the-published-revision",
                commandId=f"wrong-{suffix}",
            ),
        )

    assigned = assembly.create_assignment(
        scope,
        instance_id,
        CreateDigitalEmployeeAssignment(
            assignmentId=assignment_id,
            commandId=f"assign-{suffix}",
            assigneeId="reviewer-a",
            businessRole="reviewer",
            effectiveFrom=NOW,
        ),
    )
    with pytest.raises(DigitalEmployeeError, match="PLACEMENT_EXECUTION_NOT_ASSEMBLED"):
        assembly.create_placement(
            scope,
            instance_id,
            assignment_id,
            CreateDigitalEmployeePlacement(
                requestId=f"missing-request-{suffix}",
                placementId=f"missing-placement-{suffix}",
                workflowRunId=f"missing-workflow-{suffix}",
                taskRunId=f"missing-task-{suffix}",
                attemptId=f"missing-attempt-{suffix}",
                agentInstanceId=f"missing-agent-{suffix}",
                agentRevisionId=revision_id,
                runtimeProfileRevisionId="runtime-profile-r1",
                runtimeInstanceId=f"missing-runtime-{suffix}",
                policyVersion="policy-v1",
                requestedAt=NOW,
                decidedAt=NOW,
            ),
        )
    aggregate, agent_id, runtime_id = seed_execution_chain(
        assembly, scope, instance_id, assignment_id, revision_id
    )
    placed = assembly.create_placement(
        scope,
        instance_id,
        assignment_id,
        CreateDigitalEmployeePlacement(
            requestId=f"request-{suffix}",
            placementId=f"placement-{suffix}",
            workflowRunId=str(aggregate.workflow_run.workflow_run_id),
            taskRunId=str(aggregate.task_run.task_run_id),
            attemptId=str(aggregate.attempt.attempt_id),
            agentInstanceId=str(agent_id),
            agentRevisionId=revision_id,
            runtimeProfileRevisionId="runtime-profile-r1",
            runtimeInstanceId=str(runtime_id),
            policyVersion="policy-v1",
            requestedAt=NOW,
            decidedAt=NOW,
        ),
    )
    assert placed["decision"] == "PLACED"
    assert placed["execution"]["state"] == "UNAVAILABLE"
    assert placed["outcome"]["state"] == "UNAVAILABLE"
    assert assigned["binding"]["state"] == "UNAVAILABLE"

    assembly.repository.authority.pool.close()
    definition_service.repository.pool.close()
    restarted_definitions = definitions()
    restarted = build_digital_employee_assembly(
        DATABASE_URL or "",
        restarted_definitions,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    assert restarted.get_instance(scope, instance_id)["definition"]["digest"] == digest
    assert (
        restarted.get_assignment(scope, instance_id, assignment_id)["assignmentId"]
        == assignment_id
    )
    assert (
        restarted.get_placement(
            scope,
            instance_id,
            assignment_id,
            placed["placementId"],
            str(aggregate.attempt.attempt_id),
            str(agent_id),
        )["digest"]
        == placed["digest"]
    )

    foreign = ScopeIdentity(scope.namespace, "domain-b")
    with pytest.raises(DigitalEmployeeError, match="INSTANCE_NOT_FOUND"):
        restarted.get_instance(foreign, instance_id)
    with pytest.raises(DigitalEmployeeError, match="ASSIGNMENT_NOT_FOUND"):
        restarted.get_assignment(foreign, instance_id, assignment_id)
    restarted.repository.authority.pool.close()
    restarted_definitions.repository.pool.close()
