"""Private Workbench API schemas for Agent Definitions."""

from typing import Any

from pydantic import BaseModel, Field


class DefinitionContent(BaseModel):
    title: str
    duties: list[str] = Field(min_length=1)
    data: list[str] = []
    knowledge: list[str] = []
    skills: list[str] = []
    capabilities: list[str] = Field(min_length=1)
    runtimes: list[str] = []


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
