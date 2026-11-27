# ruff: noqa: F401,F811,E501,RUF001 -- Existing disposable owner fixtures and exact facts.
"""Real C1 budget/retention/adoption BFF; controlled model and context input."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from agent_console import conversation_goal_slots as goals
from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_relation_context import (
    current_snapshot,
    sealed_snapshot,
)
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    PreparedProviderRequest,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_assistance_api import _payload, install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.owned_business_admission import OwnedBusinessAdmission
from agent_console.provider_profile_pricing import prepare_revision
from agent_console.understanding_adoption_admission import AdoptionExperience
from agent_console.understanding_adoption_application import (
    UnderstandingAdoptionApplication,
)
from agent_console.understanding_adoption_origin import AdoptionOrigin
from agent_console.understanding_adoption_reader import reader
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from fastapi.testclient import TestClient
from test_conversation_goal_vertical import (
    adopted,
    configure_scope,
    env,
    ordinary,
    owned_ready,
    prepare_source,
    routed,
    setup,
)
from test_local_accounts_postgres import login
from test_native_typed_answer_chain import actual_root_budget


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    monkeypatch.setenv("CONVERSATION_GOAL_SLOTS_ENABLED", "1")
    monkeypatch.setenv("CONVERSATION_GOAL_NATURAL_ENABLED", "1")


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize(
    "owned_ready",
    [dict(prepare_source=prepare_source, configure_scope=configure_scope)],
    indirect=True,
)
@pytest.mark.parametrize(
    "direct", [False, True, "ANSWER_CLARIFICATION", "CURRENT_WORK"]
)
def test_same_c1_independent_result_adopts_once_without_root_reinvoke(
    owned_ready, tmp_path, request, direct
):
    e = owned_ready
    request.addfinalizer(getattr(e, "consumer_cleanup", lambda: None))
    old_app = e.adoption_client.app
    old_owner = old_app.state.understanding_adoption
    authorizer = e.draft.authorization.owner_authorization
    services = [old_owner.routing]
    for revision, schema, marker in (
        (
            "v3-relation-adoption-source",
            "conversation-understanding-output.v3-relation-adoption",
            "a",
        ),
        (
            "v3-relation-adoption-source-answers",
            "conversation-understanding-output.v3-relation-adoption-answers",
            "b",
        ),
        (
            "v4-structured-conversation",
            "conversation-understanding-output.v4-structured",
            "c",
        ),
    ):
        previous = services[-1]
        parent = previous.authorization.context_admission
        service = copy.copy(previous)
        service.profile = replace(
            previous.profile,
            profile_revision_id="profile:independent-" + marker,
            profile_digest=marker * 64,
            adapter_revision=revision,
            output_schema_version=schema,
            maximum_output_tokens=parent.configuration["output_tokens"],
        )
        config = {
            **parent.configuration,
            "profile_revision_id": service.profile.profile_revision_id,
            "profile_digest": service.profile.profile_digest,
            "configuration_digest": marker * 64,
        }
        doc = parent.experience.routing_document.model_dump(mode="json")
        doc.update(
            configuration=config,
            predecessorRoutingPolicyDigest=parent.experience.understanding_policy_digest,
        )
        path = tmp_path / (marker + ".json")
        path.write_text(json.dumps(doc))
        path.chmod(0o600)
        admission = ContextCallAdmission(e.admission.delegation, config)
        admission.experience = AdoptionExperience(e.admission, parent, path, config)
        service.authorization = GrantAdministrationDraftAuthorization(
            e.admission.delegation.grants, authorizer
        )
        service.authorization.context_admission = admission
        services.append(service)
    retained = (*reversed(services[:-1]), e.route)
    e.admission.retained_conversation_relations = tuple(
        s.authorization.context_admission for s in retained
    )
    e.admission.conversation_relation = admission
    e.admission.understanding_adoption = AdoptionOrigin(
        e.admission,
        admission,
        service.profile,
        enabled=True,
        retained=tuple(
            AdoptionOrigin(
                e.admission, s.authorization.context_admission, s.profile, enabled=True
            )
            for s in retained
        ),
    )
    original_path = e.business_owner.path
    policy = e.business_owner.policy.model_dump(mode="json")
    policy.update(
        schemaVersion="owned-business-admission.v3",
        policyVersion="independent-goal-test",
        adoptionPolicyDigest=admission.experience.understanding_policy_digest,
        retainedReadPolicyDigests=[e.business_owner.policy.digest],
        independentGoalProfile={
            "profileRevisionId": service.profile.profile_revision_id,
            "profileDigest": service.profile.profile_digest,
            "adapterRevision": service.profile.adapter_revision,
        },
    )
    path = tmp_path / "independent-business.json"
    path.write_text(json.dumps(policy))
    path.chmod(0o600)
    e.admission.owned_business = e.business_owner = OwnedBusinessAdmission(
        e.admission, path, retained_history_paths=(original_path,)
    )
    with e.repo.connection_scope() as c:
        original = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
            (config["ledger_id"],),
        ).fetchone()["record"]
        goals.migrate(c)
        legacy = c.execute(
            "SELECT version,state FROM private_conversation.journeys WHERE conversation_id=%s",
            (e.conv,),
        ).fetchone()
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=service.profile,
        ledger_id=config["ledger_id"],
        call_cap=original["callCap"],
        total_cost_cap_microusd=original["totalCostCapMicrousd"],
        input_price_microusd_per_million_tokens=0,
        output_price_microusd_per_million_tokens=0,
        profile_pricing_root_digest=_digest(original),
        allowance_id=e.admission.experience.document.allowanceId,
    )
    with budget._connection() as c:
        prepare_revision(c, budget)
    budget.migrate_and_configure()
    request.addfinalizer(budget.close)
    budget.context_admission = admission
    budget.delegation_configuration = config
    service.budget = budget
    service.transport = copy.copy(service.transport)
    before_prepare = service.transport.prepare
    service.transport.prepare = lambda **kw: PreparedProviderRequest(
        before_prepare(**kw).payload,
        ProviderBudgetQuote(10, service.profile.maximum_output_tokens, 0),
    )
    calls = []

    def dispatch(**kw):
        calls.append(kw["invocation_id"])
        snapshot = current_snapshot()
        return ProviderObservation(
            "independent:" + kw["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled",
            result_kind=DraftResultKind.DIRECT_ANSWER
            if direct is True
            else DraftResultKind.NEEDS_CLARIFICATION
            if direct == "ANSWER_CLARIFICATION"
            else DraftResultKind.DRAFT_READY,
            answer="你好。" if direct is True else None,
            clarification_question="想了解哪个概念？"
            if direct == "ANSWER_CLARIFICATION"
            else None,
            title=None
            if direct is True or direct == "ANSWER_CLARIFICATION"
            else "独立资料核对",
            description=None
            if direct is True or direct == "ANSWER_CLARIFICATION"
            else "另一次只读核对，请先选择本次资料。",
            input_tokens=10,
            output_tokens=20,
            conversation_route={
                "relation": "CURRENT_WORK"
                if direct == "CURRENT_WORK"
                else "INDEPENDENT",
                "intent": "ANSWER"
                if direct is True or direct == "ANSWER_CLARIFICATION"
                else "TASK",
                "currentQuestionToken": None,
                "contextDigest": snapshot["contextDigest"],
            },
        )

    service.transport.dispatch = dispatch
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
    records = app.state.conversation_actions.records

    # Controlled minimal neutral input isolates the new adoption transaction.
    # Separate neutral BOUND verification is not claimed by this test.
    def neutral(ctx, chat, message, *_):
        with records.connect() as c:
            records.owned(c, ctx, chat)
        return sealed_snapshot(
            chat,
            message,
            None,
            dict(
                goal=None,
                scope=None,
                stage="FIXED_WORK_BACKGROUND",
                naturalGoalIntentVersion="v1",
                currentQuestion=None,
            ),
        )

    app.state.conversation_relation_reader = neutral
    app.state.understanding_adoption = UnderstandingAdoptionApplication(
        app.state.conversation_actions,
        e.draft,
        service,
        app.state.conversation_draft_service_for,
        neutral,
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
        base = PREFIX + f"/conversations/{e.conv}"
        version = records.head(e.context, e.conv)["conversation"]["version"]
        sent = client.post(
            base + "/messages",
            headers=headers,
            json={
                "content": "你好" if direct else "请另外核对一份资料",
                "idempotencyKey": "natural-message",
                "expectedVersion": version,
            },
        )
        assert sent.status_code == 200, sent.text
        message = sent.json()["result"]["identity"]
        response = client.post(
            PREFIX + "/draft-assistance/invocations",
            headers=headers,
            json={
                "content": "你好" if direct else "请另外核对一份资料",
                "idempotencyKey": "natural-one",
                "conversationId": e.conv,
                "conversationMessageId": message,
                "conversationRouting": True,
            },
        )
        assert response.status_code in (200, 201), response.text
        value = response.json()["result"]
        assert (
            value["state"] == "SUCCEEDED"
            and value["conversationDelivery"]["state"] == "SAVED"
        ), value
        body = {
            "commandId": "adopt-independent",
            "messageId": message,
            "requestKey": "natural-one",
            "expectedConversationVersion": records.head(e.context, e.conv)[
                "conversation"
            ]["version"],
        }
        pending = client.get(
            base + "/goals/adoptions", params={"commandId": body["commandId"]}
        )
        assert (
            pending.status_code == 200
            and pending.json()["result"]["state"] == "NOT_RECORDED"
        ), pending.text
        adopted = client.post(base + "/goals/adoptions", headers=headers, json=body)
        if direct:
            assert (
                adopted.status_code == 409
                and adopted.json()["reasonCode"]
                == "CONVERSATION_GOAL_RESULT_NOT_ADOPTABLE"
            ), adopted.text
        else:
            assert adopted.status_code == 200, adopted.text
            result = adopted.json()["result"]
            assert (
                result["modelDispatched"] is False
                and result["invocationId"] == value["invocationId"]
            )
            assert result["journal"]["state"]["phase"] == "CLARIFY"
            assert (
                result["journal"]["state"]["draft"]["invocationId"]
                == value["invocationId"]
            )
            assert result["journal"]["state"]["draft"].get("inputSource") is None
            replay = client.post(base + "/goals/adoptions", headers=headers, json=body)
            assert replay.status_code == 200 and replay.json()["result"]["replayed"], (
                replay.text
            )
            read = client.get(
                base + "/goals/adoptions", params={"commandId": body["commandId"]}
            )
            assert (
                read.status_code == 200
                and read.json()["result"]["goalId"] == result["goalId"]
            ), read.text
        assert len(calls) == 1
        listing = client.get(base + "/goals")
        assert listing.status_code == 200 and listing.json()["result"]["items"] == [], (
            listing.text
        )
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT version,state FROM private_conversation.journeys WHERE conversation_id=%s",
                    (e.conv,),
                ).fetchone()
                == legacy
            )
            assert c.execute(
                "SELECT count(*) n FROM conversation_goals.slots"
            ).fetchone()["n"] == (0 if direct else 1)
            assert c.execute(
                "SELECT count(*) n FROM conversation_goals.result_adoptions"
            ).fetchone()["n"] == (0 if direct else 1)
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations WHERE invocation_id=%s",
                    (value["invocationId"],),
                ).fetchone()["n"]
                == 1
            )
        if direct:
            return
        # Read-port corruption tests preserve the real immutable audit rows.
        import copy as copy_module

        from agent_console import conversation_goal_origin as origin
        from agent_console.private_conversation import ConversationError

        original_value = service.read(e.context, value["invocationId"]).invocation
        with records.connect() as c:

            class CorruptRead:
                def __init__(self, needle, field):
                    self.needle, self.field = needle, field

                def execute(self, sql, *args, **kwargs):
                    result = c.execute(sql, *args, **kwargs)
                    if self.needle not in str(sql):
                        return result
                    row = copy_module.deepcopy(result.fetchone())
                    assert row is not None
                    row[self.field] = "wrong-persistent-column"
                    return N(fetchone=lambda: row)

            for field in (
                "tenant_id",
                "security_domain",
                "conversation_id",
                "invocation_id",
                "goal_id",
                "owner_id",
                "message_id",
                "command_key",
                "request_digest",
            ):
                with pytest.raises(ConversationError):
                    origin.validate(
                        CorruptRead(
                            "SELECT * FROM conversation_goals.result_adoptions", field
                        ),
                        e.context,
                        original_value,
                        e.business_owner.policy,
                    )
            for field in (
                "tenant_id",
                "security_domain",
                "conversation_id",
                "goal_id",
                "owner_id",
                "root_message_id",
                "command_key",
                "request_digest",
            ):
                with pytest.raises(ConversationError):
                    origin.validate(
                        CorruptRead("SELECT s.* FROM conversation_goals.slots", field),
                        e.context,
                        original_value,
                        e.business_owner.policy,
                    )
            assert (
                origin.validate(c, e.context, original_value, e.business_owner.policy)[
                    "record_digest"
                ]
                == result["adoptionDigest"]
            )
        # A genuine later user source answer uses the existing understanding
        # question owner. The first response is adopted, never invoked again.
        from agent_console.conversation_source_access import ConversationSourceAccess
        from agent_console.conversation_source_input import source_reader

        automation = N(
            bound_app=lambda call: N(
                scope=lambda p: N(
                    namespace=p.tenant_id, security_domain=p.security_domain
                )
            )
        )
        app.state.conversation_relation_reader = reader(
            neutral, records, e.draft, service, retained=retained
        )
        source = source_reader(
            automation,
            authorizer,
            records,
            adoption=True,
            owned_access=ConversationSourceAccess(
                automation, authorizer, records, e.draft
            ),
        )
        app.state.conversation_adoption_source_input = source
        app.state.understanding_adoption.reader = app.state.conversation_relation_reader

        def source_metadata(*args, **kwargs):
            raw = source(*args, **kwargs)
            if raw is None:
                return None
            content = json.loads(raw)
            return {
                k: content[k]
                for k in ("source", "sourceContentDigest", "sourceSchema", "name")
            }

        app.state.understanding_adoption.source_reader = source_metadata
        goal = result["goalId"]
        state = {
            **result["journal"]["state"],
            "source": e.business_result["inputSource"],
        }
        saved = client.post(
            base + f"/goals/{goal}/journey",
            headers=headers,
            json={"expectedVersion": result["journal"]["version"], "state": state},
        )
        assert saved.status_code == 200, saved.text
        reply = client.post(
            base + "/messages",
            headers=headers,
            json={
                "content": "确认只读检查这份资料",
                "idempotencyKey": "independent-source-answer",
                "goalId": goal,
                "expectedVersion": records.head(e.context, e.conv)["conversation"][
                    "version"
                ],
            },
        )
        assert reply.status_code == 200, reply.text
        reply_id = reply.json()["result"]["identity"]

        def source_dispatch(**kw):
            calls.append(kw["invocation_id"])
            current = current_snapshot()
            assert current["target"]["kind"] == "UNDERSTANDING"
            return ProviderObservation(
                "source:" + kw["invocation_id"],
                ObservationState.SUCCEEDED,
                correlation="controlled",
                result_kind=DraftResultKind.DRAFT_READY,
                title="独立资料核对",
                description="只读检查本次明确选定的资料。",
                input_tokens=10,
                output_tokens=20,
                conversation_route={
                    "relation": "CURRENT_QUESTION",
                    "currentQuestionToken": current["currentQuestionToken"],
                    "contextDigest": current["contextDigest"],
                },
            )

        service.transport.dispatch = source_dispatch
        response = client.post(
            PREFIX + "/draft-assistance/invocations",
            headers=headers,
            json={
                "content": "确认只读检查这份资料",
                "idempotencyKey": "independent-source-answer",
                "conversationId": e.conv,
                "conversationMessageId": reply_id,
                "conversationRouting": True,
            },
        )
        assert response.status_code in (200, 201), response.text
        continued = response.json()["result"]
        assert (
            continued["state"] == "SUCCEEDED"
            and continued["resultKind"] == "DRAFT_READY"
        ), continued
        adopted = client.post(
            base + f"/understanding-results/{reply_id}/adoption",
            headers=headers,
            json={"requestKey": "independent-source-answer"},
        )
        assert adopted.status_code == 200, adopted.text
        assert len(calls) == 2 and len(set(calls)) == 2
        saved = client.post(
            base + f"/goals/{goal}/journey",
            headers=headers,
            json={
                "expectedVersion": saved.json()["result"]["version"],
                "state": {**state, "phase": "CREATE", "draft": continued},
            },
        )
        assert saved.status_code == 200, saved.text
        e.business_result = continued
        e.business_model_call_count = len(e.calls)
        from test_owned_business_admission import owned_created

        creator = owned_created.__wrapped__(e, N(param=None))
        try:
            next(creator)
            assert e.created["revision"]["title"] == continued["draft"]["title"]
            assert len(calls) == 2
            from test_owned_business_consumer_chain import (
                test_same_owned_problem_confirms_prepares_and_worker_reads,
            )

            test_same_owned_problem_confirms_prepares_and_worker_reads(
                e, tmp_path, request
            )
            assert len(calls) == 2
            with e.repo.connection_scope() as c:
                assert (
                    c.execute(
                        "SELECT version,state FROM private_conversation.journeys WHERE conversation_id=%s",
                        (e.conv,),
                    ).fetchone()
                    == legacy
                )
            listing = client.get(base + "/goals")
            assert listing.status_code == 200 and [
                v["goalId"] for v in listing.json()["result"]["items"]
            ] == [goal], listing.text
        finally:
            creator.close()
