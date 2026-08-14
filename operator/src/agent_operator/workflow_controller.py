"""Workflow controller for AgentOS."""

from typing import Any

import kopf
from kubernetes import client, config

from agent_operator.resources import build_workflow_task
from agent_operator.workflow_graph import (
    WorkflowValidationError,
    build_workflow_graph,
    find_ready_tasks,
)


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
    """Validate and reconcile a newly created Workflow."""

    tasks = spec["tasks"]

    try:
        reconcile_workflow(
            spec=spec,
            name=name,
            namespace=namespace,
            body=body,
        )
    except WorkflowValidationError as exc:
        patch.status["phase"] = "Failed"
        raise kopf.PermanentError(str(exc)) from exc

    patch.status["phase"] = "Running"
    patch.status["taskCount"] = len(tasks)


def list_workflow_task_phases(
    *,
    workflow_name: str,
    namespace: str,
) -> dict[str, str]:
    """Return workflow task phases keyed by workflow task name."""

    load_kubernetes_config()

    api = client.CustomObjectsApi()

    response = api.list_namespaced_custom_object(
        group="agentos.io",
        version="v1alpha1",
        namespace=namespace,
        plural="tasks",
        label_selector=f"agentos.io/workflow={workflow_name}",
    )

    phases: dict[str, str] = {}

    for item in response.get("items", []):
        labels = item.get("metadata", {}).get("labels", {})
        task_name = labels.get("agentos.io/workflow-task")

        if not task_name:
            continue

        phase = item.get("status", {}).get("phase", "Pending")
        phases[task_name] = phase

    return phases


def reconcile_workflow(
    *,
    spec: dict[str, Any],
    name: str,
    namespace: str,
    body: dict[str, Any],
) -> int:
    """Reconcile runnable Tasks for a Workflow.

    Returns the number of newly created Tasks.
    """

    tasks = spec["tasks"]
    graph = build_workflow_graph(tasks)

    tasks_by_name = {task["name"]: task for task in tasks}

    task_phases = list_workflow_task_phases(
        workflow_name=name,
        namespace=namespace,
    )

    ready_task_names = find_ready_tasks(
        graph,
        task_phases,
    )

    created = 0

    for task_name in ready_task_names:
        if ensure_workflow_task(
            workflow_name=name,
            namespace=namespace,
            task_spec=tasks_by_name[task_name],
            owner=body,
        ):
            created += 1

    return created


@kopf.on.field(..., field="status.phase")
def get_workflow(
    *,
    workflow_name: str,
    namespace: str,
) -> dict[str, Any]:
    """Get a Workflow custom resource."""

    load_kubernetes_config()

    api = client.CustomObjectsApi()

    return api.get_namespaced_custom_object(
        group="agentos.io",
        version="v1alpha1",
        namespace=namespace,
        plural="workflows",
        name=workflow_name,
    )


def reconcile_workflow_for_task(
    *,
    body: dict[str, Any],
    namespace: str,
    new_phase: str | None,
) -> None:
    """Reconcile the owning Workflow after a Task phase change."""

    if new_phase != "Succeeded":
        return

    labels = body.get("metadata", {}).get("labels", {})
    workflow_name = labels.get("agentos.io/workflow")

    if not workflow_name:
        return

    workflow = get_workflow(
        workflow_name=workflow_name,
        namespace=namespace,
    )

    reconcile_workflow(
        spec=workflow["spec"],
        name=workflow_name,
        namespace=namespace,
        body=workflow,
    )


@kopf.on.field(
    "agentos.io",
    "v1alpha1",
    "tasks",
    field="status.phase",
)
def workflow_task_phase_changed(
    body: dict[str, Any],
    namespace: str,
    new: str | None,
    **_: Any,
) -> None:
    """Reconcile a Workflow when one of its Tasks succeeds."""

    reconcile_workflow_for_task(
        body=body,
        namespace=namespace,
        new_phase=new,
    )
