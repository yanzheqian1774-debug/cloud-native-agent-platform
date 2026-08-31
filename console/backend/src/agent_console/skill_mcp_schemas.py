"""Private Workbench schemas for Skill and MCP resources."""

from typing import Any

from pydantic import BaseModel, Field


class ResourceContent(BaseModel):
    description: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    instructions: str | None = None
    endpoint: str | None = None


class CreateResource(BaseModel):
    name: str = Field(min_length=1)
    content: ResourceContent


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
