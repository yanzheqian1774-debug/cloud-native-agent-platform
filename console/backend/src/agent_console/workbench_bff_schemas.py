"""Closed wire contracts for the trusted Workbench BFF."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictWorkbenchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkbenchPrincipal(StrictWorkbenchModel):
    principalId: str
    tenantId: str
    securityDomain: str


class WorkbenchSessionMetadata(StrictWorkbenchModel):
    expiresAt: datetime
    idleExpiresAt: datetime


class WorkbenchSessionResponse(StrictWorkbenchModel):
    schemaVersion: Literal["workbench-session.v1"] = "workbench-session.v1"
    principal: WorkbenchPrincipal
    session: WorkbenchSessionMetadata
    csrfToken: str = Field(min_length=1)


class WorkbenchOperationResponse(StrictWorkbenchModel):
    """Minimal BFF envelope around an owner-projected response."""

    schemaVersion: Literal["workbench-operation.v1"] = "workbench-operation.v1"
    result: dict[str, Any]
    continuationIds: tuple[str, ...] = ()


class WorkbenchErrorResponse(StrictWorkbenchModel):
    reasonCode: str = Field(min_length=1, max_length=100)


class WorkbenchExactGrant(StrictWorkbenchModel):
    owner: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)
    resource: str = Field(min_length=1, max_length=512)


class WorkbenchGrantRequestCommand(StrictWorkbenchModel):
    schemaVersion: Literal["exact-grant-request.v1"]
    purpose: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_]+$")
    requestedGrants: tuple[WorkbenchExactGrant, ...] = Field(default=(), max_length=32)
    continuationIds: tuple[str, ...] = Field(default=(), max_length=1)

    @model_validator(mode="after")
    def require_request_source(self):
        if bool(self.requestedGrants) == bool(self.continuationIds):
            raise ValueError("grant request source required")
        return self


class WorkbenchGrantRequestStatus(StrictWorkbenchModel):
    requestId: str
    state: Literal["PENDING", "APPROVED", "REJECTED"]
    aggregateVersion: int = Field(ge=1)
    submittedAt: datetime
    purpose: str
    requestedActions: tuple[str, ...]


class WorkbenchGrantDecisionCommand(StrictWorkbenchModel):
    schemaVersion: Literal["exact-grant-decision.v1"]
    expectedVersion: int = Field(ge=1)
    decision: Literal["APPROVE", "REJECT"]
    reasonCategory: str = Field(min_length=1, max_length=64)
    basisType: Literal["TICKET", "POLICY"]
    basisReference: str = Field(min_length=1, max_length=512)
    notBefore: datetime | None = None
    expiresAt: datetime | None = None

    @model_validator(mode="after")
    def require_decision_window(self):
        if self.decision == "APPROVE" and self.expiresAt is None:
            raise ValueError("approval expiry required")
        if self.decision == "REJECT" and (
            self.notBefore is not None or self.expiresAt is not None
        ):
            raise ValueError("rejection window prohibited")
        return self


class WorkbenchGrantDecisionResult(StrictWorkbenchModel):
    schemaVersion: Literal["exact-grant-decision-result.v1"] = (
        "exact-grant-decision-result.v1"
    )
    requestId: str
    decisionId: str
    state: Literal["APPROVED", "REJECTED"]
    aggregateVersion: int = Field(ge=2)
    decidedAt: datetime
    notBefore: datetime | None = None
    expiresAt: datetime | None = None


class WorkbenchAvailableContinuation(StrictWorkbenchModel):
    continuationId: str = Field(min_length=1)
    purpose: str
    expiresAt: datetime
    requestableActions: tuple[str, ...]


class WorkbenchContinuationInbox(StrictWorkbenchModel):
    continuations: tuple[WorkbenchAvailableContinuation, ...]


class WorkbenchProblemCreatorContinuation(StrictWorkbenchModel):
    schemaVersion: Literal["problem-creator-continuation.v1"] = (
        "problem-creator-continuation.v1"
    )
    relation: Literal["PROBLEM_CREATOR"] = "PROBLEM_CREATOR"
    purpose: Literal["CONTINUE_PROBLEM_READ"] = "CONTINUE_PROBLEM_READ"
    state: Literal["AVAILABLE", "CONSUMED", "EXPIRED"]
    expiresAt: datetime
    continuationId: str | None = Field(
        default=None, pattern=r"^continuation-ref\.[a-f0-9]{64}$"
    )
    requestId: str | None = None

    @model_validator(mode="after")
    def require_state_correlation(self):
        if self.state in {"AVAILABLE", "CONSUMED"} and self.continuationId is None:
            raise ValueError("continuation reference required")
        if (self.state == "CONSUMED") != (self.requestId is not None):
            raise ValueError("consumed request correlation invalid")
        return self


class WorkbenchAgentRole(StrictWorkbenchModel):
    title: str
    duties: tuple[str, ...]
    businessPurpose: str
    capabilities: tuple[str, ...]


class WorkbenchAgentRevision(StrictWorkbenchModel):
    definitionId: str
    revisionId: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str
    role: WorkbenchAgentRole


class WorkbenchPageQuery(StrictWorkbenchModel):
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)
    pageSize: int = Field(default=50, ge=1, le=200)


class WorkbenchAgentSummary(StrictWorkbenchModel):
    definitionId: str
    name: str
    revisionId: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str
    enabled: bool
    archived: bool


class WorkbenchAgentPage(StrictWorkbenchModel):
    items: tuple[WorkbenchAgentSummary, ...]
    nextCursor: str | None = None


class WorkbenchEmployeeMember(StrictWorkbenchModel):
    kind: str
    resourceId: str
    revisionId: str
    digest: str


class WorkbenchEmployeeRevision(StrictWorkbenchModel):
    resourceKind: Literal["DIGITAL_EMPLOYEE_DEFINITION"]
    employeeDefinitionId: str
    employeeDefinitionRevisionId: str
    employeeDefinitionDigest: str
    role: str
    responsibilities: tuple[str, ...]
    members: tuple[WorkbenchEmployeeMember, ...]
    publicationState: Literal["PUBLISHED", "NOT_PUBLISHED"]


class WorkbenchEmployeeSummary(StrictWorkbenchModel):
    employeeDefinitionId: str
    employeeDefinitionRevisionId: str
    employeeDefinitionDigest: str
    role: str
    publicationState: Literal["PUBLISHED", "NOT_PUBLISHED"]


class WorkbenchEmployeePage(StrictWorkbenchModel):
    items: tuple[WorkbenchEmployeeSummary, ...]
    nextCursor: str | None = None


class WorkbenchPlacementQuery(StrictWorkbenchModel):
    attemptId: str = Field(min_length=1, max_length=200)
    agentInstanceId: str = Field(min_length=1, max_length=200)


class WorkbenchPlacementBinding(StrictWorkbenchModel):
    instanceId: str
    assignmentId: str
    attemptId: str
    agentInstanceId: str


class WorkbenchPlacement(StrictWorkbenchModel):
    placementId: str
    requestId: str
    decision: str
    runtimeInstanceId: str
    policyVersion: str
    compatibilityFacts: tuple[str, ...]
    limitationCodes: tuple[str, ...]
    decidedAt: datetime
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding: WorkbenchPlacementBinding
