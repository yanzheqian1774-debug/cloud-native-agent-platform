import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.agent_binding_validation import BindingResolution
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.app import app
from agent_console.digital_employee_api import get_assembly
from agent_console.digital_employee_application import DigitalEmployeeError
from agent_console.digital_employee_bootstrap import build_digital_employee_assembly
from agent_console.digital_employee_definition import EmployeeDefinitionError
from agent_console.digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
    CreateDigitalEmployeePlacement,
)
from agent_console.execution_domain import VersionedAggregate
from agent_console.execution_postgres import (
    AgentInstanceId,
    DigitalEmployeeInstanceId,
    RuntimeInstanceId,
    ScopeIdentity,
)
from fastapi.testclient import TestClient

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
NOW = datetime(2026, 9, 3, tzinfo=UTC)


def request_headers(tenant, domain, principal="maintainer"):
    return {
        "X-Tenant-ID": tenant,
        "X-Security-Domain": domain,
        "X-Principal-ID": principal,
    }


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
    instance = assembly.repository.get_instance(
        scope, DigitalEmployeeInstanceId(instance_id)
    )
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
                "agent_definition_id": instance.definition.primary_agent_id,
                "agent_digest": instance.definition.primary_agent_digest,
                "runtime_instance_id": str(runtime_id),
            },
        ),
    )
    from agent_console.execution_application import (
        ExecutionApplicationService,
        StartExecutionCommand,
    )
    from employee_identity_support import approve_plan, authorize
    from test_execution_application_postgres import approved_plan

    instance = assembly.repository.get_instance(
        scope, DigitalEmployeeInstanceId(instance_id)
    )
    assignment = assembly.repository.assignments_for_instance(
        scope, instance.instance_id
    )[0]
    workflow = replace(
        approved_plan(suffix),
        tenant_id=scope.namespace,
        security_domain=scope.security_domain,
    )
    approved = approve_plan(authority, DATABASE_URL, workflow, instance, assignment)
    aggregate = (
        ExecutionApplicationService(authority, authorize(scope))
        .start(
            StartExecutionCommand(
                scope,
                workflow,
                approved,
                assignment.assignment_id,
                instance.instance_id,
                "collect",
                "start",
            )
        )
        .identity
    )
    return aggregate, agent_id, runtime_id


