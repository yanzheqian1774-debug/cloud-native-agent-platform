"""Explicit server-approved read-only execution scope, separate from resource review."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


class ReadonlyWork(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    problem: ExactReference
    sourceContentDigests: tuple[str, ...] = Field(min_length=1, max_length=32)
    case: Literal["delivery", "sales", "tabular"]
    nativeAgentName: str = Field(pattern=r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
    expiresAt: datetime


class ReadonlyContinuationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["readonly-work-policy.v1"] = "readonly-work-policy.v1"
    policyId: str
    policyVersion: str
    enabled: bool = False
    works: tuple[ReadonlyWork, ...] = Field(max_length=128)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_absolute():
            raise AuthorityError("READONLY_WORK_CONFIGURATION_INVALID")
        return cls.model_validate_json(path.read_text())

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def work(self, context, root, source_digest, now):
        if not self.enabled:
            raise AuthorityError("READONLY_WORK_DISABLED")
        matches = [
            w
            for w in self.works
            if (w.namespace, w.securityDomain, w.subject, w.problem)
            == (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                root,
            )
            and w.expiresAt.tzinfo is not None
            and w.expiresAt > now
            and source_digest in w.sourceContentDigests
        ]
        if len(matches) != 1:
            raise AuthorityError("READONLY_WORK_NOT_AUTHORIZED")
        return matches[0]
