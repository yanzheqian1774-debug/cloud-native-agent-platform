from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event

import psycopg
import pytest
from agent_console.authority_configuration import (
    AuthorityRuntimeConfiguration,
    CredentialConfiguration,
    RequestabilityRule,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    BrowserSession,
    ContinuationClaim,
    CredentialId,
    CurrentExactGrantDecision,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequest,
    GrantRequestStatus,
    GrantSource,
    SessionId,
    TrustedRequestContext,
    VerifiedPrincipal,
)
from agent_console.authority_foundation import (
    SignedContinuationOwner,
    build_authority_foundation,
    initialize_authority_generation,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.grant_administration_application import (
    ContinuationOfferCommand,
    GenerationAuthorizationReader,
    GrantAdministrationService,
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.workbench_bff import PREFIX, WorkbenchBffPolicy, create_workbench_bff
from fastapi.testclient import TestClient

DATABASE_URL = os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="302 exclusive real PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION = MIGRATIONS / "0018_browser_session_grant_authority.sql"


@pytest.fixture
def isolated_database() -> str:
    original = DATABASE_URL or ""
    database_name = f"impl302_{uuid.uuid4().hex}"
    admin = psycopg.connect(original, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = original.rsplit("/", 1)[0] + f"/{database_name}"
    try:
        yield database_url
    finally:
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


@pytest.fixture
def repository(isolated_database: str) -> PostgresAuthorityRepository:
    value = PostgresAuthorityRepository(isolated_database, migration_path=MIGRATION)
    value.migrate()
    try:
        yield value
    finally:
        value.close()


def principal(now: datetime) -> VerifiedPrincipal:
    return VerifiedPrincipal(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        CredentialId("credential-alice"),
        now + timedelta(days=1),
        "policy-1",
    )


def session(now: datetime, suffix: str = "one") -> BrowserSession:
    return BrowserSession(
        SessionId(f"session-{suffix}"),
        principal(now),
        now,
        now,
        now + timedelta(minutes=30),
        now + timedelta(hours=8),
        1,
        1,
    )


class KnownTestTargets:
    def is_known_exact_target(self, *_: object, **__: object) -> bool:
        return True

    def validate_continuation(self, _: ContinuationClaim, **__: object) -> bool:
        return True

    def validate_offer(self, *_: object) -> bool:
        return True


def test_migration_ledgers_and_checksum_are_consistent(
    repository: PostgresAuthorityRepository,
) -> None:
    repository.migrate()
    with repository.pool.connection() as connection:
        for schema in ("browser_identity", "authorization_admin"):
            row = connection.execute(
                f"SELECT version,checksum,adapter FROM {schema}.schema_migrations"
            ).fetchone()
            assert row == {
                "version": 18,
                "checksum": repository.migration_checksum,
                "adapter": "browser-session-grant-authority-postgresql-v18",
            }


def test_upgrades_existing_0017_baseline(isolated_database: str) -> None:
    with psycopg.connect(isolated_database) as connection, connection.transaction():
        for version in range(1, 18):
            path = next(MIGRATIONS.glob(f"{version:04d}_*.sql"))
            connection.execute(path.read_text())
    repository = PostgresAuthorityRepository(
        isolated_database, migration_path=MIGRATION
    )
    try:
        repository.migrate()
        assert repository.active_generation() is None
    finally:
        repository.close()


def test_failed_migration_leaves_no_partial_authority_schema(
    isolated_database: str, tmp_path: Path
) -> None:
    invalid = tmp_path / "0018_invalid_authority.sql"
    invalid.write_text(
        MIGRATION.read_text() + "\nSELECT missing_migration_function();\n"
    )
    repository = PostgresAuthorityRepository(isolated_database, migration_path=invalid)
    try:
        with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
            repository.migrate()
    finally:
        repository.close()
    with psycopg.connect(isolated_database) as connection:
        assert (
            connection.execute(
                "SELECT to_regnamespace('browser_identity') AS name"
            ).fetchone()[0]
            is None
        )
        assert (
            connection.execute(
                "SELECT to_regnamespace('authorization_admin') AS name"
            ).fetchone()[0]
            is None
        )


def test_explicit_initialization_and_composition_are_fail_closed(
    isolated_database: str, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    raw_credential = "exclusive-browser-bootstrap-credential"
    document = {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "policy-1",
        "auditSource": "impl-302-test",
        "credentials": [
            {
                "credentialId": "credential-alice",
                "credentialSha256": hashlib.sha256(raw_credential.encode()).hexdigest(),
                "principalId": "human:alice",
                "tenantId": "tenant-a",
                "securityDomain": "quality",
                "expiresAt": (now + timedelta(days=1)).isoformat(),
                "authenticationSource": "BROWSER_BOOTSTRAP",
                "grants": [],
            }
        ],
        "requestability": [],
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
    }
    generation_path = tmp_path / "generation-1.json"
    generation_path.write_text(json.dumps(document, sort_keys=True))
    digest = hashlib.sha256(generation_path.read_bytes()).hexdigest()
    csrf_path = tmp_path / "csrf.key"
    continuation_path = tmp_path / "continuation.key"
    csrf_path.write_bytes(b"c" * 32)
    continuation_path.write_bytes(b"o" * 32)
    runtime = AuthorityRuntimeConfiguration.from_mapping(
        {
            "schemaVersion": "authority-foundation-runtime.v1",
            "databaseUrl": isolated_database,
            "migrationPath": str(MIGRATION),
            "generationPath": str(generation_path),
            "generationDigest": digest,
            "csrfSigningKeyPath": str(csrf_path),
            "continuationSigningKeyPath": str(continuation_path),
            "recoveryControlPath": str(tmp_path / "authority-control.json"),
            "databaseFingerprint": "impl-302-database",
            "operatorId": "operator:test",
        }
    )
    policy = BrowserSessionPolicy(
        timedelta(minutes=5),
        timedelta(minutes=30),
        timedelta(hours=8),
        timedelta(minutes=10),
    )
    with pytest.raises(AuthorityError, match="AUTHORITY_RECOVERY_REQUIRED"):
        build_authority_foundation(runtime, policy)
    initialize_authority_generation(runtime, control_epoch=1, recovery_epoch=1, now=now)
    foundation = build_authority_foundation(runtime, policy)
    try:
        nonce = foundation.sessions.issue_login_nonce()
        session_secret = foundation.sessions.create_session(nonce, raw_credential)
        _, context = foundation.sessions.authenticate_session(session_secret.value)
        assert context.principal_id == "human:alice"
    finally:
        foundation.close()


def test_nonce_session_rotation_and_credential_revoke_are_atomic(
    repository: PostgresAuthorityRepository,
    isolated_database: str,
) -> None:
    now = datetime.now(UTC)
    nonce = "login-nonce-sensitive"
    nonce_digest = hashlib.sha256(nonce.encode()).hexdigest()
    repository.issue_login_nonce(nonce_digest, now + timedelta(minutes=5))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda _: repository.consume_login_nonce(nonce_digest, now=now),
                range(2),
            )
        )
    assert sorted(results) == [False, True]

    current = session(now)
    raw_secret = "session-secret-sensitive"
    repository.create_session(current, hashlib.sha256(raw_secret.encode()).hexdigest())
    restarted = PostgresAuthorityRepository(isolated_database, migration_path=MIGRATION)
    try:
        restarted.migrate()
        assert (
            restarted.touch_current_session(
                hashlib.sha256(raw_secret.encode()).hexdigest(),
                now=now + timedelta(seconds=30),
                idle_expires_at=now + timedelta(minutes=30),
                recovery_epoch=1,
            )
            is not None
        )
    finally:
        restarted.close()
    touched = repository.touch_current_session(
        hashlib.sha256(raw_secret.encode()).hexdigest(),
        now=now + timedelta(minutes=1),
        idle_expires_at=now + timedelta(minutes=31),
        recovery_epoch=1,
    )
    assert touched is not None and touched.last_seen_at == now + timedelta(minutes=1)

    replacement = session(now + timedelta(minutes=1), "two")
    replacement = BrowserSession(
        replacement.session_id,
        replacement.principal,
        replacement.issued_at,
        replacement.last_seen_at,
        replacement.idle_expires_at,
        current.absolute_expires_at,
        replacement.recovery_epoch,
        replacement.generation,
    )
    assert repository.rotate_session(
        current.session_id,
        replacement,
        hashlib.sha256(b"replacement-secret").hexdigest(),
        now=now + timedelta(minutes=1),
    )
    assert (
        repository.touch_current_session(
            hashlib.sha256(raw_secret.encode()).hexdigest(),
            now=now + timedelta(minutes=2),
            idle_expires_at=now + timedelta(minutes=32),
            recovery_epoch=1,
        )
        is None
    )
    assert (
        repository.revoke_credential_sessions(
            CredentialId("credential-alice"),
            reason="CREDENTIAL_REVOKED",
            actor_id="operator:test",
            now=now + timedelta(minutes=2),
        )
        == 1
    )
    with repository.pool.connection() as connection:
        dumped = " ".join(
            str(row)
            for table in ("login_nonces", "sessions")
            for row in connection.execute(
                f"SELECT * FROM browser_identity.{table}"
            ).fetchall()
        )
    assert nonce not in dumped
    assert raw_secret not in dumped


def test_grant_bundle_self_approval_idempotency_and_revocation(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1")
    request = GrantRequest(
        "request-1",
        "human:alice",
        scope,
        (member,),
        "CONTINUE_PROBLEM_PLAN",
        GrantRequestStatus.PENDING,
        now,
    )
    repository.activate_generation(
        1,
        "a" * 64,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    submitted = repository.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="request-key",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    replay = repository.submit_request(
        GrantRequest(
            "request-lost-response-retry",
            "human:alice",
            scope,
            (member,),
            request.purpose,
            GrantRequestStatus.PENDING,
            now,
        ),
        actor_id="human:alice",
        idempotency_key="request-key",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    assert replay.request_id == submitted.request_id
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        repository.submit_request(
            request,
            actor_id="human:alice",
            idempotency_key="request-key",
            payload_digest="2" * 64,
            target_validation=lambda _: True,
            recovery_epoch=1,
        )

    def submit_competing(value: int) -> str:
        try:
            return repository.submit_request(
                GrantRequest(
                    f"concurrent-request-{value}",
                    "human:alice",
                    scope,
                    (member,),
                    request.purpose,
                    GrantRequestStatus.PENDING,
                    now,
                ),
                actor_id="human:alice",
                idempotency_key="concurrent-request-key",
                payload_digest=str(value) * 64,
                target_validation=lambda _: True,
                recovery_epoch=1,
            ).request_id
        except AuthorityError as exc:
            return exc.reason_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        competing = tuple(executor.map(submit_competing, (7, 8)))
    assert "IDEMPOTENCY_PAYLOAD_MISMATCH" in competing
    assert sum(value.startswith("concurrent-request-") for value in competing) == 1

    self_decision = GrantDecision(
        "decision-self",
        request.request_id,
        "human:alice",
        "meta-self",
        True,
        "ASSIGNED_DUTY",
        "TICKET",
        "3" * 64,
        "policy-1",
        "test",
        now,
    )
    with pytest.raises(AuthorityError, match="GRANT_SELF_APPROVAL_PROHIBITED"):
        repository.decide_request(
            self_decision,
            grants=((GrantId("grant-self"), member, now, now + timedelta(hours=1)),),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="self-key",
            payload_digest="4" * 64,
            recovery_epoch=1,
        )
    with repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS count FROM authorization_admin.grant_decisions"
            ).fetchone()["count"]
            == 0
        )
        assert (
            repository.inspect_request(request.request_id).status
            is GrantRequestStatus.PENDING
        )

    decision = GrantDecision(
        "decision-1",
        request.request_id,
        "human:admin",
        "meta-admin",
        True,
        "ASSIGNED_DUTY",
        "TICKET",
        "3" * 64,
        "policy-1",
        "test",
        now,
    )
    result = repository.decide_request(
        decision,
        grants=((GrantId("grant-1"), member, now, now + timedelta(hours=1)),),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="decision-key",
        payload_digest="5" * 64,
        recovery_epoch=1,
    )
    assert result.grants == (GrantId("grant-1"),)
    context = TrustedRequestContext(
        "human:alice",
        scope,
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    assert repository.has_current_grant(
        context, member, now=now, generation=1, recovery_epoch=1
    )
    foreign_scope = TrustedRequestContext(
        "human:alice",
        AuthorityScope("tenant-b", "quality"),
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    assert not repository.has_current_grant(
        foreign_scope, member, now=now, generation=1, recovery_epoch=1
    )
    foreign_principal = TrustedRequestContext(
        "human:bob",
        scope,
        "credential-bob",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    assert not repository.has_current_grant(
        foreign_principal, member, now=now, generation=1, recovery_epoch=1
    )
    assert repository.revoke_grant(
        GrantId("grant-1"),
        actor_id="human:admin",
        reason="DUTY_ENDED",
        idempotency_key="revoke-key",
        payload_digest="6" * 64,
        now=now,
    )
    assert not repository.has_current_grant(
        context, member, now=now, generation=1, recovery_epoch=1
    )


def test_complete_exact_decision_uses_caller_transaction_and_tracks_revocation(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:exact")
    static_member = ExactGrant(
        "BUSINESS_PROBLEM", "READ", "business-problem:static-only"
    )
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "policy-current",
        "test",
        (
            CredentialConfiguration(
                CredentialId("credential-alice"),
                "7" * 64,
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.SERVICE_ONLY,
                (StaticGrant(static_member, GrantSource.SERVICE_ONLY),),
            ),
        ),
        (),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    request = GrantRequest(
        "exact-request",
        "human:alice",
        scope,
        (member,),
        "CONTINUE_PROBLEM_PLAN",
        GrantRequestStatus.PENDING,
        now,
    )
    repository.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="exact-request",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    issued_at = now + timedelta(seconds=1)
    expires_at = now + timedelta(hours=1)
    repository.decide_request(
        GrantDecision(
            "exact-decision",
            request.request_id,
            "human:admin",
            "meta-admin",
            True,
            "ASSIGNED_DUTY",
            "TICKET",
            "2" * 64,
            "policy-issued",
            "test",
            issued_at,
        ),
        grants=((GrantId("exact-grant"), member, issued_at, expires_at),),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="exact-decision",
        payload_digest="3" * 64,
        recovery_epoch=1,
    )
    context = TrustedRequestContext(
        "human:alice",
        scope,
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-current",
    )
    reader = GenerationAuthorizationReader(
        generation, repository, repository, recovery_epoch=1
    )
    effective_at = issued_at + timedelta(seconds=1)
    assert reader.has_current_grant(
        context,
        static_member,
        now=effective_at,
        generation=1,
        recovery_epoch=1,
    )
    assert reader.authorize_current(context, static_member, now=effective_at) is None
    assert reader.authorize_current(context, member, now=expires_at) is None
    revoke_started = Event()
    revoke_finished = Event()

    def revoke() -> bool:
        revoke_started.set()
        result = repository.revoke_grant(
            GrantId("exact-grant"),
            actor_id="human:admin",
            reason="DUTY_ENDED",
            idempotency_key="exact-revoke",
            payload_digest="4" * 64,
            now=effective_at + timedelta(seconds=1),
        )
        revoke_finished.set()
        return result

    with ThreadPoolExecutor(max_workers=1) as executor:
        with repository.connection_scope() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            bound = reader.bind_current_exact_decisions(connection, generation=1)
            current = bound.authorize_current(context, member, now=effective_at)
            assert current == CurrentExactGrantDecision(
                "exact-decision",
                context,
                member,
                1,
                "policy-issued",
                issued_at,
                expires_at,
            )
            future = executor.submit(revoke)
            assert revoke_started.wait(timeout=10)
            assert not revoke_finished.wait(timeout=0.2)
        assert future.result(timeout=10)

    assert reader.authorize_current(context, member, now=effective_at) is None


def test_application_continuation_scope_self_decision_and_dynamic_read(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-2")
    admin_meta = ExactGrant(
        "CONTINUATION_ASSIGNMENT", "ASSIGN", "continuation-scope:tenant-a:quality"
    )
    decide_meta = ExactGrant("GRANT_ADMIN", "DECIDE", "grant-scope:tenant-a:quality")
    inspect_meta = ExactGrant("GRANT_ADMIN", "INSPECT", "grant-scope:tenant-a:quality")
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "policy-1",
        "test",
        (
            CredentialConfiguration(
                CredentialId("credential-admin"),
                "7" * 64,
                "human:admin",
                scope,
                now + timedelta(days=1),
                GrantSource.SERVICE_ONLY,
                (
                    StaticGrant(admin_meta, GrantSource.STATIC_META),
                    StaticGrant(decide_meta, GrantSource.STATIC_META),
                    StaticGrant(inspect_meta, GrantSource.STATIC_META),
                ),
            ),
            CredentialConfiguration(
                CredentialId("credential-alice"),
                "8" * 64,
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.SERVICE_ONLY,
                (StaticGrant(decide_meta, GrantSource.STATIC_META),),
            ),
        ),
        (
            RequestabilityRule(
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:",
                "CONTINUE_PROBLEM_PLAN",
            ),
        ),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    reader = GenerationAuthorizationReader(
        generation, repository, repository, recovery_epoch=1
    )
    codec = SignedContinuationOwner(b"q" * 32)
    identities = (f"identity-{number}" for number in range(20))
    service = GrantAdministrationService(
        repository,
        reader,
        generation,
        continuation_owner=codec,
        target_validator=KnownTestTargets(),
        recovery_epoch=1,
        clock=lambda: now,
        identity_factory=lambda _: next(identities),
    )
    admin = TrustedRequestContext(
        "human:admin",
        scope,
        "credential-admin",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    alice = TrustedRequestContext(
        "human:alice",
        scope,
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    with pytest.raises(AuthorityError, match="DYNAMIC_META_GRANT_PROHIBITED"):
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (decide_meta,), "dynamic-meta-request"
            ),
        )
    opaque = service.assign_offer(
        admin,
        ContinuationOfferCommand(
            "human:alice",
            "CONTINUE_PROBLEM_PLAN",
            (member,),
            "problem-2:revision-1",
            "revision-1",
            now + timedelta(minutes=10),
            "assignment-command-1",
        ),
    )
    with repository.pool.connection() as connection:
        stored_offer = connection.execute(
            "SELECT continuation_digest FROM authorization_admin.continuation_offers"
        ).fetchone()
    assert (
        stored_offer["continuation_digest"]
        == hashlib.sha256(opaque.encode()).hexdigest()
    )
    assert opaque not in str(stored_offer)
    inbox_reference = f"continuation-ref.{stored_offer['continuation_digest']}"
    for claim, digest, mint_key in (
        (
            ContinuationClaim(
                "expired-offer",
                "human:alice",
                scope,
                "CONTINUE_PROBLEM_PLAN",
                (member,),
                "problem-expired:revision-1",
                "revision-1",
                1,
                now - timedelta(minutes=10),
                now - timedelta(seconds=1),
            ),
            "a" * 64,
            "expired-offer-key",
        ),
        (
            ContinuationClaim(
                "future-offer",
                "human:alice",
                scope,
                "CONTINUE_PROBLEM_PLAN",
                (member,),
                "problem-future:revision-1",
                "revision-1",
                1,
                now + timedelta(seconds=1),
                now + timedelta(minutes=5),
            ),
            "b" * 64,
            "future-offer-key",
        ),
        (
            ContinuationClaim(
                "old-generation-offer",
                "human:alice",
                scope,
                "CONTINUE_PROBLEM_PLAN",
                (member,),
                "problem-old-generation:revision-1",
                "revision-1",
                2,
                now,
                now + timedelta(minutes=5),
            ),
            "c" * 64,
            "old-generation-offer-key",
        ),
    ):
        repository.store_continuation_offer(
            claim,
            continuation_digest=digest,
            issuer_actor_id="human:admin",
            mint_key=mint_key,
            mint_payload_digest=digest,
            recovery_epoch=1,
        )
    assert service.continuation_inbox(alice) == (inbox_reference,)
    available = service.continuation_inbox_details(alice)
    assert len(available) == 1
    assert available[0].continuation_id == inbox_reference
    assert available[0].purpose == "CONTINUE_PROBLEM_PLAN"
    assert available[0].requestable_actions == ("READ",)
    assert "problem-2" not in repr(available[0])
    expired = codec.mint(
        ContinuationClaim(
            "expired-submit",
            "human:alice",
            scope,
            "CONTINUE_PROBLEM_PLAN",
            (member,),
            "problem-expired:revision-1",
            "revision-1",
            1,
            now - timedelta(minutes=5),
            now - timedelta(seconds=1),
        )
    )
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (), "expired-request-command", expired
            ),
        )
    old_generation = codec.mint(
        ContinuationClaim(
            "old-generation-submit",
            "human:alice",
            scope,
            "CONTINUE_PROBLEM_PLAN",
            (member,),
            "problem-old-generation:revision-1",
            "revision-1",
            2,
            now,
            now + timedelta(minutes=5),
        )
    )
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN",
                (),
                "old-generation-request-command",
                old_generation,
            ),
        )
    bob = TrustedRequestContext(
        "human:bob",
        scope,
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    foreign_scope = TrustedRequestContext(
        "human:alice",
        AuthorityScope("tenant-b", "quality"),
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        service.submit_request(
            bob,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (), "request-command-bob", opaque
            ),
        )
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        service.submit_request(
            foreign_scope,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (), "request-command-foreign", opaque
            ),
        )
    request = service.submit_request(
        alice,
        GrantRequestCommand(
            "CONTINUE_PROBLEM_PLAN", (), "request-command-1", inbox_reference
        ),
    )
    assert request.aggregate_version == 1
    assert service.inspect_request(alice, request.request_id).aggregate_version == 1
    assert (
        service.inspect_request(admin, request.request_id).request_id
        == request.request_id
    )
    assert service.continuation_inbox(alice) == ()
    assert (
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (), "request-command-1", opaque
            ),
        ).request_id
        == request.request_id
    )
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (), "request-command-2", opaque
            ),
        )
    direct = service.submit_request(
        alice,
        GrantRequestCommand(
            "CONTINUE_PROBLEM_PLAN", (member,), "direct-request-command"
        ),
    )
    assert (
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN", (member,), "direct-request-command"
            ),
        ).request_id
        == direct.request_id
    )
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        service.submit_request(
            alice,
            GrantRequestCommand(
                "CONTINUE_PROBLEM_PLAN",
                (
                    ExactGrant(
                        "BUSINESS_PROBLEM", "READ", "business-problem:problem-else"
                    ),
                ),
                "direct-request-command",
            ),
        )
    with pytest.raises(AuthorityError, match="GRANT_SELF_APPROVAL_PROHIBITED"):
        service.decide_request(
            alice,
            GrantDecisionCommand(
                request.request_id,
                True,
                "ASSIGNED_DUTY",
                "TICKET",
                "ticket-1",
                now,
                now + timedelta(hours=1),
                "self-decision",
            ),
        )
    decision = service.decide_request(
        admin,
        GrantDecisionCommand(
            request.request_id,
            True,
            "ASSIGNED_DUTY",
            "TICKET",
            "ticket-1",
            now,
            now + timedelta(hours=1),
            "admin-decision",
        ),
    )
    assert decision.grants
    decided_request = service.inspect_request(alice, request.request_id)
    assert decided_request.status is GrantRequestStatus.APPROVED
    assert decided_request.aggregate_version == 2
    with pytest.raises(AuthorityError, match="GRANT_REQUEST_NOT_FOUND"):
        service.inspect_request(bob, request.request_id)
    assert reader.has_current_grant(
        alice, member, now=now, generation=1, recovery_epoch=1
    )
    static_and_dynamic_generation = replace(
        generation,
        credentials=tuple(
            replace(
                item,
                grants=(*item.grants, StaticGrant(member, GrantSource.SERVICE_ONLY)),
            )
            if item.credential_id == CredentialId("credential-alice")
            else item
            for item in generation.credentials
        ),
    )
    assert GenerationAuthorizationReader(
        static_and_dynamic_generation, repository, repository, recovery_epoch=1
    ).has_current_grant(alice, member, now=now, generation=1, recovery_epoch=1)
    revoked_generation = replace(
        generation,
        static_grant_revocation_tombstones=frozenset(
            {(CredentialId("credential-alice"), member)}
        ),
    )
    assert not GenerationAuthorizationReader(
        revoked_generation, repository, repository, recovery_epoch=1
    ).has_current_grant(alice, member, now=now, generation=1, recovery_epoch=1)
    repository.revoke_grant(
        decision.grants[0],
        actor_id="human:admin",
        reason="DUTY_ENDED",
        idempotency_key="dynamic-revocation",
        payload_digest="9" * 64,
        now=now + timedelta(minutes=1),
    )
    assert not GenerationAuthorizationReader(
        static_and_dynamic_generation, repository, repository, recovery_epoch=1
    ).has_current_grant(
        alice,
        member,
        now=now + timedelta(minutes=1),
        generation=1,
        recovery_epoch=1,
    )


