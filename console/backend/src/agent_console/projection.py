"""Projection of Kubernetes Workflow execution state into Console API models."""

from collections.abc import Mapping
from typing import Any

from agent_console.schemas import (
    AgentReference,
    NodeExecution,
    UpstreamResult,
    WorkflowEdge,
    WorkflowExecutionDetail,
    WorkflowNode,
    WorkflowRunSummary,
)


def project_workflow_summary(
    workflow: Mapping[str, Any],
) -> WorkflowRunSummary:
    """Project a Kubernetes Workflow resource into a list summary."""
    metadata = workflow.get("metadata", {})
    status = workflow.get("status", {})

    return WorkflowRunSummary(
        name=metadata["name"],
        namespace=metadata["namespace"],
        phase=status.get("phase", "Pending"),
        taskCount=status.get(
            "taskCount",
            len(workflow.get("spec", {}).get("tasks", [])),
        ),
        startedAt=status.get("startedAt"),
        completedAt=status.get("completedAt"),
        createdAt=metadata.get("creationTimestamp"),
    )


def _workflow_task_name(task: Mapping[str, Any]) -> str | None:
    metadata = task.get("metadata", {})
    labels = metadata.get("labels", {})
    return labels.get("agentos.io/workflow-task")


def _tasks_by_workflow_name(
    tasks: list[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    projected: dict[str, Mapping[str, Any]] = {}

    for task in tasks:
        workflow_task_name = _workflow_task_name(task)

        if workflow_task_name:
            projected[workflow_task_name] = task

    return projected


def _project_upstream_results(
    input_from: list[str],
    tasks_by_name: Mapping[str, Mapping[str, Any]],
) -> list[UpstreamResult]:
    results: list[UpstreamResult] = []

    for source_name in input_from:
        source_task = tasks_by_name.get(source_name)

        if source_task is None:
            continue

        result = source_task.get("status", {}).get("result")

        if result is None:
            continue

        results.append(
            UpstreamResult(
                task=source_name,
                result=result,
            )
        )

    return results


def _project_node_execution(
    *,
    workflow_task: Mapping[str, Any],
    workflow_status: Mapping[str, Any],
    task: Mapping[str, Any] | None,
    input_from: list[str],
    tasks_by_name: Mapping[str, Mapping[str, Any]],
) -> NodeExecution:
    declared_input = workflow_task["input"]["prompt"]

    if task is None:
        return NodeExecution(
            phase=workflow_status.get("phase", "Pending"),
            taskRef=workflow_status.get("taskRef", {}).get("name"),
            declaredInput=declared_input,
            resolvedInput=None,
            upstreamResults=_project_upstream_results(
                input_from,
                tasks_by_name,
            ),
            reason=workflow_status.get("reason"),
            message=workflow_status.get("message"),
        )

    metadata = task.get("metadata", {})
    spec = task.get("spec", {})
    status = task.get("status", {})

    return NodeExecution(
        phase=status.get(
            "phase",
            workflow_status.get("phase", "Pending"),
        ),
        taskRef=metadata.get("name"),
        declaredInput=declared_input,
        resolvedInput=spec.get("input", {}).get("prompt"),
        upstreamResults=_project_upstream_results(
            input_from,
            tasks_by_name,
        ),
        result=status.get("result"),
        attempts=status.get("attempts"),
        startedAt=status.get("startedAt"),
        completedAt=status.get("completedAt"),
        reason=status.get("reason"),
        message=status.get("message"),
        retryable=status.get("retryable"),
    )


def _project_edges(
    workflow_tasks: list[Mapping[str, Any]],
) -> list[WorkflowEdge]:
    edges: list[WorkflowEdge] = []

    for task in workflow_tasks:
        target = task["name"]

        for source in task.get("dependsOn", []):
            edges.append(
                WorkflowEdge(
                    source=source,
                    target=target,
                    type="control",
                )
            )

        for input_source in task.get("input", {}).get("from", []):
            edges.append(
                WorkflowEdge(
                    source=input_source["task"],
                    target=target,
                    type="data",
                )
            )

    return edges


def project_workflow_detail(
    workflow: Mapping[str, Any],
    tasks: list[Mapping[str, Any]],
) -> WorkflowExecutionDetail:
    """Project Workflow and Task resources into one execution detail model."""
    metadata = workflow.get("metadata", {})
    spec = workflow.get("spec", {})
    status = workflow.get("status", {})
    workflow_tasks = spec.get("tasks", [])
    workflow_task_statuses = status.get("tasks", {})
    tasks_by_name = _tasks_by_workflow_name(tasks)

    nodes: list[WorkflowNode] = []

    for workflow_task in workflow_tasks:
        task_name = workflow_task["name"]
        input_from = [
            source["task"] for source in workflow_task.get("input", {}).get("from", [])
        ]

        node_status = workflow_task_statuses.get(task_name, {})
        task = tasks_by_name.get(task_name)

        nodes.append(
            WorkflowNode(
                name=task_name,
                agent=AgentReference(
                    name=workflow_task["agentRef"]["name"],
                ),
                dependsOn=list(workflow_task.get("dependsOn", [])),
                inputFrom=input_from,
                timeoutSeconds=workflow_task.get("timeoutSeconds", 300),
                execution=_project_node_execution(
                    workflow_task=workflow_task,
                    workflow_status=node_status,
                    task=task,
                    input_from=input_from,
                    tasks_by_name=tasks_by_name,
                ),
            )
        )

    return WorkflowExecutionDetail(
        name=metadata["name"],
        namespace=metadata["namespace"],
        phase=status.get("phase", "Pending"),
        taskCount=status.get("taskCount", len(workflow_tasks)),
        startedAt=status.get("startedAt"),
        completedAt=status.get("completedAt"),
        createdAt=metadata.get("creationTimestamp"),
        nodes=nodes,
        edges=_project_edges(workflow_tasks),
    )
