from datetime import UTC, datetime

from agent_console.app import app
from agent_console.digital_employee_api import get_assembly
from agent_console.digital_employee_application import DigitalEmployeeError
from agent_console.execution_postgres import ScopeIdentity
from fastapi.testclient import TestClient


class Assembly:
    def __init__(self):
        self.calls = []

    @staticmethod
    def scope(tenant_id, security_domain):
        return ScopeIdentity(tenant_id, security_domain)

    def list_definitions(self, scope):
        self.calls.append(("definitions", scope))
        return [{"definitionId": "definition-1"}]

    def get_definition(self, scope, definition_id):
        self.calls.append(("definition", scope, definition_id))
        if definition_id == "foreign":
            raise DigitalEmployeeError("DEFINITION_NOT_FOUND")
        return {"definition": {"definitionId": definition_id}}

    def create_instance(self, scope, principal_id, command):
        self.calls.append(("create-instance", scope, principal_id, command))
        return {
            "instanceId": command.instanceId,
            "ownerId": principal_id,
            "organizationId": scope.namespace,
            "execution": {
                "state": "UNAVAILABLE",
                "reasonCode": "EXECUTION_NOT_ASSEMBLED",
            },
        }

    def get_instance(self, scope, instance_id):
        self.calls.append(("instance", scope, instance_id))
        return {"instanceId": instance_id}

    def create_assignment(self, scope, instance_id, command):
        self.calls.append(("create-assignment", scope, instance_id, command))
        return {"assignmentId": command.assignmentId, "instanceId": instance_id}

    def get_assignment(self, scope, instance_id, assignment_id):
        self.calls.append(("assignment", scope, instance_id, assignment_id))
        return {"assignmentId": assignment_id, "instanceId": instance_id}

    def create_placement(self, scope, instance_id, assignment_id, command):
        self.calls.append(
            ("create-placement", scope, instance_id, assignment_id, command)
        )
        return {
            "placementId": command.placementId,
            "execution": {
                "state": "UNAVAILABLE",
                "reasonCode": "RUNTIME_EXECUTION_NOT_STARTED",
            },
            "outcome": {
                "state": "UNAVAILABLE",
                "reasonCode": "OUTCOME_NOT_RECORDED",
            },
        }

    def get_placement(
        self, scope, instance_id, assignment_id, placement_id, attempt_id, agent_id
    ):
        self.calls.append(
            (
                "placement",
                scope,
                instance_id,
                assignment_id,
                placement_id,
                attempt_id,
                agent_id,
            )
        )
        return {"placementId": placement_id}


def headers(tenant="tenant-a", domain="domain-a", principal="user-a"):
    return {
        "X-Tenant-ID": tenant,
        "X-Security-Domain": domain,
        "X-Principal-ID": principal,
    }


def test_definition_instance_assignment_and_placement_routes_use_trusted_scope():
    assembly = Assembly()
    app.dependency_overrides[get_assembly] = lambda: assembly
    client = TestClient(app)
    now = datetime(2026, 9, 3, tzinfo=UTC).isoformat()
    try:
        listed = client.get(
            "/api/internal/v0.2.3/digital-employees/definitions",
            headers=headers(),
        )
        assert listed.status_code == 200

        created = client.post(
            "/api/internal/v0.2.3/digital-employees/instances",
            headers=headers(),
            json={
                "instanceId": "employee-1",
                "definitionId": "definition-1",
                "definitionRevisionId": "revision-1",
                "commandId": "create-1",
            },
        )
        assert created.status_code == 201
        assert created.json()["ownerId"] == "user-a"
        assert created.json()["organizationId"] == "tenant-a"
        assert created.json()["execution"]["state"] == "UNAVAILABLE"

        assigned = client.post(
            "/api/internal/v0.2.3/digital-employees/instances/employee-1/assignments",
            headers=headers(),
            json={
                "assignmentId": "assignment-1",
                "commandId": "assign-1",
                "assigneeId": "user-b",
                "businessRole": "reviewer",
                "effectiveFrom": now,
            },
        )
        assert assigned.status_code == 201

        placed = client.post(
            "/api/internal/v0.2.3/digital-employees/instances/employee-1/assignments/assignment-1/placements",
            headers=headers(),
            json={
                "requestId": "request-1",
                "placementId": "placement-1",
                "workflowRunId": "workflow-1",
                "taskRunId": "task-1",
                "attemptId": "attempt-1",
                "agentInstanceId": "agent-1",
                "agentRevisionId": "revision-1",
                "runtimeProfileRevisionId": "runtime-profile-1",
                "runtimeInstanceId": "runtime-1",
                "policyVersion": "policy-1",
                "requestedAt": now,
                "decidedAt": now,
            },
        )
        assert placed.status_code == 201
        assert placed.json()["execution"]["state"] == "UNAVAILABLE"
        assert placed.json()["outcome"]["state"] == "UNAVAILABLE"

        read = client.get(
            "/api/internal/v0.2.3/digital-employees/instances/employee-1/assignments/assignment-1/placements/placement-1",
            headers=headers("tenant-b", "domain-b", "user-b"),
            params={"attemptId": "attempt-1", "agentInstanceId": "agent-1"},
        )
        assert read.status_code == 200
        call = assembly.calls[-1]
        assert call[1] == ScopeIdentity("tenant-b", "domain-b")
    finally:
        app.dependency_overrides.clear()


def test_foreign_definition_is_disclosure_safe_and_extra_input_is_rejected():
    assembly = Assembly()
    app.dependency_overrides[get_assembly] = lambda: assembly
    client = TestClient(app)
    try:
        response = client.get(
            "/api/internal/v0.2.3/digital-employees/definitions/foreign",
            headers=headers(),
        )
        assert response.status_code == 404
        assert response.json() == {"detail": {"reasonCode": "DEFINITION_NOT_FOUND"}}

        invalid = client.post(
            "/api/internal/v0.2.3/digital-employees/instances",
            headers=headers(),
            json={
                "instanceId": "employee-1",
                "definitionId": "definition-1",
                "definitionRevisionId": "revision-1",
                "commandId": "create-1",
                "ownerId": "attacker-selected-owner",
            },
        )
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()
