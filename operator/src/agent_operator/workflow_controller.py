"""Workflow controller for AgentOS."""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

import kopf
from kubernetes import client, config

from agent_operator.resources import build_workflow_task
from agent_operator.workflow_graph import (
    TERMINAL_UNSUCCESSFUL_PHASES,
    WorkflowValidationError,
    build_workflow_graph,
    find_ready_tasks,
    find_skipped_tasks,
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


def patch_workflow_task_statuses(
    *,
    workflow_name: str,
    namespace: str,
    body: dict[str, Any],
    task_statuses: Mapping[str, dict[str, Any]],
) -> bool:
    """Patch changed Workflow node statuses.

    Returns True when a status patch was written and False when the desired
    node statuses already match the Workflow status.
    """

    current_statuses = body.get("status", {}).get("tasks", {})

    changed_statuses = {
        task_name: task_status
        for task_name, task_status in task_statuses.items()
        if current_statuses.get(task_name) != task_status
    }

    if not changed_statuses:
        return False

    load_kubernetes_config()

    api = client.CustomObjectsApi()

    api.patch_namespaced_custom_object_status(
        group="agentos.io",
        version="v1alpha1",
        namespace=namespace,
        plural="workflows",
        name=workflow_name,
        body={
            "status": {
                "tasks": changed_statuses,
            }
        },
    )

    return True


def patch_workflow_status(
    *,
    workflow_name: str,
    namespace: str,
    body: dict[str, Any],
    phase: str,
    task_count: int,
    task_statuses: Mapping[str, dict[str, Any]],
) -> bool:
    """Patch the complete aggregated Workflow status when it changes."""

    current_status = body.get("status", {})
    current_task_statuses = current_status.get("tasks", {})

    desired_task_statuses = dict(task_statuses)

    desired_status = {
        "phase": phase,
        "taskCount": task_count,
        "tasks": desired_task_statuses,
    }

    current_projection = {
        "phase": current_status.get("phase"),
        "taskCount": current_status.get("taskCount"),
        "tasks": current_task_statuses,
    }

    if current_projection == desired_status:
        return False

    task_status_patch: dict[str, Any] = dict(desired_task_statuses)

    stale_task_names = set(current_task_statuses) - set(desired_task_statuses)

    for task_name in stale_task_names:
        task_status_patch[task_name] = None

    load_kubernetes_config()

    api = client.CustomObjectsApi()

    api.patch_namespaced_custom_object_status(
        group="agentos.io",
        version="v1alpha1",
        namespace=namespace,
        plural="workflows",
        name=workflow_name,
        body={
            "status": {
                "phase": phase,
                "taskCount": task_count,
                "tasks": task_status_patch,
            }
        },
    )

    return True


def build_skipped_task_status(
    *,
    task_name: str,
    dependencies: tuple[str, ...],
    task_phases: Mapping[str, str],
) -> dict[str, str]:
    """Build deterministic Workflow status for a skipped task."""

    blockers = [
        (dependency, task_phases.get(dependency))
        for dependency in dependencies
        if task_phases.get(dependency) in TERMINAL_UNSUCCESSFUL_PHASES
    ]

    has_direct_failure = any(phase in {"Failed", "TimedOut"} for _, phase in blockers)

    reason = "DependencyFailed" if has_direct_failure else "DependencySkipped"

    blocker_text = ", ".join(
        f"{dependency} ({phase})" for dependency, phase in blockers
    )

    return {
        "phase": "Skipped",
        "reason": reason,
        "message": (
            f"Task {task_name!r} skipped because required dependencies "
            f"cannot succeed: {blocker_text}"
        ),
    }


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


WORKFLOW_TERMINAL_TASK_PHASES = {
    "Succeeded",
    "Failed",
    "TimedOut",
    "Skipped",
}


def aggregate_workflow_phase(
    *,
    task_names: Iterable[str],
    task_phases: Mapping[str, str],
) -> str:
    """Aggregate effective task phases into the Workflow phase."""

    phases = [task_phases.get(task_name, "Pending") for task_name in task_names]

    if phases and all(phase == "Succeeded" for phase in phases):
        return "Succeeded"

    if phases and all(phase in WORKFLOW_TERMINAL_TASK_PHASES for phase in phases):
        return "Failed"

    return "Running"


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

    workflow_task_statuses = body.get("status", {}).get("tasks", {})

    for task_name, task_status in workflow_task_statuses.items():
        if task_name in task_phases:
            continue

        phase = task_status.get("phase")

        if phase == "Skipped":
            task_phases[task_name] = phase

    skipped_task_names = find_skipped_tasks(
        graph,
        task_phases,
    )

    skipped_statuses: dict[str, dict[str, Any]] = {}

    for task_name in skipped_task_names:
        skipped_status = build_skipped_task_status(
            task_name=task_name,
            dependencies=graph.dependencies[task_name],
            task_phases=task_phases,
        )

        skipped_statuses[task_name] = skipped_status
        task_phases[task_name] = "Skipped"

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

    effective_task_statuses = build_workflow_task_statuses(
        workflow_name=name,
        task_names=graph.task_names,
        task_states=task_states,
        existing_statuses=workflow_task_statuses,
    )

    for task_name, skipped_status in skipped_statuses.items():
        effective_task_statuses[task_name] = skipped_status

    effective_task_phases = {
        task_name: task_status["phase"]
        for task_name, task_status in effective_task_statuses.items()
    }

    workflow_phase = aggregate_workflow_phase(
        task_names=graph.task_names,
        task_phases=effective_task_phases,
    )

    patch_workflow_status(
        workflow_name=name,
        namespace=namespace,
        body=body,
        phase=workflow_phase,
        task_count=len(tasks),
        task_statuses=effective_task_statuses,
    )

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

    if new_phase not in {
        "Succeeded",
        "Failed",
        "TimedOut",
    }:
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
    """Reconcile a Workflow when one of its Tasks becomes terminal."""

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


def build_workflow_task_statuses(
    *,
    workflow_name: str,
    task_names: Iterable[str],
    task_states: Mapping[str, dict[str, Any]],
    existing_statuses: Mapping[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the complete Workflow node status projection."""

    statuses: dict[str, dict[str, Any]] = {}

    for task_name in task_names:
        task_state = task_states.get(task_name)

        if task_state is not None:
            statuses[task_name] = {
                "phase": task_state["phase"],
                "taskRef": {
                    "name": f"{workflow_name}-{task_name}",
                },
            }
            continue

        existing_status = existing_statuses.get(task_name)

        if existing_status is not None and existing_status.get("phase") == "Skipped":
            statuses[task_name] = deepcopy(existing_status)
            continue

        statuses[task_name] = {
            "phase": "Pending",
        }

    return statuses
