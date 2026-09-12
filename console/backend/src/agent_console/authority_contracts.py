"""Typed contracts for browser sessions and exact-resource authority."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType, Protocol

SessionId = NewType("SessionId", str)
CredentialId = NewType("CredentialId", str)
GrantId = NewType("GrantId", str)


def require_bounded_label(value: str, *, reason_code: str) -> str:
    if (
        not value
        or len(value) > 64
        or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in value)
    ):
        raise AuthorityError(reason_code)
    return value


class AuthorityError(ValueError):
    """Minimum-disclosure failure surfaced by authority application ports."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class GrantSource(StrEnum):
    SERVICE_ONLY = "SERVICE_ONLY"
    BROWSER_BOOTSTRAP = "BROWSER_BOOTSTRAP"
    STATIC_META = "STATIC_META"
    DYNAMIC = "DYNAMIC"


class GrantRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ControlState(StrEnum):
    ACTIVATION_PENDING = "ACTIVATION_PENDING"
    RECOVERY_CLOSED = "RECOVERY_CLOSED"
    ACTIVE = "ACTIVE"


class DynamicAuthorizationState(StrEnum):
    NONE = "NONE"
    ALLOWED = "ALLOWED"
    REVOKED = "REVOKED"
    UNAVAILABLE = "UNAVAILABLE"


class AuthenticationSource(StrEnum):
    """Closed set of sources permitted to construct a trusted context."""

    BROWSER_SESSION = "BROWSER_SESSION"
    SERVICE_CREDENTIAL = "SERVICE_CREDENTIAL"


@dataclass(frozen=True, slots=True)
class AuthorityScope:
    """Tenant and security-domain boundary shared by identity and grants."""

    tenant_id: str
    security_domain: str


@dataclass(frozen=True, slots=True)
class VerifiedPrincipal:
    """Principal proven by a current bootstrap or service credential."""

    principal_id: str
    scope: AuthorityScope
    credential_id: CredentialId
    credential_expires_at: datetime
    policy_version: str


@dataclass(frozen=True, slots=True)
class TrustedRequestContext:
    """Server-constructed identity passed directly to application ports."""

    principal_id: str
    scope: AuthorityScope
    session_id_or_service_credential_id: str
    authentication_source: AuthenticationSource
    authentication_policy_version: str


@dataclass(frozen=True, slots=True)
class ExactGrant:
    """One normalized, non-wildcard owner/action/resource permission."""

    owner: str
    action: str
    exact_resource: str

    def __post_init__(self) -> None:
        values = (self.owner, self.action, self.exact_resource)
        if any(not value or value.strip() != value for value in values):
            raise AuthorityError("INVALID_GRANT_TARGET")
        if (
            len(self.owner) > 64
            or len(self.action) > 64
            or len(self.exact_resource) > 512
        ):
            raise AuthorityError("INVALID_GRANT_TARGET")
        if any(any(ord(char) < 32 for char in value) for value in values):
            raise AuthorityError("INVALID_GRANT_TARGET")
        if any(any(marker in value for marker in "*?[]{}()\\") for value in values):
            raise AuthorityError("INVALID_GRANT_TARGET")
        if self.exact_resource.endswith(":"):
            raise AuthorityError("INVALID_GRANT_TARGET")


@dataclass(frozen=True, slots=True)
class BrowserSession:
    session_id: SessionId
    principal: VerifiedPrincipal
    issued_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    recovery_epoch: int
    generation: int


@dataclass(frozen=True, slots=True)
class SessionSecret:
    """Opaque value returned once; repositories receive only its digest."""

    session_id: SessionId
    value: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class GrantRequest:
    request_id: str
    subject_principal_id: str
    scope: AuthorityScope
    members: tuple[ExactGrant, ...]
    purpose: str
    status: GrantRequestStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class GrantDecision:
    decision_id: str
    request_id: str
    issuer_principal_id: str
    issuer_meta_decision_id: str
    approved: bool
    reason_category: str
    basis_type: str
    basis_reference_digest: str
    policy_version: str
    audit_source: str
    created_at: datetime
    grants: tuple[GrantId, ...] = ()


@dataclass(frozen=True, slots=True)
class ContinuationClaim:
    """Verified owner-minted, subject-bound request opportunity."""

    nonce: str
    subject_principal_id: str
    scope: AuthorityScope
    purpose: str
    members: tuple[ExactGrant, ...]
    canonical_resource_reference: str
    owner_revision: str
    policy_generation: int
    issued_at: datetime
    expires_at: datetime


