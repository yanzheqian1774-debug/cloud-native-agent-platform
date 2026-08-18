"""Tests for the Kubernetes Workflow repository."""

from typing import Any

from agent_console.repository import KubernetesWorkflowRepository


class FakeCustomObjectsApi:
    """Minimal fake Kubernetes CustomObjectsApi."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_cluster_custom_object(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("list_cluster_custom_object", kwargs))

        return {
            "items": [
                {
                    "metadata": {
                        "name": "workflow-a",
                        "namespace": "agent-workloads",
                    }
                }
            ]
        }

    def get_namespaced_custom_object(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("get_namespaced_custom_object", kwargs))

        return {
            "metadata": {
                "name": kwargs["name"],
                "namespace": kwargs["namespace"],
            }
        }

    def list_namespaced_custom_object(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("list_namespaced_custom_object", kwargs))

        return {
            "items": [
                {
                    "metadata": {
                        "name": "workflow-a-architect",
                    }
                }
            ]
        }


def test_list_workflows_uses_cluster_scope() -> None:
    api = FakeCustomObjectsApi()
    repository = KubernetesWorkflowRepository(api=api)

    workflows = repository.list_workflows()

    assert len(workflows) == 1

    method, arguments = api.calls[0]

    assert method == "list_cluster_custom_object"
    assert arguments == {
        "group": "agentos.io",
        "version": "v1alpha1",
        "plural": "workflows",
    }


def test_get_workflow_uses_namespace_and_name() -> None:
    api = FakeCustomObjectsApi()
    repository = KubernetesWorkflowRepository(api=api)

    workflow = repository.get_workflow(
        namespace="agent-workloads",
        name="workflow-a",
    )

    assert workflow["metadata"]["name"] == "workflow-a"

    method, arguments = api.calls[0]

    assert method == "get_namespaced_custom_object"
    assert arguments == {
        "group": "agentos.io",
        "version": "v1alpha1",
        "namespace": "agent-workloads",
        "plural": "workflows",
        "name": "workflow-a",
    }


def test_list_workflow_tasks_uses_workflow_label_selector() -> None:
    api = FakeCustomObjectsApi()
    repository = KubernetesWorkflowRepository(api=api)

    tasks = repository.list_workflow_tasks(
        namespace="agent-workloads",
        workflow_name="workflow-a",
    )

    assert len(tasks) == 1

    method, arguments = api.calls[0]

    assert method == "list_namespaced_custom_object"
    assert arguments == {
        "group": "agentos.io",
        "version": "v1alpha1",
        "namespace": "agent-workloads",
        "plural": "tasks",
        "label_selector": "agentos.io/workflow=workflow-a",
    }
