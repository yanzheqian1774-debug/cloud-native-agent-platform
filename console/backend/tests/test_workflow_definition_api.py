from agent_console.app import app
from agent_console.workflow_definition_api import get_service
from agent_console.workflow_definition_repository import (
    InMemoryWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService
from fastapi.testclient import TestClient


def payload():
    return {
        "name": "Supplier response workflow",
        "content": {
            "description": "Governed response",
            "tasks": [
                {
                    "taskId": "analyze",
                    "name": "Analyze",
                    "dependsOn": [],
                    "inputs": ["quality-records"],
                    "outputs": ["analysis"],
                    "capabilityRequirements": ["supplier-quality-analysis"],
                    "references": [],
                    "retryLimit": 1,
                    "timeoutSeconds": 300,
                    "failurePolicy": "FAIL_WORKFLOW",
                }
            ],
            "inputs": ["quality-records"],
            "outputs": ["analysis"],
            "runtimeProfile": {
                "kind": "RUNTIME_PROFILE",
                "resourceId": "runtime-profile:native",
                "revisionId": "runtime-profile-revision:one",
            },
        },
    }


def test_private_api_exact_digest_publication_and_comparison():
    service = WorkflowDefinitionService(
        InMemoryWorkflowDefinitionRepository(), lambda _scope, _reference: True
    )
    app.dependency_overrides[get_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post(
            "/api/internal/v0.2.2/workflow-definitions", json=payload()
        )
        assert created.status_code == 201
        definition = created.json()["definition"]
        resource_id = definition["workflowDefinitionId"]
        validated = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/validation",
            json={"expectedVersion": 1},
        ).json()["definition"]
        digest = validated["revisions"][-1]["digest"]
        conflict = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/reviews",
            json={"expectedVersion": 2, "digest": "sha256:wrong", "reason": "checked"},
        )
        assert conflict.status_code == 409
        reviewed = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/reviews",
            json={"expectedVersion": 2, "digest": digest, "reason": "checked"},
        ).json()["definition"]
        published = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/publications",
            json={
                "expectedVersion": 3,
                "digest": digest,
                "reviewId": reviewed["reviews"][-1]["reviewId"],
            },
        ).json()["definition"]
        successor = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/successors",
            json={"expectedVersion": 4},
        ).json()["definition"]
        comparison = client.get(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/comparison",
            params={
                "leftRevisionId": published["publishedRevisionId"],
                "rightRevisionId": successor["currentDraftRevisionId"],
            },
        )
        assert comparison.status_code == 200
        assert comparison.json()["digestChanged"] is True
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_api_strictly_rejects_pod_yaml():
    service = WorkflowDefinitionService(InMemoryWorkflowDefinitionRepository())
    app.dependency_overrides[get_service] = lambda: service
    try:
        value = payload()
        value["content"]["tasks"][0]["podYaml"] = "kind: Pod"
        assert (
            TestClient(app)
            .post("/api/internal/v0.2.2/workflow-definitions", json=value)
            .status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(get_service, None)
