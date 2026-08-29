"""Strict internal DTOs for intervention and outcome feedback capture."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InterventionEventKind = Literal[
    "TASK_ADDED",
    "TASK_REMOVED",
    "TASK_REWRITTEN",
    "TASK_ORDER_OR_DEPENDENCY_CHANGED",
    "ROLE_REPLACED",
    "ROLE_GAP_IDENTIFIED",
    "DATA_REQUIREMENT_CHANGED",
    "KNOWLEDGE_REQUIREMENT_CHANGED",
    "SKILL_CHANGED",
    "CAPABILITY_CHANGED",
    "APPROVAL_POINT_CHANGED",
    "CONSTRAINT_CHANGED",
    "OUTPUT_FORMAT_CHANGED",
    "WORKFLOW_REJECTED",
    "RESULT_FEEDBACK_PROVIDED",
]
InterventionLifecycle = Literal["RECORDED", "EXCLUDED", "RETAINED", "TOMBSTONED"]
AffectedElementReference = Literal[
    "WORKFLOW",
    "WORKFLOW_OBJECTIVE",
    "TASK_REQUIREMENT",
    "TASK_DEPENDENCY",
    "ROLE_BINDING",
    "DATA_REQUIREMENT",
    "KNOWLEDGE_REQUIREMENT",
    "SKILL_BINDING",
    "CAPABILITY_BINDING",
    "APPROVAL_POINT",
    "CONSTRAINT",
    "OUTPUT_FORMAT",
    "OUTCOME",
]
CorrectionPatchReference = Literal[
    "NO_PATCH",
    "OBJECTIVE_REPLACEMENT",
    "TASK_SET_PATCH",
    "DEPENDENCY_PATCH",
    "ROLE_BINDING_PATCH",
    "DATA_REQUIREMENT_PATCH",
    "KNOWLEDGE_REQUIREMENT_PATCH",
    "SKILL_BINDING_PATCH",
    "CAPABILITY_BINDING_PATCH",
    "APPROVAL_POINT_PATCH",
    "CONSTRAINT_PATCH",
    "OUTPUT_FORMAT_PATCH",
]
InterventionReasonCode = Literal[
    "HUMAN_CORRECTION",
    "HUMAN_REJECTION",
    "ROLE_GAP",
    "MISSING_TASK",
    "EXTRA_TASK",
    "WRONG_DATA",
    "INSUFFICIENT_DATA",
    "WRONG_KNOWLEDGE",
    "WRONG_ROLE",
    "WRONG_SKILL",
    "WRONG_CAPABILITY",
    "WRONG_ORDER",
    "MISSING_CONSTRAINT",
    "WRONG_OUTPUT_FORMAT",
    "CITATION_NOT_USEFUL",
]
FeedbackReasonCode = Literal[
    "MISSING_TASK",
    "EXTRA_TASK",
    "WRONG_DATA",
    "INSUFFICIENT_DATA",
    "WRONG_KNOWLEDGE",
    "WRONG_ROLE",
    "WRONG_SKILL",
    "WRONG_CAPABILITY",
    "WRONG_ORDER",
    "MISSING_CONSTRAINT",
    "WRONG_OUTPUT_FORMAT",
    "CITATION_NOT_USEFUL",
]
OutcomeAssessment = Literal["SATISFIED", "PARTIALLY_SATISFIED", "UNSATISFIED"]
OptimizationUseConsentDecision = Literal["GRANTED", "DENIED"]
CaptureProvenance = Literal["LIVE_EXECUTION", "SYNTHETIC_PREVIEW"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImmutableStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InterventionCaptureCommand(StrictModel):
    predecessorRevisionId: str
    successorRevisionId: str
    outcomeId: str
    evidenceId: str
    eventKind: InterventionEventKind
    affectedElementReference: AffectedElementReference
    correctionPatchReference: CorrectionPatchReference
    reasonCode: InterventionReasonCode
    optimizationUseConsentDecision: OptimizationUseConsentDecision


class InterventionLifecycleCommand(StrictModel):
    lifecycle: Literal["EXCLUDED", "RETAINED", "TOMBSTONED"]


class OutcomeFeedbackCommand(StrictModel):
    outcomeId: str
    evidenceId: str
    assessment: OutcomeAssessment
    reasonCodes: list[FeedbackReasonCode] = Field(min_length=1, max_length=12)
    supersedesFeedbackId: str | None = None


class InterventionEventRecord(ImmutableStrictModel):
    schemaVersion: Literal[1] = 1
    recordId: str
    interventionEventId: str
    recordDigest: str
    lifecycle: InterventionLifecycle
    supersedesRecordId: str | None
    journeyId: str
    predecessorRevisionId: str
    predecessorRevisionDigest: str
    successorRevisionId: str
    successorRevisionDigest: str
    affectedElementReference: AffectedElementReference
    correctionPatchReference: CorrectionPatchReference
    eventKind: InterventionEventKind
    reasonCode: str
    principalId: str
    decisionTime: str
    tenantId: str
    securityDomain: str
    platformExecutionIdentity: str
    outcomeId: str
    executionEvidenceIds: tuple[str, ...]
    provenance: CaptureProvenance
    optimizationUseConsentDecision: OptimizationUseConsentDecision


class OutcomeFeedbackRecord(ImmutableStrictModel):
    schemaVersion: Literal[1] = 1
    feedbackId: str
    feedbackDigest: str
    revision: int = Field(ge=1)
    supersedesFeedbackId: str | None
    journeyId: str
    canonicalWorkflowRevisionId: str
    platformExecutionIdentity: str
    outcomeId: str
    evidenceId: str
    assessment: OutcomeAssessment
    reasonCodes: tuple[FeedbackReasonCode, ...]
    principalId: str
    decisionTime: str
    tenantId: str
    securityDomain: str
    provenance: CaptureProvenance


class OutcomeFeedbackView(ImmutableStrictModel):
    lifecycle: Literal["RECORDED", "SUPERSEDED"]
    record: OutcomeFeedbackRecord


class InterventionFeedbackIdentity(ImmutableStrictModel):
    journeyId: str
    tenantId: str
    securityDomain: str
    predecessorRevisionId: str | None
    successorRevisionId: str
    platformExecutionIdentity: str
    outcomeId: str
    evidenceIds: tuple[str, ...]
    provenance: CaptureProvenance


class InterventionFeedbackProjection(ImmutableStrictModel):
    projection: Literal["PRODUCT", "TECHNICAL"]
    identity: InterventionFeedbackIdentity
    interventions: tuple[InterventionEventRecord, ...]
    outcomeFeedback: tuple[OutcomeFeedbackView, ...]


class InterventionFeedbackResponse(ImmutableStrictModel):
    schemaVersion: Literal[1] = 1
    state: Literal["READY"] = "READY"
    reasonCode: Literal["INTERVENTION_FEEDBACK_READY"] = "INTERVENTION_FEEDBACK_READY"
    product: InterventionFeedbackProjection
    technical: InterventionFeedbackProjection


class InterventionFeedbackError(StrictModel):
    schemaVersion: Literal[1] = 1
    state: Literal["DENIED", "NOT_FOUND", "CONFLICT", "INVALID", "UNAVAILABLE"]
    reasonCode: str
    message: Literal["Intervention and feedback capture is unavailable"] = (
        "Intervention and feedback capture is unavailable"
    )
