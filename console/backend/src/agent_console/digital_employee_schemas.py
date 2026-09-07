"""Strict internal Product API schemas for Digital Employee assembly."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeCompositionMember(_StrictModel):
    kind: Literal["AGENT", "WORKFLOW", "SKILL", "MCP", "KNOWLEDGE", "RUNTIME_PROFILE"]
    resourceId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^(?:sha256:)?[a-f0-9]{64}$")


class CreateEmployeeDefinition(_StrictModel):
    employeeDefinitionId: str = Field(min_length=1, max_length=200)
    employeeDefinitionRevisionId: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    responsibilities: list[str] = Field(min_length=1, max_length=32)
    members: list[EmployeeCompositionMember] = Field(min_length=1, max_length=128)
    predecessorEmployeeRevisionId: str | None = Field(default=None, max_length=200)
    expectedVersion: int = Field(ge=0)
    commandId: str = Field(min_length=1, max_length=200)


class DecideEmployeeDefinition(_StrictModel):
    employeeDefinitionRevisionId: str = Field(min_length=1, max_length=200)
    employeeDefinitionDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expectedVersion: int = Field(ge=1)
    commandId: str = Field(min_length=1, max_length=200)


class CreateDigitalEmployeeInstance(_StrictModel):
    instanceId: str = Field(min_length=1, max_length=200)
    employeeDefinitionId: str = Field(min_length=1, max_length=200)
    employeeDefinitionRevisionId: str = Field(min_length=1, max_length=200)
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
