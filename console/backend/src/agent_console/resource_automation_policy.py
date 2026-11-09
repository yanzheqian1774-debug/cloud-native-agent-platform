"""Server-configured D11 policy, real existing credential and bounded data scope."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    ExactGrant,
    GrantSource,
    TrustedRequestContext,
)
from .browser_session_application import StaticGenerationAuthenticator
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


class WorkScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    problem: ExactReference
    sourceContentDigests: tuple[str, ...] = Field(min_length=1, max_length=32)
    expiresAt: datetime


class AdministratorWorkScope(WorkScope):
    """D12 server-created scope; never accepted by the policy configuration parser."""

    sourceContentDigests: tuple[str, ...] = ()
    allDevelopmentSources: bool = True


class AutomationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: str = "resource-preparation-policy.v1"
    policyId: str
    policyVersion: str
    issuer: str
    credentialPath: Path
    kubeconfigPath: Path
    kubeContext: str
    enabled: bool = False
    workScopes: tuple[WorkScope, ...] = Field(max_length=128)
    maxResources: int = Field(default=16, ge=1, le=32)
    grantTTLSeconds: int = Field(default=1800, ge=60, le=3600)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_absolute():
            raise AuthorityError("RESOURCE_POLICY_CONFIGURATION_INVALID")
        policy = cls.model_validate_json(path.read_text())
        if policy.schemaVersion != "resource-preparation-policy.v1" or not (
            policy.credentialPath.is_absolute() and policy.kubeconfigPath.is_absolute()
        ):
            raise AuthorityError("RESOURCE_POLICY_CONFIGURATION_INVALID")
        return policy

    @property
    def digest(self):
        # Public facts contain a digest, never credential material/path.
        return canonical_digest(self.model_dump(mode="json"))

    def authenticate(self, grants, subject):
        if not self.enabled:
            raise AuthorityError("RESOURCE_POLICY_DISABLED")
        now = grants.clock()
        verified = StaticGenerationAuthenticator(
            grants.generation, source=GrantSource.SERVICE_ONLY
        ).authenticate(self.credentialPath.read_text().strip(), now=now)
        if (
            verified.principal_id != self.issuer
            or not self.issuer.startswith("service:")
            or verified.scope != subject.scope
            or verified.principal_id == subject.principal_id
        ):
            raise AuthorityError("RESOURCE_POLICY_SCOPE_DENIED")
        context = TrustedRequestContext(
            verified.principal_id,
            verified.scope,
            verified.credential_id,
            AuthenticationSource.SERVICE_CREDENTIAL,
            verified.policy_version,
        )
        # Real current generation, credential revocation and metadata grant.
        grants._require(
            context,
            ExactGrant(
                "GRANT_ADMIN",
                "DECIDE",
                f"grant-scope:{subject.scope.tenant_id}:{subject.scope.security_domain}",
            ),
        )
        return context

    def work(self, subject, root, now):
        matches = [
            w
            for w in self.workScopes
            if w.namespace == subject.scope.tenant_id
            and w.securityDomain == subject.scope.security_domain
            and w.subject == subject.principal_id
            and w.problem == root
            and w.expiresAt.tzinfo is not None
            and w.expiresAt > now
        ]
        if len(matches) != 1:
            raise AuthorityError("RESOURCE_POLICY_WORK_SCOPE_DENIED")
        return matches[0]

    def probe_runtime(self, namespace):
        # Existing Kubernetes client, read only; no dispatch or token export.
        from kubernetes import client, config

        configuration = client.Configuration()
        config.load_kube_config(
            config_file=str(self.kubeconfigPath),
            context=self.kubeContext,
            client_configuration=configuration,
        )
        with client.ApiClient(configuration) as api:
            value = client.CoreV1Api(api).read_namespace(namespace, _request_timeout=3)
        if value.status.phase != "Active":
            raise AuthorityError("RESOURCE_RUNTIME_NOT_ACTIVE")
        return {
            "check": "NATIVE_NAMESPACE_CREDENTIAL_READ",
            "namespace": namespace,
            "status": "PASSED",
            "observedAt": datetime.now(UTC).isoformat(),
        }


def source_digest(content):
    docs = content.get("documents", [])
    if len(docs) != 1 or len(docs[0].get("chunks", [])) != 1:
        raise AuthorityError("RESOURCE_SOURCE_SNAPSHOT_REQUIRED")
    raw = docs[0]["chunks"][0]["content"]
    digest = hashlib.sha256(raw.encode()).hexdigest()
    if digest != docs[0]["contentDigest"]:
        raise AuthorityError("RESOURCE_SOURCE_CORRUPT")
    source = json.loads(raw)
    from .planning_source_change import validate_data

    validate_data(source)
    return digest
