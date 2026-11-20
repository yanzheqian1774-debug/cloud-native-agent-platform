"""Canonical bridge retains persisted intent identity and strict claim gates."""

from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from agent_console.conversation_actions import original_action
from agent_console.draft_assistance_api import BeginDraftAssistance
from agent_console.private_conversation import ConversationError, digest
from test_conversation_actions import create, journey, post, prepare  # noqa: F401
from test_private_conversation import database  # noqa: F401


@pytest.mark.parametrize("explicit", [False, True])
def test_persisted_default_intent_claim_keeps_original_digest(journey, explicit):  # noqa: F811
    j = journey
    conversation = create(j)
    payload = {"idempotencyKey": str(uuid4()), "content": "明确目标"}
    if explicit:
        payload.update(conversationRouting=False, expectedParentVersion=0)
    headers, _ = prepare(j, conversation, "DRAFT", payload)
    intent = headers["X-Conversation-Intent"]

    def stored():
        with psycopg.connect(j.dsn) as c:
            return c.execute(
                "SELECT payload,payload_digest,claimed_at FROM "
                "private_conversation.action_intents WHERE intent_id=%s",
                (intent,),
            ).fetchone()

    before = stored()
    assert before[0]["conversationRouting"] is False
    assert before[0]["expectedParentVersion"] == 0
    assert before[2] is None
    post(j, "/draft-assistance/invocations", payload, headers, 201)
    after = stored()
    assert before[:2] == after[:2]
    assert after[2] is not None
    calls = j.transport.dispatch_count
    post(j, "/draft-assistance/invocations", payload, headers, 409)
    assert j.transport.dispatch_count == calls == 1


@pytest.mark.parametrize(
    "change",
    [
        {"conversationRouting": True},
        {"expectedParentVersion": 1},
        {"content": "changed"},
    ],
)
def test_bridge_never_normalizes_away_changed_intent(change):
    payload = {"idempotencyKey": "original", "content": "original"}
    expected = BeginDraftAssistance.model_validate(payload).model_dump(
        mode="json", exclude_none=True
    )
    calls = []

    def claim(ctx, conversation, identity, action, actual):
        if digest(actual) != digest(expected):
            raise ConversationError("CONVERSATION_INTENT_PAYLOAD_MISMATCH")

    request = SimpleNamespace(
        headers={
            "x-conversation-intent": "intent",
            "x-conversation-id": "conversation",
        },
        app=SimpleNamespace(
            state=SimpleNamespace(conversation_actions=SimpleNamespace(claim=claim))
        ),
    )
    with pytest.raises(ConversationError, match="CONVERSATION_INTENT_PAYLOAD_MISMATCH"):
        original_action(
            request, object(), "DRAFT", {**payload, **change}, lambda: calls.append(1)
        )
    assert calls == []


def test_headerless_bridge_does_not_validate_or_change_invocation():
    request = SimpleNamespace(headers={})
    assert (
        original_action(request, None, "DRAFT", {}, lambda: "unchanged") == "unchanged"
    )
