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


class JourneyUnderstanding(StrictModel):
    question: str
    scope: list[str]
    facts: list[str]
    assumptions: list[str]
    uncertainties: list[str]
    expectedOutcome: list[str]
    provenance: Literal["DETERMINISTIC_DEMO_INTERPRETATION"]


class JourneyTaskProjection(StrictModel):
    taskId: str
    title: str
    purpose: str
    inputs: list[str]
    actions: list[str]
    dependencies: list[str]
    expectedOutputs: list[str]
    completionConditions: list[str]
    approvalRequired: bool
    requiredRole: str
    matchedRole: str | None
    matchState: Literal["MATCHED", "ROLE_GAP", "NOT_EVALUATED"]
    definitionId: str | None
    definitionVersion: str | None
    definitionDigest: str | None
    descriptorId: str | None = None
    publicationState: str = "NOT_EXPOSED"
    matchAuthorization: str = "NOT_EXPOSED"
    publicationDecisionId: str | None = None
    skills: list[str]
    mcpCapabilities: list[str]
    knowledgeRefs: list[str]
    runtimeRefs: list[str]
    readiness: Literal["READY", "ROLE_GAP", "DENIED", "UNAVAILABLE", "NOT_BOUND"]
    reasonCodes: list[str]
    state: Literal[
        "NOT_STARTED", "WAITING_DEPENDENCY", "READY", "RUNNING", "SUCCEEDED", "FAILED"
    ]


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
    understanding: JourneyUnderstanding | None = None
    decomposition: list[str] = []
    projectedTasks: list[JourneyTaskProjection] = []


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
