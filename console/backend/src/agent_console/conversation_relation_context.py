"""Request-local minimal owner snapshot; no client supplied task authority."""

import json
from contextlib import contextmanager
from contextvars import ContextVar

from .draft_assistance import DraftAssistanceError
from .private_conversation import digest

_snapshot = ContextVar("server_current_conversation", default=None)
_goal = ContextVar("server_conversation_goal", default=None)


def current_snapshot():
    return _snapshot.get()


def metadata_for_snapshot(value, *, include_source_branch=True):
    if value is None:
        return None
    metadata = {
        k: value[k]
        for k in (
            "conversationId",
            "messageId",
            "contextDigest",
            "currentQuestionToken",
            "target",
        )
    }
    if value.get("input", {}).get("naturalGoalIntentVersion") == "v1":
        metadata["naturalGoalIntentVersion"] = "v1"
    if value.get("neutralBinding") is not None:
        metadata["neutralBinding"] = value["neutralBinding"]
    if value.get("goalId") is not None:
        metadata["goalId"] = value["goalId"]
    if value.get("failedRetryOf") is not None:
        metadata["failedRetryOf"] = value["failedRetryOf"]
        metadata["failedRetryInputDigest"] = value["failedRetryInputDigest"]
    if include_source_branch:
        current = value.get("input") or {}
        metadata["sourceInputBranch"] = {
            "currentQuestionType": current.get("currentQuestionType"),
            "hasCurrentQuestion": bool(current.get("currentQuestion")),
        }
    return metadata


def current_metadata():
    metadata = metadata_for_snapshot(current_snapshot())
    goal = _goal.get()
    if goal is not None:
        if metadata is not None and any(
            metadata.get(k, v) != v for k, v in goal.items()
        ):
            raise DraftAssistanceError("CONVERSATION_GOAL_BINDING_CHANGED")
        metadata = {**(metadata or {}), **goal}
    return metadata


@contextmanager
def bind_goal(value):
    token = _goal.set(value)
    try:
        yield
    finally:
        _goal.reset(token)


@contextmanager
def bind_snapshot(value):
    token = _snapshot.set(value)
    try:
        yield
    finally:
        _snapshot.reset(token)


def sealed_snapshot(conversation, message, target, current, *, goal_id=None):
    # Only the minimal authorized business input reaches the model. The mapping
    # to owner identifiers remains in non-content invocation metadata.
    fingerprint = digest(
        {"conversationId": conversation, "target": target, "current": current}
    )
    question_token = fingerprint if target is not None else None
    return {
        **({"goalId": goal_id} if goal_id is not None else {}),
        "conversationId": conversation,
        "messageId": message,
        "contextDigest": fingerprint,
        "currentQuestionToken": question_token,
        "target": target,
        "input": {
            "kind": "SERVER_CURRENT_CONVERSATION",
            **current,
            "currentQuestionToken": question_token,
        },
    }


def provider_input():
    value = current_snapshot()
    if value is None:
        raise DraftAssistanceError("CONVERSATION_ROUTING_CONTEXT_REQUIRED")
    return json.dumps(value["input"], ensure_ascii=False, sort_keys=True)


def validated_route(result, request_payload):
    sent = json.loads(request_payload)
    frames = sent.get("input", [])
    if len(frames) != 2:
        raise ValueError("CONVERSATION_ROUTING_CONTEXT_REQUIRED")
    snapshot = json.loads(frames[1]["content"][0]["text"])
    token = result["currentQuestionToken"]
    if result["relation"] == "CURRENT_QUESTION" and (
        snapshot.get("kind") != "SERVER_CURRENT_CONVERSATION"
        or not snapshot.get("currentQuestion")
        or token != snapshot.get("currentQuestionToken")
    ):
        raise ValueError("CONVERSATION_ROUTING_QUESTION_MISMATCH")
    route = {"relation": result["relation"], "currentQuestionToken": token}
    if snapshot.get("naturalGoalIntentVersion") == "v1":
        if snapshot.get("kind") != "SERVER_CURRENT_CONVERSATION" or result.get(
            "intent"
        ) not in {"TASK", "ANSWER"}:
            raise ValueError("CONVERSATION_GOAL_INTENT_INVALID")
        route["intent"] = result["intent"]
    return route
