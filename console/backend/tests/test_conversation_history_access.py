# ruff: noqa: F401,F811 -- Shared isolated PostgreSQL fixtures.
"""History grants preserve owner reads without replaying model or execution work."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_experience_admission import (
    ConversationExperienceAdmission,
)
from agent_console.conversation_history_access import prepare as prepare_history
from agent_console.draft_assistance_authorization import (
    cancel_grant,
    read_grant,
    request_grant,
)
from agent_console.grant_administration_application import GrantRequestCommand
from agent_console.private_conversation import PrivateConversations
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import configure, prepare, pytestmark
from test_local_accounts_postgres import setup


@pytest.fixture
def history(env, tmp_path):
    e = env
    invocation, owner, path, document = configure(e, tmp_path)
    document["historyReadEnabled"] = True
    path.write_text(json.dumps(document))
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    prepare(e, invocation, owner)
    grants = e.admission.delegation.grants
    members = (
        request_grant(invocation),
        read_grant(invocation),
        cancel_grant(invocation),
    )
    generation = replace(
        grants.generation,
        requestability=tuple(
            RequestabilityRule(
                g.owner, g.action, g.exact_resource, "PROBLEM_DRAFT_ASSISTANCE"
            )
            for g in members
        ),
    )
    grants._generation_provider = lambda: generation
    grants.target_validator = SimpleNamespace(
        is_known_exact_target=lambda context, member, **kw: member in members
    )
    request = grants.submit_request(
        e.reviewer,
        GrantRequestCommand("PROBLEM_DRAFT_ASSISTANCE", members, "original-read"),
    )
    e.admission.experience.authorize_requests(
        e.admission, e.reviewer, invocation, [request.request_id]
    )
    migrations = Path(__file__).parents[1] / "migrations"
    source = dict(
        kind="DRAFT",
        invocationId=invocation.invocation_id,
        contextId=invocation.context_id,
        turnId=invocation.turn_id,
        turnVersion=invocation.turn_version,
    )
    with e.repo.connection_scope() as c:
        for name in [
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ]:
            c.execute((migrations / name).read_text())
        c.execute(
            "INSERT INTO private_conversation.conversations (tenant_id,"
            "security_domain,conversation_id,owner_id,title,request_key"
            ",request_digest) VALUES(%s,%s,'approved-"
            "conversation',%s,'retained','create','digest')",
            (
                e.reviewer.scope.tenant_id,
                e.reviewer.scope.security_domain,
                e.reviewer.principal_id,
            ),
        )
        c.execute(
            "INSERT INTO private_conversation.messages (tenant_id,secur"
            "ity_domain,conversation_id,message_id,sequence,author_id,c"
            "ontent,disposition,request_key,request_digest) "
            "VALUES(%s,%s,'approved-"
            "conversation','message',1,'assistant','original "
            "answer','SOURCE','message','digest')",
            (e.reviewer.scope.tenant_id, e.reviewer.scope.security_domain),
        )
        c.execute(
            "INSERT INTO private_conversation.message_facts "
            "VALUES(%s,%s,'approved-"
            "conversation','message','SOURCE',%s)",
            (
                e.reviewer.scope.tenant_id,
                e.reviewer.scope.security_domain,
                Jsonb({"source": source}),
            ),
        )
        # Historical expiry is a fixture, never an operation on deployed grants.
        c.execute(
            "UPDATE authorization_admin.grants SET "
            "not_before=now()-interval '9 "
            "hours',expires_at=now()-interval '1 hour'"
        )
    e.records = PrivateConversations(e.repo.pool.conninfo, lambda *_: {})
    e.source, e.grants, e.read = invocation, grants, read_grant(invocation)

    def run(context=None):
        with e.repo.connection_scope() as c:
            return prepare_history(
                e.admission,
                e.records,
                context or e.reviewer,
                "approved-conversation",
                c,
            )

    e.run = run
    return e


def test_expired_read_renews_once_under_concurrent_refresh(history):
    e = history
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: e.run(), range(2)))
    assert sorted(r["items"][0]["state"] for r in results) == ["APPROVED", "EFFECTIVE"]
    assert e.run()["items"][0]["state"] == "EFFECTIVE"
    with e.repo.connection_scope() as c:
        new = c.execute(
            "SELECT action FROM authorization_admin.grants WHERE "
            "issuer_principal_id='policy:f3-conversation-history-read'"
        ).fetchall()
        assert new == [{"action": "READ_DRAFT_ASSISTANCE_INVOCATION"}]
        assert (
            c.execute("SELECT content FROM private_conversation.messages").fetchone()[
                "content"
            ]
            == "original answer"
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM "
                "authorization_admin.audit_events WHERE "
                "event_type='CONVERSATION_HISTORY_READ_GRANTED'"
            ).fetchone()["n"]
            == 1
        )


def test_foreign_account_or_source_never_receives_grant(history):
    e = history
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        e.run(e.business)
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE private_conversation.message_facts SET "
            "facts=jsonb_set(facts,'{source,turnVersion}','999')"
        )
    with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
        e.run()
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grants "
                "WHERE issuer_principal_id='policy:f3-conversation-"
                "history-read'"
            ).fetchone()["n"]
            == 0
        )


def test_disabled_history_policy_does_not_issue_grants(history):
    e = history
    e.admission.experience.document = e.admission.experience.document.model_copy(
        update={"historyReadEnabled": False}
    )
    assert e.run() == {"available": False, "items": []}


def test_explicit_read_revocation_is_not_renewed(history):
    from agent_console.grant_administration_application import GrantRevocationCommand

    e = history
    assert e.run()["items"][0]["state"] == "APPROVED"
    with e.repo.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants "
            "WHERE issuer_principal_id='policy:f3-conversation-history-read'"
        ).fetchone()["grant_id"]
    e.grants.revoke_grant(
        e.reviewer, GrantRevocationCommand(grant, "USER_REQUESTED", "revoke-read", True)
    )
    assert e.run()["items"][0]["state"] == "REVOKED"
    assert e.run()["items"][0]["state"] == "REVOKED"


def test_disabled_account_cannot_renew_history(history):
    e = history
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE browser_identity.local_accounts SET status='DISABLED' "
            "WHERE username='reviewer324'"
        )
    with pytest.raises(AuthorityError, match="ACCOUNT_INACTIVE"):
        e.run()


def test_http_requires_post_csrf_and_accepts_no_authority_fields(history):
    from contextlib import nullcontext

    from agent_console.conversation_history_access import install_history_access
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    e = history
    app = FastAPI()
    app.state.conversation_actions = SimpleNamespace(records=e.records)

    def authenticate(request):
        if request.headers.get("test-session") != "valid":
            raise HTTPException(401)
        return object(), e.reviewer

    def csrf(request, _session):
        if request.headers.get("x-csrf-token") != "valid":
            raise HTTPException(403)

    install_history_access(
        e.admission,
        SimpleNamespace(controller=SimpleNamespace(protected_request=nullcontext)),
    )(app, authenticate, csrf, None)
    client = TestClient(app)
    url = "/api/workbench/v1/conversations/approved-conversation/history-access"
    assert client.get(url).status_code == 405
    assert client.post(url, json={}).status_code == 401
    assert (
        client.post(url, json={}, headers={"test-session": "valid"}).status_code == 403
    )
    headers = {"test-session": "valid", "x-csrf-token": "valid"}
    assert client.post(url, json={"invoke": True}, headers=headers).status_code == 422
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grants "
                "WHERE issuer_principal_id='policy:f3-conversation-history-read'"
            ).fetchone()["n"]
            == 0
        )
    result = client.post(url, json={}, headers=headers)
    assert result.status_code == 200
    assert result.json()["result"]["items"][0]["state"] == "APPROVED"


def test_read_lease_can_renew_again_without_execution_authority(history):
    e = history
    assert e.run()["items"][0]["state"] == "APPROVED"
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.grants SET not_before=now()-interval '9 hours',"
            "expires_at=now()-interval '1 hour' WHERE "
            "issuer_principal_id='policy:f3-conversation-history-read'"
        )
    assert e.run()["items"][0]["state"] == "APPROVED"
    with e.repo.connection_scope() as c:
        rows = c.execute(
            "SELECT action FROM authorization_admin.grants WHERE "
            "issuer_principal_id='policy:f3-conversation-history-read'"
        ).fetchall()
        assert rows == [{"action": "READ_DRAFT_ASSISTANCE_INVOCATION"}] * 2


def test_expired_business_window_denies_history_before_reading_sources(env, tmp_path):
    e = env
    _, _, path, document = configure(e, tmp_path, expired=True)
    document["historyReadEnabled"] = True
    path.write_text(json.dumps(document))
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="EXPERIENCE_EXPIRED"),
    ):
        prepare_history(e.admission, None, e.reviewer, "approved-conversation", c)
