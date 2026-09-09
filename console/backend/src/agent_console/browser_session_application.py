"""Browser Session Authority application service.

This module defines no HTTP routes and performs no bootstrap side effects.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from agent_console.authority_configuration import StaticAuthorityGeneration
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    BrowserSession,
    BrowserSessionRepository,
    CredentialId,
    GrantSource,
    SessionId,
    SessionSecret,
    TrustedRequestContext,
    VerifiedPrincipal,
    require_bounded_label,
)


@dataclass(frozen=True, slots=True)
class BrowserSessionPolicy:
    login_nonce_lifetime: timedelta
    idle_lifetime: timedelta
    absolute_lifetime: timedelta
    csrf_lifetime: timedelta

    def __post_init__(self) -> None:
        lifetimes = (
            self.login_nonce_lifetime,
            self.idle_lifetime,
            self.absolute_lifetime,
            self.csrf_lifetime,
        )
        if any(value <= timedelta(0) for value in lifetimes):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if self.idle_lifetime > self.absolute_lifetime:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        if self.csrf_lifetime > timedelta(minutes=10):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")


class StaticGenerationAuthenticator:
    """Constant-time verifier over the active immutable generation."""

    def __init__(
        self,
        generation: StaticAuthorityGeneration | Callable[[], StaticAuthorityGeneration],
        *,
        source: GrantSource,
    ) -> None:
        if source not in {
            GrantSource.BROWSER_BOOTSTRAP,
            GrantSource.SERVICE_ONLY,
        }:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        self._generation_provider = (
            generation if callable(generation) else lambda: generation
        )
        self.source = source

    @property
    def generation(self) -> StaticAuthorityGeneration:
        return self._generation_provider()

    def authenticate(self, credential: str, *, now: datetime) -> VerifiedPrincipal:
        if not credential:
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        presented = hashlib.sha256(credential.encode()).hexdigest()
        match = None
        for item in self.generation.credentials:
            if hmac.compare_digest(presented, item.credential_sha256):
                match = item
        if (
            match is None
            or match.authentication_source is not self.source
            or match.credential_id in self.generation.credential_revocation_tombstones
            or now >= match.expires_at
        ):
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return VerifiedPrincipal(
            principal_id=match.principal_id,
            scope=match.scope,
            credential_id=match.credential_id,
            credential_expires_at=match.expires_at,
            policy_version=self.generation.policy_version,
        )


class BrowserSessionService:
    def __init__(
        self,
        repository: BrowserSessionRepository,
        authenticator: StaticGenerationAuthenticator,
        policy: BrowserSessionPolicy,
        *,
        csrf_signing_key: bytes,
        recovery_epoch: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        if len(csrf_signing_key) < 32 or recovery_epoch < 1:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        self.repository = repository
        self.authenticator = authenticator
        self.policy = policy
        self.csrf_signing_key = csrf_signing_key
        self.recovery_epoch = recovery_epoch
        self.clock = clock
        self.token_factory = token_factory

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def issue_login_nonce(self) -> str:
        now = self.clock()
        nonce = self.token_factory()
        self.repository.issue_login_nonce(
            self._digest(nonce), now + self.policy.login_nonce_lifetime
        )
        return nonce

    def create_session(self, login_nonce: str, credential: str) -> SessionSecret:
        now = self.clock()
        if not self.repository.consume_login_nonce(self._digest(login_nonce), now=now):
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        principal = self.authenticator.authenticate(credential, now=now)
        value = self.token_factory()
        session_id = SessionId(f"session-{self.token_factory()}")
        expires_at = min(
            now + self.policy.absolute_lifetime,
            principal.credential_expires_at,
        )
        session = BrowserSession(
            session_id=session_id,
            principal=principal,
            issued_at=now,
            last_seen_at=now,
            idle_expires_at=min(now + self.policy.idle_lifetime, expires_at),
            absolute_expires_at=expires_at,
            recovery_epoch=self.recovery_epoch,
            generation=self.authenticator.generation.generation,
        )
        self.repository.create_session(session, self._digest(value))
        return SessionSecret(session_id, value, expires_at)

    def authenticate_session(
        self, value: str
    ) -> tuple[BrowserSession, TrustedRequestContext]:
        now = self.clock()
        session = self.repository.touch_current_session(
            self._digest(value),
            now=now,
            idle_expires_at=now + self.policy.idle_lifetime,
            recovery_epoch=self.recovery_epoch,
        )
        if session is None or not self._credential_is_current(session, now=now):
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return session, TrustedRequestContext(
            principal_id=session.principal.principal_id,
            scope=session.principal.scope,
            session_id_or_service_credential_id=session.session_id,
            authentication_source=AuthenticationSource.BROWSER_SESSION,
            authentication_policy_version=session.principal.policy_version,
        )

    def _credential_is_current(self, session: BrowserSession, *, now: datetime) -> bool:
        current = self.authenticator.generation.credential_by_id(
            session.principal.credential_id
        )
        return (
            current is not None
            and current.authentication_source is GrantSource.BROWSER_BOOTSTRAP
            and current.principal_id == session.principal.principal_id
            and current.scope == session.principal.scope
            and session.principal.credential_id
            not in self.authenticator.generation.credential_revocation_tombstones
            and now < session.principal.credential_expires_at
            and now < current.expires_at
            and session.generation <= self.authenticator.generation.generation
        )

    def rotate_session(self, current_value: str) -> SessionSecret:
        current, _ = self.authenticate_session(current_value)
        now = self.clock()
        replacement_value = self.token_factory()
        replacement = BrowserSession(
            session_id=SessionId(f"session-{self.token_factory()}"),
            principal=current.principal,
            issued_at=now,
            last_seen_at=now,
            idle_expires_at=min(
                now + self.policy.idle_lifetime, current.absolute_expires_at
            ),
            absolute_expires_at=current.absolute_expires_at,
            recovery_epoch=current.recovery_epoch,
            generation=self.authenticator.generation.generation,
        )
        if not self.repository.rotate_session(
            current.session_id,
            replacement,
            self._digest(replacement_value),
            now=now,
        ):
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return SessionSecret(
            replacement.session_id,
            replacement_value,
            replacement.absolute_expires_at,
        )

    def logout(self, value: str, *, actor_id: str) -> None:
        session, _ = self.authenticate_session(value)
        self.repository.revoke_session(
            session.session_id,
            reason="LOGOUT",
            actor_id=actor_id,
            now=self.clock(),
        )

    def operator_revoke_session(
        self,
        session_id: SessionId,
        *,
        actor_id: str,
        reason_category: str,
    ) -> bool:
        require_bounded_label(reason_category, reason_code="INVALID_SESSION_REVOCATION")
        return self.repository.revoke_session(
            session_id,
            reason=reason_category,
            actor_id=actor_id,
            now=self.clock(),
        )

    def operator_revoke_credential(
        self,
        credential_id: CredentialId,
        *,
        actor_id: str,
        reason_category: str,
    ) -> int:
        require_bounded_label(reason_category, reason_code="INVALID_SESSION_REVOCATION")
        return self.repository.revoke_credential_sessions(
            credential_id,
            reason=reason_category,
            actor_id=actor_id,
            now=self.clock(),
        )

    def issue_csrf(self, session: BrowserSession) -> str:
        now = self.clock()
        expires_at = min(
            now + self.policy.csrf_lifetime,
            session.idle_expires_at,
            session.absolute_expires_at,
        )
        payload = json.dumps(
            {
                "sessionId": session.session_id,
                "generation": session.generation,
                "expiresAt": expires_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
        signature = hmac.new(
            self.csrf_signing_key, encoded.encode(), hashlib.sha256
        ).hexdigest()
        return f"{encoded}.{signature}"

    def verify_csrf(self, token: str, session: BrowserSession) -> None:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(
                self.csrf_signing_key, encoded.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
            expires_at = datetime.fromisoformat(payload["expiresAt"])
            valid = (
                payload["sessionId"] == session.session_id
                and payload["generation"] == session.generation
                and expires_at.tzinfo is not None
                and self.clock() < expires_at.astimezone(UTC)
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AuthorityError("CSRF_VALIDATION_FAILED") from exc
        if not valid:
            raise AuthorityError("CSRF_VALIDATION_FAILED")
