"""Workflow controller for AgentOS."""

from collections.abc import Mapping
from copy import deepcopy
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


def list_workflow_task_states(
    *,
    workflow_name: str,
    namespace: str,
) -> dict[str, dict[str, Any]]:
    """List Workflow task execution states, including phase and result."""
    load_kubernetes_config()
    api = client.CustomObjectsApi()

    response = api.list_namespaced_custom_object(
        group="agentos.io",
        version="v1alpha1",
        namespace=namespace,
        plural="tasks",
        label_selector=f"agentos.io/workflow={workflow_name}",
    )

    states: dict[str, dict[str, Any]] = {}

    for item in response.get("items", []):
        metadata = item.get("metadata", {})
        labels = metadata.get("labels", {})
        workflow_task_name = labels.get("agentos.io/workflow-task")

        if not workflow_task_name:
            continue

        status = item.get("status", {})

        states[workflow_task_name] = {
            "phase": status.get("phase", "Pending"),
            "result": status.get("result"),
        }

    return states


def list_workflow_task_phases(
    *,
    workflow_name: str,
    namespace: str,
) -> dict[str, str]:
    states = list_workflow_task_states(
        workflow_name=workflow_name,
        namespace=namespace,
    )

    return {task_name: state["phase"] for task_name, state in states.items()}


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

    task_states = list_workflow_task_states(
        workflow_name=name,
        namespace=namespace,
    )

    task_phases = {
        task_name: state["phase"] for task_name, state in task_states.items()
    }

    ready_task_names = find_ready_tasks(
        graph,
        task_phases,
    )

    created = 0

    for task_name in ready_task_names:
        task_spec = tasks_by_name[task_name]

        task_results: dict[str, str] = {}
        missing_result = False

        for source in task_spec.get("input", {}).get("from", []):
            source_task = source["task"]

            source_state = task_states.get(
                source_task,
                {},
            )

            source_result = source_state.get("result")

            if source_result is None:
                missing_result = True
                break

            task_results[source_task] = source_result

        if missing_result:
            continue

        resolved_task_spec = deepcopy(task_spec)

        resolved_task_spec["input"]["prompt"] = resolve_task_prompt(
            task_spec=task_spec,
            task_results=task_results,
        )

        resolved_task_spec["input"].pop(
            "from",
            None,
        )

        if ensure_workflow_task(
            workflow_name=name,
            namespace=namespace,
            task_spec=resolved_task_spec,
            owner=body,
        ):
            created += 1

    return created


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


def resolve_task_prompt(
    *,
    task_spec: dict[str, Any],
    task_results: Mapping[str, str],
) -> str:
    """Resolve a workflow task prompt with upstream task results."""
    prompt = task_spec["input"]["prompt"]
    sources = task_spec["input"].get("from", [])

    if not sources:
        return prompt

    sections = [
        prompt,
        "",
        "Previous task results:",
    ]

    for source in sources:
        task_name = source["task"]
        sections.extend(
            [
                "",
                f"[{task_name}]",
                task_results[task_name],
            ]
        )

    return "\n".join(sections)
