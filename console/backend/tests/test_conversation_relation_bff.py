"""Real session/grants/retention with two profiles; model and budget are fixtures."""

# ruff: noqa: F401,F811 -- Shared isolated PostgreSQL fixtures.
import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_experience_admission import (
    LEDGER,
    ConversationExperienceAdmission,
)
from agent_console.conversation_history_access import install_history_access
from agent_console.conversation_relation_admission import RelationExperience
from agent_console.conversation_relation_context import provider_input, validated_route
from agent_console.conversation_relation_reader import reader as relation_reader
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    PreparedProviderRequest,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.draft_assistance_policy import policy_for, validate_result
from agent_console.provider_budget_allowance import prepare as prepare_allowance
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from conversation_relation_fixture import existing_work
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_policy import direct
from test_local_accounts_postgres import login
from test_owned_conversation_bff import ordinary
from test_owned_conversation_understanding import successor
from test_provider_budget_allowance import document as allowance_document
from test_recovery_bound_understanding import setup


@pytest.fixture
def routed(ordinary, setup, tmp_path):
    e = ordinary
    _, _, sessions, _ = setup
    root = e.admission
    path = root.experience.path
    document = json.loads(path.read_text())
    for key in (
        "ownedConversationUnderstanding",
        "predecessorSchemaVersion",
        "predecessorPolicyDigest",
    ):
        document.pop(key, None)
    owner = NS(
        _connection=e.repo.connection_scope,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=e.draft.profile,
        ledger_id=LEDGER,
    )
    allowance = allowance_document(owner, calls=100, cost=10_000_000)
    allowance["authorizationDigest"] = document["authorizationDigest"]
    saved = prepare_allowance(owner, allowance)
    root.configuration = {
        **root.configuration,
        "calls": 100,
        "cost_microusd": 10_000_000,
    }
    document.update(
        schemaVersion="f3-conversation-experience.v2",
        allowanceId=saved["allowanceId"],
        configuration=root.configuration,
    )
    path.write_text(json.dumps(document))
    root.experience = ConversationExperienceAdmission(path, root.configuration)
    successor(e, path, document)
    route = copy.copy(e.draft)
    route.profile = replace(
        e.draft.profile,
        profile_revision_id="profile:relation",
        profile_digest="c" * 64,
        adapter_revision="v3-relation",
        output_schema_version="conversation-understanding-output.v3-relation",
    )
    configuration = {
        **root.configuration,
        "profile_revision_id": route.profile.profile_revision_id,
        "profile_digest": route.profile.profile_digest,
        "configuration_digest": "d" * 64,
    }
    relation_path = tmp_path / "relation.json"
    relation_path.write_text(
        json.dumps(
            {
                "schemaVersion": "f3-conversation-relation-admission.v1",
                "predecessorUnderstandingPolicyDigest": (
                    root.experience.understanding_policy_digest
                ),
                "sharedAllowanceId": saved["allowanceId"],
                "configuration": configuration,
                "externalWrites": False,
                "scopeMode": "EXISTING_BUSINESS_WORK",
            }
        )
    )
    relation_path.chmod(0o600)
    admission = ContextCallAdmission(root.delegation, configuration)
    admission.experience = RelationExperience(root, relation_path, configuration)
    root.conversation_relation = admission
    authorizer = e.draft.authorization.owner_authorization
    route.authorization = GrantAdministrationDraftAuthorization(
        root.delegation.grants, authorizer
    )
    route.authorization.context_admission = admission
    route.transport = copy.copy(e.draft.transport)
    e.relation_result = direct()
    e.route_calls = []

    def prepare(**kw):
        return PreparedProviderRequest(
            json.dumps(
                {
                    "input": [
                        {"content": [{"text": kw["content"]}]},
                        {"content": [{"text": provider_input()}]},
                    ]
                }
            ),
            ProviderBudgetQuote(10, 50, 0),
        )

    def dispatch(**kw):
        e.route_calls.append(kw["invocation_id"])
        result = e.relation_result
        validate_result(
            result,
            policy_for("v3-relation", "conversation-understanding-output.v3-relation"),
            frozenset(),
        )
        proof = validated_route(result, kw["request"].payload)
        return ProviderObservation(
            "offline:" + kw["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled-relation",
            result_kind=DraftResultKind(result["kind"]),
            answer=result["answer"],
            clarification_question=result["clarificationQuestion"],
            conversation_route=proof,
            input_tokens=10,
            output_tokens=20,
        )

    route.transport.prepare, route.transport.dispatch = prepare, dispatch
    business, problem_repository, e.problem, e.work_state = existing_work(
        e, authorizer, sessions
    )
    app = create_workbench_bff(
        sessions,
        authorizer,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(),
        conversation_database_url=e.repo.pool.conninfo,
        route_installers=(
            install_draft_assistance_routes(e.draft, route),
            install_history_access(root, authorizer),
        ),
    )
    app.state.conversation_relation_reader = relation_reader(
        app, authorizer, business, app.state.conversation_actions
    )
    secret = login(sessions, "reviewer324")
    session, _ = sessions.authenticate_session(secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": sessions.issue_csrf(session),
    }
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE, secret.value)
        e.route_client, e.route, e.routing_admission, e.route_headers = (
            client,
            route,
            admission,
            headers,
        )
        e.routing_sessions = sessions
        try:
            yield e
        finally:
            problem_repository.pool.close()


