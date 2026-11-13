"""Actual sessions, grants, BFF and reference owner; model/budget are controlled."""

# ruff: noqa: F401,F811 -- Reuse isolated PostgreSQL/session fixtures.
import copy
import json
from dataclasses import replace

import pytest
from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_history_access import install_history_access
from agent_console.conversation_relation_context import (
    current_snapshot,
    validated_route,
)
from agent_console.conversation_source_input import source_reader
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    ProviderObservation,
)
from agent_console.draft_assistance_api import _payload, install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.understanding_adoption_admission import AdoptionExperience
from agent_console.understanding_adoption_application import (
    UnderstandingAdoptionApplication,
)
from agent_console.understanding_adoption_postgres import migrate
from agent_console.understanding_adoption_reader import reader
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from fastapi.testclient import TestClient
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup


@pytest.fixture
def adopted(routed, tmp_path, request):
    e = routed
    old_reply = e.route_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.route_headers,
        json={
            "content": "你好",
            "idempotencyKey": "old-c1",
            "conversationId": e.conv,
            "conversationMessageId": e.message,
            "conversationRouting": True,
        },
    )
    assert old_reply.status_code in (200, 201), old_reply.text
    e.old_c1 = old_reply.json()["result"]
    business_scope = str(getattr(request, "param", "")).startswith("BUSINESS")
    if business_scope:
        # Isolated owned conversation already named by the unchanged exact policy.
        with e.repo.connection_scope() as c:
            c.execute(
                "INSERT INTO private_conversation.conversations "
                "(tenant_id,security_domain,conversation_id,owner_id,title,"
                "request_key,request_digest) "
                "VALUES(%s,%s,'approved-conversation',%s,'Approved fixture',"
                "'approved-fixture','fixture')",
                (
                    e.context.scope.tenant_id,
                    e.context.scope.security_domain,
                    e.context.principal_id,
                ),
            )
        e.conv = "approved-conversation"
        sent = e.post(
            f"/conversations/{e.conv}/messages",
            {
                "content": "你好",
                "expectedVersion": 0,
                "idempotencyKey": "initial-business-message",
            },
        )
        assert sent.status_code == 200, sent.text
        e.message = sent.json()["result"]["identity"]
    primary = e.draft
    initial_calls = []

    def initial(**kw):
        initial_calls.append(kw["invocation_id"])
        return ProviderObservation(
            "question:" + kw["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled",
            result_kind=DraftResultKind.DRAFT_READY
            if getattr(request, "param", None) == "READY_SOURCE"
            else DraftResultKind.NEEDS_DATA
            if str(getattr(request, "param", "")).endswith("DATA")
            else DraftResultKind.NEEDS_CLARIFICATION,
            title="原材料核对"
            if getattr(request, "param", None) == "READY_SOURCE"
            else None,
            description="检查已确认范围的交接材料。"
            if getattr(request, "param", None) == "READY_SOURCE"
            else None,
            clarification_question=None
            if str(getattr(request, "param", "")).endswith("DATA")
            or getattr(request, "param", None) == "READY_SOURCE"
            else "请确认环境。",
            data_needs=["请提供材料"]
            if str(getattr(request, "param", "")).endswith("DATA")
            else None,
            input_tokens=10,
            output_tokens=20,
        )

    primary.transport.dispatch = initial
    first = e.post(
        "/draft-assistance/invocations",
        {
            "content": "你好",
            "idempotencyKey": "initial",
            "conversationId": e.conv,
            "conversationMessageId": e.message,
        },
    )
    assert first.status_code in (200, 201), first.text
    original = first.json()["result"]
    assert original["state"] == "SUCCEEDED", original
    state = {
        "phase": "CLARIFY",
        "key": "initial-work",
        "draft": original,
        "messages": [{"id": "user:" + e.message, "text": "你好"}],
        "log": [],
    }
    saved = e.post(
        f"/conversations/{e.conv}/journey",
        {"expectedVersion": 0 if business_scope else 7, "state": state},
    )
    assert saved.status_code == 200, saved.text
    route = copy.copy(e.route)
    route.profile = replace(
        route.profile,
        profile_revision_id="profile:adoption",
        profile_digest="e" * 64,
        adapter_revision="v3-relation-adoption",
        output_schema_version="conversation-understanding-output.v3-relation-adoption",
    )
    configuration = {
        **e.routing_admission.configuration,
        "profile_revision_id": route.profile.profile_revision_id,
        "profile_digest": route.profile.profile_digest,
        "configuration_digest": "f" * 64,
    }
    policy = tmp_path / "adoption.json"
    document = e.routing_admission.experience.routing_document.model_dump(mode="json")
    document.update(
        schemaVersion="f3-conversation-relation-admission.v2",
        scopeMode="EXISTING_WORK_AND_INITIAL_UNDERSTANDING",
        configuration=configuration,
        predecessorRoutingPolicyDigest=e.routing_admission.experience.understanding_policy_digest,
    )
    policy.write_text(json.dumps(document))
    policy.chmod(0o600)
    admission = ContextCallAdmission(e.admission.delegation, configuration)
    admission.experience = AdoptionExperience(
        e.admission, e.routing_admission, policy, configuration
    )
    e.admission.retained_conversation_relations = (e.routing_admission,)
    e.admission.conversation_relation = admission
    authorizer = primary.authorization.owner_authorization
    route.authorization = GrantAdministrationDraftAuthorization(
        e.admission.delegation.grants, authorizer
    )
    route.authorization.context_admission = admission
    route.transport = copy.copy(e.route.transport)
    e.calls = []
    e.snapshots = []
    e.kind = DraftResultKind.NEEDS_CLARIFICATION

    def dispatch(**kw):
        e.calls.append(kw["invocation_id"])
        snapshot = current_snapshot()
        e.snapshots.append(snapshot)
        relation = (
            "INDEPENDENT"
            if e.kind is DraftResultKind.DIRECT_ANSWER
            else "CURRENT_QUESTION"
        )
        proof = {
            "relation": relation,
            "contextDigest": snapshot["contextDigest"],
            "currentQuestionToken": snapshot["currentQuestionToken"]
            if relation == "CURRENT_QUESTION"
            else None,
        }
        return ProviderObservation(
            "answer:" + kw["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled",
            result_kind=e.kind,
            clarification_question="还需要确认检查范围。"
            if e.kind is DraftResultKind.NEEDS_CLARIFICATION
            else None,
            title="检查生产交接" if e.kind is DraftResultKind.DRAFT_READY else None,
            description="按已确认的生产范围检查交接材料。"
            if e.kind is DraftResultKind.DRAFT_READY
            else None,
            answer="你好。" if e.kind is DraftResultKind.DIRECT_ANSWER else None,
            input_tokens=10,
            output_tokens=20,
            conversation_route=proof,
        )

    route.transport.dispatch = dispatch
    # Controlled recorded usage; not a production settlement assertion.
    primary.budget.read_settlement = lambda identity: {
        "status": "ESTIMATE_SETTLED"
        if identity in primary.budget.usage
        else "PENDING_RECONCILIATION",
        "reservation_retained": identity not in primary.budget.usage,
    }
    app = create_workbench_bff(
        e.routing_sessions,
        authorizer,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(),
        conversation_database_url=e.repo.pool.conninfo,
        route_installers=(
            install_draft_assistance_routes(
                primary, route, retained_routing_services=(e.route,)
            ),
            install_history_access(e.admission, authorizer),
        ),
    )
    app.state.conversation_relation_reader = reader(
        lambda *_: pytest.fail("unexpected work fallback"),
        app.state.conversation_actions.records,
        primary,
        route,
    )
    app.state.conversation_adoption_source_input = source_reader(
        None, authorizer, app.state.conversation_actions.records, adoption=True
    )
    app.state.understanding_adoption = UnderstandingAdoptionApplication(
        app.state.conversation_actions,
        primary,
        route,
        app.state.conversation_draft_service_for,
        app.state.conversation_relation_reader,
        lambda *args: app.state.conversation_adoption_source_input(*args),
        _payload,
    )
    migrate(primary.repository)
    secret = login(e.routing_sessions, "reviewer324")
    session, _ = e.routing_sessions.authenticate_session(secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": e.routing_sessions.issue_csrf(session),
    }
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE, secret.value)
        e.adoption_client, e.adoption_headers, e.original, e.initial_calls = (
            client,
            headers,
            original,
            initial_calls,
        )
        yield e


def answer(e, key="answer"):
    head = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/head").json()[
        "result"
    ]
    sent = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/messages",
        headers=e.adoption_headers,
        json={
            "content": "生产环境",
            "idempotencyKey": "message:" + key,
            "expectedVersion": head["conversation"]["version"],
        },
    )
    assert sent.status_code == 200, sent.text
    message = sent.json()["result"]["identity"]
    result = e.adoption_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.adoption_headers,
        json={
            "content": "生产环境",
            "idempotencyKey": key,
            "conversationId": e.conv,
            "conversationMessageId": message,
            "conversationRouting": True,
        },
    )
    assert result.status_code in (200, 201), result.text
    assert result.json()["result"]["state"] == "SUCCEEDED", result.text
    return (
        f"/conversations/{e.conv}/understanding-results/{message}/adoption",
        result.json()["result"],
    )


