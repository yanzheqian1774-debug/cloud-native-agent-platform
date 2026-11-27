"""Explicit server-approved read-only execution scope, separate from resource review."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_contracts import AuthorityError
from .ontology_execution import DocumentSemanticsBinding
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


class ReadonlyWork(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    problem: ExactReference
    sourceContentDigests: tuple[str, ...] = Field(min_length=1, max_length=32)
    case: Literal["delivery", "sales", "tabular", "document"]
    nativeAgentName: str = Field(pattern=r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
    expiresAt: datetime
    documentRules: DocumentSemanticsBinding | None = None

    @model_validator(mode="after")
    def document_rule_case(self):
        if self.documentRules is not None and self.case != "document":
            raise ValueError("DOCUMENT_RULE_CASE_MISMATCH")
        return self


class ReadonlyContinuationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["readonly-work-policy.v1"] = "readonly-work-policy.v1"
    policyId: str
    policyVersion: str
    enabled: bool = False
    works: tuple[ReadonlyWork, ...] = Field(max_length=128)
    developmentTabularAgentName: str | None = Field(
        default=None, pattern=r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$"
    )

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_absolute():
            raise AuthorityError("READONLY_WORK_CONFIGURATION_INVALID")
        raw = path.read_text()
        import json

        if json.loads(raw).get("schemaVersion") == "readonly-work-policy.v2":
            from .readonly_native_policy import ReadonlyContinuationPolicyV2

            return ReadonlyContinuationPolicyV2.model_validate_json(raw)
        return cls.model_validate_json(raw)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json", exclude_none=True))

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
