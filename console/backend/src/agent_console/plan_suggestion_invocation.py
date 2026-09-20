"""Planning-owned invocation contract, separate from pre-Problem draft identity."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .plan_suggestion_domain import (
    Digest,
    ExactReference,
    Identity,
    Immutable,
    PlanSemantics,
    ProblemTarget,
    Text,
)

PURPOSE = "CONFIRMED_PROBLEM_PLAN_SUGGESTION"


class PlanningProfile(Immutable):
    profile_revision_id: Identity
    profile_digest: Digest
    model: ExactReference
    adapter_id: Identity
    adapter_revision: Identity
    maximum_output_tokens: int = Field(ge=1, le=32768)
    maximum_input_bytes: int = Field(ge=1, le=65536)
    real_calls_enabled: bool = False


class PlanningRequest(Immutable):
    target: ProblemTarget
    source_proposal: ExactReference | None = None
    answers: tuple[Text, ...] = Field(default=(), max_length=16)
    idempotency_key: Identity
    predecessor_invocation_id: Identity | None = None


class PlanningInvocationTarget(Immutable):
    schema_version: Literal["plan-suggestion-target.v1"] = "plan-suggestion-target.v1"
    purpose: Literal["CONFIRMED_PROBLEM_PLAN_SUGGESTION"] = PURPOSE
    namespace: Identity
    security_domain: Identity
    invocation_id: Identity
    suggestion_context_id: Identity
    request_revision: int = Field(ge=1)
    predecessor_invocation_id: Identity | None = None
    problem: ProblemTarget
    source_proposal: ExactReference | None
    variant: Literal["FIRST_PROPOSAL", "SUCCESSOR_PROPOSAL"]
    resource_snapshot: ExactReference | None
    input_commitment: Digest
    output_schema: Literal[
        "plan-suggestion-output.v1", "planning-diagnostic-output.v1"
    ] = "plan-suggestion-output.v1"
    policy_version: Identity

    @model_validator(mode="after")
    def source_variant(self):
        if (self.source_proposal is None) != (self.variant == "FIRST_PROPOSAL"):
            raise ValueError("PLANNING_INVOCATION_TARGET_INVALID")
        return self


class PlanningProviderResult(Immutable):
    """Only normalized bounded business output may be retained by Planning."""

    kind: Literal["NEEDS_CLARIFICATION", "VALID_SUGGESTION", "UNSUPPORTED"]
    questions: tuple[Text, ...] = Field(default=(), max_length=8)
    semantics: PlanSemantics | None = None

    @model_validator(mode="after")
    def result_shape(self):
        if self.kind == "VALID_SUGGESTION":
            if self.semantics is None or self.questions:
                raise ValueError("PLANNING_RESULT_INVALID")
        elif self.kind == "NEEDS_CLARIFICATION":
            if not self.questions or self.semantics is not None:
                raise ValueError("PLANNING_RESULT_INVALID")
        elif self.questions or self.semantics is not None:
            raise ValueError("PLANNING_RESULT_INVALID")
        return self
