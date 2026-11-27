"""Real message/root-understanding/admission/CREATE owners; offline provider only."""

# ruff: noqa: F401,F811,E501,RUF001 -- Original dedicated random-database fixtures.
from types import SimpleNamespace

import pytest
from agent_console import conversation_goal_slots as goals
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    ProviderObservation,
)
from agent_console.workbench_bff import PREFIX
from owned_business_consumer_support import configure_scope, prepare_source
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [
    pytestmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [dict(prepare_source=prepare_source, configure_scope=configure_scope)],
        indirect=True,
    ),
]


@pytest.fixture(autouse=True)
def enable_goal_routes(monkeypatch):
    monkeypatch.setenv("CONVERSATION_GOAL_SLOTS_ENABLED", "1")


@pytest.mark.parametrize("direct", [False, True, "NEEDS_DATA"])
def test_new_message_one_root_understanding_creates_in_own_goal(
    owned_ready, tmp_path, request, direct
):
    e = owned_ready
    request.addfinalizer(getattr(e, "consumer_cleanup", lambda: None))
    records = e.client.app.state.conversation_actions.records
    from agent_console.conversation_source_access import ConversationSourceAccess
    from agent_console.conversation_source_input import source_reader

    automation = SimpleNamespace(
        bound_app=lambda call: SimpleNamespace(
            scope=lambda p: SimpleNamespace(
                namespace=p.tenant_id, security_domain=p.security_domain
            )
        )
    )
    authorizer = e.draft.authorization.owner_authorization
    e.client.app.state.conversation_source_input = source_reader(
        automation,
        authorizer,
        records,
        owned_access=ConversationSourceAccess(automation, authorizer, records, e.draft),
    )
    with e.repo.connection_scope() as c:
        goals.migrate(c)
        legacy = c.execute(
            "SELECT version,state FROM private_conversation.journeys WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (*records.scope(e.context), e.conv),
        ).fetchone()
    prefix = f"/conversations/{e.conv}"
    version = records.head(e.context, e.conv)["conversation"]["version"]
    sent = e.post(
        prefix + "/messages",
        {
            "content": "独立核对另一批已授权资料",
            "idempotencyKey": "new-goal-message",
            "expectedVersion": version,
        },
    )
    assert sent.status_code == 200, sent.text
    message = sent.json()["result"]["identity"]
    command = dict(
        commandId="new-goal", messageId=message, expectedConversationVersion=version + 1
    )
    created_slot = e.post(prefix + "/goals", command)
    assert created_slot.status_code == 200, created_slot.text
    goal = created_slot.json()["result"]["goalId"]
    receipt = e.client.get(PREFIX + prefix + "/goals", params={"commandId": "new-goal"})
    assert receipt.status_code == 200 and receipt.json()["result"]["goalId"] == goal
    selected = None if direct else e.business_result["inputSource"]
    state = dict(
        phase="UNDERSTAND",
        key="initial-work",
        userMessageId=message,
        question="独立核对另一批已授权资料",
        source=selected,
        messages=[{"id": "user:" + message, "text": "独立核对另一批已授权资料"}],
    )
    saved = e.post(
        prefix + f"/goals/{goal}/journey", {"expectedVersion": 0, "state": state}
    )
    assert saved.status_code == 200, saved.text
    calls = []

    def dispatch(**kw):
        calls.append(kw["invocation_id"])
        return ProviderObservation(
            "new-goal-result:" + kw["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled",
            result_kind=DraftResultKind.NEEDS_DATA
            if direct == "NEEDS_DATA"
            else DraftResultKind.DIRECT_ANSWER
            if direct
            else DraftResultKind.DRAFT_READY,
            answer="这是已有信息的解释，无需执行新任务。" if direct is True else None,
            data_needs=["请选择已授权资料。"] if direct == "NEEDS_DATA" else None,
            title=None if direct else "独立资料核对",
            description=None
            if direct
            else "只读核对另一批已授权资料，不执行外部变更。",
            input_tokens=10,
            output_tokens=20,
        )

    from dataclasses import replace

    # Shared fixture's root configuration has a placeholder profile digest; the
    # earlier tests only adopted routing output. Bind this new root call's actual
    # snapshot to that exact fixture configuration before any new invocation.
    e.draft.profile = replace(
        e.draft.profile, profile_digest=e.admission.configuration["profile_digest"]
    )
    e.draft.transport.dispatch = dispatch
    payload = dict(
        content=state["question"],
        idempotencyKey="new-goal-understanding",
        conversationId=e.conv,
        conversationMessageId=message,
    )
    response = e.post("/draft-assistance/invocations", payload)
    assert response.status_code in (200, 201), response.text
    result = response.json()["result"]
    assert result.get("conversationDelivery", {}).get("state") == "SAVED", result
    assert result["state"] == "SUCCEEDED" and result["resultKind"] == (
        "NEEDS_DATA"
        if direct == "NEEDS_DATA"
        else "DIRECT_ANSWER"
        if direct
        else "DRAFT_READY"
    ), result
    assert len(calls) == 1
    with e.repo.connection_scope() as c:
        value = e.draft.repository._latest(
            c,
            e.draft.read(e.context, result["invocationId"]).invocation.scope,
            result["invocationId"],
        )
        assert value.conversation_context["goalId"] == goal
        assert value.input_source == selected
    denied = e.post(
        "/draft-assistance/invocations",
        {**payload, "idempotencyKey": "must-not-reinvoke"},
    )
    assert (
        denied.status_code == 409
        and denied.json()["reasonCode"] == "CONVERSATION_GOAL_MESSAGE_ALREADY_CLAIMED"
    ), denied.text
    assert len(calls) == 1
    if direct is True:
        # An optional private dispatch envelope is not a business work entry.
        # The UI lists only real object-bound goals, never chat answers.
        visible_goals = e.client.get(PREFIX + prefix + "/goals")
        assert visible_goals.status_code == 200, visible_goals.text
        assert visible_goals.json()["result"]["items"] == []
        assert visible_goals.json()["result"]["hasMore"] is False
        second_message = e.post(
            prefix + "/messages",
            {
                "content": "另一条全新问题",
                "idempotencyKey": "cross-goal-message",
                "expectedVersion": records.head(e.context, e.conv)["conversation"][
                    "version"
                ],
            },
        )
        assert second_message.status_code == 200, second_message.text
        second_id = second_message.json()["result"]["identity"]
        second_goal = e.post(
            prefix + "/goals",
            {
                "commandId": "second-independent-goal",
                "messageId": second_id,
                "expectedConversationVersion": records.head(e.context, e.conv)[
                    "conversation"
                ]["version"],
            },
        )
        assert second_goal.status_code == 200, second_goal.text
        wrong_parent = e.post(
            "/draft-assistance/invocations",
            {
                "content": "另一条全新问题",
                "idempotencyKey": "cross-goal-parent",
                "conversationId": e.conv,
                "conversationMessageId": second_id,
                "parentContextId": result["contextId"],
                "parentTurnId": result["turnId"],
                "predecessorInvocationId": result["invocationId"],
                "expectedParentVersion": result["turnVersion"],
            },
        )
        assert (
            wrong_parent.status_code == 409
            and wrong_parent.json()["reasonCode"]
            == "CONVERSATION_GOAL_PREDECESSOR_CHANGED"
        ), wrong_parent.text
        assert len(calls) == 1
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT 1 FROM authorization_admin.context_call_objects WHERE context_id=%s AND owner='BUSINESS_PROBLEM'",
                    (result["contextId"],),
                ).fetchone()
                is None
            )
            assert (
                c.execute(
                    "SELECT version,state FROM private_conversation.journeys WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                    (*records.scope(e.context), e.conv),
                ).fetchone()
                == legacy
            )
        return
    journal_version = 1
    if direct == "NEEDS_DATA":
        state = {
            **state,
            "phase": "CLARIFY",
            "draft": result,
            "source": e.business_result["inputSource"],
        }
        saved = e.post(
            prefix + f"/goals/{goal}/journey", {"expectedVersion": 1, "state": state}
        )
        assert saved.status_code == 200, saved.text
        reply = e.post(
            prefix + "/messages",
            {
                "content": "确认，只读核对这份资料",
                "idempotencyKey": "goal-source-answer",
                "expectedVersion": records.head(e.context, e.conv)["conversation"][
                    "version"
                ],
                "goalId": goal,
            },
        )
        assert reply.status_code == 200, reply.text
        reply_id = reply.json()["result"]["identity"]
        before_routes = len(e.calls)
        # Read the real owner projection before dispatch so a failed binding
        # names its original gate rather than being obscured by the HTTP mapper.
        e.adoption_client.app.state.conversation_relation_reader(
            e.context, e.conv, reply_id, e.draft
        )
        response = e.adoption_client.post(
            PREFIX + "/draft-assistance/invocations",
            headers=e.adoption_headers,
            json={
                "content": "确认，只读核对这份资料",
                "idempotencyKey": "goal-source-answer",
                "conversationId": e.conv,
                "conversationMessageId": reply_id,
                "conversationRouting": True,
            },
        )
        assert response.status_code in (200, 201), response.text
        result = response.json()["result"]
        assert (
            result["state"] == "SUCCEEDED" and result["resultKind"] == "DRAFT_READY"
        ), result
        adopted_result = e.adoption_client.post(
            PREFIX + prefix + f"/understanding-results/{reply_id}/adoption",
            headers=e.adoption_headers,
            json={"requestKey": "goal-source-answer"},
        )
        assert adopted_result.status_code == 200, adopted_result.text
        assert len(e.calls) == before_routes + 1 and len(calls) == 1
        e.business_model_call_count = len(e.calls)
        journal_version = 2
    saved = e.post(
        prefix + f"/goals/{goal}/journey",
        {
            "expectedVersion": journal_version,
            "state": {**state, "phase": "CREATE", "draft": result},
        },
    )
    assert saved.status_code == 200, saved.text
    e.business_result = result
    creator = owned_created.__wrapped__(e, SimpleNamespace(param=None))
    try:
        next(creator)
        assert e.created["revision"]["title"] == result["draft"]["title"]
        assert len(calls) == 1
        from test_owned_business_consumer_chain import (
            test_same_owned_problem_confirms_prepares_and_worker_reads,
        )

        test_same_owned_problem_confirms_prepares_and_worker_reads(e, tmp_path, request)
        assert len(calls) == 1
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT version,state FROM private_conversation.journeys WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                    (*records.scope(e.context), e.conv),
                ).fetchone()
                == legacy
            )
            assert (
                goals.read(c, records, e.context, e.conv, goal)["state"]["draft"][
                    "invocationId"
                ]
                == result["invocationId"]
            )
        reread = e.client.get(PREFIX + prefix + f"/goals/{goal}/journey")
        assert reread.status_code == 200 and len(calls) == 1
    finally:
        creator.close()
