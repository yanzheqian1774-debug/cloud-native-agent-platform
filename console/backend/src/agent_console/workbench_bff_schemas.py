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
