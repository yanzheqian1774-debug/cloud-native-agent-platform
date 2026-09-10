"""Closed wire contracts for the trusted Workbench BFF."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
