"""Real isolated PostgreSQL: accounts outlive bootstrap, never outlive Grants."""

import hashlib
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from agent_console.authority_configuration import StaticAuthorityLoader
from agent_console.authority_contracts import ExactGrant, GrantSource
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
)
from agent_console.local_accounts import migrate, operate

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
        "developmentAdministrator": True,
    }
    for username, role in [
        ("demo324", "requester"),
        ("reviewer324", "approver"),
        ("devadmin", "development-admin"),
    ]:
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
                "principalId": "human:development-admin"
                if username == "devadmin"
                else "human:demo323-" + role,
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


def test_admin_role_uses_real_account_session_and_persistent_scope(setup):
    repo, generation, service, reader = setup
    secret = login(service, "devadmin")
    _, context = service.authenticate_session(secret.value)
    grants = [
        ExactGrant("KNOWLEDGE", "READ_RESOURCE", "knowledge:new-unseen-revision"),
        ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", "model:new-model"),
        ExactGrant(
            "SKILL", "MANAGE_RESOURCE", "skill-invocation:resource-management:skill:new"
        ),
    ]

    def permitted(ctx, current=reader):
        return current.has_current_grants(
            ctx, grants, now=service.clock(), generation=1, recovery_epoch=1
        )

    assert permitted(context) == (True, True, True)
    decision = reader.authorize_current(context, grants[1], now=service.clock())
    assert decision and decision.decision_id.startswith("development-role:")
    assert decision.context.principal_id == "human:development-admin"
    _, normal = service.authenticate_session(login(service).value)
    assert permitted(normal) == (False, False, False)
    assert permitted(
        replace(context, scope=type(context.scope)("other", "isolated-real-demo"))
    ) == (False, False, False)
    assert permitted(replace(context, principal_id="human:forged")) == (
        False,
        False,
        False,
    )
    # Role does not expire with the old eight-hour resource-sharing windows.
    later = service.clock() + timedelta(hours=9)
    service.clock = lambda: later
    _, renewed = service.authenticate_session(login(service, "devadmin").value)
    assert permitted(renewed) == (True, True, True)
    disabled = GenerationAuthorizationReader(
        replace(generation, development_administrator=False),
        repo,
        repo,
        recovery_epoch=1,
    )
    assert permitted(renewed, disabled) == (False, False, False)
    operate(
        repo,
        generation.account_by_id("local-account:devadmin"),
        action="DISABLE",
        command_id="disable-admin",
        operator_id="operator:test",
        now=later,
    )
    assert permitted(renewed) == (False, False, False)
    assert reader.authorize_current(renewed, grants[1], now=later) is None


def test_admin_continues_other_conversation_without_impersonation(setup):
    from agent_console.development_administrator import authorized
    from agent_console.private_conversation import (
        ConversationError,
        PrivateConversations,
    )

    repo, generation, service, reader = setup
    with repo.connection_scope() as c:
        for file in [
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ]:
            c.execute((MIGRATION.parent / file).read_text())
    records = PrivateConversations(
        repo.pool.conninfo,
        lambda ctx, target: {},
        lambda c, ctx: authorized(
            reader, ctx, generation=1, recovery_epoch=1, connection=c
        ),
    )
    _, owner = service.authenticate_session(login(service).value)
    _, admin = service.authenticate_session(login(service, "devadmin").value)
    _, other = service.authenticate_session(login(service, "reviewer324").value)
    identity = records.create(
        owner, {"title": "Owner's test", "idempotencyKey": "original-conversation"}
    )["conversation_id"]
    assert identity in [r["conversation_id"] for r in records.list(admin)["items"]]
    with pytest.raises(ConversationError):
        records.read(other, identity)
    records.mutate(
        admin,
        identity,
        {
            "idempotencyKey": "administrator-message",
            "expectedVersion": 0,
            "content": "管理员继续核对",
        },
        "message",
    )
    result = records.read(owner, identity)
    assert result["messages"][0]["author_id"] == admin.principal_id
    with repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT owner_id FROM private_conversation.conversations "
                "WHERE conversation_id=%s",
                (identity,),
            ).fetchone()["owner_id"]
            == owner.principal_id
        )
    operate(
        repo,
        generation.account_by_id("local-account:devadmin"),
        action="DISABLE",
        command_id="disable-cross-conversation",
        operator_id="operator:test",
        now=service.clock(),
    )
    with pytest.raises(ConversationError):
        records.read(admin, identity)
