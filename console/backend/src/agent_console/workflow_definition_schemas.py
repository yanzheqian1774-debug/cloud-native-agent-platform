"""Private Workflow Definition Workbench schemas."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExactReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["AGENT", "SKILL", "MCP", "KNOWLEDGE", "RUNTIME_PROFILE"]
    resourceId: str = Field(min_length=1)
    revisionId: str = Field(min_length=1)


class WorkflowTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taskId: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    name: str = Field(min_length=1, max_length=120)
    dependsOn: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []
    capabilityRequirements: list[str] = []
    references: list[ExactReference] = []
    retryLimit: int = Field(default=0, ge=0, le=10)
    timeoutSeconds: int = Field(default=300, ge=1, le=86400)
    failurePolicy: Literal["FAIL_WORKFLOW", "SKIP_DEPENDENTS"] = "FAIL_WORKFLOW"


class WorkflowContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    tasks: list[WorkflowTask] = Field(min_length=1, max_length=200)
    inputs: list[str] = []
    outputs: list[str] = []
    runtimeProfile: ExactReference


class CreateWorkflowDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: WorkflowContent


class EditWorkflowDefinition(BaseModel):
    expectedVersion: int
    content: WorkflowContent


class VersionCommand(BaseModel):
    expectedVersion: int


class ReviewCommand(VersionCommand):
    digest: str
    decision: Literal["APPROVE", "REJECT"] = "APPROVE"
    reason: str


class PublishCommand(VersionCommand):
    digest: str
    reviewId: str


class WorkflowDefinitionResponse(BaseModel):
    definition: dict[str, Any]
    productProjection: dict[str, Any]
    technicalProjection: dict[str, Any]
