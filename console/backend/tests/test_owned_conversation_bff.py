"""Actual session/BFF/input/admission/grants/retention with offline model output."""

# ruff: noqa: F401,F811 -- Shared isolated PostgreSQL fixtures.
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.conversation_history_access import install_history_access
from agent_console.conversation_source_input import source_reader
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    ProviderObservation,
)
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
    cancel_grant,
    model_grant,
    read_grant,
    request_grant,
)
from agent_console.draft_assistance_postgres import _invocation
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from fastapi.testclient import TestClient
from test_context_call_admission import env
from test_conversation_experience_admission import configure, pytestmark
from test_local_accounts_postgres import login, setup
from test_owned_conversation_understanding import successor


@pytest.fixture
def ordinary(env, setup, tmp_path):
    e = env
    _, _, sessions, reader = setup
    e.draft.profile = replace(e.draft.profile, adapter_revision="v3")
    _, _, path, document = configure(e, tmp_path)
    document["historyReadEnabled"] = True
    successor(e, path, document)
    grants = e.admission.delegation.grants
    generation = replace(
        grants.generation,
        requestability=tuple(
            RequestabilityRule(owner, action, prefix, purpose)
            for owner, action, prefix, purpose in (
                (
                    "DRAFT_ASSISTANCE",
                    "REQUEST_DRAFT_ASSISTANCE",
                    "draft-assistance:",
                    "PROBLEM_DRAFT_ASSISTANCE",
                ),
                (
                    "DRAFT_ASSISTANCE",
                    "READ_DRAFT_ASSISTANCE_INVOCATION",
                    "draft-assistance:",
                    "PROBLEM_DRAFT_ASSISTANCE",
                ),
                (
                    "DRAFT_ASSISTANCE",
                    "CANCEL_DRAFT_ASSISTANCE_INVOCATION",
                    "draft-assistance:",
                    "PROBLEM_DRAFT_ASSISTANCE",
                ),
                (
                    "MODEL_GOVERNANCE",
                    "INVOKE_MODEL",
                    "model:",
                    "PROBLEM_DRAFT_MODEL_INVOKE",
                ),
            )
        ),
    )
    grants._generation_provider = lambda: generation

    def known(context, member, **kwargs):
        with e.repo.connection_scope() as c:
            rows = c.execute(
                "SELECT record FROM draft_assistance.invocation_versions"
            ).fetchall()
        return any(
            i.initiating_principal_id == context.principal_id
            and member
            in (request_grant(i), read_grant(i), cancel_grant(i), model_grant(i))
            for i in (_invocation(r["record"]) for r in rows)
        )

    grants.target_validator = NS(is_known_exact_target=known)
    controller = NS(
        protected_request=lambda: nullcontext(generation),
        readiness=NS(recovery_epoch=1),
    )
    authorizer = WorkbenchOwnerAuthorization(controller, e.repo, reader)
    authorization = GrantAdministrationDraftAuthorization(grants, authorizer)
    authorization.context_admission = e.admission
    e.draft.authorization = authorization
    dispatches = []

    def dispatch(**kwargs):
        dispatches.append(kwargs["invocation_id"])
        return ProviderObservation(
            "offline:" + kwargs["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled",
            result_kind=DraftResultKind.DIRECT_ANSWER,
            answer="你好,有什么需要我协助?",
            input_tokens=2,
            output_tokens=10,
        )

    e.draft.transport.dispatch = dispatch
    with e.repo.connection_scope() as c:
        for name in (
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ):
            c.execute((Path(__file__).parents[1] / "migrations" / name).read_text())
    app = create_workbench_bff(
        sessions,
        authorizer,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(),
        conversation_database_url=e.repo.pool.conninfo,
        route_installers=(
            install_draft_assistance_routes(e.draft),
            install_history_access(e.admission, authorizer),
        ),
    )
    app.state.conversation_source_input = source_reader(
        None, authorizer, app.state.conversation_actions.records
    )
    secret = login(sessions, "reviewer324")
    session, context = sessions.authenticate_session(secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": sessions.issue_csrf(session),
    }
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE, secret.value)

        def post(path, body):
            return client.post(PREFIX + path, json=body, headers=headers)

        created = post(
            "/conversations", {"title": "普通问题", "idempotencyKey": "fresh-chat"}
        )
        assert created.status_code == 200, created.text
        conv = created.json()["result"]["conversation_id"]
        message = post(
            f"/conversations/{conv}/messages",
            {"content": "你好", "idempotencyKey": "hello", "expectedVersion": 0},
        )
        assert message.status_code == 200, message.text
        e.client, e.post, e.conv = client, post, conv
        e.message = message.json()["result"]["identity"]
        e.dispatches, e.context, e.reader, e.generation = (
            dispatches,
            context,
            reader,
            generation,
        )
        yield e


