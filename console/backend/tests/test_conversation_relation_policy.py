"""Successor schema and exact owner routing checks; no real model invocation."""

import copy
import json
from types import SimpleNamespace as NS

import pytest
from agent_console.conversation_relation_context import sealed_snapshot, validated_route
from agent_console.conversation_relation_policy import REVISION, SCHEMA_VERSION
from agent_console.conversation_relation_validation import validated_target
from agent_console.draft_assistance_policy import (
    PolicyValidationError,
    policy_for,
    validate_result,
)
from agent_console.private_conversation import ConversationError


def direct():
    return {
        "kind": "DIRECT_ANSWER",
        "intent": "ANSWER",
        "answer": "你好。",
        "dataNeeds": [],
        "questions": [],
        "understanding": [],
        "title": None,
        "description": None,
        "clarificationQuestion": None,
        "relation": "INDEPENDENT",
        "currentQuestionToken": None,
    }


def reply():
    return {
        **direct(),
        "kind": "CURRENT_QUESTION_ANSWER",
        "intent": "TASK",
        "relation": "CURRENT_QUESTION",
        "currentQuestionToken": "a" * 64,
        "answer": None,
    }


def test_relation_successor_does_not_mutate_published_policy():
    old = policy_for("v3-execution", "conversation-understanding-output.v3-execution")
    before = (old.digest, old.schema, old.instructions)
    new = policy_for(REVISION, SCHEMA_VERSION)
    assert new.digest != old.digest
    schema = new.schema
    schema["properties"]["kind"]["enum"].append("INVALID")
    assert "INVALID" not in new.schema["properties"]["kind"]["enum"]
    assert (old.digest, old.schema, old.instructions) == before
    assert validate_result(direct(), new, frozenset()) == []
    assert validate_result(reply(), new, frozenset()) == []
    with pytest.raises(PolicyValidationError):
        validate_result(reply(), old, frozenset())


@pytest.mark.parametrize(
    "mutation",
    [
        {"relation": "CURRENT_QUESTION"},
        {"currentQuestionToken": "b" * 64},
        {"relation": "AMBIGUOUS"},
        {"relation": "NEW_SCOPE"},
        {"intent": "TASK"},
    ],
)
def test_direct_answer_cannot_authorize_or_answer_current_question(mutation):
    with pytest.raises(PolicyValidationError):
        validate_result(
            {**direct(), **mutation}, policy_for(REVISION, SCHEMA_VERSION), frozenset()
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"currentQuestionToken": None},
        {"currentQuestionToken": "not-a-token"},
        {"answer": "rewritten response"},
        {"intent": "ANSWER"},
        {"relation": "INDEPENDENT"},
        {"questions": ["other question"]},
    ],
)
def test_current_question_requires_exact_structural_route(mutation):
    with pytest.raises(PolicyValidationError):
        validate_result(
            {**reply(), **mutation}, policy_for(REVISION, SCHEMA_VERSION), frozenset()
        )


def snapshot():
    return sealed_snapshot(
        "conv",
        "message",
        {
            "kind": "NATIVE",
            "invocationId": "invocation",
            "questionKey": "q",
            "questionDigest": "q-digest",
            "executionDigest": "e",
            "journalVersion": 7,
            "journeyKey": "work",
            "expiresAt": "fixed-owner-expiry",
        },
        {
            "goal": "核对交接",
            "scope": "只读生产环境",
            "currentQuestion": "适用生产还是测试?",
            "stage": "RUNNING",
        },
    )


def test_provider_cannot_invent_question_or_borrow_old_token():
    value = snapshot()
    request = json.dumps(
        {
            "input": [
                {"content": [{"text": "new user message"}]},
                {"content": [{"text": json.dumps(value["input"])}]},
            ]
        }
    )
    answer = {**reply(), "currentQuestionToken": value["currentQuestionToken"]}
    assert validated_route(answer, request)["relation"] == "CURRENT_QUESTION"
    with pytest.raises(ValueError):
        validated_route(reply(), request)
    independent = copy.deepcopy(value["input"])
    independent["currentQuestion"] = None
    request = json.dumps(
        {"input": [{}, {"content": [{"text": json.dumps(independent)}]}]}
    )
    with pytest.raises(ValueError):
        validated_route(answer, request)


