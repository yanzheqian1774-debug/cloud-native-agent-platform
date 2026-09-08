"""Private Workbench schemas for Skill and MCP resources."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_console.skill_invocation_domain import (
    ExecutorRevision,
    SideEffectClass,
    SideEffectPolicy,
    SkillIOLimits,
)


def validate_skill_operations(value: Any) -> list[dict[str, Any]]:
    """Validate the existing governed operation wire record using its domain types."""
    if not isinstance(value, list) or not value:
        raise ValueError("SKILL_OPERATIONS_REQUIRED")
    names = set()
    for operation in value:
        if not isinstance(operation, dict) or set(operation) != {
            "name",
            "inputSchema",
            "outputSchema",
            "sideEffectClass",
            "executorId",
            "executorRevision",
            "executorConfigurationDigest",
            "sideEffectPolicy",
            "ioLimits",
        }:
            raise ValueError("SKILL_OPERATION_FIELDS_INVALID")
        name = operation["name"]
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 200
            or name in names
        ):
            raise ValueError("SKILL_OPERATION_NAME_INVALID")
        names.add(name)
        if not all(
            isinstance(operation[key], dict) for key in ("inputSchema", "outputSchema")
        ):
            raise ValueError("SKILL_OPERATION_SCHEMA_INVALID")
        ExecutorRevision(
            operation["executorId"],
            operation["executorRevision"],
            operation["executorConfigurationDigest"],
        )
        policy = operation["sideEffectPolicy"]
        if not isinstance(policy, dict) or set(policy) != {
            "policyId",
            "policyRevision",
            "policyDigest",
        }:
            raise ValueError("SKILL_OPERATION_POLICY_INVALID")
        SideEffectPolicy(
            policy["policyId"],
            policy["policyRevision"],
            policy["policyDigest"],
            SideEffectClass(operation["sideEffectClass"]),
        )
        limits = operation["ioLimits"]
        if not isinstance(limits, dict) or set(limits) != {
            "policyId",
            "policyRevision",
            "maxInputBytes",
            "maxOutputBytes",
            "maxObjectDepth",
            "maxProperties",
            "timeoutMs",
        }:
            raise ValueError("SKILL_OPERATION_LIMITS_INVALID")
        SkillIOLimits(
            limits["policyId"],
            limits["policyRevision"],
            limits["maxInputBytes"],
            limits["maxOutputBytes"],
            limits["maxObjectDepth"],
            limits["maxProperties"],
            limits["timeoutMs"],
        )
    return value


class ResourceContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: list[dict[str, Any]] | None = None

    @field_validator("operations", mode="before")
    @classmethod
    def operations_contract(cls, value):
        return validate_skill_operations(value)

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
    model_config = ConfigDict(extra="forbid")
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
    model_config = ConfigDict(extra="forbid")
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
