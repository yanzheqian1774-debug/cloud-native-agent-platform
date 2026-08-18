"""Tests for Kubernetes-to-Console execution projections."""

from agent_console.projection import (
    project_workflow_detail,
    project_workflow_summary,
)


def workflow_resource() -> dict:
    return {
        "metadata": {
            "name": "example-workflow",
            "namespace": "agent-workloads",
            "creationTimestamp": "2026-08-18T10:00:00Z",
        },
        "spec": {
            "tasks": [
                {
                    "name": "architect",
                    "agentRef": {"name": "engineering-architect"},
                    "input": {"prompt": "Design the feature."},
                    "timeoutSeconds": 300,
                },
                {
                    "name": "builder",
                    "agentRef": {"name": "engineering-builder"},
                    "dependsOn": ["architect"],
                    "input": {
                        "prompt": "Implement the feature.",
                        "from": [{"task": "architect"}],
                    },
                    "timeoutSeconds": 300,
                },
                {
                    "name": "reviewer",
                    "agentRef": {"name": "engineering-reviewer"},
                    "dependsOn": ["builder"],
                    "input": {
                        "prompt": "Review the implementation.",
                        "from": [{"task": "builder"}],
                    },
                    "timeoutSeconds": 300,
                },
            ]
        },
        "status": {
            "phase": "Running",
            "taskCount": 3,
            "startedAt": "2026-08-18T10:00:01Z",
            "tasks": {
                "architect": {
                    "phase": "Succeeded",
                    "taskRef": {"name": "example-workflow-architect"},
                },
                "builder": {
                    "phase": "Failed",
                    "taskRef": {"name": "example-workflow-builder"},
                },
                "reviewer": {
                    "phase": "Skipped",
                    "reason": "DependencyFailed",
                    "message": (
                        "Task 'reviewer' skipped because required "
                        "dependencies cannot succeed: builder (Failed)"
                    ),
                },
            },
        },
    }


def task_resource(
    *,
    workflow_task: str,
    name: str,
    prompt: str,
    phase: str,
    result: str | None = None,
    attempts: int = 1,
    reason: str | None = None,
    message: str | None = None,
    retryable: bool | None = None,
) -> dict:
    return {
        "metadata": {
            "name": name,
            "namespace": "agent-workloads",
            "labels": {
                "agentos.io/workflow": "example-workflow",
                "agentos.io/workflow-task": workflow_task,
            },
        },
        "spec": {
            "agentRef": {
                "name": f"engineering-{workflow_task}",
            },
            "input": {
                "prompt": prompt,
            },
            "timeoutSeconds": 300,
        },
        "status": {
            "phase": phase,
            "result": result,
            "attempts": attempts,
            "startedAt": "2026-08-18T10:00:02Z",
            "completedAt": "2026-08-18T10:00:03Z",
            "reason": reason,
            "message": message,
            "retryable": retryable,
        },
    }


def test_project_workflow_summary() -> None:
    summary = project_workflow_summary(workflow_resource())

    assert summary.name == "example-workflow"
    assert summary.namespace == "agent-workloads"
    assert summary.phase == "Running"
    assert summary.taskCount == 3
    assert summary.startedAt == "2026-08-18T10:00:01Z"


def test_project_detail_uses_workflow_spec_as_dag_source() -> None:
    detail = project_workflow_detail(
        workflow_resource(),
        tasks=[],
    )

    assert [node.name for node in detail.nodes] == [
        "architect",
        "builder",
        "reviewer",
    ]

    assert [(edge.source, edge.target, edge.type) for edge in detail.edges] == [
        ("architect", "builder", "control"),
        ("architect", "builder", "data"),
        ("builder", "reviewer", "control"),
        ("builder", "reviewer", "data"),
    ]


def test_project_succeeded_task_execution() -> None:
    architect = task_resource(
        workflow_task="architect",
        name="example-workflow-architect",
        prompt="Design the feature.",
        phase="Succeeded",
        result="architecture result",
    )

    detail = project_workflow_detail(
        workflow_resource(),
        tasks=[architect],
    )

    execution = detail.nodes[0].execution

    assert execution.phase == "Succeeded"
    assert execution.taskRef == "example-workflow-architect"
    assert execution.resolvedInput == "Design the feature."
    assert execution.result == "architecture result"
    assert execution.attempts == 1


def test_project_failed_task_execution() -> None:
    builder = task_resource(
        workflow_task="builder",
        name="example-workflow-builder",
        prompt="Resolved builder prompt.",
        phase="Failed",
        reason="UpstreamUnavailable",
        message="model provider returned HTTP 503",
        retryable=True,
        attempts=3,
    )

    detail = project_workflow_detail(
        workflow_resource(),
        tasks=[builder],
    )

    execution = detail.nodes[1].execution

    assert execution.phase == "Failed"
    assert execution.reason == "UpstreamUnavailable"
    assert execution.message == "model provider returned HTTP 503"
    assert execution.retryable is True
    assert execution.attempts == 3


def test_project_skipped_node_without_task_cr() -> None:
    detail = project_workflow_detail(
        workflow_resource(),
        tasks=[],
    )

    execution = detail.nodes[2].execution

    assert execution.phase == "Skipped"
    assert execution.taskRef is None
    assert execution.resolvedInput is None
    assert execution.reason == "DependencyFailed"


def test_project_unscheduled_node_defaults_to_pending() -> None:
    workflow = workflow_resource()
    workflow["status"]["tasks"].pop("reviewer")

    detail = project_workflow_detail(
        workflow,
        tasks=[],
    )

    execution = detail.nodes[2].execution

    assert execution.phase == "Pending"
    assert execution.taskRef is None


def test_project_upstream_results_from_task_execution() -> None:
    architect = task_resource(
        workflow_task="architect",
        name="example-workflow-architect",
        prompt="Design the feature.",
        phase="Succeeded",
        result="architecture result",
    )

    builder = task_resource(
        workflow_task="builder",
        name="example-workflow-builder",
        prompt="Resolved builder prompt with architecture result.",
        phase="Running",
    )

    detail = project_workflow_detail(
        workflow_resource(),
        tasks=[architect, builder],
    )

    execution = detail.nodes[1].execution

    assert execution.declaredInput == "Implement the feature."
    assert execution.resolvedInput == (
        "Resolved builder prompt with architecture result."
    )
    assert len(execution.upstreamResults) == 1
    assert execution.upstreamResults[0].task == "architect"
    assert execution.upstreamResults[0].result == "architecture result"


def test_project_timed_out_task_execution() -> None:
    builder = task_resource(
        workflow_task="builder",
        name="example-workflow-builder",
        prompt="Resolved builder prompt.",
        phase="TimedOut",
        reason="ExecutionTimeout",
        message="task execution deadline exceeded",
        retryable=False,
        attempts=2,
    )

    detail = project_workflow_detail(
        workflow_resource(),
        tasks=[builder],
    )

    execution = detail.nodes[1].execution

    assert execution.phase == "TimedOut"
    assert execution.taskRef == "example-workflow-builder"
    assert execution.reason == "ExecutionTimeout"
    assert execution.message == "task execution deadline exceeded"
    assert execution.retryable is False
    assert execution.attempts == 2
