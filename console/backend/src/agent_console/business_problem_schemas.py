"""Strict HTTP contracts for durable Business Problem and Plan entry."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBusinessProblem(_StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    ownerId: str = Field(min_length=1, max_length=200)
    idempotencyKey: str = Field(min_length=1, max_length=200)


class ReviseBusinessProblem(_StrictModel):
    predecessorRevisionId: str = Field(min_length=1, max_length=200)
    expectedVersion: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    ownerId: str = Field(min_length=1, max_length=200)
    idempotencyKey: str = Field(min_length=1, max_length=200)


class CreateCriterionRevision(_StrictModel):
    successCriterionId: str | None = Field(default=None, max_length=200)
    predecessorRevisionId: str | None = Field(default=None, max_length=200)
    expectedVersion: int | None = Field(default=None, ge=1)
    criterionType: Literal[
        "DETERMINISTIC_BOOLEAN",
        "NUMERIC_THRESHOLD",
        "CATEGORICAL_RESULT",
        "EVIDENCE_PRESENCE",
        "HUMAN_EVALUATED",
        "NOT_MEASURABLE",
    ]
    measurement: dict[str, Any]
    requiredEvidenceKinds: list[str] = Field(max_length=32)
    evaluatorType: str = Field(min_length=1, max_length=200)
    evaluatorVersion: str = Field(min_length=1, max_length=200)
    applicability: dict[str, Any] = Field(default_factory=dict)
    idempotencyKey: str = Field(min_length=1, max_length=200)


class CreateCriteriaSetRevision(_StrictModel):
    problemRevisionId: str = Field(min_length=1, max_length=200)
    predecessorSetRevisionId: str | None = Field(default=None, max_length=200)
    orderedCriterionRevisionIds: list[str] = Field(min_length=1, max_length=64)
    expectedVersion: int = Field(ge=1)
    idempotencyKey: str = Field(min_length=1, max_length=200)


class TransitionBusinessProblem(_StrictModel):
    toState: Literal["ACTIVE", "IN_PROGRESS", "RESOLVED", "CLOSED"]
    expectedVersion: int = Field(ge=1)
    idempotencyKey: str = Field(min_length=1, max_length=200)


class PreparePlan(_StrictModel):
    problemRevisionId: str = Field(min_length=1, max_length=200)
    problemRevisionDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    criteriaSetRevisionId: str = Field(min_length=1, max_length=200)
    criteriaSetDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expectedProblemVersion: int = Field(ge=1)
    workflowDefinitionId: str = Field(min_length=1, max_length=200)
    workflowDefinitionRevisionId: str = Field(min_length=1, max_length=200)
    workflowDefinitionDigest: str = Field(pattern=r"^(?:sha256:)?[a-f0-9]{64}$")
    employeeDefinitionId: str = Field(min_length=1, max_length=200)
    employeeDefinitionRevisionId: str = Field(min_length=1, max_length=200)
    employeeDefinitionDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    digitalEmployeeInstanceId: str = Field(min_length=1, max_length=200)
    assignmentId: str = Field(min_length=1, max_length=200)
    idempotencyKey: str = Field(min_length=1, max_length=200)

    @field_validator("workflowDefinitionDigest")
    @classmethod
    def normalize_workflow_digest(cls, value):
        return value.removeprefix("sha256:")


class DecidePlan(PreparePlan):
    planVersion: int = Field(ge=1)
    planDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expectedVersion: int = Field(ge=1)
    decision: Literal["APPROVE", "REJECT"] = "APPROVE"
    reasonCategory: Literal[
        "BUSINESS_APPROVAL",
        "BUSINESS_REJECTION",
        "POLICY_APPROVAL",
        "POLICY_REJECTION",
    ]
    idempotencyKey: str = Field(min_length=1, max_length=200)
