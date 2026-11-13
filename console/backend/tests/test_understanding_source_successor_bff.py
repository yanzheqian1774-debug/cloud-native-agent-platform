"""Real isolated owners across old C2/current source profile; controlled model."""

# ruff: noqa: F401,F811 -- Existing isolated PostgreSQL fixtures.
import copy
import json
from dataclasses import replace

import pytest
from agent_console.context_call_admission import ContextCallAdmission
from agent_console.draft_assistance import DraftResultKind
from agent_console.draft_assistance_api import _payload, install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.understanding_adoption_admission import AdoptionExperience
from agent_console.understanding_adoption_application import (
    UnderstandingAdoptionApplication,
)
from agent_console.understanding_adoption_reader import reader
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_prepared_resources import reference
from fastapi.testclient import TestClient
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted, answer
from test_understanding_adoption_source import select


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize("revoke_at", [None, "before_model", "before_adoption"])
def test_selected_old_c2_question_continues_with_exact_successor(
    adopted, tmp_path, revoke_at, *, on_ready=None
):
    e = adopted
    selected = select(e)

    def revoke_source():
        with e.repo.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants "
                "WHERE subject_principal_id=%s AND owner='KNOWLEDGE' "
                "AND action='READ_RESOURCE' AND exact_resource=%s",
                (
                    e.context.principal_id,
                    reference(
                        "knowledge", selected["resource_id"], selected["revision_id"]
                    ),
                ),
            ).fetchone()
        e.admission.delegation.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                "source-successor-withdrawal",
                surrender=True,
            ),
        )

    old_transport = e.adoption_client.app.state.understanding_adoption.routing.transport
    dispatch = old_transport.dispatch

    def needs_data(**kwargs):
        observed = dispatch(**kwargs)
        return (
            replace(
                observed,
                result_kind=DraftResultKind.NEEDS_DATA,
                clarification_question=None,
                data_needs=["资料目前只有名称。请提供正文。"],
            )
            if observed.result_kind is DraftResultKind.NEEDS_CLARIFICATION
            else observed
        )

    old_transport.dispatch = needs_data
    old_path, old_result = answer(e, "old-selected")
    saved = e.adoption_client.post(
        PREFIX + old_path,
        headers=e.adoption_headers,
        json={"requestKey": "old-selected"},
    )
    assert saved.status_code == 200, saved.text
    journal = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/journey").json()[
        "result"
    ]
    journal["state"]["draft"] = saved.json()["result"]["understanding"]
    update = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/journey",
        headers=e.adoption_headers,
        json={"expectedVersion": journal["version"], "state": journal["state"]},
    )
    assert update.status_code == 200, update.text
    old_app = e.adoption_client.app
    old_owner = old_app.state.understanding_adoption
    old_route = old_owner.routing
    previous = old_route.authorization.context_admission
    successor = copy.copy(old_route)
    successor.profile = replace(
        old_route.profile,
        profile_revision_id="profile:source-body",
        profile_digest="1" * 64,
        adapter_revision="v3-relation-adoption-source",
    )
    configuration = {
        **previous.configuration,
        "profile_revision_id": successor.profile.profile_revision_id,
        "profile_digest": successor.profile.profile_digest,
        "configuration_digest": "2" * 64,
    }
    document = previous.experience.routing_document.model_dump(mode="json")
    document.update(
        configuration=configuration,
        predecessorRoutingPolicyDigest=previous.experience.understanding_policy_digest,
    )
    policy = tmp_path / "source-successor.json"
    policy.write_text(json.dumps(document))
    policy.chmod(0o600)
    admission = ContextCallAdmission(e.admission.delegation, configuration)
    admission.experience = AdoptionExperience(
        e.admission, previous, policy, configuration
    )
    authorizer = e.draft.authorization.owner_authorization
    successor.authorization = GrantAdministrationDraftAuthorization(
        e.admission.delegation.grants, authorizer
    )
    successor.authorization.context_admission = admission
    e.admission.retained_conversation_relations = (previous, e.routing_admission)
    e.admission.conversation_relation = admission
    app = create_workbench_bff(
        e.routing_sessions,
        authorizer,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(),
        conversation_database_url=e.repo.pool.conninfo,
        route_installers=(
            install_draft_assistance_routes(
                e.draft, successor, retained_routing_services=(old_route, e.route)
            ),
        ),
    )
    app.state.conversation_relation_reader = reader(
        lambda *_: pytest.fail("unexpected work fallback"),
        app.state.conversation_actions.records,
        e.draft,
        successor,
        retained=(old_route,),
    )
    app.state.conversation_adoption_source_input = (
        old_app.state.conversation_adoption_source_input
    )
    app.state.understanding_adoption = UnderstandingAdoptionApplication(
        app.state.conversation_actions,
        e.draft,
        successor,
        app.state.conversation_draft_service_for,
        app.state.conversation_relation_reader,
        old_owner.source_reader,
        _payload,
        retained=(old_route,),
        source_transaction=authorizer.controller.protected_request,
    )
    secret = login(e.routing_sessions, "reviewer324")
    session, _ = e.routing_sessions.authenticate_session(secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": e.routing_sessions.issue_csrf(session),
    }
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE, secret.value)
        e.adoption_client, e.adoption_headers = client, headers
        before = len(e.calls)
        if revoke_at is None:
            # The reused ordinary-only fixture omits this administrator read
            # prerequisite. Supply its actual generation, not an allow decision.
            authorizer.controller.readiness.generation = (
                e.admission.delegation.grants.generation.generation
            )
            stranger = login(e.routing_sessions, "devadmin")
            stranger_session, _ = e.routing_sessions.authenticate_session(
                stranger.value
            )
            client.cookies.set(SESSION_COOKIE, stranger.value)
            foreign_headers = {
                "origin": "https://testserver",
                "x-csrf-token": e.routing_sessions.issue_csrf(stranger_session),
            }
            foreign = client.post(
                PREFIX + old_path,
                headers=foreign_headers,
                json={"requestKey": "old-selected"},
            )
            assert foreign.status_code in (403, 404), foreign.text
            assert len(e.calls) == before
            client.cookies.set(SESSION_COOKIE, secret.value)
        historical = client.get(
            PREFIX + old_path, params={"requestKey": "old-selected"}
        )
        assert historical.status_code == 200, historical.text
        assert len(e.calls) == before
        if revoke_at == "before_model":
            revoke_source()
            reservations_before = len(e.draft.budget.reservations)
            head = client.get(PREFIX + f"/conversations/{e.conv}/head").json()["result"]
            sent = client.post(
                PREFIX + f"/conversations/{e.conv}/messages",
                headers=headers,
                json={
                    "content": "请使用同一资料继续",
                    "idempotencyKey": "revoked-message",
                    "expectedVersion": head["conversation"]["version"],
                },
            )
            assert sent.status_code == 200, sent.text
            denied = client.post(
                PREFIX + "/draft-assistance/invocations",
                headers=headers,
                json={
                    "content": "请使用同一资料继续",
                    "idempotencyKey": "revoked-request",
                    "conversationId": e.conv,
                    "conversationMessageId": sent.json()["result"]["identity"],
                    "conversationRouting": True,
                },
            )
            assert denied.status_code == 403, denied.text
            assert len(e.calls) == before
            assert len(e.draft.budget.reservations) == reservations_before
            with e.repo.connection_scope() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM draft_assistance.result_adoptions"
                    ).fetchone()["n"]
                    == 1
                )
            return
        e.kind = DraftResultKind.DRAFT_READY
        path, current = answer(e, "same-source-successor")
        if revoke_at == "before_adoption":
            revoke_source()
        result = client.post(
            PREFIX + path, headers=headers, json={"requestKey": "same-source-successor"}
        )
        assert result.status_code == (403 if revoke_at else 200), result.text
        if revoke_at:
            assert len(e.calls) == before + 1
            with e.repo.connection_scope() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM draft_assistance.result_adoptions"
                    ).fetchone()["n"]
                    == 1
                )
            return
        assert current["inputSource"] == old_result["inputSource"]
        assert (
            result.json()["result"]["adoption"]["target"]["original_invocation_id"]
            == old_result["invocationId"]
        )
        refreshed = client.get(
            PREFIX + path, params={"requestKey": "same-source-successor"}
        )
        assert refreshed.status_code == 200, refreshed.text
        assert len(e.calls) == before + 1
        assert len(e.initial_calls) == 1
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_assistance.result_adoptions"
                ).fetchone()["n"]
                == 2
            )
        if on_ready is not None:
            on_ready(e, current, old_route, successor)
