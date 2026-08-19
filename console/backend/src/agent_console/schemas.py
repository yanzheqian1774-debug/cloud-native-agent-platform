"""API schemas for the AgentOS Workflow Execution Console."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

WorkflowPhase = Literal[
    "Pending",
    "Running",
    "Succeeded",
    "Failed",
]

NodePhase = Literal[
    "Pending",
    "Running",
    "Succeeded",
    "Failed",
    "TimedOut",
    "Skipped",
]

EdgeType = Literal[
    "control",
    "data",
]


class ConsoleModel(BaseModel):
    """Base model for Console API responses."""

    model_config = ConfigDict(extra="forbid")


class WorkflowRunSummary(ConsoleModel):
    """Summary of one Workflow execution."""

    name: str
    namespace: str
    phase: WorkflowPhase
    taskCount: int
    startedAt: str | None = None
    completedAt: str | None = None
    createdAt: str | None = None


class WorkflowRunList(ConsoleModel):
    """List response for Workflow executions."""

    items: list[WorkflowRunSummary]


class AgentReference(ConsoleModel):
    """Agent referenced by a Workflow node."""

    name: str


class UpstreamResult(ConsoleModel):
    """Execution result consumed from an upstream Workflow node."""

    task: str
    result: str


class NodeExecution(ConsoleModel):
    """Effective execution state for a Workflow node."""

    phase: NodePhase
    taskRef: str | None = None
    declaredInput: str
    resolvedInput: str | None = None
    upstreamResults: list[UpstreamResult] = []
    result: str | None = None
    attempts: int | None = None
    startedAt: str | None = None
    completedAt: str | None = None
    reason: str | None = None
    message: str | None = None
    retryable: bool | None = None


class WorkflowNode(ConsoleModel):
    """Projected Workflow DAG node."""

    name: str
    agent: AgentReference
    dependsOn: list[str] = []
    inputFrom: list[str] = []
    timeoutSeconds: int
    execution: NodeExecution


class WorkflowEdge(ConsoleModel):
    """Projected Workflow DAG edge."""

    source: str
    target: str
    type: EdgeType


class WorkflowExecutionDetail(ConsoleModel):
    """Complete read-only Workflow execution projection."""

    name: str
    namespace: str
    phase: WorkflowPhase
    taskCount: int
    startedAt: str | None = None
    completedAt: str | None = None
    createdAt: str | None = None
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