def test_no_business_list_bff_retains_and_refreshes_answer(ordinary):
    e = ordinary
    assert not e.reader.has_current_grant(
        e.context,
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        now=e.draft.clock(),
        generation=e.generation.generation,
        recovery_epoch=1,
    )
    body = {
        "content": "你好",
        "idempotencyKey": "hello-understanding",
        "conversationId": e.conv,
        "conversationMessageId": e.message,
    }
    response = e.post("/draft-assistance/invocations", body)
    assert response.status_code in (200, 201), response.text
    result = response.json()["result"]
    assert result["resultKind"] == "DIRECT_ANSWER", result
    assert result["conversationDelivery"]["state"] == "SAVED", result
    refreshed = e.client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-results/{e.message}",
        params={"requestKey": body["idempotencyKey"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["result"]["answer"] == result["answer"]
    assert len(e.dispatches) == 1
    # Retained reads may expire independently of the unchanged allowance.
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.grants "
            "SET not_before=now()-interval '9 hours', "
            "expires_at=now()-interval '1 hour' "
            "WHERE owner='DRAFT_ASSISTANCE' "
            "AND action='READ_DRAFT_ASSISTANCE_INVOCATION'"
        )
    denied = e.client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-results/{e.message}",
        params={"requestKey": body["idempotencyKey"]},
    )
    assert denied.status_code == 404
    renewal = e.post(f"/conversations/{e.conv}/history-access", {})
    assert renewal.status_code == 200, renewal.text
    assert [item["state"] for item in renewal.json()["result"]["items"]] == ["APPROVED"]
    restored = e.client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-results/{e.message}",
        params={"requestKey": body["idempotencyKey"]},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["result"]["answer"] == result["answer"]
    assert len(e.dispatches) == 1


@pytest.mark.parametrize("invalid", ["owner", "archived", "message", "source"])
def test_bff_rejects_invalid_ownership_message_and_selected_source(ordinary, invalid):
    from psycopg.types.json import Jsonb

    e = ordinary
    with e.repo.connection_scope() as c:
        if invalid == "owner":
            c.execute(
                "UPDATE private_conversation.conversations SET owner_id='human:another'"
            )
        elif invalid == "archived":
            c.execute("UPDATE private_conversation.conversations SET archived_at=now()")
        elif invalid == "message":
            c.execute(
                "UPDATE private_conversation.messages SET author_id='human:another'"
            )
        else:
            c.execute(
                "INSERT INTO private_conversation.journeys "
                "(tenant_id,security_domain,conversation_id,version,state) "
                "VALUES(%s,%s,%s,1,%s)",
                (
                    e.context.scope.tenant_id,
                    e.context.scope.security_domain,
                    e.conv,
                    Jsonb({"source": {"selected": True}, "userMessageId": e.message}),
                ),
            )
    response = e.post(
        "/draft-assistance/invocations",
        {
            "content": "你好",
            "idempotencyKey": "invalid",
            "conversationId": e.conv,
            "conversationMessageId": e.message,
        },
    )
    assert response.status_code in (403, 404, 409), response.text
    if invalid == "source":
        assert response.json()["reasonCode"] == "CONVERSATION_INPUT_ACCESS_DENIED"
    assert e.dispatches == []
