"""Separate fail-closed authorization for bounded Knowledge retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agent_console.knowledge_pack import canonical_digest, identifier, utc


class KnowledgeAuthorizationError(ValueError):
    """Nondisclosing authorization failure."""


class AuthorizationAction(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REVOKE = "REVOKE"


DENIAL_CODE = "KNOWLEDGE_ACCESS_DENIED"


def _deny() -> KnowledgeAuthorizationError:
    return KnowledgeAuthorizationError(DENIAL_CODE)


@dataclass(frozen=True, slots=True)
class KnowledgeAuthorizationDecision:
    decision_id: str
    replay_identity: str
    action: AuthorizationAction
    tenant_id: str
    security_domain: str
    purpose: str
    knowledge_pack_id: str
    knowledge_pack_version: str
    knowledge_pack_digest: str
    document_id: str
    document_version: str
    document_digest: str
    policy_version: str
    effective_at: datetime
    expires_at: datetime
    authority: str
    decision_digest: str

    @classmethod
    def create(cls, **values: object) -> KnowledgeAuthorizationDecision:
        try:
            action = values.get("action")
            if not isinstance(action, AuthorizationAction):
                raise _deny()
            effective = utc(values.get("effective_at"), DENIAL_CODE)
            expires = utc(values.get("expires_at"), DENIAL_CODE)
            if expires <= effective:
                raise _deny()
            normalized = {
                key: identifier(values.get(key), DENIAL_CODE)
                for key in (
                    "decision_id",
                    "replay_identity",
                    "tenant_id",
                    "security_domain",
                    "purpose",
                    "knowledge_pack_id",
                    "knowledge_pack_version",
                    "document_id",
                    "document_version",
                    "policy_version",
                    "authority",
                )
            }
            for key in ("knowledge_pack_digest", "document_digest"):
                value = values.get(key)
                if (
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(char not in "0123456789abcdef" for char in value)
                ):
                    raise _deny()
                normalized[key] = value
            semantic = {
                **normalized,
                "action": action,
                "effectiveAt": effective,
                "expiresAt": expires,
            }
            return cls(
                **normalized,
                action=action,
                effective_at=effective,
                expires_at=expires,
                decision_digest=canonical_digest(
                    semantic, domain="knowledge-authorization.v1"
                ),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, KnowledgeAuthorizationError):
                raise
            raise _deny() from exc


@dataclass(frozen=True, slots=True)
class AuthorizationExpectation:
    tenant_id: str
    security_domain: str
    purpose: str
    knowledge_pack_id: str
    knowledge_pack_version: str
    knowledge_pack_digest: str
    document_id: str
    document_version: str
    document_digest: str
    policy_version: str


def require_current_allow(
    decision: object,
    expectation: AuthorizationExpectation,
    *,
    evaluation_time: datetime,
) -> KnowledgeAuthorizationDecision:
    """Validate entirely from caller-supplied authority before source inspection."""
    try:
        now = utc(evaluation_time, DENIAL_CODE)
        if not isinstance(decision, KnowledgeAuthorizationDecision):
            raise _deny()
        rebuilt = KnowledgeAuthorizationDecision.create(
            **{
                name: getattr(decision, name)
                for name in (
                    "decision_id",
                    "replay_identity",
                    "action",
                    "tenant_id",
                    "security_domain",
                    "purpose",
                    "knowledge_pack_id",
                    "knowledge_pack_version",
                    "knowledge_pack_digest",
                    "document_id",
                    "document_version",
                    "document_digest",
                    "policy_version",
                    "effective_at",
                    "expires_at",
                    "authority",
                )
            }
        )
        if rebuilt != decision or decision.action is not AuthorizationAction.ALLOW:
            raise _deny()
        if not decision.effective_at <= now < decision.expires_at:
            raise _deny()
        for name in expectation.__dataclass_fields__:
            if getattr(decision, name) != getattr(expectation, name):
                raise _deny()
        return decision
    except (AttributeError, TypeError, ValueError) as exc:
        if isinstance(exc, KnowledgeAuthorizationError):
            raise
        raise _deny() from exc
