from __future__ import annotations

import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    BrowserSession,
    CredentialId,
    ExactGrant,
    GrantId,
    GrantSource,
    SessionId,
    TrustedRequestContext,
    VerifiedPrincipal,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization

DATABASE_URL = os.environ.get("AUTHORITY_I2_TEST_DATABASE_URL")
MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "0018_browser_session_grant_authority.sql"
)


class FakeController:
    def __init__(self, generation: StaticAuthorityGeneration) -> None:
        self.generation = generation
        self.readiness = SimpleNamespace(recovery_epoch=1)

    @contextmanager
    def protected_request(self):
        yield self.generation


class FakeRepository:
    def __init__(self) -> None:
        self.connection = object()

    @contextmanager
    def connection_scope(self):
        yield self.connection


class FakeReader:
    def __init__(self, allowed: tuple[bool, ...]) -> None:
        self.allowed = allowed
        self.connection = None

    def has_current_grants(self, context, grants, **values):
        self.connection = values["connection"]
        return self.allowed


def generation(now: datetime) -> StaticAuthorityGeneration:
    return StaticAuthorityGeneration(
        generation=1,
        digest="a" * 64,
        policy_version="policy-1",
        audit_source="impl-305-test",
        credentials=(
            CredentialConfiguration(
                credential_id=CredentialId("credential-alice"),
                credential_sha256="b" * 64,
                principal_id="human:alice",
                scope=AuthorityScope("tenant-a", "quality"),
                expires_at=now + timedelta(days=1),
                authentication_source=GrantSource.BROWSER_BOOTSTRAP,
                grants=(),
            ),
        ),
        requestability=(),
        credential_revocation_tombstones=frozenset(),
    )


def context() -> TrustedRequestContext:
    return TrustedRequestContext(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        "session-one",
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )


def test_adapter_shares_authorization_connection_and_denies_atomically() -> None:
    now = datetime(2029, 1, 1, tzinfo=UTC)
    repository = FakeRepository()
    reader = FakeReader((True,))
    adapter = WorkbenchOwnerAuthorization(
        FakeController(generation(now)),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        reader,  # type: ignore[arg-type]
        clock=lambda: now,
    )
    grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1")
    result = adapter.execute(
        context(),
        (grant,),
        operation="READ_PROBLEM",
        payload={},
        path={"problem_id": "problem-1"},
        query={},
        handler=lambda call: call.connection,
    )
    assert result is repository.connection
    assert reader.connection is repository.connection

    denied = WorkbenchOwnerAuthorization(
        FakeController(generation(now)),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        FakeReader((False,)),  # type: ignore[arg-type]
        clock=lambda: now,
    )
    called = False

    def handler(call):
        nonlocal called
        called = True

    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        denied.execute(
            context(),
            (grant,),
            operation="READ_PROBLEM",
            payload={},
            path={},
            query={},
            handler=handler,
        )
    assert not called


@pytest.fixture
def repository():
    if not DATABASE_URL:
        pytest.skip("305 exclusive real PostgreSQL 15 required")
    database_name = f"impl305_{uuid.uuid4().hex}"
    admin = psycopg.connect(DATABASE_URL, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    value = None
    try:
        value = PostgresAuthorityRepository(
            database_url, migration_path=MIGRATION, timeout=30.0
        )
        value.migrate()
        yield value
    finally:
        if value is not None:
            value.close()
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


def seed(repository: PostgresAuthorityRepository):
    now = datetime.now(UTC)
    principal = VerifiedPrincipal(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        CredentialId("credential-alice"),
        now + timedelta(days=1),
        "policy-1",
    )
    session = BrowserSession(
        SessionId("session-one"),
        principal,
        now,
        now,
        now + timedelta(minutes=30),
        now + timedelta(hours=8),
        1,
        1,
    )
    repository.create_session(session, hashlib.sha256(b"secret").hexdigest())
    grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1")
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.active_generation "
            "(generation,generation_digest,recovery_epoch,activated_by,activated_at) "
            "VALUES (1,%s,1,'operator:test',%s)",
            ("a" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,"
            "purpose,state,created_at,decided_at) "
            "VALUES ('request-one','human:alice','tenant-a','quality',"
            "'READ_PROBLEM','APPROVED',%s,%s)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) "
            "VALUES ('decision-one','request-one','human:bob','meta-one',true,"
            "'ASSIGNED_DUTY','POLICY',%s,'policy-1','test',%s)",
            ("c" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants "
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,"
            "recovery_epoch) VALUES ('grant-one','decision-one','request-one',"
            "'human:alice','tenant-a','quality','BUSINESS_PROBLEM','READ',"
            "'business-problem:problem-1','POLICY',%s,'human:bob','meta-one',"
            "'policy-1','test',%s,%s,%s,1)",
            ("c" * 64, now - timedelta(minutes=1), now + timedelta(hours=1), now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants "
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,"
            "action,exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES ('grant-one','human:alice','tenant-a','quality',"
            "'BUSINESS_PROBLEM','READ','business-problem:problem-1',%s,%s,1)",
            (now - timedelta(minutes=1), now + timedelta(hours=1)),
        )
        connection.execute("CREATE TABLE owner_effects (effect_id text PRIMARY KEY)")
    static = generation(now)
    reader = GenerationAuthorizationReader(
        static, repository, repository, recovery_epoch=1
    )
    adapter = WorkbenchOwnerAuthorization(
        FakeController(static),  # type: ignore[arg-type]
        repository,
        reader,
        clock=lambda: now,
    )
    return now, grant, adapter


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_revocation_serializes_after_owner_commit(repository, revocation: str) -> None:
    now, grant, adapter = seed(repository)
    handler_entered = Event()
    release_handler = Event()
    revocation_started = Event()

    def owner_call():
        def handler(call):
            handler_entered.set()
            assert release_handler.wait(timeout=5)
            call.connection.execute(
                "INSERT INTO owner_effects(effect_id) VALUES ('effect-one')"
            )
            return {"effectId": "effect-one"}

        return adapter.execute(
            context(),
            (grant,),
            operation="READ_PROBLEM",
            payload={},
            path={},
            query={},
            handler=handler,
        )

    def revoke():
        revocation_started.set()
        if revocation == "grant":
            return repository.revoke_grant(
                GrantId("grant-one"),
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-one",
                payload_digest="d" * 64,
                now=now,
            )
        return repository.revoke_session(
            SessionId("session-one"),
            reason="LOGOUT",
            actor_id="human:alice",
            now=now,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        effect_future = executor.submit(owner_call)
        assert handler_entered.wait(timeout=5)
        revoke_future = executor.submit(revoke)
        assert revocation_started.wait(timeout=5)
        with pytest.raises(TimeoutError):
            revoke_future.result(timeout=0.2)
        release_handler.set()
        assert effect_future.result(timeout=5) == {"effectId": "effect-one"}
        assert revoke_future.result(timeout=5)

    with repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM owner_effects"
            ).fetchone()["total"]
            == 1
        )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        adapter.execute(
            context(),
            (grant,),
            operation="READ_PROBLEM",
            payload={},
            path={},
            query={},
            handler=lambda call: {},
        )
