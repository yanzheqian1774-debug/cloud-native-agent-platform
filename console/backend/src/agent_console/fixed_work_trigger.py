"""Bounded explicit one-use binding; no timer or service identity substitution."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_contracts import AuthenticationSource
from .digital_employee_definition import digest
from .workbench_owner_authorization import WorkbenchOwnerError


class TriggerBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenantId: str = Field(min_length=1, max_length=200)
    securityDomain: str = Field(min_length=1, max_length=200)
    subjectId: str = Field(min_length=1, max_length=200)
    workId: str = Field(min_length=1, max_length=200)
    revisionId: str = Field(min_length=1, max_length=200)
    workDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preparationDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["EXPLICIT_ORIGINAL_SUBJECT", "EXPLICIT_SERVICE"]


class TriggerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["fixed-work-one-use-policy.v1"]
    policyId: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    expiresAt: datetime
    bindings: tuple[TriggerBinding, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def valid(self):
        if self.expiresAt.tzinfo is None:
            raise ValueError("aware expiry required")
        ids = [
            (b.tenantId, b.securityDomain, b.preparationDigest) for b in self.bindings
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("one binding per preparation")
        return self

    @property
    def digest(self):
        return digest(self.model_dump(mode="json"))

    def require(self, context, path, now):
        if not self.enabled or now >= self.expiresAt:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_UNAVAILABLE", 503)
        bindings = [
            b
            for b in self.bindings
            if (
                b.tenantId,
                b.securityDomain,
                b.subjectId,
                b.workId,
                b.revisionId,
                b.preparationDigest,
            )
            == (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                path["work_id"],
                path["revision_id"],
                path["digest"],
            )
        ]
        if len(bindings) != 1:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_DENIED", 403)
        binding = bindings[0]
        expected = (
            AuthenticationSource.SERVICE_CREDENTIAL
            if binding.mode == "EXPLICIT_SERVICE"
            else AuthenticationSource.BROWSER_SESSION
        )
        if context.authentication_source is not expected:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_DENIED", 403)
        # No service model/plan admission owner has been composed here yet.
        # Do not turn a configuration assertion into independently granted authority.
        if binding.mode == "EXPLICIT_SERVICE":
            raise WorkbenchOwnerError("FIXED_WORK_SERVICE_ADMISSION_UNAVAILABLE", 503)
        return binding
