"""Narrow existing service grants; configuration never issues authority."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_contracts import AuthenticationSource, AuthorityError
from .digital_employee_definition import digest
from .plan_suggestion_domain import ExactReference, ProblemTarget
from .planning_contracts import PlanningPolicy


class ServicePlanningPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["fixed-work-service-planning.v1"]
    policyId: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    tenantId: str = Field(min_length=1, max_length=200)
    securityDomain: str = Field(min_length=1, max_length=200)
    subjectId: str = Field(pattern=r"^service:[A-Za-z0-9:._-]{1,190}$")
    credentialId: str = Field(min_length=1, max_length=200)
    work: ExactReference
    target: ProblemTarget
    resourceSnapshot: ExactReference
    planningPolicy: PlanningPolicy | None = None
    allowedEventIds: tuple[str, ...] = Field(min_length=1, max_length=128)
    eventWindows: dict[str, tuple[datetime, datetime]]
    profileRevisionId: str = Field(min_length=1, max_length=200)
    profileDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    model: ExactReference
    ledgerId: str = Field(min_length=1, max_length=200)
    maximumInputTokens: int = Field(strict=True, ge=1)
    maximumOutputTokens: int = Field(strict=True, ge=1)
    expiresAt: datetime

    @model_validator(mode="after")
    def aware(self):
        if len(set(self.allowedEventIds)) != len(self.allowedEventIds) or any(
            not 1 <= len(event) <= 200 or any(c.isspace() for c in event)
            for event in self.allowedEventIds
        ):
            raise ValueError("bounded unique trusted events required")
        if self.expiresAt.tzinfo is None:
            raise ValueError("aware expiry required")
        if set(self.eventWindows) != set(self.allowedEventIds) or any(
            begin.tzinfo is None
            or end.tzinfo is None
            or not begin < end <= self.expiresAt
            for begin, end in self.eventWindows.values()
        ):
            raise ValueError("exact aware event windows within expiry required")
        if self.expiresAt.tzinfo is None:
            raise ValueError("aware expiry required")
        return self

    @property
    def digest(self):
        return digest(self.model_dump(mode="json"))

    @property
    def model_target(self):
        m = self.model
        return (
            f"model:invocation:plan-suggestion:{m.resource_id}:"
            f"{m.revision_id}:{m.digest}"
        )

    @classmethod
    def load(cls, path):
        p = Path(path)
        try:
            if not p.is_absolute() or p.stat().st_mode & 0o077:
                raise ValueError("private absolute policy required")
            raw = p.read_text()
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError("policy object required")
            if document.get("schemaVersion") == "fixed-work-service-planning.v2":
                from .fixed_work_bound_policy import BoundServicePlanningPolicy

                return BoundServicePlanningPolicy.model_validate_json(raw)
            return cls.model_validate_json(raw)
        except (OSError, ValueError) as exc:
            raise AuthorityError("FIXED_WORK_SERVICE_POLICY_UNAVAILABLE") from exc

    def require(self, context, now):
        if not self.enabled or now >= self.expiresAt:
            raise AuthorityError("FIXED_WORK_SERVICE_POLICY_UNAVAILABLE")
        if (
            context.authentication_source is not AuthenticationSource.SERVICE_CREDENTIAL
            or (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                context.session_id_or_service_credential_id,
            )
            != (self.tenantId, self.securityDomain, self.subjectId, self.credentialId)
        ):
            raise AuthorityError("FIXED_WORK_SERVICE_IDENTITY_DENIED")

    def require_event(self, event, now):
        if (
            event not in self.allowedEventIds
            or not self.eventWindows[event][0] <= now < self.eventWindows[event][1]
        ):
            raise AuthorityError("FIXED_WORK_SERVICE_EVENT_NOT_DUE")
