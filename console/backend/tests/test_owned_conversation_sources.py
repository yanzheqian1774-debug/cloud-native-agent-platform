"""Real account/policy/grant owners in isolated PostgreSQL, no model or runtime."""

# ruff: noqa: F401, F811
from contextlib import nullcontext
from types import SimpleNamespace as NS

import pytest
from agent_console.conversation_source_access import ConversationSourceAccess
from agent_console.private_conversation import ConversationError, PrivateConversations
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from test_context_call_admission import env
from test_conversation_experience_admission import configure, pytestmark
from test_local_accounts_postgres import setup
from test_owned_conversation_understanding import conversation, successor


def access(e):
    grants = e.admission.delegation.grants
    adapter = WorkbenchOwnerAuthorization(
        NS(
            protected_request=lambda: nullcontext(grants.generation),
            readiness=NS(recovery_epoch=grants.recovery_epoch),
        ),
        e.repo,
        grants.authorization,
    )
    return ConversationSourceAccess(
        None,
        adapter,
        PrivateConversations(e.repo.pool.conninfo, lambda *args: None),
        NS(authorization=NS(context_admission=e.admission)),
    )


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "archived",
        "other-owner",
        "expired",
        "changed-policy",
        "disabled-account",
        "stale-generation",
    ],
)
def test_owned_catalogue_admission_has_no_model_or_grant_write(env, tmp_path, case):
    e = env
    _, _, path, document = configure(e, tmp_path, expired=case == "expired")
    successor(e, path, document)
    conversation(
        e,
        owner=e.business.principal_id if case == "other-owner" else None,
        archived=case == "archived",
    )
    if case == "changed-policy":
        path.unlink()
    with e.repo.connection_scope() as c:
        if case == "disabled-account":
            c.execute(
                "UPDATE browser_identity.local_accounts SET status='DISABLED' "
                "WHERE account_id='local-account:reviewer324'"
            )
        if case == "stale-generation":
            c.execute("UPDATE authorization_admin.active_generation SET generation=2")
    reader = access(e)
    if case == "valid":
        assert (
            reader.execute(
                e.reviewer, "new-own", lambda call: call.context.principal_id
            )
            == e.reviewer.principal_id
        )
    else:
        with pytest.raises(ConversationError):
            reader.execute(
                e.reviewer, "new-own", lambda call: pytest.fail("handler entered")
            )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.context_call_requests"
            ).fetchone()["n"]
            == 0
        )


def test_current_conversation_admission_does_not_create_resource_read(
    env, tmp_path, monkeypatch
):
    from agent_console import conversation_sources
    from agent_console.authority_contracts import AuthorityError
    from agent_console.workbench_business_problem import OwnerPrincipal

    e = env
    _, _, path, document = configure(e, tmp_path)
    successor(e, path, document)
    conversation(e)
    reader = access(e)
    reader.automation = NS(
        bound_app=lambda call: NS(
            scope=lambda p: NS(namespace=p.tenant_id, security_domain=p.security_domain)
        )
    )
    monkeypatch.setattr(
        conversation_sources,
        "identities",
        lambda *a: [
            {"identity": "knowledge:private", "revision": "1", "digest": "a" * 64}
        ],
    )
    monkeypatch.setattr(
        conversation_sources,
        "read_published",
        lambda *a: pytest.fail("unreadable content loaded"),
    )
    assert reader.catalogue(e.reviewer, "new-own") == {
        "items": [],
        "executionStarted": False,
    }
    with pytest.raises(ConversationError, match="CONVERSATION_SOURCE_ACCESS_DENIED"):
        reader.execute(
            e.reviewer,
            "new-own",
            lambda call: call.authority.require(
                OwnerPrincipal(
                    e.reviewer.principal_id, "s5-323-demo", "isolated-real-demo"
                ),
                "BUSINESS_PROBLEM",
                "LIST",
                "business-problem:collection",
            ),
        )
    with pytest.raises(AuthorityError):
        reader.catalogue(e.business, "new-own")


def test_owned_catalogue_real_bff_route_preserves_ownership(env, tmp_path, monkeypatch):
    from agent_console import conversation_sources
    from agent_console.private_conversation_api import install_private_conversations
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    e = env
    _, _, path, document = configure(e, tmp_path)
    successor(e, path, document)
    conversation(e)
    reader = access(e)
    reader.automation = NS(
        bound_app=lambda call: NS(
            scope=lambda p: NS(namespace=p.tenant_id, security_domain=p.security_domain)
        )
    )
    monkeypatch.setattr(conversation_sources, "identities", lambda *a: [])
    app = FastAPI()
    install_private_conversations(
        app,
        lambda request: (None, e.reviewer),
        lambda *a: None,
        reader.authorizer,
        (),
        e.repo.pool.conninfo,
    )
    app.state.conversation_source_access = reader
    with TestClient(app) as client:
        response = client.get("/api/workbench/v1/conversations/new-own/sources")
        assert response.status_code == 200
        assert response.json()["result"] == {"items": [], "executionStarted": False}
        assert (
            client.get("/api/workbench/v1/conversations/not-owned/sources").status_code
            == 404
        )