class Authenticator(Protocol):
    def authenticate(self, credential: str, *, now: datetime) -> VerifiedPrincipal: ...


class BrowserSessionRepository(Protocol):
    def issue_login_nonce(self, digest: str, expires_at: datetime) -> None: ...

    def consume_login_nonce(self, digest: str, *, now: datetime) -> bool: ...

    def create_session(self, session: BrowserSession, secret_digest: str) -> None: ...

    def touch_current_session(
        self,
        secret_digest: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
        recovery_epoch: int,
    ) -> BrowserSession | None: ...

    def rotate_session(
        self,
        current_session_id: SessionId,
        replacement: BrowserSession,
        replacement_secret_digest: str,
        *,
        now: datetime,
    ) -> bool: ...

    def revoke_session(
        self,
        session_id: SessionId,
        *,
        reason: str,
        actor_id: str,
        now: datetime,
    ) -> bool: ...

    def revoke_credential_sessions(
        self,
        credential_id: CredentialId,
        *,
        reason: str,
        actor_id: str,
        now: datetime,
    ) -> int: ...

    def current_credential_id(
        self,
        context: TrustedRequestContext,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> CredentialId | None: ...


class GrantAdministrationRepository(Protocol):
    def inspect_request(self, request_id: str) -> GrantRequest: ...

    def inspect_request_for(
        self,
        request_id: str,
        context: TrustedRequestContext,
        *,
        administrator_authorized: bool,
    ) -> GrantRequest: ...

    def inspect_grant_subject(
        self, grant_id: GrantId
    ) -> tuple[str, AuthorityScope]: ...

    def inspect_grant_for_subject(
        self, grant_id: GrantId, context: TrustedRequestContext
    ) -> tuple[str, AuthorityScope]: ...

    def store_continuation_offer(
        self,
        claim: ContinuationClaim,
        *,
        continuation_digest: str,
        issuer_actor_id: str,
        mint_key: str,
        mint_payload_digest: str,
        recovery_epoch: int,
    ) -> ContinuationClaim: ...

    def list_continuation_offers(
        self,
        context: TrustedRequestContext,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> tuple[ContinuationClaim, ...]: ...

    def submit_request(
        self,
        request: GrantRequest,
        *,
        actor_id: str,
        idempotency_key: str,
        payload_digest: str,
        target_validation: Callable[[object], bool],
        recovery_epoch: int,
        continuation_digest: str | None = None,
    ) -> GrantRequest: ...

    def decide_request(
        self,
        decision: GrantDecision,
        *,
        grants: Sequence[tuple[GrantId, ExactGrant, datetime, datetime]],
        expected_status: GrantRequestStatus,
        idempotency_key: str,
        payload_digest: str,
        recovery_epoch: int,
    ) -> GrantDecision: ...

    def revoke_grant(
        self,
        grant_id: GrantId,
        *,
        actor_id: str,
        reason: str,
        idempotency_key: str,
        payload_digest: str,
        now: datetime,
    ) -> bool: ...


class CurrentAuthorizationReader(Protocol):
    def read_linearized_authorization_states(
        self,
        context: TrustedRequestContext,
        grants: Sequence[ExactGrant],
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
        connection: object | None = None,
        configure_transaction: bool = True,
    ) -> tuple[CredentialId | None, tuple[DynamicAuthorizationState, ...]]: ...

    def has_current_grants(
        self,
        context: TrustedRequestContext,
        grants: Sequence[ExactGrant],
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
        connection: object | None = None,
        configure_transaction: bool = True,
    ) -> tuple[bool, ...]: ...

    def read_linearized_authorization_state(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> tuple[CredentialId | None, DynamicAuthorizationState]: ...

    def read_dynamic_authorization_state(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> DynamicAuthorizationState: ...

    def has_dynamic_revocation(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> bool: ...

    def has_current_grant(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> bool: ...


class ContinuationOwner(Protocol):
    def mint(self, claim: ContinuationClaim) -> str: ...

    def resolve_continuation(
        self, opaque_continuation: str, *, now: datetime
    ) -> ContinuationClaim: ...


class GrantTargetValidator(Protocol):
    """Domain-owner adapter; it reads canonical facts but never writes grants."""

    def is_known_exact_target(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool: ...

    def validate_continuation(
        self, claim: ContinuationClaim, *, connection: object | None = None
    ) -> bool: ...

    def validate_offer(
        self,
        scope: AuthorityScope,
        members: Sequence[ExactGrant],
        canonical_resource_reference: str,
        owner_revision: str,
    ) -> bool: ...
