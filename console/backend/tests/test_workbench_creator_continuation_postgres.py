from __future__ import annotations

import hashlib
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    RequestabilityRule,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantSource,
)
from agent_console.authority_foundation import SignedContinuationOwner
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_continuation import (
    BusinessProblemContinuationValidator,
    BusinessProblemCreateCoordinator,
)
from agent_console.business_problem_domain import BusinessProblemRevision
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.business_problem_schemas import CreateBusinessProblem
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
    GrantAdministrationService,
)
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from fastapi.testclient import TestClient

DATABASE_URL = os.environ.get("CREATOR_CONTINUATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="305 creator-continuation PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


class Controller:
    def __init__(self, generation: StaticAuthorityGeneration) -> None:
        self.generation = generation
        self.readiness = SimpleNamespace(recovery_epoch=1)

    @contextmanager
    def protected_request(self):
        yield self.generation


def static_generation(now: datetime) -> StaticAuthorityGeneration:
    scope = AuthorityScope("tenant-a", "quality")
    collection_create = ExactGrant(
        "BUSINESS_PROBLEM", "CREATE", "business-problem:collection"
    )
    collection_read = ExactGrant(
        "BUSINESS_PROBLEM", "READ", "business-problem:collection"
    )
    decide = ExactGrant("GRANT_ADMIN", "DECIDE", "grant-scope:tenant-a:quality")
    return StaticAuthorityGeneration(
        generation=1,
        digest="a" * 64,
        policy_version="policy-1",
        audit_source="impl-305-creator-test",
        credentials=(
            CredentialConfiguration(
                CredentialId("credential-alice"),
                hashlib.sha256(b"alice-secret").hexdigest(),
                "human:alice",
                scope,
                now + timedelta(hours=8),
                GrantSource.BROWSER_BOOTSTRAP,
                (
                    StaticGrant(collection_create, GrantSource.BROWSER_BOOTSTRAP),
                    StaticGrant(collection_read, GrantSource.BROWSER_BOOTSTRAP),
                ),
            ),
            CredentialConfiguration(
                CredentialId("credential-bob"),
                hashlib.sha256(b"bob-secret").hexdigest(),
                "human:bob",
                scope,
                now + timedelta(hours=8),
                GrantSource.BROWSER_BOOTSTRAP,
                (StaticGrant(decide, GrantSource.STATIC_META),),
            ),
        ),
        requestability=(
            RequestabilityRule(
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:",
                "CONTINUE_PROBLEM_READ",
            ),
        ),
        credential_revocation_tombstones=frozenset(),
    )


@pytest.fixture
def integrated_authority():
    original = DATABASE_URL or ""
    database_name = f"impl305_creator_{uuid.uuid4().hex}"
    admin = psycopg.connect(original, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = original.rsplit("/", 1)[0] + f"/{database_name}"
    authority = None
    problems = None
    try:
        with psycopg.connect(database_url) as connection:
            for version in range(1, 13):
                connection.execute(
                    next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
                )
        problems = PostgresBusinessProblemRepository(
            database_url,
            migration_path=MIGRATIONS / "0013_business_problem_authority.sql",
            creator_receipt_migration_path=(
                MIGRATIONS / "0020_business_problem_creator_receipt.sql"
            ),
            timeout=30,
        )
        problems.migrate()
        authority = PostgresAuthorityRepository(
            database_url,
            migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql",
            timeout=30,
        )
        authority.pool.resize(1, 8)
        authority.migrate()
        now = datetime.now(UTC)
        generation = static_generation(now)
        authority.activate_generation(
            1,
            generation.digest,
            1,
            operator_id="operator:test",
            revoked_credentials=(),
            now=now,
        )
        sessions = BrowserSessionService(
            authority,
            StaticGenerationAuthenticator(
                generation, source=GrantSource.BROWSER_BOOTSTRAP
            ),
            BrowserSessionPolicy(
                login_nonce_lifetime=timedelta(minutes=5),
                idle_lifetime=timedelta(minutes=30),
                absolute_lifetime=timedelta(hours=8),
                csrf_lifetime=timedelta(minutes=10),
            ),
            csrf_signing_key=b"c" * 32,
            recovery_epoch=1,
        )
        authorization = GenerationAuthorizationReader(
            generation,
            authority,
            authority,
            recovery_epoch=1,
        )
        validator = BusinessProblemContinuationValidator(problems)
        grants = GrantAdministrationService(
            authority,
            authorization,
            generation,
            continuation_owner=SignedContinuationOwner(b"k" * 32),
            target_validator=validator,
            recovery_epoch=1,
        )
        application = BusinessProblemApplication(
            PostgresProblemPlanUnitOfWork(problems, object()),
            None,
            object(),
            object(),
            object(),
        )
        authorizer = WorkbenchOwnerAuthorization(
            Controller(generation),  # type: ignore[arg-type]
            authority,
            authorization,
        )

        def build_application(*, coordinator_clock=None):
            coordinator = BusinessProblemCreateCoordinator(
                grants,
                clock=coordinator_clock or grants.clock,
                identity_factory=grants.identity_factory,
            )
            return create_workbench_bff(
                sessions,
                authorizer,
                WorkbenchBffPolicy("console.example", "https://console.example"),
                operations=business_problem_operations(application, coordinator),
                grant_administration=grants,
            )

        yield SimpleNamespace(
            database_url=database_url,
            authority=authority,
            problems=problems,
            application=application,
            grants=grants,
            build_application=build_application,
        )
    finally:
        if authority is not None:
            authority.close()
        if problems is not None:
            problems.pool.close()
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


def login(client: TestClient, credential: str) -> str:
    form = client.get(f"{PREFIX}/login")
    nonce = re.search(r'name="loginNonce" value="([^"]+)"', form.text)
    assert nonce is not None
    response = client.post(
        f"{PREFIX}/session",
        data={"loginNonce": nonce.group(1), "bootstrapCredential": credential},
        headers={"origin": "https://console.example"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    session = client.get(f"{PREFIX}/session")
    assert session.status_code == 200
    return session.json()["csrfToken"]


def create_problem(client: TestClient, csrf: str, *, key: str = "create-one"):
    return client.post(
        f"{PREFIX}/problems",
        json={
            "title": "Supplier quality",
            "description": "Reduce escaped defects",
            "ownerId": "business-owner",
            "idempotencyKey": key,
        },
        headers={
            "origin": "https://console.example",
            "x-csrf-token": csrf,
        },
    )


def test_public_create_replay_request_decision_and_exact_read(
    integrated_authority,
) -> None:
    application = integrated_authority.build_application()
    alice = TestClient(application, base_url="https://console.example")
    bob = TestClient(application, base_url="https://console.example")
    alice_csrf = login(alice, "alice-secret")
    bob_csrf = login(bob, "bob-secret")

    created = create_problem(alice, alice_csrf)
    assert created.status_code == 201
    created_result = created.json()["result"]
    continuation = created_result["creatorContinuation"]
    assert continuation["state"] == "AVAILABLE"
    continuation_id = continuation["continuationId"]
    problem_id = created_result["revision"]["business_problem_id"]

    cookie = alice.cookies.get(SESSION_COOKIE)
    assert cookie is not None

    def replay_once():
        client = TestClient(application, base_url="https://console.example")
        client.cookies.set(SESSION_COOKIE, cookie)
        return create_problem(client, alice_csrf).json()["result"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        replays = tuple(executor.map(lambda _: replay_once(), range(8)))
    assert {item["revision"]["revision_id"] for item in replays} == {
        created_result["revision"]["revision_id"]
    }
    assert {item["creatorContinuation"]["continuationId"] for item in replays} == {
        continuation_id
    }

    first_revision = integrated_authority.problems.get_problem(
        ScopeIdentity("tenant-a", "quality"),
        problem_id,
        authorized=True,
    )[0]
    successor = BusinessProblemRevision(
        first_revision.scope,
        problem_id,
        f"{problem_id}:2",
        2,
        first_revision.revision_id,
        "Supplier quality revised",
        "Reduce escaped defects and rework",
        first_revision.owner_id,
        first_revision.created_by,
        datetime.now(UTC),
    )
    integrated_authority.problems.add_problem_revision(
        successor,
        expected_version=1,
        idempotency_key="revision-two",
        payload_digest=successor.digest,
        authorized=True,
    )
    after_revision = create_problem(alice, alice_csrf).json()["result"]
    assert after_revision["revision"]["revision_id"] == first_revision.revision_id
    assert after_revision["creatorContinuation"]["continuationId"] == continuation_id

    wrong_subject = bob.post(
        f"{PREFIX}/authorization/grant-requests",
        json={
            "schemaVersion": "exact-grant-request.v1",
            "purpose": "CONTINUE_PROBLEM_READ",
            "continuationIds": [continuation_id],
        },
        headers={
            "origin": "https://console.example",
            "x-csrf-token": bob_csrf,
            "idempotency-key": "bob-request",
        },
    )
    assert wrong_subject.status_code == 404
    assert wrong_subject.json()["reasonCode"] == "CONTINUATION_INVALID"

    requested = alice.post(
        f"{PREFIX}/authorization/grant-requests",
        json={
            "schemaVersion": "exact-grant-request.v1",
            "purpose": "CONTINUE_PROBLEM_READ",
            "continuationIds": [continuation_id],
        },
        headers={
            "origin": "https://console.example",
            "x-csrf-token": alice_csrf,
            "idempotency-key": "alice-request",
        },
    )
    assert requested.status_code == 202
    request_id = requested.json()["requestId"]
    consumed = create_problem(alice, alice_csrf).json()["result"]["creatorContinuation"]
    assert consumed["state"] == "CONSUMED"
    assert consumed["continuationId"] == continuation_id
    assert consumed["requestId"] == request_id

    decided = bob.post(
        f"{PREFIX}/authorization/grant-requests/{request_id}/decisions",
        json={
            "schemaVersion": "exact-grant-decision.v1",
            "expectedVersion": 1,
            "decision": "APPROVE",
            "reasonCategory": "ASSIGNED_BUSINESS_DUTY",
            "basisType": "TICKET",
            "basisReference": "SEC-305",
            "expiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
        headers={
            "origin": "https://console.example",
            "x-csrf-token": bob_csrf,
            "idempotency-key": "bob-decision",
        },
    )
    assert decided.status_code == 201
    assert decided.json()["state"] == "APPROVED"
    assert decided.json()["aggregateVersion"] == 2

    exact_read = alice.get(f"{PREFIX}/problems/{problem_id}")
    assert exact_read.status_code == 200
    assert exact_read.json()["result"]["problem"]["business_problem_id"] == problem_id
    with integrated_authority.authority.pool.connection() as connection:
        counts = connection.execute(
            "SELECT "
            "(SELECT count(*) FROM authorization_admin.continuation_offers) AS offers,"
            "(SELECT count(*) FROM authorization_admin.continuation_consumptions) "
            "AS consumptions,"
            "(SELECT count(*) FROM authorization_admin.grant_requests) AS requests"
        ).fetchone()
    assert counts == {"offers": 1, "consumptions": 1, "requests": 1}


def test_concurrent_first_create_mints_one_durable_offer(
    integrated_authority,
) -> None:
    application = integrated_authority.build_application()
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    cookie = alice.cookies.get(SESSION_COOKIE)
    assert cookie is not None

    def create_once(_):
        client = TestClient(application, base_url="https://console.example")
        client.cookies.set(SESSION_COOKIE, cookie)
        response = create_problem(client, csrf, key="concurrent-first-mint")
        assert response.status_code == 201
        return response.json()["result"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(create_once, range(12)))

    assert len({item["revision"]["revision_id"] for item in results}) == 1
    assert len({item["creatorContinuation"]["continuationId"] for item in results}) == 1
    with integrated_authority.authority.pool.connection() as connection:
        counts = connection.execute(
            "SELECT "
            "(SELECT count(*) FROM business_problem_authority.problems) AS problems,"
            "(SELECT count(*) FROM business_problem_authority.creator_receipts) "
            "AS receipts,"
            "(SELECT count(*) FROM authorization_admin.continuation_offers) AS offers"
        ).fetchone()
    assert counts == {"problems": 1, "receipts": 1, "offers": 1}


def test_owner_commit_survives_mint_failure_and_same_key_recovers(
    integrated_authority, monkeypatch
) -> None:
    application = integrated_authority.build_application()
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    original = integrated_authority.authority.store_continuation_offer

    def unavailable(*args, **kwargs):
        raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")

    monkeypatch.setattr(
        integrated_authority.authority, "store_continuation_offer", unavailable
    )
    failed = create_problem(alice, csrf, key="mint-recovery")
    assert failed.status_code == 503
    assert failed.json()["reasonCode"] == "CONTINUATION_MINT_UNAVAILABLE"
    with psycopg.connect(integrated_authority.database_url) as connection:
        counts = connection.execute(
            "SELECT "
            "(SELECT count(*) FROM business_problem_authority.problems),"
            "(SELECT count(*) FROM business_problem_authority.creator_receipts),"
            "(SELECT count(*) FROM authorization_admin.continuation_offers)"
        ).fetchone()
    assert counts == (1, 1, 0)

    monkeypatch.setattr(
        integrated_authority.authority, "store_continuation_offer", original
    )
    recovered = create_problem(alice, csrf, key="mint-recovery")
    assert recovered.status_code == 201
    assert recovered.json()["result"]["creatorContinuation"]["state"] == "AVAILABLE"
    with integrated_authority.authority.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM authorization_admin.continuation_offers"
            ).fetchone()["total"]
            == 1
        )


def test_committed_offer_with_lost_response_recovers_same_reference(
    integrated_authority, monkeypatch
) -> None:
    application = integrated_authority.build_application()
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    original = integrated_authority.authority.store_continuation_offer
    response_lost = False

    def commit_then_lose_response(*args, **kwargs):
        nonlocal response_lost
        persisted = original(*args, **kwargs)
        if not response_lost:
            response_lost = True
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")
        return persisted

    monkeypatch.setattr(
        integrated_authority.authority,
        "store_continuation_offer",
        commit_then_lose_response,
    )
    failed = create_problem(alice, csrf, key="lost-mint-response")
    assert failed.status_code == 503
    assert failed.json()["reasonCode"] == "CONTINUATION_MINT_UNAVAILABLE"
    with integrated_authority.authority.pool.connection() as connection:
        stored = connection.execute(
            "SELECT continuation_digest FROM authorization_admin.continuation_offers"
        ).fetchone()
    assert stored is not None

    recovered = create_problem(alice, csrf, key="lost-mint-response")
    assert recovered.status_code == 201
    continuation = recovered.json()["result"]["creatorContinuation"]
    assert continuation["state"] == "AVAILABLE"
    assert continuation["continuationId"] == (
        "continuation-ref." + stored["continuation_digest"]
    )
    with integrated_authority.authority.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM authorization_admin.continuation_offers"
            ).fetchone()["total"]
            == 1
        )


@pytest.mark.parametrize("mismatch", ["REVOKED", "OWNER_REVISION"])
def test_replay_rejects_revoked_or_mismatched_offer(
    integrated_authority, mismatch: str
) -> None:
    application = integrated_authority.build_application()
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    created = create_problem(alice, csrf, key=f"invalid-offer-{mismatch.lower()}")
    assert created.status_code == 201
    with integrated_authority.authority.pool.connection() as connection:
        if mismatch == "REVOKED":
            connection.execute(
                "UPDATE authorization_admin.continuation_offers "
                "SET revoked_at=clock_timestamp()"
            )
        else:
            connection.execute(
                "UPDATE authorization_admin.continuation_offers SET owner_revision=%s",
                ("problem-owner-revision.v1.sha256." + "f" * 64,),
            )

    replay = create_problem(alice, csrf, key=f"invalid-offer-{mismatch.lower()}")
    assert replay.status_code == 409
    assert replay.json()["reasonCode"] == "CREATOR_CONTINUATION_INVALIDATED"


def test_expired_before_first_mint_returns_no_reference(integrated_authority) -> None:
    application = integrated_authority.build_application(
        coordinator_clock=lambda: datetime.now(UTC) + timedelta(minutes=11)
    )
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    created = create_problem(alice, csrf, key="expired-before-mint")
    continuation = created.json()["result"]["creatorContinuation"]
    assert continuation["state"] == "EXPIRED"
    assert "continuationId" not in continuation
    with integrated_authority.authority.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM authorization_admin.continuation_offers"
            ).fetchone()["total"]
            == 0
        )


def test_legacy_problem_without_receipt_is_rejected(integrated_authority) -> None:
    principal = SimpleNamespace(
        principal_id="human:alice",
        tenant_id="tenant-a",
        security_domain="quality",
    )
    private = BusinessProblemApplication(
        integrated_authority.application.uow,
        SimpleNamespace(require=lambda *args: None),
        object(),
        object(),
        object(),
    )
    command = CreateBusinessProblem(
        title="Legacy problem",
        description="Created before receipt support",
        ownerId="business-owner",
        idempotencyKey="legacy-key",
    )
    private.create_problem(principal, command)

    application = integrated_authority.build_application()
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    replay = alice.post(
        f"{PREFIX}/problems",
        json=command.model_dump(mode="json"),
        headers={
            "origin": "https://console.example",
            "x-csrf-token": csrf,
        },
    )
    assert replay.status_code == 409
    assert replay.json()["reasonCode"] == "CREATOR_RECEIPT_REQUIRED"
