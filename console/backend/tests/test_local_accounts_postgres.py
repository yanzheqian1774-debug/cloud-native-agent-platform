"""Real isolated PostgreSQL: accounts outlive bootstrap, never outlive Grants."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from agent_console.authority_configuration import StaticAuthorityLoader
from agent_console.authority_contracts import AuthorityError, ExactGrant, GrantSource
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
    GrantAdministrationService,
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.local_accounts import migrate, operate, verify_schema

URL = os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="exclusive PostgreSQL required")
MIGRATION = (
    Path(__file__).parents[1] / "migrations/0018_browser_session_grant_authority.sql"
)
PASSWORD = "test-only-account-password-324"


@pytest.fixture
def setup():
    name = "accounts324_" + uuid4().hex
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    repo = PostgresAuthorityRepository(
        URL.rsplit("/", 1)[0] + "/" + name, migration_path=MIGRATION
    )
    repo.migrate()
    migrate(repo)
    now = datetime.now(UTC)
    document = {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "test",
        "auditSource": "isolated-test",
        "credentials": [],
        "requestability": [
            {
                "owner": "PLAN",
                "action": "READ",
                "resourcePrefix": "plan:",
                "purpose": "TEST",
            }
        ],
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
        "localAccounts": [],
    }
    for username, role in [("demo324", "requester"), ("reviewer324", "approver")]:
        grants = (
            [
                {
                    "owner": "GRANT_ADMIN",
                    "action": a,
                    "resource": "grant-scope:s5-323-demo:isolated-real-demo",
                    "source": "STATIC_META",
                }
                for a in ["INSPECT", "DECIDE"]
            ]
            if role == "approver"
            else [
                {
                    "owner": "BUSINESS_PROBLEM",
                    "action": "CREATE",
                    "resource": "business-problem:collection",
                    "source": "BROWSER_BOOTSTRAP",
                }
            ]
        )
        document["credentials"].append(
            {
                "credentialId": "expired-" + role,
                "credentialSha256": hashlib.sha256(role.encode()).hexdigest(),
                "principalId": "human:demo323-" + role,
                "tenantId": "s5-323-demo",
                "securityDomain": "isolated-real-demo",
                "expiresAt": (now - timedelta(hours=1)).isoformat(),
                "authenticationSource": "BROWSER_BOOTSTRAP",
                "grants": grants,
            }
        )
        document["localAccounts"].append(
            {"username": username, "grantSourceCredentialId": "expired-" + role}
        )
    generation = StaticAuthorityLoader._parse(document, digest="a" * 64)
    repo.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    for account in generation.local_accounts:
        operate(
            repo,
            account,
            action="CREATE",
            command_id="create-" + account.username,
            operator_id="operator:test",
            now=now,
            password=PASSWORD,
        )
    service = BrowserSessionService(
        repo,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=8),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    reader = GenerationAuthorizationReader(generation, repo, repo, recovery_epoch=1)
    try:
        yield repo, generation, service, reader
    finally:
        repo.close()
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s",
                (name,),
            )
            admin.execute(f'DROP DATABASE "{name}"')


def login(service, user="demo324", password=PASSWORD):
    return service.create_account_session(service.issue_login_nonce(), user, password)


def test_expired_bootstrap_account_restart_and_rotation(setup):
    repo, generation, service, reader = setup
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        service.create_session(service.issue_login_nonce(), "requester")
    secret = login(service)
    session, context = service.authenticate_session(secret.value)
    grant = ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection")
    assert reader.has_current_grant(
        context, grant, now=service.clock(), generation=1, recovery_epoch=1
    )
    assert session.absolute_expires_at > generation.credentials[0].expires_at
    # Restart preserves passwords and active sessions.
    service = BrowserSessionService(
        repo,
        service.authenticator,
        service.policy,
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    service.authenticate_session(secret.value)
    rotated = service.rotate_session(secret.value)
    service.authenticate_session(rotated.value)
    with pytest.raises(AuthorityError):
        service.authenticate_session(secret.value)
    service.logout(rotated.value, actor_id=context.principal_id)
    with pytest.raises(AuthorityError):
        service.authenticate_session(rotated.value)
    login(service)
    verify_schema(repo)
    migrate(repo)
    repo.verify_existing_schema()


@pytest.mark.parametrize("action", ["RESET", "DISABLE", "REVOKE"])
def test_lifecycle_revokes_session_and_current_authorization(setup, action):
    repo, generation, service, reader = setup
    secret = login(service)
    _, context = service.authenticate_session(secret.value)
    account = generation.local_accounts[0]
    password = "replacement-test-password-324" if action == "RESET" else None
    operate(
        repo,
        account,
        action=action,
        command_id=action,
        operator_id="operator:test",
        now=service.clock(),
        password=password,
    )
    with pytest.raises(AuthorityError):
        service.authenticate_session(secret.value)
    assert not reader.has_current_grant(
        context,
        ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        now=service.clock(),
        generation=1,
        recovery_epoch=1,
    )
    with pytest.raises(AuthorityError):
        login(service)
    if action == "RESET":
        login(service, password=password)
        assert (
            operate(
                repo,
                account,
                action=action,
                command_id=action,
                operator_id="operator:test",
                now=service.clock(),
                password=password,
            )
            == 2
        )
        with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
            operate(
                repo,
                account,
                action=action,
                command_id=action,
                operator_id="operator:test",
                now=service.clock(),
                password=PASSWORD,
            )
    if action == "DISABLE":
        operate(
            repo,
            account,
            action="ENABLE",
            command_id="enable",
            operator_id="operator:test",
            now=service.clock(),
        )
        login(service)
        with pytest.raises(AuthorityError):
            service.authenticate_session(secret.value)
    if action == "REVOKE":
        with pytest.raises(AuthorityError):
            operate(
                repo,
                account,
                action="RESET",
                command_id="reset",
                operator_id="operator:test",
                now=service.clock(),
                password=PASSWORD,
            )


def test_grant_expiry_scope_and_original_request_decision(setup):
    repo, generation, service, reader = setup
    _, subject = service.authenticate_session(login(service).value)
    _, issuer = service.authenticate_session(login(service, "reviewer324").value)
    grants = GrantAdministrationService(
        repo,
        reader,
        generation,
        continuation_owner=None,
        recovery_epoch=1,
        target_validator=SimpleNamespace(
            is_known_exact_target=lambda context, grant, **kw: (
                grant == ExactGrant("PLAN", "READ", "plan:exact")
            )
        ),
    )
    member = ExactGrant("PLAN", "READ", "plan:exact")
    request = grants.submit_request(
        subject, GrantRequestCommand("TEST", (member,), "original")
    )
    command = GrantDecisionCommand(
        request.request_id,
        True,
        "TEST",
        "TICKET",
        "isolated-test",
        None,
        service.clock() + timedelta(minutes=5),
        "decision",
    )
    # Meta denial or self-approval must never write a decision.
    with pytest.raises(AuthorityError):
        grants.decide_request(subject, command)
    grants.decide_request(issuer, command)
    assert reader.authorize_current(subject, member, now=service.clock())
    # Session stays within its idle limit; the exact Grant expires independently.
    later = service.clock() + timedelta(minutes=6)
    assert reader.authorize_current(subject, member, now=later) is None
    assert reader.has_current_grant(
        subject,
        ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        now=later,
        generation=1,
        recovery_epoch=1,
    )
    wrong = replace(subject, scope=replace(subject.scope, security_domain="other"))
    assert reader.authorize_current(wrong, member, now=service.clock()) is None
    with repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == 1
        )


def test_persistent_throttle_and_no_unknown_account_disclosure(setup):
    repo, _, service, _ = setup
    for _ in range(10):
        with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
            login(service, password="invalid-but-long-password")
    service = BrowserSessionService(
        repo,
        service.authenticator,
        service.policy,
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        login(service)
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        login(service, "unknown")
    service.clock = lambda: datetime.now(UTC) + timedelta(minutes=16)
    login(service)


def test_account_lock_orders_revocation_after_current_owner_read(setup):
    repo, generation, service, reader = setup
    _, context = service.authenticate_session(login(service).value)
    entered = Event()
    done = Event()

    def revoke():
        entered.set()
        operate(
            repo,
            generation.local_accounts[0],
            action="REVOKE",
            command_id="revoke",
            operator_id="operator:test",
            now=service.clock(),
        )
        done.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with repo.connection_scope() as c:
            assert reader.has_current_grants(
                context,
                (
                    ExactGrant(
                        "BUSINESS_PROBLEM", "CREATE", "business-problem:collection"
                    ),
                ),
                now=service.clock(),
                generation=1,
                recovery_epoch=1,
                connection=c,
                configure_transaction=False,
            ) == (True,)
            future = pool.submit(revoke)
            assert entered.wait(2)
            assert not done.wait(0.1)
        future.result(timeout=5)
    assert not reader.has_current_grant(
        context,
        ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        now=service.clock(),
        generation=1,
        recovery_epoch=1,
    )


def test_tombstones_and_account_binding_do_not_bypass_prior_revoke(setup):
    _, generation, service, reader = setup
    secret = login(service)
    _, context = service.authenticate_session(secret.value)
    revoked = replace(
        generation,
        credential_revocation_tombstones=frozenset(
            {generation.local_accounts[0].grant_source_id}
        ),
    )
    service.authenticator._generation_provider = lambda: revoked
    reader._generation_provider = lambda: revoked
    with pytest.raises(AuthorityError):
        login(service)
    with pytest.raises(AuthorityError):
        service.authenticate_session(secret.value)
    assert not reader.has_current_grant(
        context,
        ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        now=service.clock(),
        generation=1,
        recovery_epoch=1,
    )


def test_real_bff_cookie_csrf_retry_and_no_business_replay(setup):
    import re

    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient

    _, _, service, _ = setup
    app = create_workbench_bff(
        service, object(), WorkbenchBffPolicy("127.0.0.1", "https://127.0.0.1")
    )
    with TestClient(app, base_url="https://127.0.0.1") as client:
        headers = {"origin": "https://127.0.0.1", "accept": "text/html"}
        page = client.get(
            "/api/workbench/v1/login?returnTo=/authorization-admin?request=original"
        )
        assert 'name="username"' in page.text and 'id="show-password"' in page.text
        nonce = re.search(r'name="loginNonce" value="([^"]+)"', page.text).group(1)
        denied = client.post(
            "/api/workbench/v1/session",
            data={
                "loginNonce": nonce,
                "username": "demo324",
                "password": "wrong-test-password",
            },
            headers=headers,
            follow_redirects=False,
        )
        assert denied.status_code == 401
        assert denied.headers["referrer-policy"] == "same-origin"
        assert "set-cookie" not in denied.headers
        nonce = re.search(r'name="loginNonce" value="([^"]+)"', denied.text).group(1)
        response = client.post(
            "/api/workbench/v1/session",
            data={
                "loginNonce": nonce,
                "username": "demo324",
                "password": PASSWORD,
                "returnTo": "/authorization-admin?request=original",
            },
            headers=headers,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/authorization-admin?request=original"
        cookie = response.headers["set-cookie"]
        assert all(
            flag in cookie
            for flag in [
                "__Host-workbench_session=",
                "HttpOnly",
                "Secure",
                "SameSite=strict",
            ]
        )
        session = client.get("/api/workbench/v1/session")
        assert session.status_code == 200
        assert session.json()["principal"]["principalId"] == "human:demo323-requester"
        assert client.get("/api/workbench/v1/session").status_code == 200
        assert (
            client.delete("/api/workbench/v1/session", headers=headers).status_code
            == 403
        )
        assert (
            client.delete(
                "/api/workbench/v1/session",
                headers={**headers, "x-csrf-token": session.json()["csrfToken"]},
            ).status_code
            == 204
        )
        assert client.get("/api/workbench/v1/session").status_code == 401


def test_account_schema_checksum_and_transaction_rollback(setup, tmp_path):
    repo, _, _, _ = setup
    original = repo.migration_path
    (tmp_path / original.name).write_text(original.read_text())
    extension = original.parent / "0036_local_test_accounts.sql"
    (tmp_path / extension.name).write_text(extension.read_text() + "\n-- drift\n")
    repo.migration_path = tmp_path / original.name
    try:
        with pytest.raises(AuthorityError, match="AUTHORITY_SCHEMA_INCOMPATIBLE"):
            migrate(repo)
    finally:
        repo.migration_path = original
    with repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) AS n FROM browser_identity.local_account_commands"
        ).fetchone()["n"]
    # Existing identity must not be overwritten by a new create command.
    binding = setup[1].local_accounts[0]
    with pytest.raises(AuthorityError, match="LOCAL_ACCOUNT_ALREADY_EXISTS"):
        operate(
            repo,
            binding,
            action="CREATE",
            command_id="duplicate-create",
            operator_id="operator:test",
            now=datetime.now(UTC),
            password=PASSWORD,
        )
    with repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM browser_identity.local_account_commands"
            ).fetchone()["n"]
            == before
        )
