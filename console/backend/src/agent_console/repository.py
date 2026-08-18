"""Kubernetes repository for Workflow execution resources."""

from typing import Any, Protocol

from kubernetes import client, config

GROUP = "agentos.io"
VERSION = "v1alpha1"


class WorkflowRepository(Protocol):
    """Read-only repository contract for Workflow execution state."""

    def list_workflows(self) -> list[dict[str, Any]]:
        """List Workflow resources."""
        ...

    def get_workflow(
        self,
        namespace: str,
        name: str,
    ) -> dict[str, Any]:
        """Get one Workflow resource."""
        ...

    def list_workflow_tasks(
        self,
        namespace: str,
        workflow_name: str,
    ) -> list[dict[str, Any]]:
        """List Task resources owned by one Workflow."""
        ...


def load_kubernetes_config() -> None:
    """Load in-cluster configuration or fall back to local kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


class KubernetesWorkflowRepository:
    """Read-only Kubernetes implementation of WorkflowRepository."""

    def __init__(
        self,
        api: client.CustomObjectsApi | None = None,
    ) -> None:
        if api is None:
            load_kubernetes_config()
            api = client.CustomObjectsApi()

        self._api = api

    def list_workflows(self) -> list[dict[str, Any]]:
        response = self._api.list_cluster_custom_object(
            group=GROUP,
            version=VERSION,
            plural="workflows",
        )

        return response.get("items", [])

    def get_workflow(
        self,
        namespace: str,
        name: str,
    ) -> dict[str, Any]:
        return self._api.get_namespaced_custom_object(
            group=GROUP,
            version=VERSION,
            namespace=namespace,
            plural="workflows",
            name=name,
        )

    def list_workflow_tasks(
        self,
        namespace: str,
        workflow_name: str,
    ) -> list[dict[str, Any]]:
        response = self._api.list_namespaced_custom_object(
            group=GROUP,
            version=VERSION,
            namespace=namespace,
            plural="tasks",
            label_selector=f"agentos.io/workflow={workflow_name}",
        )

        return response.get("items", [])
