"""Tests for Workflow Console application services."""

from typing import Any

from agent_console.service import WorkflowService


class FakeWorkflowRepository:
    """Repository fixture for Workflow service tests."""

    def __init__(
        self,
        workflows: list[dict[str, Any]],
    ) -> None:
        self.workflows = workflows

    def list_workflows(self) -> list[dict[str, Any]]:
        return self.workflows

    def get_workflow(
        self,
        namespace: str,
        name: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_workflow_tasks(
        self,
        namespace: str,
        workflow_name: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


def workflow(
    name: str,
    created_at: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "name": name,
        "namespace": "default",
    }

    if created_at is not None:
        metadata["creationTimestamp"] = created_at

    return {
        "metadata": metadata,
        "spec": {
            "tasks": [
                {
                    "name": "task-a",
                    "agentRef": {
                        "name": "agent-a",
                    },
                    "input": {
                        "prompt": "Run task A.",
                    },
                    "timeoutSeconds": 300,
                }
            ]
        },
        "status": {
            "phase": "Succeeded",
            "taskCount": 1,
        },
    }


def test_list_workflows_orders_newest_first() -> None:
    repository = FakeWorkflowRepository(
        workflows=[
            workflow(
                "older",
                "2026-08-18T08:00:00Z",
            ),
            workflow(
                "newest",
                "2026-08-18T10:00:00Z",
            ),
            workflow(
                "middle",
                "2026-08-18T09:00:00Z",
            ),
        ]
    )

    service = WorkflowService(repository)

    response = service.list_workflows()

    assert [item.name for item in response.items] == [
        "newest",
        "middle",
        "older",
    ]


def test_list_workflows_places_missing_timestamp_last() -> None:
    repository = FakeWorkflowRepository(
        workflows=[
            workflow("missing", None),
            workflow(
                "newest",
                "2026-08-18T10:00:00Z",
            ),
        ]
    )

    service = WorkflowService(repository)

    response = service.list_workflows()

    assert [item.name for item in response.items] == [
        "newest",
        "missing",
    ]


def test_list_workflows_empty_state() -> None:
    repository = FakeWorkflowRepository(workflows=[])

    service = WorkflowService(repository)

    response = service.list_workflows()

    assert response.items == []
