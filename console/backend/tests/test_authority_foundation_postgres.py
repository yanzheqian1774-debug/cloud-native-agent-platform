from __future__ import annotations

import hashlib
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from agent_console.browser_session_application import BrowserSessionPolicy
from agent_console.grant_administration_application import (
    ContinuationOfferCommand,
    GenerationAuthorizationReader,
    GrantAdministrationService,
    GrantDecisionCommand,
    GrantRequestCommand,
)

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
    submitted = repository.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="request-key",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
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
    )
    assert replay.request_id == submitted.request_id
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        repository.submit_request(
            request,
            actor_id="human:alice",
            idempotency_key="request-key",
            payload_digest="2" * 64,
            target_validation=lambda _: True,
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

    repository.activate_generation(
        1,
        "a" * 64,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
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
    assert service.continuation_inbox(alice) == (opaque,)
    bob = TrustedRequestContext(
        "human:bob",
        scope,
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
    request = service.submit_request(
        alice,
        GrantRequestCommand("CONTINUE_PROBLEM_PLAN", (), "request-command-1", opaque),
    )
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
