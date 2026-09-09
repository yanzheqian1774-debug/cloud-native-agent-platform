from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, current_thread
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
from agent_console.workbench_owner_authorization import (
    WorkbenchOwnerAuthorization,
    WorkbenchOwnerError,
)

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
        self.connection = FakeConnection()

    @contextmanager
    def connection_scope(self):
        yield self.connection


class FakeConnection:
    def __init__(self) -> None:
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)


class FakeReader:
    def __init__(self, allowed: tuple[bool, ...]) -> None:
        self.allowed = allowed
        self.connection = None
        self.configure_transaction = None

    def has_current_grants(self, context, grants, **values):
        self.connection = values["connection"]
        self.configure_transaction = values["configure_transaction"]
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
    assert reader.configure_transaction is False
    assert repository.connection.statements == [
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
    ]

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
        value.pool.resize(1, 8)
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
        connection.execute(
            "CREATE TABLE owner_replay_effects ("
            "idempotency_key text PRIMARY KEY,payload_digest text NOT NULL,"
            "result_record jsonb NOT NULL)"
        )
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


def wait_for_database_waiters(
    repository: PostgresAuthorityRepository, minimum: int
) -> None:
    """Wait for PostgreSQL lock registration, not a guessed timing window."""
    deadline = time.monotonic() + 5
    with psycopg.connect(repository.pool.conninfo, autocommit=True) as connection:
        while time.monotonic() < deadline:
            total = connection.execute(
                "SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a "
                "USING (pid) WHERE a.datname=current_database() AND NOT l.granted"
            ).fetchone()[0]
            if total >= minimum:
                return
            time.sleep(0.01)
    pytest.fail(f"expected at least {minimum} PostgreSQL lock waiters")


def replaying_owner_handler(
    *,
    payload_digest: str,
    first_has_claim: Event,
    release_first: Event,
    replay_entered_claim: Event,
):
    def handler(call):
        is_first = current_thread().name.startswith("owner-effect")
        if not is_first:
            replay_entered_claim.set()
        call.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 297))",
            ("workbench-owner-replay",),
        )
        if is_first:
            first_has_claim.set()
            assert release_first.wait(timeout=30)
        row = call.connection.execute(
            "SELECT payload_digest,result_record FROM owner_replay_effects "
            "WHERE idempotency_key='same-key' FOR UPDATE"
        ).fetchone()
        if row is not None:
            if row["payload_digest"] != payload_digest:
                raise WorkbenchOwnerError("BUSINESS_PROBLEM_CONFLICT", 409)
            return row["result_record"]
        result = {"effectId": "effect-one"}
        call.connection.execute(
            "INSERT INTO owner_replay_effects "
            "(idempotency_key,payload_digest,result_record) "
            "VALUES ('same-key',%s,%s::jsonb)",
            (payload_digest, json.dumps(result)),
        )
        return result

    return handler


def execute_replay_candidate(
    adapter: WorkbenchOwnerAuthorization,
    grant: ExactGrant,
    *,
    payload_digest: str,
    first_has_claim: Event,
    release_first: Event,
    replay_entered_claim: Event,
):
    return adapter.execute(
        context(),
        (grant,),
        operation="OWNER_REPLAY",
        payload={"payloadDigest": payload_digest},
        path={},
        query={},
        handler=replaying_owner_handler(
            payload_digest=payload_digest,
            first_has_claim=first_has_claim,
            release_first=release_first,
            replay_entered_claim=replay_entered_claim,
        ),
    )


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


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_waiting_same_payload_replays_once_before_revocation(
    repository, revocation: str
) -> None:
    now, grant, adapter = seed(repository)
    first_has_claim = Event()
    release_first = Event()
    replay_entered_claim = Event()
    revocation_started = Event()
    payload_digest = "e" * 64

    def invoke(digest: str):
        return execute_replay_candidate(
            adapter,
            grant,
            payload_digest=digest,
            first_has_claim=first_has_claim,
            release_first=release_first,
            replay_entered_claim=replay_entered_claim,
        )

    def revoke():
        revocation_started.set()
        if revocation == "grant":
            return repository.revoke_grant(
                GrantId("grant-one"),
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-during-replay",
                payload_digest="f" * 64,
                now=now,
            )
        return repository.revoke_session(
            SessionId("session-one"),
            reason="LOGOUT",
            actor_id="human:alice",
            now=now,
        )

    with (
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-effect"
        ) as owner_executor,
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-replay"
        ) as replay_executor,
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-revoke"
        ) as revoke_executor,
    ):
        owner = owner_executor.submit(invoke, payload_digest)
        assert first_has_claim.wait(timeout=5)
        replay = replay_executor.submit(invoke, payload_digest)
        assert replay_entered_claim.wait(timeout=5)
        wait_for_database_waiters(repository, 1)
        revoke_future = revoke_executor.submit(revoke)
        assert revocation_started.wait(timeout=5)
        wait_for_database_waiters(repository, 2)
        release_first.set()

        expected = {"effectId": "effect-one"}
        assert owner.result(timeout=5) == expected
        assert replay.result(timeout=5) == expected
        assert revoke_future.result(timeout=5)

    assert replay_entered_claim.is_set()
    with repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM owner_replay_effects"
            ).fetchone()["total"]
            == 1
        )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        invoke(payload_digest)


def test_waiting_different_payload_conflicts_without_repeating_effect(
    repository,
) -> None:
    _, grant, adapter = seed(repository)
    first_has_claim = Event()
    release_first = Event()
    replay_entered_claim = Event()

    def invoke(digest: str):
        return execute_replay_candidate(
            adapter,
            grant,
            payload_digest=digest,
            first_has_claim=first_has_claim,
            release_first=release_first,
            replay_entered_claim=replay_entered_claim,
        )

    with (
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-effect"
        ) as owner_executor,
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-replay"
        ) as replay_executor,
    ):
        owner = owner_executor.submit(invoke, "1" * 64)
        assert first_has_claim.wait(timeout=5)
        conflict = replay_executor.submit(invoke, "2" * 64)
        assert replay_entered_claim.wait(timeout=5)
        wait_for_database_waiters(repository, 1)
        release_first.set()

        assert owner.result(timeout=5) == {"effectId": "effect-one"}
        with pytest.raises(WorkbenchOwnerError) as raised:
            conflict.result(timeout=5)
        assert raised.value.reason_code == "BUSINESS_PROBLEM_CONFLICT"
        assert raised.value.status_code == 409

    assert replay_entered_claim.is_set()
    with repository.pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) AS total,min(payload_digest) AS payload_digest "
            "FROM owner_replay_effects"
        ).fetchone()
    assert row == {"total": 1, "payload_digest": "1" * 64}
