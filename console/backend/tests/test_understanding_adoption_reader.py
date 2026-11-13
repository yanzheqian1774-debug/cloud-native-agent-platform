"""Real-session initial snapshot reads; model output is controlled, never live."""

# ruff: noqa: F401,F811 -- Shared isolated fixtures.
from types import SimpleNamespace as NS

import pytest
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    ProviderObservation,
)
from agent_console.private_conversation import ConversationError
from agent_console.understanding_adoption_reader import reader
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_local_accounts_postgres import setup
from test_owned_conversation_bff import ordinary


def initial(e):
    calls = []

    def dispatch(**kwargs):
        calls.append(kwargs["invocation_id"])
        return ProviderObservation(
            "fixture:" + kwargs["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled-initial-question",
            result_kind=DraftResultKind.NEEDS_CLARIFICATION,
            clarification_question="请确认需要检查的环境。",
            input_tokens=10,
            output_tokens=20,
        )

    e.draft.transport.dispatch = dispatch
    response = e.post(
        "/draft-assistance/invocations",
        {
            "content": "你好",
            "idempotencyKey": "initial-question",
            "conversationId": e.conv,
            "conversationMessageId": e.message,
        },
    )
    assert response.status_code in (200, 201), response.text
    value = response.json()["result"]
    assert value["conversationDelivery"]["state"] == "SAVED", value
    state = {"phase": "CLARIFY", "key": "original-work", "draft": value}
    saved = e.post(
        f"/conversations/{e.conv}/journey", {"expectedVersion": 0, "state": state}
    )
    assert saved.status_code == 200, saved.text
    records = e.client.app.state.conversation_actions.records
    read = reader(
        lambda *_: pytest.fail("unexpected existing-work fallback"),
        records,
        e.draft,
        None,
    )
    return value, state, calls, read


def test_initial_reader_uses_exact_saved_owner_question_without_advancing_head(
    ordinary,
):
    e = ordinary
    value, _state, calls, read = initial(e)
    result = read(e.context, e.conv, e.message, e.draft)
    assert result["input"]["currentQuestion"] == "请确认需要检查的环境。"
    assert result["input"]["goal"] == "你好"
    assert result["input"]["currentQuestionType"] == "UNDERSTANDING"
    assert result["target"]["invocationId"] == value["invocationId"]
    assert result["target"]["journalVersion"] == 1
    assert len(calls) == 1
    assert read(e.context, e.conv, e.message, e.draft) == result
    assert len(calls) == 1


def test_initial_reader_rejects_pending_or_error_without_using_old_question(ordinary):
    e = ordinary
    _, state, calls, read = initial(e)
    response = e.post(
        f"/conversations/{e.conv}/journey",
        {"expectedVersion": 1, "state": {**state, "pending": "understanding"}},
    )
    assert response.status_code == 200, response.text
    with pytest.raises(ConversationError, match="CONTEXT_UNAVAILABLE"):
        read(e.context, e.conv, e.message, e.draft)
    assert len(calls) == 1
