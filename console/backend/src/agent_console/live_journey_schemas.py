"""Strict internal DTOs for the Product live planning journey."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JourneyIdentity(StrictModel):
    tenantId: str
    securityDomain: str
    canonicalWorkflowRevisionId: str
    canonicalDigest: str
    sharedSnapshotId: str
    graphSnapshotId: str
    platformExecutionIdentity: str | None
    approvalId: str
    placementDecisionId: str
    evidenceIds: list[str]
    citationIds: list[str]


class JourneyCitation(StrictModel):
    citationId: str
    retrievalEvidenceId: str
    authorizationDecisionId: str
    knowledgePackId: str
    knowledgePackVersion: str
    knowledgePackDigest: str
    documentId: str
    documentVersion: str
    documentDigest: str
    sectionId: str
    chunkId: str
    status: Literal["AVAILABLE", "STALE"]


class JourneyOutcome(StrictModel):
    outcomeId: str
    classification: Literal["SUCCEEDED", "FAILED", "UNKNOWN"]
    summary: str
    comparableMetric: str
    comparableValue: float | None


class JourneyRevision(StrictModel):
    revision: int = Field(ge=1)
    predecessorRevisionId: str | None
    objective: str
    lifecycle: Literal["PENDING_APPROVAL", "APPROVED", "EXECUTABLE", "SUPERSEDED"]
    approvalState: Literal["PENDING", "APPROVED", "REJECTED"]
    identity: JourneyIdentity
    planTaskIds: list[str]
    matchState: Literal["MATCHED", "PARTIAL", "ROLE_GAP", "DENIED", "ERROR"]
    placementState: Literal["PLACED", "UNAVAILABLE", "STALE", "DENIED", "ERROR"]
    knowledgeState: Literal[
        "AVAILABLE", "STALE", "EXPIRED", "DENIED", "NOT_FOUND", "UNAVAILABLE", "ERROR"
    ]
    executionState: Literal[
        "NOT_REQUESTED",
        "AUTHORIZED_HANDOFF",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "UNAVAILABLE",
    ]
    answer: str | None
    citations: list[JourneyCitation]
    outcome: JourneyOutcome | None
    limitationCodes: list[str]


class JourneyProjection(StrictModel):
    projection: Literal["PRODUCT", "TECHNICAL"]
    identity: JourneyIdentity
    revision: JourneyRevision


class LiveJourneyResponse(StrictModel):
    schemaVersion: Literal[1] = 1
    journeyId: str
    state: Literal["LIVE", "STALE", "DENIED", "UNAVAILABLE", "ERROR"]
    provenance: Literal["LIVE_EXECUTION", "SYNTHETIC_PREVIEW"]
    reasonCode: str
    product: JourneyProjection
    technical: JourneyProjection
    predecessor: JourneyRevision | None
    successor: JourneyRevision


class CorrectionRequest(StrictModel):
    predecessorRevisionId: str
    predecessorDigest: str
    objective: str = Field(min_length=1, max_length=500)
    reasonCode: str = Field(min_length=1, max_length=128)


class ApprovalRequest(StrictModel):
    candidateDigest: str
    decision: Literal["APPROVE", "REJECT"]
    reasonCode: str = Field(min_length=1, max_length=128)
    replayIdentity: str = Field(min_length=1, max_length=200)


class RerunRequest(StrictModel):
    canonicalWorkflowRevisionId: str
    canonicalDigest: str


class LiveJourneyError(StrictModel):
    schemaVersion: Literal[1] = 1
    state: Literal["DENIED", "NOT_FOUND", "AUTHORITY_MISSING", "STALE", "ERROR"]
    reasonCode: str
    message: str
