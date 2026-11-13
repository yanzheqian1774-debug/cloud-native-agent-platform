"""Bounded test-catalog READ policy; no activation or authority writes on load."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .authority_configuration import validate_registered_grant
from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    ExactGrant,
    GrantSource,
    TrustedRequestContext,
)
from .browser_session_application import StaticGenerationAuthenticator
from .resource_use_domain import canonical_digest

READ_ACTIONS = {
    "SKILL": {"READ_RESOURCE"},
    "KNOWLEDGE": {"READ_RESOURCE"},
    "AGENT": {"READ_RESOURCE", "LIST"},
    "RUNTIME_PROFILE": {"READ_RESOURCE"},
    "WORKFLOW": {"READ", "LIST"},
    "EMPLOYEE": {"READ", "LIST"},
    "BUSINESS_CAPABILITY": {"READ", "LIST"},
    "TOOL": {"READ", "LIST"},
    "MODEL_GOVERNANCE": {"READ_MODEL"},
    "TEAM": {"READ", "LIST"},
    "BUSINESS_ONTOLOGY": {"READ", "LIST"},
}
COLLECTIONS = {
    ("AGENT", "LIST"): "agent:collection",
    ("WORKFLOW", "LIST"): "workflow:collection",
    ("EMPLOYEE", "LIST"): "employee:collection",
    ("BUSINESS_CAPABILITY", "LIST"): "business-capability:collection",
    ("TOOL", "LIST"): "tool:collection",
    ("MODEL_GOVERNANCE", "READ_MODEL"): "model:catalog",
    ("TEAM", "LIST"): "team:collection",
    ("BUSINESS_ONTOLOGY", "LIST"): "business-ontology:collection",
}


class TestReadTarget(BaseModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid", frozen=True)
    owner: str
    action: str
    resource: str = Field(min_length=1, max_length=2048)
    digest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    purpose: str = Field(min_length=1, max_length=64)

    @property
    def grant(self):
        return ExactGrant(self.owner, self.action, self.resource)

    @model_validator(mode="after")
    def read_only(self):
        validate_registered_grant(self.grant, allow_meta=False)
        if self.action not in READ_ACTIONS.get(self.owner, set()):
            raise ValueError("TEST_READ_POLICY_WRITE_FORBIDDEN")
        collection = COLLECTIONS.get((self.owner, self.action)) == self.resource
        if collection != (self.digest is None):
            raise ValueError("TEST_READ_POLICY_EXACT_DIGEST_REQUIRED")
        return self


class TestReadPolicy(BaseModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["test-resource-read-policy.v1"]
    policyId: str = Field(min_length=1, max_length=64)
    policyVersion: str = Field(min_length=1, max_length=64)
    enabled: bool = False
    tenant: str
    securityDomain: str
    subjects: tuple[str, ...] = Field(min_length=1, max_length=32)
    issuer: str
    credentialPath: Path
    expiresAt: datetime
    grantTTLSeconds: int = Field(default=3600, ge=60, le=28800)
    targets: tuple[TestReadTarget, ...] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def bounded(self):
        if (
            not self.credentialPath.is_absolute()
            or not self.issuer.startswith("service:")
            or self.issuer in self.subjects
            or any(not s.startswith("human:") for s in self.subjects)
            or len(set(self.subjects)) != len(self.subjects)
            or self.expiresAt.tzinfo is None
            or self.expiresAt.utcoffset() != UTC.utcoffset(None)
            or len({t.grant for t in self.targets}) != len(self.targets)
        ):
            raise ValueError("TEST_READ_POLICY_CONFIGURATION_INVALID")
        return self

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_absolute():
            raise AuthorityError("TEST_READ_POLICY_CONFIGURATION_INVALID")
        return cls.model_validate_json(path.read_text())

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def authenticate(self, grants, subject):
        now = grants.clock()
        if not self.enabled:
            raise AuthorityError("TEST_READ_POLICY_DISABLED")
        if (
            subject.authentication_source != AuthenticationSource.BROWSER_SESSION
            or subject.principal_id not in self.subjects
            or subject.scope.tenant_id != self.tenant
            or subject.scope.security_domain != self.securityDomain
            or now >= self.expiresAt
        ):
            raise AuthorityError("TEST_READ_POLICY_SCOPE_DENIED")
        verified = StaticGenerationAuthenticator(
            grants.generation, source=GrantSource.SERVICE_ONLY
        ).authenticate(self.credentialPath.read_text().strip(), now=now)
        if verified.principal_id != self.issuer or verified.scope != subject.scope:
            raise AuthorityError("TEST_READ_POLICY_SCOPE_DENIED")
        issuer = TrustedRequestContext(
            verified.principal_id,
            verified.scope,
            verified.credential_id,
            AuthenticationSource.SERVICE_CREDENTIAL,
            verified.policy_version,
        )
        grants._require(
            issuer,
            ExactGrant(
                "GRANT_ADMIN",
                "DECIDE",
                f"grant-scope:{self.tenant}:{self.securityDomain}",
            ),
        )
        # Never authorize merely because the manifest contains the target.
        for target in self.targets:
            grants._validate_requestable(target.purpose, (target.grant,))
        return issuer, min(self.expiresAt, verified.credential_expires_at)
