"""Pagination of already-authorized task projections; never accepts raw snapshots."""

from collections import Counter
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .workbench_owner_authorization import WorkbenchOwnerError


class CurrentWorkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflowRunId: str
    preparationDigest: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str
    createdAt: datetime
    initiatorId: str | None
    executionState: str
    displayState: Literal[
        "waiting", "completed", "running", "failed", "cancelled", "unknown"
    ]
    progressVersion: int | None = Field(ge=1)
    problemId: str
    problemRevisionId: str
    problemDigest: str = Field(pattern=r"^[0-9a-f]{64}$")
    pendingQuestionCount: int | None = Field(ge=0)
    planVersion: int | None = Field(default=None, ge=1)
    participantCount: int | None = Field(default=None, ge=0)
    completedTaskCount: int | None = Field(default=None, ge=0)
    taskCount: int | None = Field(default=None, ge=0)
    updatedAt: datetime | None = None
    questionsDigest: str | None = None
    outcomeVersion: int | None = Field(default=None, ge=1)
    artifactCount: int = Field(ge=0)
    businessResolution: Literal["CONFIRMED_SOLVED", "NOT_SOLVED", "UNDETERMINED"] | None
    originConversationId: str | None
    originVerified: bool

    @field_validator("createdAt")
    @classmethod
    def aware_created_at(cls, value):
        if value.tzinfo is None:
            raise ValueError("CURRENT_WORK_TIMESTAMP_INVALID")
        return value.astimezone(UTC)


def directory_page(
    items, query, codec, context, *, generation, recovery_epoch, read_at
):
    """Filter/count/page one complete authorized set, with no database effects.

    Counts include the same scope, search and state predicates as total/items.
    The caller must finish authorization before calling this function. Refuse
    untyped raw fact dictionaries so private fields cannot leak into a response.
    """
    if any(not isinstance(item, CurrentWorkItem) for item in items):
        raise TypeError("CURRENT_WORK_AUTHORIZED_PROJECTION_REQUIRED")
    if len({item.workflowRunId for item in items}) != len(items):
        raise WorkbenchOwnerError("CURRENT_WORK_DUPLICATE_RUN", 503)
    after = query.after(
        codec, context, generation=generation, recovery_epoch=recovery_epoch
    )
    matches = [
        item
        for item in items
        if (query.scopeFilter == "visible" or item.initiatorId == context.principal_id)
        and query.query.casefold() in (item.title + " " + item.workflowRunId).casefold()
        and (query.state == "all" or item.displayState == query.state)
    ]
    matches.sort(key=lambda item: (item.createdAt, item.workflowRunId), reverse=True)
    counts = Counter(item.displayState for item in matches)
    remaining = matches
    if after:
        try:
            after_time = datetime.fromisoformat(after[0])
            if after_time.tzinfo is None:
                raise ValueError
        except ValueError as exc:
            raise WorkbenchOwnerError("REQUEST_INVALID", 422) from exc
        remaining = [
            item
            for item in matches
            if (item.createdAt, item.workflowRunId) < (after_time, after[1])
        ]
    page = remaining[: query.pageSize]
    token = None
    if len(remaining) > len(page):
        last = page[-1]
        token = query.next_cursor(
            codec,
            context,
            generation=generation,
            recovery_epoch=recovery_epoch,
            created_at=last.createdAt.isoformat(),
            workflow_run_id=last.workflowRunId,
        )
    return {
        "schemaVersion": "current-work-directory.v1",
        "scopeFilter": query.scopeFilter,
        "subject": context.principal_id,
        "tenantId": context.scope.tenant_id,
        "securityDomain": context.scope.security_domain,
        "readAt": read_at.isoformat(),
        "complete": True,
        "total": len(matches),
        "counts": {
            state: counts[state]
            for state in (
                "waiting",
                "completed",
                "running",
                "failed",
                "cancelled",
                "unknown",
            )
        },
        "items": [item.model_dump(mode="json") for item in page],
        "nextCursor": token,
    }
