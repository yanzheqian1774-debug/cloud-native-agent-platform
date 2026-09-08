"""Server-controlled authentication and exact resource authorization."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class GovernedAuthorizationError(ValueError):
    """Minimum-disclosure authentication or authorization failure."""


@dataclass(frozen=True, slots=True)
class GovernedPrincipal:
    principal_id: str
    tenant_id: str
    security_domain: str
    credential_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class GovernedAuthorizationDecision:
    decision_id: str
    principal_id: str
    tenant_id: str
    security_domain: str
    owner: str
    action: str
    resource: str
    expires_at: datetime
    policy_version: str
    audit_source: str


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def request_semantic(command: Any) -> dict[str, object]:
    body = command.model_dump()
    inputs = body.pop("input")
    return {**body, "inputDigest": _digest(inputs)}


def execution_start_resource(command: Any) -> str:
    return f"governed-execution:start:{_digest(request_semantic(command))}"


def skill_invoke_resource(command: Any) -> str:
    return f"skill-invocation:invoke:{_digest(request_semantic(command))}"


def execution_read_resource(run_id: str, attempt_id: str) -> str:
    return f"governed-execution:read:{run_id}:{attempt_id}"


def skill_read_resource(invocation_id: str) -> str:
    return f"skill-invocation:read:{invocation_id}"


def resource_use_read_resource(resource_use_id: str) -> str:
    return f"resource-use:read:{resource_use_id}"


def evidence_reference_resource(evidence_id: str) -> str:
    return f"evidence-reference:read:{evidence_id}"


class GovernedExecutionAuthority:
    """Verify bearer credentials and issue exact, bounded in-process decisions."""

    def __init__(self, configuration: dict[str, Any]) -> None:
        try:
            if configuration["schemaVersion"] != "governed-execution-auth.v1":
                raise ValueError
            self.policy_version = str(configuration["policyVersion"])
            self.audit_source = str(configuration["auditSource"])
            credentials = tuple(configuration["credentials"])
            if not self.policy_version or not self.audit_source or not credentials:
                raise ValueError
            self._credentials = credentials
            credential_ids: set[str] = set()
            credential_digests: set[str] = set()
            for item in credentials:
                digest = item["credentialSha256"]
                if len(digest) != 64 or any(
                    c not in "0123456789abcdef" for c in digest
                ):
                    raise ValueError
                self._expiry(item["expiresAt"])
                if not all(
                    item.get(name)
                    for name in (
                        "credentialId",
                        "principalId",
                        "tenantId",
                        "securityDomain",
                    )
                ):
                    raise ValueError
                if (
                    item["credentialId"] in credential_ids
                    or digest in credential_digests
                ):
                    raise ValueError
                credential_ids.add(item["credentialId"])
                credential_digests.add(digest)
                for grant in item.get("grants", ()):
                    if not all(
                        grant.get(name) for name in ("owner", "action", "resource")
                    ):
                        raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise GovernedAuthorizationError("GOVERNED_AUTHORITY_UNAVAILABLE") from exc

    @classmethod
    def from_file(cls, path: str) -> GovernedExecutionAuthority:
        try:
            raw = Path(path).read_text(encoding="utf-8")
            return cls(json.loads(raw))
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernedAuthorizationError("GOVERNED_AUTHORITY_UNAVAILABLE") from exc

    @staticmethod
    def _expiry(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC)

    def authenticate(self, authorization: str | None) -> GovernedPrincipal:
        if not authorization or not authorization.startswith("Bearer "):
            raise GovernedAuthorizationError("AUTHENTICATION_REQUIRED")
        token = authorization.removeprefix("Bearer ")
        if not token:
            raise GovernedAuthorizationError("AUTHENTICATION_REQUIRED")
        presented = hashlib.sha256(token.encode()).hexdigest()
        matched = None
        for item in self._credentials:
            if hmac.compare_digest(presented, item["credentialSha256"]):
                matched = item
        if matched is None:
            raise GovernedAuthorizationError("AUTHENTICATION_REQUIRED")
        expires = self._expiry(matched["expiresAt"])
        if datetime.now(UTC) >= expires:
            raise GovernedAuthorizationError("AUTHENTICATION_REQUIRED")
        return GovernedPrincipal(
            matched["principalId"],
            matched["tenantId"],
            matched["securityDomain"],
            matched["credentialId"],
            expires,
        )

    def require(
        self,
        principal: GovernedPrincipal,
        owner: str,
        action: str,
        resource: str,
    ) -> GovernedAuthorizationDecision:
        credential = next(
            (
                item
                for item in self._credentials
                if item["credentialId"] == principal.credential_id
                and item["principalId"] == principal.principal_id
                and item["tenantId"] == principal.tenant_id
                and item["securityDomain"] == principal.security_domain
            ),
            None,
        )
        grant = (
            None
            if credential is None
            else next(
                (
                    item
                    for item in credential.get("grants", ())
                    if item["owner"] == owner
                    and item["action"] == action
                    and item["resource"] == resource
                ),
                None,
            )
        )
        if grant is None or datetime.now(UTC) >= principal.expires_at:
            raise GovernedAuthorizationError("GOVERNED_EXECUTION_NOT_FOUND")
        semantic = {
            "principalId": principal.principal_id,
            "tenantId": principal.tenant_id,
            "securityDomain": principal.security_domain,
            "owner": owner,
            "action": action,
            "resource": resource,
            "expiresAt": principal.expires_at.isoformat(),
            "policyVersion": self.policy_version,
            "auditSource": self.audit_source,
        }
        return GovernedAuthorizationDecision(
            f"governed-authorization:{_digest(semantic)}",
            principal.principal_id,
            principal.tenant_id,
            principal.security_domain,
            owner,
            action,
            resource,
            principal.expires_at,
            self.policy_version,
            self.audit_source,
        )

    def allows(self, principal, owner, action, resource) -> bool:
        try:
            self.require(principal, owner, action, resource)
            return True
        except GovernedAuthorizationError:
            return False
