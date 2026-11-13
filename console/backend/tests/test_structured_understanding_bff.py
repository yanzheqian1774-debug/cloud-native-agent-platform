"""Real isolated conversation/adoption owners with actual prepare/SSE decoder.

The HTTPS socket and usage ledger are controlled fixtures; real budget readers
are separately covered by test_structured_successor_budget. No provider call.
"""

# ruff: noqa: F401,F811 -- Reuse disposable PG fixtures.
import copy
import json
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_relation_context import current_snapshot
from agent_console.draft_assistance_api import _payload, install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.structured_understanding_wire import REVISION, VERSION
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
from fastapi.testclient import TestClient
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_structured_understanding_adapter import exchange, prepared
from test_structured_understanding_wire import draft
from test_understanding_adoption_bff import adopted, answer
from test_understanding_adoption_source import select


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize("withdraw", [False, True, "failed_predecessor"])
def test_same_chat_new_wire_adopts_once_and_keeps_old_reader(
    adopted, prepared, tmp_path, monkeypatch, withdraw
):
    e = adopted
    prior_failure = None
    if withdraw == "failed_predecessor":
        from test_conversation_understanding_failure import failed

        prior_failure = failed(e)
        selected = None
    else:
        selected = select(e)
    old_app = e.adoption_client.app
    old_owner = old_app.state.understanding_adoption
    old = old_owner.routing
    authorizer = e.draft.authorization.owner_authorization

    def successor(previous, revision, schema, name):
        service = copy.copy(previous)
        service.profile = replace(
            previous.profile,
            profile_revision_id="profile:" + name,
            profile_digest=name[0] * 64,
            adapter_revision=revision,
            output_schema_version=schema,
        )
        parent = previous.authorization.context_admission
        config = {
            **parent.configuration,
            "profile_revision_id": service.profile.profile_revision_id,
            "profile_digest": service.profile.profile_digest,
            "configuration_digest": name[-1] * 64,
        }
        document = parent.experience.routing_document.model_dump(mode="json")
        document.update(
            configuration=config,
            predecessorRoutingPolicyDigest=parent.experience.understanding_policy_digest,
        )
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(document))
        path.chmod(0o600)
        admission = ContextCallAdmission(e.admission.delegation, config)
        admission.experience = AdoptionExperience(e.admission, parent, path, config)
        service.authorization = GrantAdministrationDraftAuthorization(
            e.admission.delegation.grants, authorizer
        )
        service.authorization.context_admission = admission
        return service

    source = successor(
        old,
        "v3-relation-adoption-source",
        "conversation-understanding-output.v3-relation-adoption",
        "aaa",
    )
    typed = successor(
        source,
        "v3-relation-adoption-source-answers",
        "conversation-understanding-output.v3-relation-adoption-answers",
        "bbb",
    )
    service = successor(typed, REVISION, VERSION, "ccc")
    retained = (typed, source, old, e.route)
    e.admission.retained_conversation_relations = tuple(
        s.authorization.context_admission for s in retained
    )
    e.admission.conversation_relation = service.authorization.context_admission
    transport = prepared.transport
    service.profile = replace(service.profile, adapter_id=prepared.profile.adapter_id)
    transport.configuration = replace(
        transport.configuration,
        maximum_output_tokens=service.profile.maximum_output_tokens,
        total_timeout_seconds=service.profile.total_timeout_seconds,
    )
    service.transport = transport
    observations = []

    def dispatch(**kwargs):
        snapshot = current_snapshot()
        value = draft()
        value["currentQuestionToken"] = snapshot["currentQuestionToken"]
        payload = json.loads(kwargs["request"].payload)
        sealed = json.loads(payload["input"][-1]["content"][0]["text"])
        messages = sealed["serverUserMessages"]
        for item in value["understanding"].values():
            if isinstance(item, dict):
                item["sourceRefs"] = [messages[0]["id"]]
        observation = exchange(
            monkeypatch,
            NS(
                transport=transport,
                request=kwargs["request"],
                profile=kwargs["profile"],
            ),
            {"result": value},
        )
        observations.append(observation)
        return observation

    transport.dispatch = dispatch
    app = create_workbench_bff(
        e.routing_sessions,
        authorizer,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(),
        conversation_database_url=e.repo.pool.conninfo,
        route_installers=(
            install_draft_assistance_routes(
                e.draft, service, retained_routing_services=retained
            ),
        ),
    )
    app.state.conversation_relation_reader = reader(
        lambda *_: pytest.fail("work fallback"),
        app.state.conversation_actions.records,
        e.draft,
        service,
        retained=retained,
    )
    app.state.conversation_adoption_source_input = (
        old_app.state.conversation_adoption_source_input
    )
    app.state.understanding_adoption = UnderstandingAdoptionApplication(
        app.state.conversation_actions,
        e.draft,
        service,
        app.state.conversation_draft_service_for,
        app.state.conversation_relation_reader,
        old_owner.source_reader,
        _payload,
        retained=retained,
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
        historical = client.get(
            PREFIX + f"/conversations/{e.conv}/understanding-results/{e.message}",
            params={"requestKey": "old-c1"},
        )
        assert historical.status_code == 200, historical.text
        assert historical.json()["result"]["invocationId"] == e.old_c1["invocationId"]
        assert historical.json()["result"]["answer"] == "你好。"
        request_key = "wire-once"
        if prior_failure is not None:
            from test_conversation_understanding_failure import body

            listing = client.get(
                PREFIX + f"/conversations/{e.conv}/understanding-failures"
            )
            assert listing.status_code == 200, listing.text
            item = listing.json()["result"]["items"][0]
            assert item["continuationEligible"], listing.text
            assert item["invocationId"] == prior_failure[1]["invocationId"]
            message = item["messageId"]
            request_key = item["successorRequestKey"]
            request_body = body(e, item)
        else:
            head = client.get(PREFIX + f"/conversations/{e.conv}/head").json()["result"]
            sent = client.post(
                PREFIX + f"/conversations/{e.conv}/messages",
                headers=headers,
                json={
                    "content": "生产环境",
                    "idempotencyKey": "wire-message",
                    "expectedVersion": head["conversation"]["version"],
                },
            )
            assert sent.status_code == 200, sent.text
            message = sent.json()["result"]["identity"]
            envelope = {
                **prepared.envelope,
                "messages": [{"id": "user:" + message, "text": "生产环境"}],
            }
            request_body = {
                "content": json.dumps(envelope),
                "idempotencyKey": request_key,
                "conversationId": e.conv,
                "conversationMessageId": message,
                "conversationRouting": True,
            }
        response = client.post(
            PREFIX + "/draft-assistance/invocations", headers=headers, json=request_body
        )
        assert response.status_code in (200, 201), response.text
        result = response.json()["result"]
        path = f"/conversations/{e.conv}/understanding-results/{message}/adoption"
        assert result["state"] == "SUCCEEDED", result
        if withdraw is True:
            from agent_console.grant_administration_application import (
                GrantRevocationCommand,
            )
            from agent_console.workbench_prepared_resources import reference

            with e.repo.connection_scope() as c:
                grant = c.execute(
                    "SELECT grant_id FROM authorization_admin.grants "
                    "WHERE subject_principal_id=%s AND owner='KNOWLEDGE' "
                    "AND action='READ_RESOURCE' AND exact_resource=%s",
                    (
                        e.context.principal_id,
                        reference(
                            "knowledge",
                            selected["resource_id"],
                            selected["revision_id"],
                        ),
                    ),
                ).fetchone()
            e.admission.delegation.grants.revoke_grant(
                e.context,
                GrantRevocationCommand(
                    grant["grant_id"],
                    "TEST_WITHDRAWAL",
                    "wire-withdraw",
                    surrender=True,
                ),
            )
            rejected = client.post(
                PREFIX + path, headers=headers, json={"requestKey": request_key}
            )
            assert rejected.status_code == 403, rejected.text
            assert transport.dispatch_count == 1
            with e.repo.connection_scope() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM draft_assistance.result_adoptions"
                    ).fetchone()["n"]
                    == 0
                )
            return
        response = client.post(
            PREFIX + path, headers=headers, json={"requestKey": request_key}
        )
        assert response.status_code == 200, response.text
        first = response.json()["result"]
        assert (
            first["adoption"]["target"]["original_invocation_id"]
            == e.original["invocationId"]
        )
        for response in (
            client.get(PREFIX + path, params={"requestKey": request_key}),
            client.post(
                PREFIX + path, headers=headers, json={"requestKey": request_key}
            ),
        ):
            assert response.status_code == 200, response.text
            assert response.json()["result"]["adoption"] == first["adoption"]
        assert len(observations) == transport.dispatch_count == 1
        assert len(e.initial_calls) == 1
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_assistance.result_adoptions"
                ).fetchone()["n"]
                == 1
            )
