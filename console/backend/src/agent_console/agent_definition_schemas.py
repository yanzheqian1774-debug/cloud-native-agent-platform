"""Private Workbench API schemas for Agent Definitions."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExactResourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resourceId: str = Field(min_length=1, max_length=240)
    revisionId: str = Field(min_length=1, max_length=240)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class McpToolReference(ExactResourceReference):
    toolName: str = Field(min_length=1, max_length=160)
    snapshotId: str | None = Field(default=None, max_length=240)


class KnowledgeReference(ExactResourceReference):
    snapshotId: str | None = Field(default=None, max_length=240)


class TypedReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=80)
    resourceId: str = Field(min_length=1, max_length=240)
    revisionId: str | None = Field(default=None, max_length=240)
    digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class GovernedBindings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[ExactResourceReference] = []
    mcpTools: list[McpToolReference] = []
    knowledge: list[KnowledgeReference] = []
    model: TypedReference | None = None
    workflow: TypedReference | None = None
    runtimeProfile: TypedReference | None = None


class DefinitionContent(BaseModel):
    title: str
    duties: list[str] = Field(min_length=1)
    data: list[str] = []
    knowledge: list[str] = []
    skills: list[str] = []
    capabilities: list[str] = Field(min_length=1)
    runtimes: list[str] = []
    businessPurpose: str = ""
    bindings: GovernedBindings = GovernedBindings()


class CreateAgentDefinition(BaseModel):
    name: str
    content: DefinitionContent


class EditAgentDefinition(BaseModel):
    expectedVersion: int
    content: DefinitionContent


class VersionCommand(BaseModel):
    expectedVersion: int


class ReviewCommand(VersionCommand):
    digest: str
    decision: str = "APPROVE"
    reason: str


class PublishCommand(VersionCommand):
    digest: str
    reviewId: str


class LifecycleCommand(VersionCommand):
    reason: str


class AgentDefinitionResponse(BaseModel):
    definition: dict[str, Any]
    productProjection: dict[str, Any]
    technicalProjection: dict[str, Any]
