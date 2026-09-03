"""Strict internal Product API schemas for Digital Employee assembly."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateDigitalEmployeeInstance(_StrictModel):
    instanceId: str = Field(min_length=1, max_length=200)
    definitionId: str = Field(min_length=1, max_length=200)
    definitionRevisionId: str = Field(min_length=1, max_length=200)
    commandId: str = Field(min_length=1, max_length=200)
    workspaceReference: str | None = Field(default=None, max_length=200)
    modelReference: str | None = Field(default=None, max_length=200)
    policyReferences: list[str] = Field(default_factory=list, max_length=100)


class CreateDigitalEmployeeAssignment(_StrictModel):
    assignmentId: str = Field(min_length=1, max_length=200)
    commandId: str = Field(min_length=1, max_length=200)
    assigneeId: str = Field(min_length=1, max_length=200)
    businessRole: str = Field(min_length=1, max_length=200)
    effectiveFrom: datetime
    effectiveUntil: datetime | None = None


class CreateDigitalEmployeePlacement(_StrictModel):
    requestId: str = Field(min_length=1, max_length=200)
    placementId: str = Field(min_length=1, max_length=200)
    workflowRunId: str = Field(min_length=1, max_length=200)
    taskRunId: str = Field(min_length=1, max_length=200)
    attemptId: str = Field(min_length=1, max_length=200)
    agentInstanceId: str = Field(min_length=1, max_length=200)
    agentRevisionId: str = Field(min_length=1, max_length=200)
    runtimeProfileRevisionId: str = Field(min_length=1, max_length=200)
    runtimeInstanceId: str = Field(min_length=1, max_length=200)
    policyVersion: str = Field(min_length=1, max_length=200)
    capabilityRequirements: list[str] = Field(default_factory=list, max_length=100)
    resourceRequirements: list[str] = Field(default_factory=list, max_length=100)
    isolationRequirements: list[str] = Field(default_factory=list, max_length=100)
    stateRequirements: list[str] = Field(default_factory=list, max_length=100)
    compatibilityFacts: list[str] = Field(default_factory=list, max_length=100)
    limitationCodes: list[str] = Field(default_factory=list, max_length=100)
    requestedAt: datetime
    decidedAt: datetime


class PlacementReadContext(_StrictModel):
    attemptId: str = Field(min_length=1, max_length=200)
    agentInstanceId: str = Field(min_length=1, max_length=200)
