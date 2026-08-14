"""Workflow controller for AgentOS."""

from typing import Any

import kopf
from kubernetes import client, config

from agent_operator.resources import build_workflow_task
from agent_operator.workflow_graph import WorkflowValidationError, build_workflow_graph


def load_kubernetes_config() -> None:
    """Load Kubernetes configuration for in-cluster or local execution."""

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def ensure_workflow_task(
    *,
    workflow_name: str,
    namespace: str,
    task_spec: dict[str, Any],
    owner: dict[str, Any],
) -> bool:
    """Ensure a Workflow-owned Task exists.

    Returns True when the Task was created and False when it already existed.
    """

    resource = build_workflow_task(
        workflow_name=workflow_name,
        namespace=namespace,
        task_spec=task_spec,
    )

    kopf.adopt(resource, owner=owner)

    load_kubernetes_config()

    api = client.CustomObjectsApi()

    try:
        api.create_namespaced_custom_object(
            group="agentos.io",
            version="v1alpha1",
            namespace=namespace,
            plural="tasks",
            body=resource,
        )
    except client.ApiException as exc:
        if exc.status == 409:
            return False
        raise

    return True


@kopf.on.create("agentos.io", "v1alpha1", "workflows")
def create_workflow(
    spec: dict[str, Any],
    name: str,
    namespace: str,
    body: dict[str, Any],
    patch: kopf.Patch,
    **_: Any,
) -> None:
    """Validate a Workflow and create its root Tasks."""

    tasks = spec["tasks"]

    try:
        graph = build_workflow_graph(tasks)
    except WorkflowValidationError as exc:
        patch.status["phase"] = "Failed"
        raise kopf.PermanentError(str(exc)) from exc

    tasks_by_name = {task["name"]: task for task in tasks}

    root_task_names = [
        task_name for task_name in graph.task_names if not graph.dependencies[task_name]
    ]

    for task_name in root_task_names:
        ensure_workflow_task(
            workflow_name=name,
            namespace=namespace,
            task_spec=tasks_by_name[task_name],
            owner=body,
        )

    patch.status["phase"] = "Running"
    patch.status["taskCount"] = len(tasks)
