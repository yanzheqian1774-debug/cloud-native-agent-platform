"""Contract tests for Console API schemas."""

import pytest
from agent_console.schemas import (
    AgentReference,
    NodeExecution,
    UpstreamResult,
    WorkflowEdge,
    WorkflowExecutionDetail,
    WorkflowNode,
    WorkflowRunList,
    WorkflowRunSummary,
)
from pydantic import ValidationError


def test_workflow_run_list_contract() -> None:
    response = WorkflowRunList(
        items=[
            WorkflowRunSummary(
                name="engineering-s4-009-001",
                namespace="agent-workloads",
                phase="Succeeded",
                taskCount=4,
                startedAt="2026-08-18T06:56:16Z",
                completedAt="2026-08-18T06:58:21Z",
                createdAt="2026-08-18T06:56:16Z",
            )
        ]
    )

    payload = response.model_dump()

    assert payload["items"][0]["phase"] == "Succeeded"
    assert payload["items"][0]["taskCount"] == 4


def test_workflow_detail_preserves_control_and_data_edges() -> None:
    detail = WorkflowExecutionDetail(
        name="engineering-s4-009-001",
        namespace="agent-workloads",
        phase="Running",
        taskCount=2,
        nodes=[
            WorkflowNode(
                name="architect",
                agent=AgentReference(name="engineering-architect"),
                dependsOn=[],
                inputFrom=[],
                timeoutSeconds=300,
                execution=NodeExecution(
                    phase="Succeeded",
                    declaredInput="Design the feature.",
                    resolvedInput="Design the feature.",
                    result="architecture result",
                    attempts=1,
                ),
            ),
            WorkflowNode(
                name="builder",
                agent=AgentReference(name="engineering-builder"),
                dependsOn=["architect"],
                inputFrom=["architect"],
                timeoutSeconds=300,
                execution=NodeExecution(
                    phase="Running",
                    taskRef="engineering-s4-009-001-builder",
                    declaredInput="Implement the feature.",
                    resolvedInput=(
                        "Implement the feature.\n\n"
                        "Upstream task architect result:\n"
                        "architecture result"
                    ),
                    upstreamResults=[
                        UpstreamResult(
                            task="architect",
                            result="architecture result",
                        )
                    ],
                    attempts=1,
                ),
            ),
        ],
        edges=[
            WorkflowEdge(
                source="architect",
                target="builder",
                type="control",
            ),
            WorkflowEdge(
                source="architect",
                target="builder",
                type="data",
            ),
        ],
    )

    payload = detail.model_dump()

    assert payload["nodes"][1]["dependsOn"] == ["architect"]
    assert payload["nodes"][1]["inputFrom"] == ["architect"]
    assert payload["nodes"][1]["execution"]["upstreamResults"] == [
        {
            "task": "architect",
            "result": "architecture result",
        }
    ]
    assert payload["edges"] == [
        {
            "source": "architect",
            "target": "builder",
            "type": "control",
        },
        {
            "source": "architect",
            "target": "builder",
            "type": "data",
        },
    ]


def test_skipped_node_does_not_require_task_reference() -> None:
    node = WorkflowNode(
        name="reviewer",
        agent=AgentReference(name="engineering-reviewer"),
        dependsOn=["builder"],
        inputFrom=["builder"],
        timeoutSeconds=300,
        execution=NodeExecution(
            phase="Skipped",
            taskRef=None,
            declaredInput="Review the result.",
            resolvedInput=None,
            reason="DependencyFailed",
            message="builder failed",
        ),
    )

    assert node.execution.phase == "Skipped"
    assert node.execution.taskRef is None
    assert node.execution.attempts is None


def test_machine_phase_values_are_language_neutral() -> None:
    summary = WorkflowRunSummary(
        name="example",
        namespace="default",
        phase="Succeeded",
        taskCount=1,
    )

    assert summary.phase == "Succeeded"

    with pytest.raises(ValidationError):
        WorkflowRunSummary(
            name="example",
            namespace="default",
            phase="成功",
            taskCount=1,
        )


def test_console_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WorkflowRunSummary(
            name="example",
            namespace="default",
            phase="Succeeded",
            taskCount=1,
            unexpected="value",
        )
