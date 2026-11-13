"""Server-only, explicit-subject ontology maintenance scopes; no execution rights."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .ontology_domain import DocumentRulesContent, OntologyContent
from .resource_automation_policy import AutomationPolicy
from .resource_use_domain import canonical_digest

Action = Literal[
    "CREATE", "REVISE", "VALIDATE", "TEST", "REVIEW", "PUBLISH", "DEPRECATE"
]


class MaintenanceScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    ontologyIds: tuple[str, ...] = Field(default=(), max_length=128)
    createPrefix: str | None = Field(default=None, min_length=4, max_length=80)
    actions: tuple[Action, ...] = Field(min_length=1, max_length=7)
    expiresAt: datetime


class MaintenancePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["ontology-maintenance-policy.v1"] = (
        "ontology-maintenance-policy.v1"
    )
    enabled: bool = False
    policyId: str
    policyVersion: str
    issuer: str
    credentialPath: Path
    workScopes: tuple[MaintenanceScope, ...] = Field(max_length=128)
    grantTTLSeconds: int = Field(default=1800, ge=60, le=3600)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def authenticate(self, grants, subject):
        return AutomationPolicy.authenticate(self, grants, subject)

    def work(self, subject, identity, action, now):
        matches = [
            s
            for s in self.workScopes
            if s.namespace == subject.scope.tenant_id
            and s.securityDomain == subject.scope.security_domain
            and s.subject == subject.principal_id
            and action in s.actions
            and (
                identity in s.ontologyIds
                or (
                    action == "CREATE"
                    and s.createPrefix
                    and identity.startswith(s.createPrefix)
                )
            )
            and s.expiresAt.tzinfo is not None
            and s.expiresAt > now
        ]
        if len(matches) != 1:
            raise AuthorityError("ONTOLOGY_MAINTENANCE_SCOPE_DENIED")
        return matches[0]


class MaintenanceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Action
    commandKey: str = Field(min_length=8, max_length=120)
    ontologyId: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    expectedVersion: int = Field(ge=0)
    baseRevision: str | None = Field(default=None, max_length=128)
    baseDigest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    revision: str | None = Field(default=None, max_length=128)
    digest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    content: OntologyContent | DocumentRulesContent | None = None
    reason: str = Field(min_length=1, max_length=500)