def test_actual_bff_adopts_once_refreshes_without_dispatch_or_journal_change(adopted):
    e = adopted
    path, value = answer(e)
    before = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/journey").json()
    result = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert result.status_code == 200, result.text
    body = result.json()["result"]
    assert body["understanding"]["invocationId"] == value["invocationId"]
    assert body["understanding"]["clarificationQuestion"] == "还需要确认检查范围。"
    for method in ("get", "post", "get"):
        response = (
            e.adoption_client.get(PREFIX + path, params={"requestKey": "answer"})
            if method == "get"
            else e.adoption_client.post(
                PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
            )
        )
        assert response.status_code == 200, response.text
    assert (
        e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/journey").json()
        == before
    )
    assert len(e.calls) == len(e.initial_calls) == 1
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_assistance.result_adoptions"
            ).fetchone()["n"]
            == 1
        )


def test_unrelated_result_cannot_consume_original_question(adopted):
    e = adopted
    e.kind = DraftResultKind.DIRECT_ANSWER
    path, _ = answer(e)
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 409, response.text
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_assistance.result_adoptions"
            ).fetchone()["n"]
            == 0
        )
    assert len(e.calls) == 1


def test_c1_history_uses_its_recorded_profile_after_successor_installed(adopted):
    e = adopted
    response = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-results/{e.message}",
        params={"requestKey": "old-c1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["invocationId"] == e.old_c1["invocationId"]
    assert response.json()["result"]["answer"] == "你好。"
    assert e.calls == []


def test_unsettled_usage_blocks_adoption_without_new_reservation(adopted):
    e = adopted
    path, _ = answer(e)
    count = len(e.draft.budget.reservations)
    e.draft.budget.usage.clear()
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 409, response.text
    assert response.json()["reasonCode"] == "UNDERSTANDING_ADOPTION_BUDGET_UNRESOLVED"
    assert len(e.draft.budget.reservations) == count
    assert len(e.calls) == 1


def test_next_question_uses_adopted_result_and_keeps_root_goal(adopted):
    e = adopted
    path, _ = answer(e)
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 200, response.text
    saved = response.json()["result"]
    journal = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/journey").json()[
        "result"
    ]
    journal["state"]["draft"] = saved["understanding"]
    response = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/journey",
        headers=e.adoption_headers,
        json={"expectedVersion": journal["version"], "state": journal["state"]},
    )
    assert response.status_code == 200, response.text
    path2, next_result = answer(e, "second-answer")
    response = e.adoption_client.post(
        PREFIX + path2, headers=e.adoption_headers, json={"requestKey": "second-answer"}
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["result"]["adoption"]["target"]["original_invocation_id"]
        == saved["understanding"]["invocationId"]
    )
    assert next_result["invocationId"] != saved["understanding"]["invocationId"]
    assert len(e.calls) == 2 and len(e.initial_calls) == 1
    first = e.snapshots[0]["input"]["serverUserMessages"]
    second = e.snapshots[1]["input"]["serverUserMessages"]
    assert len(first) == 1 and len(second) == 2
    assert first[0] in second
    assert all(m["id"].startswith("server-message:") for m in second)
    assert any(m["text"] == "生产环境" for m in second)


def test_stale_tab_cannot_dispatch_again_after_question_adoption(adopted):
    e = adopted
    path, _ = answer(e)
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 200, response.text
    head = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/head").json()[
        "result"
    ]
    sent = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/messages",
        headers=e.adoption_headers,
        json={
            "content": "另一份回答",
            "expectedVersion": head["conversation"]["version"],
            "idempotencyKey": "stale-answer",
        },
    )
    response = e.adoption_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.adoption_headers,
        json={
            "content": "另一份回答",
            "idempotencyKey": "stale-understanding",
            "conversationId": e.conv,
            "conversationMessageId": sent.json()["result"]["identity"],
            "conversationRouting": True,
        },
    )
    assert response.status_code >= 400, response.text
    assert (
        response.json()["reasonCode"]
        == "UNDERSTANDING_ADOPTION_PARENT_ALREADY_CONSUMED"
    )
    assert len(e.calls) == 1