@pytest.mark.parametrize(
    "field",
    ["questionKey", "questionDigest", "invocationId", "journalVersion", "expiresAt"],
)
def test_revalidation_rejects_changed_owner_question_version_and_expiry(field):
    original = snapshot()
    route = {
        "relation": "CURRENT_QUESTION",
        "currentQuestionToken": original["currentQuestionToken"],
        "contextDigest": original["contextDigest"],
    }
    invocation = NS(conversation_context=original, conversation_route=route)
    value = {
        "resultKind": "CURRENT_QUESTION_ANSWER",
        "conversationRoute": route,
        "conversationDelivery": {"state": "SAVED"},
    }
    assert validated_target(invocation, value, original) == original["target"]
    changed = copy.deepcopy(original)
    changed["target"][field] = "changed"
    with pytest.raises(ConversationError, match="CONTEXT_CHANGED"):
        validated_target(invocation, value, changed)


def test_unrelated_answer_and_unknown_cannot_consume_active_work():
    original = snapshot()
    route = {
        "relation": "INDEPENDENT",
        "currentQuestionToken": None,
        "contextDigest": original["contextDigest"],
    }
    invocation = NS(conversation_context=original, conversation_route=route)
    value = {
        "resultKind": "DIRECT_ANSWER",
        "conversationRoute": route,
        "conversationDelivery": {"state": "SAVED"},
    }
    unchanged = copy.deepcopy(original)
    assert validated_target(invocation, value, {}) is None
    assert original == unchanged
    value["conversationDelivery"]["state"] = "NOT_COMPLETED"
    with pytest.raises(ConversationError):
        validated_target(invocation, value, {})


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"phase": "CLARIFY"},
        {"phase": "UNDERSTAND", "problem": {"business_problem_id": "old"}},
        {"phase": "CLARIFY", "problem": {"business_problem_id": "old"}},
    ],
)
@pytest.mark.parametrize("application", [NS(), NS(state=None), NS(state=NS())])
def test_initial_understanding_cannot_enter_existing_work_profile(
    monkeypatch, state, application
):
    from agent_console import conversation_relation_reader as module

    monkeypatch.setattr(module, "_journal", lambda *_: {"version": 1, "state": state})

    class ForbiddenOwner:
        def execute(self, *args, **kwargs):
            pytest.fail("stage rejection must precede all work owner reads")

    read = module.reader(application, ForbiddenOwner(), NS(), NS(records=NS()))
    with pytest.raises(ConversationError, match="CONVERSATION_ROUTING_WORK_REQUIRED"):
        read(NS(), "conversation", "message", NS())


def test_configured_focus_denial_does_not_fall_back_to_legacy_journal(monkeypatch):
    from agent_console import conversation_relation_reader as module

    def forbidden(*args, **kwargs):
        pytest.fail("denied focus must not fall back to legacy work")

    def denied(*args, **kwargs):
        raise ConversationError("CONVERSATION_SOURCE_UNAVAILABLE", 403)

    monkeypatch.setattr(module, "_journal", forbidden)
    application = NS(state=NS(fixed_cycle_focus_reader=denied))
    read = module.reader(application, NS(execute=forbidden), NS(), NS(records=NS()))
    with pytest.raises(ConversationError, match="CONVERSATION_SOURCE_UNAVAILABLE"):
        read(NS(), "conversation", "message", NS())


def test_configured_focus_remains_exact_read_only_snapshot(monkeypatch):
    from agent_console import conversation_relation_reader as module

    def forbidden(*args, **kwargs):
        pytest.fail("resolved focus must not invoke the legacy work reader")

    calls = []
    observation = {"contentComplete": True, "outputs": []}

    def focus(context, conversation, *, message_id):
        calls.append((context, conversation, message_id))
        return {}, observation

    monkeypatch.setattr(module, "_journal", forbidden)
    application = NS(state=NS(fixed_cycle_focus_reader=focus))
    read = module.reader(application, NS(execute=forbidden), NS(), NS(records=NS()))
    context = NS()
    value = read(context, "conversation", "message", NS())
    assert calls == [(context, "conversation", "message")]
    assert value["target"] is None and value["currentQuestionToken"] is None
    assert value["input"]["currentQuestion"] is None
    assert value["input"]["fixedCycleObservation"] == observation