def test_public_authorization_ports_use_real_session_and_postgres_state(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:hidden")
    assign_meta = ExactGrant(
        "CONTINUATION_ASSIGNMENT", "ASSIGN", "continuation-scope:tenant-a:quality"
    )
    decide_meta = ExactGrant("GRANT_ADMIN", "DECIDE", "grant-scope:tenant-a:quality")
    generation = StaticAuthorityGeneration(
        1,
        "d" * 64,
        "policy-1",
        "test",
        (
            CredentialConfiguration(
                CredentialId("credential-alice"),
                hashlib.sha256(b"browser-secret").hexdigest(),
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.BROWSER_BOOTSTRAP,
                (),
            ),
            CredentialConfiguration(
                CredentialId("credential-admin"),
                "e" * 64,
                "human:admin",
                scope,
                now + timedelta(days=1),
                GrantSource.SERVICE_ONLY,
                (
                    StaticGrant(assign_meta, GrantSource.STATIC_META),
                    StaticGrant(decide_meta, GrantSource.STATIC_META),
                ),
            ),
        ),
        (
            RequestabilityRule(
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:",
                "CONTINUE_PROBLEM_PLAN",
            ),
        ),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    reader = GenerationAuthorizationReader(
        generation, repository, repository, recovery_epoch=1
    )
    codec = SignedContinuationOwner(b"q" * 32)
    identities = (f"browser-port-{number}" for number in range(20))
    grants = GrantAdministrationService(
        repository,
        reader,
        generation,
        continuation_owner=codec,
        target_validator=KnownTestTargets(),
        recovery_epoch=1,
        clock=lambda: now,
        identity_factory=lambda _: next(identities),
    )
    admin = TrustedRequestContext(
        "human:admin",
        scope,
        "credential-admin",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    grants.assign_offer(
        admin,
        ContinuationOfferCommand(
            "human:alice",
            "CONTINUE_PROBLEM_PLAN",
            (member,),
            "problem:hidden:revision-1",
            "revision-1",
            now + timedelta(minutes=10),
            "browser-offer",
        ),
    )
    sessions = BrowserSessionService(
        repository,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=8),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"s" * 32,
        recovery_epoch=1,
        clock=lambda: now,
    )
    app = create_workbench_bff(
        sessions,
        object(),  # type: ignore[arg-type]
        WorkbenchBffPolicy("console.example", "https://console.example"),
        grant_administration=grants,
    )
    client = TestClient(app, base_url="https://console.example")
    login_form = client.get(f"{PREFIX}/login")
    nonce = re.search(r'name="loginNonce" value="([^"]+)"', login_form.text)
    assert nonce is not None
    logged_in = client.post(
        f"{PREFIX}/session",
        headers={
            "origin": "https://console.example",
            "content-type": "application/x-www-form-urlencoded",
        },
        content=(f"loginNonce={nonce.group(1)}&bootstrapCredential=browser-secret"),
        follow_redirects=False,
    )
    assert logged_in.status_code == 303
    csrf = client.get(f"{PREFIX}/session").json()["csrfToken"]

    inbox = client.get(f"{PREFIX}/authorization/continuations?state=AVAILABLE")
    assert inbox.status_code == 200
    reference = inbox.json()["continuations"][0]["continuationId"]
    assert reference.startswith("continuation-ref.")
    assert "hidden" not in reference
    submitted = client.post(
        f"{PREFIX}/authorization/grant-requests",
        headers={
            "origin": "https://console.example",
            "x-csrf-token": csrf,
            "idempotency-key": "browser-request",
        },
        json={
            "schemaVersion": "exact-grant-request.v1",
            "purpose": "CONTINUE_PROBLEM_PLAN",
            "continuationIds": [reference],
        },
    )
    assert submitted.status_code == 202
    request_id = submitted.json()["requestId"]
    assert submitted.json()["aggregateVersion"] == 1
    assert client.get(
        f"{PREFIX}/authorization/continuations?state=AVAILABLE"
    ).json() == {"continuations": []}

    grants.decide_request(
        admin,
        GrantDecisionCommand(
            request_id,
            True,
            "ASSIGNED_DUTY",
            "TICKET",
            "ticket-1",
            now,
            now + timedelta(hours=1),
            "browser-decision",
        ),
    )
    status = client.get(f"{PREFIX}/authorization/grant-requests/{request_id}")
    assert status.status_code == 200
    assert status.json()["state"] == "APPROVED"
    assert status.json()["aggregateVersion"] == 2
    assert "hidden" not in status.text


def test_recovery_epoch_invalidates_sessions_continuations_and_effective_grants(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    browser = session(now)
    repository.create_session(browser, hashlib.sha256(b"secret").hexdigest())
    repository.activate_generation(
        1,
        "a" * 64,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-3")
    request = GrantRequest(
        "recovery-request",
        "human:alice",
        scope,
        (member,),
        "CONTINUE_PROBLEM_PLAN",
        GrantRequestStatus.PENDING,
        now,
    )
    repository.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="recovery-request",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    decision = GrantDecision(
        "recovery-decision",
        request.request_id,
        "human:admin",
        "meta-admin",
        True,
        "ASSIGNED_DUTY",
        "TICKET",
        "2" * 64,
        "policy-1",
        "test",
        now,
    )
    repository.decide_request(
        decision,
        grants=((GrantId("recovery-grant"), member, now, now + timedelta(hours=1)),),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="recovery-decision",
        payload_digest="3" * 64,
        recovery_epoch=1,
    )
    claim = ContinuationClaim(
        "recovery-offer",
        "human:alice",
        scope,
        "CONTINUE_PROBLEM_PLAN",
        (member,),
        "problem-3:revision-1",
        "revision-1",
        1,
        now,
        now + timedelta(minutes=10),
    )
    repository.store_continuation_offer(
        claim,
        continuation_digest="4" * 64,
        issuer_actor_id="human:admin",
        mint_key="recovery-offer-key",
        mint_payload_digest="5" * 64,
        recovery_epoch=1,
    )

    repository.reconcile_recovery(
        recovery_epoch=2,
        database_fingerprint="database-restored",
        generation=1,
        generation_digest="a" * 64,
        migration_version=18,
        operator_id="operator:test",
        audit_continuity_digest="6" * 64,
        now=now + timedelta(minutes=1),
    )
    assert (
        repository.touch_current_session(
            hashlib.sha256(b"secret").hexdigest(),
            now=now + timedelta(minutes=2),
            idle_expires_at=now + timedelta(minutes=30),
            recovery_epoch=2,
        )
        is None
    )
    context = TrustedRequestContext(
        "human:alice",
        scope,
        "credential-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-1",
    )
    assert not repository.has_current_grant(
        context,
        member,
        now=now + timedelta(minutes=2),
        generation=1,
        recovery_epoch=2,
    )
    assert (
        repository.list_continuation_offers(
            context, now=now + timedelta(minutes=2), recovery_epoch=2
        )
        == ()
    )
    repository.complete_recovery(
        recovery_epoch=2,
        generation=1,
        generation_digest="a" * 64,
        operator_id="operator:test",
        now=now + timedelta(minutes=2),
    )
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        repository.submit_request(
            replace(
                request,
                request_id="post-recovery-continuation",
                created_at=now + timedelta(minutes=3),
            ),
            actor_id="human:alice",
            idempotency_key="post-recovery-continuation",
            payload_digest="7" * 64,
            target_validation=lambda _: True,
            continuation_digest="4" * 64,
            recovery_epoch=2,
        )


def test_linearized_browser_authorization_orders_session_and_grant_changes(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:linearized")
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "policy-1",
        "test",
        (
            CredentialConfiguration(
                CredentialId("credential-alice"),
                "7" * 64,
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.BROWSER_BOOTSTRAP,
                (),
            ),
        ),
        (),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    first_session = session(now, "linearized-first")
    repository.create_session(first_session, hashlib.sha256(b"first").hexdigest())
    request = GrantRequest(
        "linearized-request",
        "human:alice",
        scope,
        (member,),
        "CONTINUE_PROBLEM_PLAN",
        GrantRequestStatus.PENDING,
        now,
    )
    repository.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="linearized-request",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    reader = GenerationAuthorizationReader(
        generation, repository, repository, recovery_epoch=1
    )
    entered = Event()
    release = Event()

    def checkpoint() -> None:
        entered.set()
        assert release.wait(timeout=10)

    repository._authorization_read_checkpoint = checkpoint
    first_context = TrustedRequestContext(
        "human:alice",
        scope,
        first_session.session_id,
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            reader.has_current_grant,
            first_context,
            member,
            now=now,
            generation=1,
            recovery_epoch=1,
        )
        assert entered.wait(timeout=10)
        assert repository.revoke_session(
            first_session.session_id,
            reason="SESSION_REVOKED",
            actor_id="human:alice",
            now=now + timedelta(seconds=1),
        )
        repository.decide_request(
            GrantDecision(
                "linearized-decision",
                request.request_id,
                "human:admin",
                "meta-admin",
                True,
                "ASSIGNED_DUTY",
                "TICKET",
                "2" * 64,
                "policy-1",
                "test",
                now + timedelta(seconds=1),
            ),
            grants=(
                (
                    GrantId("linearized-grant"),
                    member,
                    now,
                    now + timedelta(hours=1),
                ),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="linearized-decision",
            payload_digest="3" * 64,
            recovery_epoch=1,
        )
        release.set()
        assert result.result(timeout=10) is False

    second_session = session(now, "linearized-second")
    repository.create_session(second_session, hashlib.sha256(b"second").hexdigest())
    second_context = replace(
        first_context, session_id_or_service_credential_id=second_session.session_id
    )
    entered.clear()
    release.clear()
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            reader.has_current_grant,
            second_context,
            member,
            now=now + timedelta(seconds=2),
            generation=1,
            recovery_epoch=1,
        )
        assert entered.wait(timeout=10)
        assert repository.revoke_session(
            second_session.session_id,
            reason="SESSION_REVOKED",
            actor_id="human:alice",
            now=now + timedelta(seconds=3),
        )
        release.set()
        assert result.result(timeout=10) is True
    repository._authorization_read_checkpoint = lambda: None
    assert not reader.has_current_grant(
        second_context,
        member,
        now=now + timedelta(seconds=4),
        generation=1,
        recovery_epoch=1,
    )
    third_session = session(now, "linearized-third")
    repository.create_session(third_session, hashlib.sha256(b"third").hexdigest())
    third_context = replace(
        first_context, session_id_or_service_credential_id=third_session.session_id
    )
    entered.clear()
    release.clear()
    repository._authorization_read_checkpoint = checkpoint
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            reader.has_current_grant,
            third_context,
            member,
            now=now + timedelta(seconds=5),
            generation=1,
            recovery_epoch=1,
        )
        assert entered.wait(timeout=10)
        assert repository.revoke_grant(
            GrantId("linearized-grant"),
            actor_id="human:admin",
            reason="DUTY_ENDED",
            idempotency_key="linearized-revoke",
            payload_digest="4" * 64,
            now=now + timedelta(seconds=6),
        )
        release.set()
        assert result.result(timeout=10) is True
    repository._authorization_read_checkpoint = lambda: None
    assert not reader.has_current_grant(
        third_context,
        member,
        now=now + timedelta(seconds=7),
        generation=1,
        recovery_epoch=1,
    )


def test_browser_cannot_use_service_only_authority(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:service-only")
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "policy-1",
        "test",
        (
            CredentialConfiguration(
                CredentialId("credential-alice"),
                "7" * 64,
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.SERVICE_ONLY,
                (StaticGrant(member, GrantSource.SERVICE_ONLY),),
            ),
        ),
        (),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    browser = session(now, "service-only")
    repository.create_session(browser, hashlib.sha256(b"service-only").hexdigest())
    context = TrustedRequestContext(
        "human:alice",
        scope,
        browser.session_id,
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )
    assert not GenerationAuthorizationReader(
        generation, repository, repository, recovery_epoch=1
    ).has_current_grant(context, member, now=now, generation=1, recovery_epoch=1)


def test_same_continuation_has_one_concurrent_consumer(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:concurrent")
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "policy-1",
        "test",
        (),
        (
            RequestabilityRule(
                member.owner,
                member.action,
                "business-problem:",
                "CONTINUE_PROBLEM_PLAN",
            ),
        ),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    claim = ContinuationClaim(
        "concurrent-offer",
        "human:alice",
        scope,
        "CONTINUE_PROBLEM_PLAN",
        (member,),
        "problem:revision",
        "revision",
        1,
        now,
        now + timedelta(minutes=10),
    )
    digest = "4" * 64
    repository.store_continuation_offer(
        claim,
        continuation_digest=digest,
        issuer_actor_id="human:admin",
        mint_key="concurrent-offer",
        mint_payload_digest="5" * 64,
        recovery_epoch=1,
    )
    start = Barrier(3)

    def consume(number: int) -> str:
        start.wait(timeout=10)
        try:
            return repository.submit_request(
                GrantRequest(
                    f"concurrent-continuation-request-{number}",
                    "human:alice",
                    scope,
                    (member,),
                    "CONTINUE_PROBLEM_PLAN",
                    GrantRequestStatus.PENDING,
                    now,
                ),
                actor_id="human:alice",
                idempotency_key=f"concurrent-continuation-{number}",
                payload_digest=str(number) * 64,
                target_validation=lambda _: True,
                continuation_digest=digest,
                recovery_epoch=1,
            ).request_id
        except AuthorityError as exc:
            return exc.reason_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(consume, number) for number in (6, 7)]
        start.wait(timeout=10)
        results = [future.result(timeout=10) for future in futures]
    assert results.count("CONTINUATION_INVALID") == 1
    assert (
        sum(value.startswith("concurrent-continuation-request-") for value in results)
        == 1
    )


def test_recovery_terminates_old_requests_and_namespaces_commands(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:recovery")
    repository.activate_generation(
        1,
        "a" * 64,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    pending = GrantRequest(
        "pre-recovery-pending",
        "human:alice",
        scope,
        (member,),
        "CONTINUE_PROBLEM_PLAN",
        GrantRequestStatus.PENDING,
        now,
    )
    repository.submit_request(
        pending,
        actor_id="human:alice",
        idempotency_key="pending-command",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    decided = replace(pending, request_id="pre-recovery-decided")
    repository.submit_request(
        decided,
        actor_id="human:alice",
        idempotency_key="decided-command",
        payload_digest="2" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    old_decision = GrantDecision(
        "pre-recovery-decision",
        decided.request_id,
        "human:admin",
        "meta-admin",
        True,
        "ASSIGNED_DUTY",
        "TICKET",
        "3" * 64,
        "policy-1",
        "test",
        now,
    )
    repository.decide_request(
        old_decision,
        grants=(
            (GrantId("pre-recovery-grant"), member, now, now + timedelta(hours=1)),
        ),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="old-decision-command",
        payload_digest="4" * 64,
        recovery_epoch=1,
    )
    repository.reconcile_recovery(
        recovery_epoch=2,
        database_fingerprint="database-restored",
        generation=1,
        generation_digest="a" * 64,
        migration_version=18,
        operator_id="operator:recovery",
        audit_continuity_digest="5" * 64,
        now=now + timedelta(minutes=1),
    )
    assert (
        repository.inspect_request(pending.request_id).status
        is GrantRequestStatus.REJECTED
    )
    with repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS count FROM authorization_admin.grant_decisions "
                "WHERE request_id=%s",
                (pending.request_id,),
            ).fetchone()["count"]
            == 0
        )
        recovery_audit = connection.execute(
            "SELECT event_type,actor_id,outcome,reason_category,recovery_epoch FROM "
            "authorization_admin.audit_events WHERE subject_id=%s",
            (pending.subject_principal_id,),
        ).fetchall()
    assert {
        "event_type": "GRANT_REQUEST_RECOVERY_TERMINATED",
        "actor_id": "operator:recovery",
        "outcome": "TERMINATED",
        "reason_category": "DATABASE_RECOVERY",
        "recovery_epoch": 2,
    } in recovery_audit
    with pytest.raises(AuthorityError, match="AUTHORITY_RECOVERY_REQUIRED"):
        repository.submit_request(
            replace(pending, request_id="closed-recovery-request"),
            actor_id="human:alice",
            idempotency_key="pending-command",
            payload_digest="1" * 64,
            target_validation=lambda _: True,
            recovery_epoch=2,
        )
    repository.complete_recovery(
        recovery_epoch=2,
        generation=1,
        generation_digest="a" * 64,
        operator_id="operator:recovery",
        now=now + timedelta(minutes=2),
    )
    with pytest.raises(AuthorityError, match="AUTHORITY_RECOVERY_REQUIRED"):
        repository.decide_request(
            replace(old_decision, decision_id="stale-epoch-decision"),
            grants=(
                (
                    GrantId("stale-epoch-grant"),
                    member,
                    now,
                    now + timedelta(hours=1),
                ),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="stale-epoch-decision",
            payload_digest="6" * 64,
            recovery_epoch=1,
        )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_STATE_STALE"):
        repository.decide_request(
            replace(
                old_decision,
                decision_id="terminated-request-decision",
                request_id=pending.request_id,
            ),
            grants=(
                (
                    GrantId("terminated-request-grant"),
                    member,
                    now,
                    now + timedelta(hours=1),
                ),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="terminated-request-decision",
            payload_digest="6" * 64,
            recovery_epoch=2,
        )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_STATE_STALE"):
        repository.decide_request(
            old_decision,
            grants=(
                (GrantId("replayed-grant"), member, now, now + timedelta(hours=1)),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="old-decision-command",
            payload_digest="4" * 64,
            recovery_epoch=2,
        )
    new_request = replace(
        pending,
        request_id="post-recovery-request",
        created_at=now + timedelta(minutes=2),
    )
    assert (
        repository.submit_request(
            new_request,
            actor_id="human:alice",
            idempotency_key="pending-command",
            payload_digest="1" * 64,
            target_validation=lambda _: True,
            recovery_epoch=2,
        ).request_id
        == new_request.request_id
    )
    new_decision = replace(
        old_decision,
        decision_id="post-recovery-decision",
        request_id=new_request.request_id,
        basis_reference_digest="5" * 64,
        created_at=now + timedelta(minutes=2),
    )
    assert (
        repository.decide_request(
            new_decision,
            grants=(
                (
                    GrantId("post-recovery-grant"),
                    member,
                    now + timedelta(minutes=2),
                    now + timedelta(hours=1),
                ),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="post-recovery-decision",
            payload_digest="7" * 64,
            recovery_epoch=2,
        ).decision_id
        == new_decision.decision_id
    )
    with repository.pool.connection() as connection:
        submitted_epoch = connection.execute(
            "SELECT recovery_epoch FROM authorization_admin.audit_events "
            "WHERE event_type='GRANT_REQUEST_SUBMITTED' AND subject_id=%s "
            "ORDER BY occurred_at DESC LIMIT 1",
            (new_request.subject_principal_id,),
        ).fetchone()["recovery_epoch"]
    assert submitted_epoch == 2


def test_recovery_and_decision_follow_active_epoch_lock_order(
    repository: PostgresAuthorityRepository,
) -> None:
    now = datetime.now(UTC)
    scope = AuthorityScope("tenant-a", "quality")
    member = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:race")
    repository.activate_generation(
        1,
        "a" * 64,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )

    def submit(request_id: str, command: str, epoch: int) -> GrantRequest:
        request = GrantRequest(
            request_id,
            "human:alice",
            scope,
            (member,),
            "CONTINUE_PROBLEM_PLAN",
            GrantRequestStatus.PENDING,
            now,
        )
        return repository.submit_request(
            request,
            actor_id="human:alice",
            idempotency_key=command,
            payload_digest=hashlib.sha256(command.encode()).hexdigest(),
            target_validation=lambda _: True,
            recovery_epoch=epoch,
        )

    first = submit("decision-first-request", "decision-first-submit", 1)
    decision_locked = Event()
    release_decision = Event()

    def decision_checkpoint() -> None:
        decision_locked.set()
        assert release_decision.wait(timeout=10)

    repository._decision_request_locked_checkpoint = decision_checkpoint
    first_decision = GrantDecision(
        "decision-first",
        first.request_id,
        "human:admin",
        "meta-admin",
        True,
        "ASSIGNED_DUTY",
        "TICKET",
        "1" * 64,
        "policy-1",
        "test",
        now,
    )

    def decide_first() -> GrantDecision:
        return repository.decide_request(
            first_decision,
            grants=(
                (
                    GrantId("decision-first-grant"),
                    member,
                    now,
                    now + timedelta(hours=1),
                ),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="decision-first",
            payload_digest="2" * 64,
            recovery_epoch=1,
        )

    recovery_started = Event()

    def recover(epoch: int) -> None:
        recovery_started.set()
        repository.reconcile_recovery(
            recovery_epoch=epoch,
            database_fingerprint=f"database-restored-{epoch}",
            generation=1,
            generation_digest="a" * 64,
            migration_version=18,
            operator_id="operator:recovery",
            audit_continuity_digest=str(epoch) * 64,
            now=now + timedelta(minutes=epoch),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        decision_future = executor.submit(decide_first)
        assert decision_locked.wait(timeout=10)
        recovery_future = executor.submit(recover, 2)
        assert recovery_started.wait(timeout=10)
        release_decision.set()
        assert (
            decision_future.result(timeout=10).decision_id == first_decision.decision_id
        )
        recovery_future.result(timeout=10)
    repository._decision_request_locked_checkpoint = lambda: None
    assert (
        repository.inspect_request(first.request_id).status
        is GrantRequestStatus.APPROVED
    )
    repository.complete_recovery(
        recovery_epoch=2,
        generation=1,
        generation_digest="a" * 64,
        operator_id="operator:recovery",
        now=now + timedelta(minutes=3),
    )

    second = submit("recovery-first-request", "recovery-first-submit", 2)
    recovery_locked = Event()
    release_recovery = Event()

    def recovery_checkpoint() -> None:
        recovery_locked.set()
        assert release_recovery.wait(timeout=10)

    repository._recovery_requests_locked_checkpoint = recovery_checkpoint
    second_decision = replace(
        first_decision,
        decision_id="recovery-first-decision",
        request_id=second.request_id,
    )

    def decide_second() -> GrantDecision:
        return repository.decide_request(
            second_decision,
            grants=(
                (
                    GrantId("recovery-first-grant"),
                    member,
                    now,
                    now + timedelta(hours=1),
                ),
            ),
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key="recovery-first-decision",
            payload_digest="3" * 64,
            recovery_epoch=2,
        )

    decision_started = Event()

    def start_second_decision() -> GrantDecision:
        decision_started.set()
        return decide_second()

    with ThreadPoolExecutor(max_workers=2) as executor:
        recovery_future = executor.submit(recover, 3)
        assert recovery_locked.wait(timeout=10)
        decision_future = executor.submit(start_second_decision)
        assert decision_started.wait(timeout=10)
        release_recovery.set()
        recovery_future.result(timeout=10)
        with pytest.raises(AuthorityError, match="AUTHORITY_RECOVERY_REQUIRED"):
            decision_future.result(timeout=10)
    assert (
        repository.inspect_request(second.request_id).status
        is GrantRequestStatus.REJECTED
    )
