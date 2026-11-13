"""Pure configuration only: no scheduling or execution authority."""

from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError


class AuthoringScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenantId: str = Field(min_length=1, max_length=200)
    securityDomain: str = Field(min_length=1, max_length=200)
    subjectId: str = Field(min_length=1, max_length=200)
    teamId: str = Field(min_length=1, max_length=200)
    teamRevisionId: str = Field(min_length=1, max_length=200)
    teamDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    operations: tuple[Literal["READ", "SAVE"], ...] = Field(min_length=1, max_length=2)


class AuthoringPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["fixed-work-authoring-policy.v1"]
    policyId: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    expiresAt: datetime
    scopes: tuple[AuthoringScope, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def valid(self):
        identities = [
            (s.tenantId, s.securityDomain, s.subjectId, s.teamId, s.teamRevisionId)
            for s in self.scopes
        ]
        if self.expiresAt.tzinfo is None or len(set(identities)) != len(identities):
            raise ValueError("invalid policy scope or expiry")
        return self

    @classmethod
    def load(cls, path):
        p = Path(path)
        try:
            if not p.is_absolute() or p.stat().st_mode & 0o077:
                raise ValueError("private absolute policy required")
            return cls.model_validate_json(p.read_text())
        except (OSError, ValueError) as exc:
            raise WorkbenchOwnerError("FIXED_WORK_AUTHORING_UNAVAILABLE", 503) from exc

    def require(self, context, team_id, revision_id, operation, now):
        if not self.enabled or now >= self.expiresAt:
            raise WorkbenchOwnerError("FIXED_WORK_AUTHORING_UNAVAILABLE", 503)
        matches = [
            s
            for s in self.scopes
            if (s.tenantId, s.securityDomain, s.subjectId, s.teamId, s.teamRevisionId)
            == (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                team_id,
                revision_id,
            )
            and operation in s.operations
        ]
        if len(matches) != 1:
            raise WorkbenchOwnerError("FIXED_WORK_AUTHORING_NOT_AUTHORIZED", 403)
        return matches[0]


class TriggerDraft(StrictWorkbenchModel):
    kind: Literal["SCHEDULE", "EVENT"]
    timezone: str | None = Field(default=None, max_length=100)
    localTime: str | None = Field(
        default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"
    )
    cadence: Literal["DAILY", "WEEKDAY"] | None = None
    eventDescription: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def complete(self):
        if self.kind == "SCHEDULE":
            if (
                not self.timezone
                or not self.localTime
                or not self.cadence
                or self.eventDescription is not None
            ):
                raise ValueError("schedule configuration incomplete")
            try:
                ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("unknown timezone") from exc
        elif (
            self.timezone is not None
            or self.localTime is not None
            or self.cadence is not None
            or not self.eventDescription
            or not self.eventDescription.strip()
        ):
            raise ValueError("event configuration incomplete")
        return self


class SaveDraft(StrictWorkbenchModel):
    workId: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$")
    revisionId: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$")
    predecessorRevisionId: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$"
    )
    expectedVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=4000)
    trigger: TriggerDraft

    @model_validator(mode="after")
    def meaningful(self):
        if not self.title.strip() or not self.instruction.strip():
            raise ValueError("configuration text required")
        if (self.expectedVersion == 0) != (self.predecessorRevisionId is None):
            raise ValueError("predecessor and expected version must agree")
        if self.revisionId == self.predecessorRevisionId:
            raise ValueError("revision must be new")
        return self
