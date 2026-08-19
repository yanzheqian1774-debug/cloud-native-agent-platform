"""HTTP contract tests for the Console backend."""

from typing import Any

from agent_console.app import app, get_repository
from fastapi.testclient import TestClient


class FakeWorkflowRepository:
    """In-memory read-only repository used by HTTP tests."""

    def __init__(self) -> None:
        self.workflow = {
            "metadata": {
                "name": "example-workflow",
                "namespace": "agent-workloads",
                "creationTimestamp": "2026-08-18T10:00:00Z",
            },
            "spec": {
                "tasks": [
                    {
                        "name": "architect",
                        "agentRef": {
                            "name": "engineering-architect",
                        },
                        "input": {
                            "prompt": "Design the feature.",
                        },
                        "timeoutSeconds": 300,
                    }
                ]
            },
            "status": {
                "phase": "Succeeded",
                "taskCount": 1,
                "startedAt": "2026-08-18T10:00:01Z",
                "completedAt": "2026-08-18T10:00:03Z",
                "tasks": {
                    "architect": {
                        "phase": "Succeeded",
                        "taskRef": {
                            "name": "example-workflow-architect",
                        },
                    }
                },
            },
        }

        self.task = {
            "metadata": {
                "name": "example-workflow-architect",
                "namespace": "agent-workloads",
                "labels": {
                    "agentos.io/workflow": "example-workflow",
                    "agentos.io/workflow-task": "architect",
                },
            },
            "spec": {
                "agentRef": {
                    "name": "engineering-architect",
                },
                "input": {
                    "prompt": "Design the feature.",
                },
                "timeoutSeconds": 300,
            },
            "status": {
                "phase": "Succeeded",
                "result": "architecture result",
                "attempts": 1,
            },
        }

    def list_workflows(self) -> list[dict[str, Any]]:
        return [self.workflow]

    def get_workflow(
        self,
        namespace: str,
        name: str,
    ) -> dict[str, Any]:
        assert namespace == "agent-workloads"
        assert name == "example-workflow"
        return self.workflow

    def list_workflow_tasks(
        self,
        namespace: str,
        workflow_name: str,
    ) -> list[dict[str, Any]]:
        assert namespace == "agent-workloads"
        assert workflow_name == "example-workflow"
        return [self.task]


def fake_repository() -> FakeWorkflowRepository:
    return FakeWorkflowRepository()


app.dependency_overrides[get_repository] = fake_repository

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_workflows() -> None:
    response = client.get("/api/v1/workflows")

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["items"]) == 1
    assert payload["items"][0]["name"] == "example-workflow"
    assert payload["items"][0]["phase"] == "Succeeded"
    assert payload["items"][0]["taskCount"] == 1


def test_get_workflow_detail() -> None:
    response = client.get("/api/v1/workflows/agent-workloads/example-workflow")

    assert response.status_code == 200

    payload = response.json()

    assert payload["name"] == "example-workflow"
    assert payload["phase"] == "Succeeded"
    assert len(payload["nodes"]) == 1

    node = payload["nodes"][0]

    assert node["name"] == "architect"
    assert node["agent"]["name"] == "engineering-architect"
    assert node["execution"]["phase"] == "Succeeded"
    assert node["execution"]["result"] == "architecture result"


def test_get_workflow_not_found_returns_404() -> None:
    from kubernetes.client.exceptions import ApiException

    class NotFoundRepository(FakeWorkflowRepository):
        def get_workflow(
            self,
            namespace: str,
            name: str,
        ) -> dict[str, Any]:
            raise ApiException(status=404)

    def not_found_repository() -> NotFoundRepository:
        return NotFoundRepository()

    app.dependency_overrides[get_repository] = not_found_repository

    try:
        response = client.get("/api/v1/workflows/agent-workloads/missing-workflow")
    finally:
        app.dependency_overrides[get_repository] = fake_repository

    assert response.status_code == 404
    assert response.json() == {
        "detail": "workflow not found",
    }
