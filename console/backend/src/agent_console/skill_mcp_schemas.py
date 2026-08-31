"""Private Workbench schemas for Skill and MCP resources."""

from typing import Any

from pydantic import BaseModel, Field


class ResourceContent(BaseModel):
    description: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    instructions: str | None = None
    endpoint: str | None = None
    secretReference: str | None = None
    inputSchema: dict[str, Any] = {}
    outputSchema: dict[str, Any] = {}
    parameters: list[dict[str, Any]] = []
    errorPolicy: dict[str, Any] = {}
    timeoutSeconds: int = Field(default=5, ge=1, le=30)
    sideEffect: str = "NONE"
    idempotency: str = "IDEMPOTENT"
    permissions: list[str] = []
    dependencies: list[str] = []
    examples: list[dict[str, Any]] = []


class CreateResource(BaseModel):
    name: str = Field(min_length=1)
    content: ResourceContent


class ImportManifest(BaseModel):
    manifestVersion: str
    kind: str
    name: str = Field(min_length=1)
    content: ResourceContent


class CloneCommand(BaseModel):
    revisionId: str
    name: str = Field(min_length=1)


class EditResource(BaseModel):
    expectedVersion: int
    content: ResourceContent


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


class BindCommand(VersionCommand):
    skillRevisionId: str
    mcpResourceId: str
    mcpRevisionId: str
    capability: str
    reason: str


class InvokeCommand(VersionCommand):
    bindingId: str
    authorization: str
    input: dict[str, Any] = {}
    timeoutSeconds: float = Field(default=5, ge=0.1, le=30)


class TestCaseCommand(VersionCommand):
    name: str = Field(min_length=1, max_length=120)
    input: dict[str, Any] = {}
    expected: dict[str, Any] = {}


class DiscoveryCommand(VersionCommand):
    timeoutSeconds: float = Field(default=5, ge=0.1, le=30)


class ToolSelectionCommand(VersionCommand):
    snapshotId: str
    toolNames: list[str] = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=1)


class McpInvocationCommand(VersionCommand):
    selectionId: str
    toolName: str
    authorization: str
    input: dict[str, Any] = {}
    timeoutSeconds: float = Field(default=5, ge=0.1, le=30)
    cancelRequested: bool = False
