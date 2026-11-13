"""One-response initial understanding schema; no registered/real model call."""

import json

import pytest
from agent_console.draft_assistance_policy import (
    PolicyValidationError,
    policy_for,
    validate_result,
)
from agent_console.understanding_adoption_policy import REVISION, SCHEMA_VERSION, route
from test_conversation_relation_policy import direct, reply
from test_draft_assistance_policy import result


def full():
    return {
        **result(),
        "answer": None,
        "intent": "TASK",
        "dataNeeds": [],
        "relation": "CURRENT_QUESTION",
        "currentQuestionToken": "a" * 64,
    }


def payload(kind):
    return json.dumps(
        {
            "input": [
                {"content": [{"text": "new original message"}]},
                {
                    "content": [
                        {
                            "text": json.dumps(
                                {
                                    "kind": "SERVER_CURRENT_CONVERSATION",
                                    "currentQuestionType": kind,
                                    "currentQuestion": "Which scope?",
                                    "currentQuestionToken": "a" * 64,
                                }
                            )
                        }
                    ]
                },
            ]
        }
    )


def test_initial_reply_contains_full_understanding_in_same_result():
    value = full()
    validate_result(value, policy_for(REVISION, SCHEMA_VERSION), frozenset({"user:1"}))
    assert route(value, payload("UNDERSTANDING"))["relation"] == "CURRENT_QUESTION"
    with pytest.raises(PolicyValidationError):
        validate_result(
            value,
            policy_for("v3-relation", "conversation-understanding-output.v3-relation"),
            frozenset({"user:1"}),
        )


def test_c1_and_r5_exact_digests_remain_unchanged():
    assert (
        policy_for(
            "v3-relation", "conversation-understanding-output.v3-relation"
        ).digest
        == "37e687a05f72c3fdf92e52d56b8f3d99e85ca31bf28de96b12feed1e96363c96"
    )
    assert (
        policy_for(
            "v3-execution", "conversation-understanding-output.v3-execution"
        ).digest
        == "bcf2df75c2c5d730da10b01f8ee186e5b00fb2ac8190947e4285fb1c68a97aab"
    )


@pytest.mark.parametrize("owner", ["NATIVE", "PLANNING", None])
def test_full_draft_cannot_be_submitted_to_other_question_owner(owner):
    with pytest.raises(ValueError, match="OWNER_RESULT_MISMATCH"):
        route(full(), payload(owner))


def test_initial_label_only_is_rejected_instead_of_calling_model_again():
    with pytest.raises(ValueError, match="OWNER_RESULT_MISMATCH"):
        route(reply(), payload("UNDERSTANDING"))


def test_unrelated_direct_answer_remains_valid_and_does_not_consume_question():
    value = direct()
    assert (
        validate_result(value, policy_for(REVISION, SCHEMA_VERSION), frozenset()) == []
    )
    assert route(value, payload("UNDERSTANDING")) == {
        "relation": "INDEPENDENT",
        "currentQuestionToken": None,
    }


def test_selected_source_frame_requires_exact_server_attachment_kind():
    value = json.loads(payload("UNDERSTANDING"))
    value["input"].insert(
        1, {"content": [{"text": json.dumps({"kind": "USER_SOURCE"})}]}
    )
    with pytest.raises(ValueError, match="SOURCE_CONFLICT"):
        route(full(), json.dumps(value))


@pytest.mark.parametrize("kind", ["DRAFT_READY", "NEEDS_DATA", "NEEDS_CLARIFICATION"])
def test_full_result_revalidation_requires_explicit_initial_adoption(kind):
    from types import SimpleNamespace

    from agent_console.conversation_relation_context import sealed_snapshot
    from agent_console.conversation_relation_validation import validated_target
    from agent_console.private_conversation import ConversationError

    current = sealed_snapshot(
        "conversation",
        "message",
        {"kind": "UNDERSTANDING", "invocationId": "original", "journalVersion": 3},
        {
            "goal": "original goal",
            "scope": "production",
            "stage": "CLARIFY",
            "currentQuestion": "Which environment?",
            "currentQuestionType": "UNDERSTANDING",
        },
    )
    route = {
        "relation": "CURRENT_QUESTION",
        "contextDigest": current["contextDigest"],
        "currentQuestionToken": current["currentQuestionToken"],
    }
    original = SimpleNamespace(conversation_context=current, conversation_route=route)
    value = {
        "resultKind": kind,
        "conversationRoute": route,
        "conversationDelivery": {"state": "SAVED"},
    }
    with pytest.raises(ConversationError):
        validated_target(original, value, current)
    assert (
        validated_target(original, value, current, initial_adoption=True)
        == current["target"]
    )
    changed = {**current, "target": {**current["target"], "journalVersion": 4}}
    with pytest.raises(ConversationError):
        validated_target(original, value, changed, initial_adoption=True)
    value["resultKind"] = "CURRENT_QUESTION_ANSWER"
    with pytest.raises(ConversationError):
        validated_target(original, value, current, initial_adoption=True)


@pytest.mark.parametrize(
    "messages",
    [
        [{"id": "user:foreign", "text": "x"}],
        [{"id": "server-message:one", "text": "x"}] * 2,
        [{"id": "server-message:one", "text": ""}],
        [{"id": "server-message:one", "text": "x", "subject": "other"}],
    ],
)
def test_historical_references_accept_only_bounded_server_message_shape(messages):
    from agent_console.understanding_adoption_policy import server_references

    request = json.loads(payload("UNDERSTANDING"))
    frame = request["input"][-1]["content"][0]
    snapshot = json.loads(frame["text"])
    snapshot["serverUserMessages"] = messages
    frame["text"] = json.dumps(snapshot)
    with pytest.raises(ValueError):
        server_references(json.dumps(request))