def test_parallel_profile_single_call_and_exact_retained_read_without_journal_write(
    routed,
):
    e = routed
    original = e.work_state
    caps = e.route_client.get(PREFIX + "/draft-assistance/capabilities")
    assert caps.json()["result"]["conversationRelationRouting"] is True
    body = {
        "content": "你好",
        "idempotencyKey": "independent",
        "conversationId": e.conv,
        "conversationMessageId": e.message,
        "conversationRouting": True,
    }
    response = e.route_client.post(
        PREFIX + "/draft-assistance/invocations", json=body, headers=e.route_headers
    )
    assert response.status_code in (200, 201), response.text
    result = response.json()["result"]
    assert result["conversationDelivery"]["state"] == "SAVED", result
    assert result["conversationRoute"]["relation"] == "INDEPENDENT"
    assert len(e.route_calls) == 1 and e.dispatches == []
    path = f"/conversations/{e.conv}/understanding-results/{e.message}"
    for suffix in ("", "/route"):
        refreshed = e.route_client.get(
            PREFIX + path + suffix, params={"requestKey": "independent"}
        )
        assert refreshed.status_code == 200, refreshed.text
    with e.repo.connection_scope() as c:
        assert c.execute(
            "SELECT version,state FROM private_conversation.journeys"
        ).fetchone() == {"version": 7, "state": original}
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.policies"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.allowances"
            ).fetchone()["n"]
            == 1
        )
    assert len(e.route_calls) == 1 and e.dispatches == []

    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.grants "
            "SET not_before=now()-interval '9 hours', "
            "expires_at=now()-interval '1 hour' "
            "WHERE owner='DRAFT_ASSISTANCE' "
            "AND action='READ_DRAFT_ASSISTANCE_INVOCATION'"
        )
    e.admission.conversation_relation = None
    rejected = e.route_client.post(
        PREFIX + f"/conversations/{e.conv}/history-access",
        headers=e.route_headers,
        json={},
    )
    assert rejected.status_code >= 400, rejected.text
    e.admission.conversation_relation = e.routing_admission
    renewed = e.route_client.post(
        PREFIX + f"/conversations/{e.conv}/history-access",
        headers=e.route_headers,
        json={},
    )
    assert renewed.status_code == 200, renewed.text
    # Work-history targets also contain already-effective reads; ordering does
    # not identify the expired invocation whose exact GET is checked below.
    renewal_states = [item["state"] for item in renewed.json()["result"]["items"]]
    assert "APPROVED" in renewal_states
    assert set(renewal_states) <= {"APPROVED", "EFFECTIVE"}
    refreshed = e.route_client.get(PREFIX + path, params={"requestKey": "independent"})
    assert refreshed.status_code == 200, refreshed.text
    assert len(e.route_calls) == 1 and e.dispatches == []


def test_capability_is_current_account_bound_and_forced_request_cannot_dispatch(routed):
    e = routed
    secret = login(e.routing_sessions, "demo324")
    session, _ = e.routing_sessions.authenticate_session(secret.value)
    client = e.route_client
    client.cookies.set(SESSION_COOKIE, secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": e.routing_sessions.issue_csrf(session),
    }
    assert (
        client.get(PREFIX + "/draft-assistance/capabilities").json()["result"][
            "conversationRelationRouting"
        ]
        is False
    )
    conv = client.post(
        PREFIX + "/conversations",
        headers=headers,
        json={"title": "other", "idempotencyKey": "other-conv"},
    ).json()["result"]["conversation_id"]
    message = client.post(
        PREFIX + f"/conversations/{conv}/messages",
        headers=headers,
        json={
            "expectedVersion": 0,
            "content": "你好",
            "idempotencyKey": "other-message",
        },
    ).json()["result"]["identity"]
    denied = client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=headers,
        json={
            "content": "你好",
            "idempotencyKey": "other-route",
            "conversationId": conv,
            "conversationMessageId": message,
            "conversationRouting": True,
        },
    )
    assert denied.status_code >= 400, denied.text
    assert e.route_calls == [] and e.dispatches == []


def test_record_does_not_fall_back_to_current_default_profile(routed):
    e = routed
    body = {
        "content": "你好",
        "idempotencyKey": "profile-read",
        "conversationId": e.conv,
        "conversationMessageId": e.message,
        "conversationRouting": True,
    }
    response = e.route_client.post(
        PREFIX + "/draft-assistance/invocations", json=body, headers=e.route_headers
    )
    assert response.status_code in (200, 201), response.text
    e.route.profile = replace(e.route.profile, profile_revision_id="profile:other")
    response = e.route_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-results/{e.message}",
        params={"requestKey": "profile-read"},
    )
    assert response.status_code >= 400
    assert response.json()["reasonCode"] == "CONVERSATION_ROUTING_SERVICE_UNAVAILABLE"
    assert len(e.route_calls) == 1 and e.dispatches == []


@pytest.mark.parametrize("mutation", ["archived", "missing_link", "stale_problem"])
def test_work_context_refusal_happens_before_model_and_preserves_original_work(
    routed, mutation
):
    e = routed
    with e.repo.connection_scope() as c:
        if mutation == "archived":
            c.execute("UPDATE private_conversation.conversations SET archived_at=now()")
        elif mutation == "missing_link":
            c.execute("DELETE FROM private_conversation.links")
        else:
            state = copy.deepcopy(e.work_state)
            state["problem"]["digest"] = "0" * 64
            c.execute(
                "UPDATE private_conversation.journeys SET state=%s", (Jsonb(state),)
            )
        before = c.execute(
            "SELECT version,state FROM private_conversation.journeys"
        ).fetchall()
    response = e.route_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.route_headers,
        json={
            "content": "你好",
            "idempotencyKey": "refused-route",
            "conversationId": e.conv,
            "conversationMessageId": e.message,
            "conversationRouting": True,
        },
    )
    assert response.status_code >= 400, response.text
    assert e.route_calls == [] and e.dispatches == []
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT version,state FROM private_conversation.journeys"
            ).fetchall()
            == before
        )