def test_real_postgres_exact_chain_restart_and_scope_isolation(monkeypatch):
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
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeDefinitionService,
        EmployeeRevision,
        MemberKind,
    )
    from test_digital_employee_definition_postgres import Authorized

    agent_definition_id, agent_revision_id, agent_digest = (
        definition_id,
        revision_id,
        digest,
    )
    employee = EmployeeRevision(
        scope,
        f"employee-definition-{suffix}",
        "employee-revision",
        "Reviewer",
        ("Review quality",),
        (
            CompositionMember(
                MemberKind.AGENT, agent_definition_id, agent_revision_id, agent_digest
            ),
        ),
    )
    service = EmployeeDefinitionService(
        assembly.employee_definitions, Authorized(scope)
    )
    current = service.create(
        employee, expected_version=0, command_id=f"employee-create-{suffix}"
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        current = service.decide(
            scope,
            employee.definition_id,
            employee.revision_id,
            employee.digest,
            action,
            expected_version=current["aggregateVersion"],
            command_id=f"{action}-{suffix}",
        )
    definition_id, revision_id, digest = (
        employee.definition_id,
        employee.revision_id,
        employee.digest,
    )
    instance_id = f"employee-{suffix}"
    assignment_id = f"assignment-{suffix}"
    created = assembly.create_instance(
        scope,
        "owner-a",
        CreateDigitalEmployeeInstance(
            instanceId=instance_id,
            employeeDefinitionId=definition_id,
            employeeDefinitionRevisionId=revision_id,
            commandId=f"create-{suffix}",
        ),
    )
    assert created["employeeDefinition"] == {
        "authorityKind": "DIGITAL_EMPLOYEE_DEFINITION_V1",
        "employeeDefinitionId": definition_id,
        "employeeDefinitionRevisionId": revision_id,
        "digest": digest,
    }
    assert created["relationships"]["directComposition"] == [
        {
            "kind": "AGENT",
            "resource_id": agent_definition_id,
            "revision_id": agent_revision_id,
            "digest": agent_digest,
        }
    ]
    # Agent-internal dependencies retain their owner, not employee direct bindings.
    assert "knowledge" not in created["relationships"]
    assert created["execution"]["state"] == "UNAVAILABLE"

    with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_NOT_FOUND"):
        assembly.create_instance(
            scope,
            "owner-a",
            CreateDigitalEmployeeInstance(
                instanceId=f"wrong-{suffix}",
                employeeDefinitionId=definition_id,
                employeeDefinitionRevisionId="not-the-published-revision",
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
                agentRevisionId=agent_revision_id,
                runtimeProfileRevisionId="runtime-profile-r1",
                runtimeInstanceId=f"missing-runtime-{suffix}",
                policyVersion="policy-v1",
                requestedAt=NOW,
                decidedAt=NOW,
            ),
        )
    aggregate, agent_id, runtime_id = seed_execution_chain(
        assembly, scope, instance_id, assignment_id, agent_revision_id
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
            agentRevisionId=agent_revision_id,
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
    assert assembly.repository.placement_request_matches(
        scope,
        placed["placementId"],
        aggregate.attempt.attempt_id,
        agent_id,
    )
    assert not assembly.repository.placement_request_matches(
        scope,
        placed["placementId"],
        "another-attempt",
        agent_id,
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            assembly.repository,
            "placement_request_matches",
            lambda *_args: False,
        )
        with pytest.raises(DigitalEmployeeError, match="PLACEMENT_NOT_FOUND"):
            assembly.get_placement(
                scope,
                instance_id,
                assignment_id,
                placed["placementId"],
                str(aggregate.attempt.attempt_id),
                str(agent_id),
            )

    assembly.repository.authority.pool.close()
    definition_service.repository.pool.close()
    restarted_definitions = definitions()
    restarted = build_digital_employee_assembly(
        DATABASE_URL or "",
        restarted_definitions,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    assert (
        restarted.get_instance(scope, instance_id)["employeeDefinition"]["digest"]
        == digest
    )
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


def test_real_http_employee_definition_to_instance_chain_and_restart():
    suffix = uuid.uuid4().hex
    tenant = f"http-tenant-{suffix}"
    domain = "http-domain"
    scope = ScopeIdentity(tenant, domain)
    agent_definitions = definitions()
    agent_scope = agent_definitions.scope(tenant, domain)
    agent_id, agent_revision_id, agent_digest = publish(agent_definitions, agent_scope)
    assembly = build_digital_employee_assembly(
        DATABASE_URL or "",
        agent_definitions,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    app.dependency_overrides[get_assembly] = lambda: assembly
    client = TestClient(app)
    employee_id = f"employee-definition-{suffix}"
    employee_revision_id = "employee-revision-1"
    instance_id = f"employee-instance-{suffix}"
    headers = request_headers(tenant, domain)
    create_body = {
        "employeeDefinitionId": employee_id,
        "employeeDefinitionRevisionId": employee_revision_id,
        "role": "Supplier quality reviewer",
        "responsibilities": ["Review exact quality evidence"],
        "members": [
            {
                "kind": "AGENT",
                "resourceId": agent_id,
                "revisionId": agent_revision_id,
                "digest": agent_digest,
            }
        ],
        "expectedVersion": 0,
        "commandId": f"create-employee-definition-{suffix}",
    }
    try:
        unauthenticated = client.post(
            "/api/internal/v0.2.3/digital-employees/definitions",
            json=create_body,
        )
        assert unauthenticated.status_code == 401
        assert unauthenticated.json() == {
            "detail": {"reasonCode": "AUTHENTICATION_REQUIRED"}
        }
        empty = client.get(
            "/api/internal/v0.2.3/digital-employees/definitions", headers=headers
        )
        assert empty.status_code == 200
        assert empty.json() == []

        created = client.post(
            "/api/internal/v0.2.3/digital-employees/definitions",
            headers=headers,
            json=create_body,
        )
        assert created.status_code == 201
        employee_digest = created.json()["employeeDefinitionDigest"]
        assert created.json()["resourceKind"] == "DIGITAL_EMPLOYEE_DEFINITION"
        assert created.json()["employeeDefinitionId"] == employee_id

        replay = client.post(
            "/api/internal/v0.2.3/digital-employees/definitions",
            headers=headers,
            json=create_body,
        )
        assert replay.status_code == 201
        assert replay.json() == created.json()

        listed = client.get(
            "/api/internal/v0.2.3/digital-employees/definitions", headers=headers
        )
        assert listed.status_code == 200
        assert any(
            item["employeeDefinitionId"] == employee_id for item in listed.json()
        )

        exact_url = "/api/internal/v0.2.3/digital-employees/definitions/" + employee_id
        exact_params = {"employeeDefinitionRevisionId": employee_revision_id}
        read = client.get(exact_url, headers=headers, params=exact_params)
        assert read.status_code == 200
        assert read.json() == created.json()

        stale = client.post(
            f"{exact_url}/validate",
            headers=headers,
            json={
                "employeeDefinitionRevisionId": employee_revision_id,
                "employeeDefinitionDigest": employee_digest,
                "expectedVersion": 9,
                "commandId": f"stale-validate-{suffix}",
            },
        )
        assert stale.status_code == 409
        assert stale.json() == {"detail": {"reasonCode": "STALE_AGGREGATE_VERSION"}}
        assert (
            client.get(exact_url, headers=headers, params=exact_params).json()["facts"]
            == created.json()["facts"]
        )

        current = created.json()
        for action in ("validate", "approve", "publish"):
            response = client.post(
                f"{exact_url}/{action}",
                headers=headers,
                json={
                    "employeeDefinitionRevisionId": employee_revision_id,
                    "employeeDefinitionDigest": employee_digest,
                    "expectedVersion": current["aggregateVersion"],
                    "commandId": f"{action}-{suffix}",
                },
            )
            assert response.status_code == 200
            current = response.json()
        assert current["published"] is True
        assert current["matchable"] is False

        denied = client.get(
            exact_url,
            headers=request_headers("other-tenant", domain, "other-maintainer"),
            params=exact_params,
        )
        assert denied.status_code == 404
        assert denied.json() == {"detail": {"reasonCode": "EMPLOYEE_NOT_FOUND"}}

        masquerade_id = f"masquerade-{suffix}"
        masquerade = client.post(
            "/api/internal/v0.2.3/digital-employees/instances",
            headers=headers,
            json={
                "instanceId": masquerade_id,
                "employeeDefinitionId": agent_id,
                "employeeDefinitionRevisionId": agent_revision_id,
                "commandId": f"masquerade-{suffix}",
            },
        )
        assert masquerade.status_code == 404
        assert masquerade.json() == {"detail": {"reasonCode": "EMPLOYEE_NOT_FOUND"}}
        assert (
            assembly.repository.get_instance(
                scope, DigitalEmployeeInstanceId(masquerade_id)
            )
            is None
        )

        instance = client.post(
            "/api/internal/v0.2.3/digital-employees/instances",
            headers=headers,
            json={
                "instanceId": instance_id,
                "employeeDefinitionId": employee_id,
                "employeeDefinitionRevisionId": employee_revision_id,
                "commandId": f"create-instance-{suffix}",
            },
        )
        assert instance.status_code == 201
        assert (
            instance.json()["employeeDefinition"]["employeeDefinitionId"] == employee_id
        )

        assignment = client.post(
            f"/api/internal/v0.2.3/digital-employees/instances/{instance_id}/assignments",
            headers=headers,
            json={
                "assignmentId": f"assignment-{suffix}",
                "commandId": f"assign-{suffix}",
                "assigneeId": "reviewer",
                "businessRole": "quality-reviewer",
                "effectiveFrom": NOW.isoformat(),
            },
        )
        assert assignment.status_code == 201
    finally:
        app.dependency_overrides.clear()
        assembly.repository.authority.pool.close()
        agent_definitions.repository.pool.close()

    restarted_definitions = definitions()
    restarted = build_digital_employee_assembly(
        DATABASE_URL or "",
        restarted_definitions,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    app.dependency_overrides[get_assembly] = lambda: restarted
    restarted_client = TestClient(app)
    try:
        recovered = restarted_client.get(
            "/api/internal/v0.2.3/digital-employees/definitions/" + employee_id,
            headers=headers,
            params={"employeeDefinitionRevisionId": employee_revision_id},
        )
        assert recovered.status_code == 200
        assert recovered.json()["employeeDefinitionDigest"] == employee_digest
        instance = restarted_client.get(
            f"/api/internal/v0.2.3/digital-employees/instances/{instance_id}",
            headers=headers,
        )
        assert instance.status_code == 200
        assert (
            instance.json()["employeeDefinition"]["employeeDefinitionId"] == employee_id
        )
    finally:
        app.dependency_overrides.clear()
        restarted.repository.authority.pool.close()
        restarted_definitions.repository.pool.close()
