from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
)
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    BrowserSession,
    CredentialId,
    GrantSource,
    SessionId,
    TrustedRequestContext,
)
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)


class MemorySessionRepository:
    def __init__(self) -> None:
        self.nonces: dict[str, datetime] = {}
        self.sessions: dict[str, tuple[str, BrowserSession]] = {}
        self.revoked: set[SessionId] = set()

    def issue_login_nonce(self, digest: str, expires_at: datetime) -> None:
        self.nonces[digest] = expires_at

    def consume_login_nonce(self, digest: str, *, now: datetime) -> bool:
        expires = self.nonces.pop(digest, None)
        return expires is not None and now < expires

    def create_session(self, session: BrowserSession, secret_digest: str) -> None:
        self.sessions[secret_digest] = (secret_digest, session)

    def touch_current_session(
        self,
        secret_digest: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
        recovery_epoch: int,
    ) -> BrowserSession | None:
        item = self.sessions.get(secret_digest)
        if item is None:
            return None
        session = item[1]
        if (
            session.session_id in self.revoked
            or session.recovery_epoch != recovery_epoch
            or now >= session.idle_expires_at
            or now >= session.absolute_expires_at
        ):
            return None
        session = replace(
            session,
            last_seen_at=now,
            idle_expires_at=min(idle_expires_at, session.absolute_expires_at),
        )
        self.sessions[secret_digest] = (secret_digest, session)
        return session

    def rotate_session(
        self,
        current_session_id: SessionId,
        replacement: BrowserSession,
        replacement_secret_digest: str,
        *,
        now: datetime,
    ) -> bool:
        if current_session_id in self.revoked:
            return False
        self.revoked.add(current_session_id)
        self.create_session(replacement, replacement_secret_digest)
        return True

    def revoke_session(self, session_id: SessionId, **_: object) -> bool:
        fresh = session_id not in self.revoked
        self.revoked.add(session_id)
        return fresh

    def revoke_credential_sessions(
        self, credential_id: CredentialId, **_: object
    ) -> int:
        matches = [
            session.session_id
            for _, session in self.sessions.values()
            if session.principal.credential_id == credential_id
            and session.session_id not in self.revoked
        ]
        self.revoked.update(matches)
        return len(matches)

    def current_credential_id(
        self, context: TrustedRequestContext, **_: object
    ) -> CredentialId | None:
        return next(
            (
                session.principal.credential_id
                for _, session in self.sessions.values()
                if session.session_id == context.session_id_or_service_credential_id
                and session.session_id not in self.revoked
            ),
            None,
        )


def build_service() -> tuple[
    BrowserSessionService, MemorySessionRepository, list[datetime]
]:
    now = [datetime(2029, 1, 1, tzinfo=UTC)]
    credential = "browser-credential-value"
    generation = StaticAuthorityGeneration(
        generation=3,
        digest="c" * 64,
        policy_version="policy-3",
        audit_source="test",
        credentials=(
            CredentialConfiguration(
                credential_id=CredentialId("credential-alice"),
                credential_sha256=hashlib.sha256(credential.encode()).hexdigest(),
                principal_id="human:alice",
                scope=AuthorityScope("tenant-a", "quality"),
                expires_at=now[0] + timedelta(days=1),
                authentication_source=GrantSource.BROWSER_BOOTSTRAP,
                grants=(),
            ),
        ),
        requestability=(),
        credential_revocation_tombstones=frozenset(),
    )
    values = iter(("nonce", "session-secret", "one", "replacement", "two"))
    repository = MemorySessionRepository()
    service = BrowserSessionService(
        repository,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            login_nonce_lifetime=timedelta(minutes=5),
            idle_lifetime=timedelta(minutes=30),
            absolute_lifetime=timedelta(hours=8),
            csrf_lifetime=timedelta(minutes=10),
        ),
        csrf_signing_key=b"c" * 32,
        recovery_epoch=7,
        clock=lambda: now[0],
        token_factory=lambda: next(values),
    )
    return service, repository, now


def test_nonce_is_single_use_and_session_secret_is_not_persisted() -> None:
    service, repository, _ = build_service()
    nonce = service.issue_login_nonce()
    secret = service.create_session(nonce, "browser-credential-value")

    assert secret.value == "session-secret"
    assert "session-secret" not in repr(repository.sessions)
    session, context = service.authenticate_session(secret.value)
    assert context.principal_id == "human:alice"
    assert session.recovery_epoch == 7
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        service.create_session(nonce, "browser-credential-value")


def test_rotation_logout_expiry_and_csrf_binding() -> None:
    service, _, now = build_service()
    nonce = service.issue_login_nonce()
    secret = service.create_session(nonce, "browser-credential-value")
    session, _ = service.authenticate_session(secret.value)
    csrf = service.issue_csrf(session)
    service.verify_csrf(csrf, session)

    now[0] += timedelta(minutes=11)
    with pytest.raises(AuthorityError, match="CSRF_VALIDATION_FAILED"):
        service.verify_csrf(csrf, session)

    replacement = service.rotate_session(secret.value)
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        service.authenticate_session(secret.value)
    rotated, _ = service.authenticate_session(replacement.value)
    with pytest.raises(AuthorityError, match="CSRF_VALIDATION_FAILED"):
        service.verify_csrf(csrf, rotated)

    service.logout(replacement.value, actor_id="human:alice")
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        service.authenticate_session(replacement.value)

    now[0] += timedelta(hours=9)
    assert now[0] > secret.expires_at
