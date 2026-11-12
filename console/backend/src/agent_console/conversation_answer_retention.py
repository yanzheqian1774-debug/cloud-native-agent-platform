"""Retain actual owner-returned understanding content in existing private records.

No client content endpoint, model dispatch, schema change or invocation-log retention.
"""

import json

from .conversation_actions import reference
from .private_conversation import ConversationError, digest

FIELDS = (
    "resultKind",
    "answer",
    "dataNeeds",
    "clarificationQuestion",
    "draft",
    "understanding",
)


def require_target(
    actions, ctx, conversation, message_id, content=None, *, allow_archived=False
):
    with actions.records.connect() as c:
        row = actions.records.owned(c, ctx, conversation)
        if row["archived_at"] and not allow_archived:
            raise ConversationError("CONVERSATION_ARCHIVED")
        message = c.execute(
            "SELECT m.content FROM private_conversation.messages m WHERE "
            "m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s "
            "AND m.message_id=%s AND m.author_id=%s AND NOT EXISTS "
            "(SELECT 1 FROM private_conversation.message_facts f WHERE "
            "f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain "
            "AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id)",
            (*actions.records.scope(ctx), conversation, message_id, ctx.principal_id),
        ).fetchone()
        if not message:
            raise ConversationError("CONVERSATION_REQUEST_MESSAGE_MISMATCH")
        if content is None:
            return
        try:
            envelope = json.loads(content)
        except ValueError:
            envelope = None
        latest = content
        if isinstance(envelope, dict):
            from .draft_assistance_policy import (
                PolicyValidationError,
                conversation_context_references,
            )

            try:
                conversation_context_references(content)
                latest = envelope["messages"][-1]["text"]
            except (PolicyValidationError, KeyError, IndexError, TypeError) as exc:
                raise ConversationError(
                    "CONVERSATION_REQUEST_CONTENT_INVALID", 422
                ) from exc
        previous = (
            envelope.get("previousAssistantResponse")
            if isinstance(envelope, dict)
            else None
        )
        if previous:
            retained = c.execute(
                "SELECT facts FROM private_conversation.message_facts WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                "AND facts->>'assistantResponse'='true' "
                "AND facts#>>'{source,invocationId}'=%s",
                (*actions.records.scope(ctx), conversation, previous["invocationId"]),
            ).fetchone()
            if (
                not retained
                or retained["facts"].get("response", {}).get("answer")
                != previous["answer"]
            ):
                raise ConversationError("CONVERSATION_PREVIOUS_ANSWER_MISMATCH")
            actions.source_read(ctx, retained["facts"]["source"])
        if latest != message["content"]:
            raise ConversationError("CONVERSATION_REQUEST_MESSAGE_MISMATCH")


def retain(actions, ctx, conversation, value, *, request_key, message_id):
    """Only called with the original governed service response, never request JSON."""
    if value["state"] != "SUCCEEDED":
        return {**value, "conversationDelivery": {"state": "NOT_COMPLETED"}}
    source = reference("DRAFT", value)
    observed = actions.source_read(ctx, source)
    if (
        observed["receiptState"] != "SUCCEEDED"
        or observed.get("resultKind") != value["resultKind"]
    ):
        raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
    key = "assistant-response:" + digest(source)
    with actions.records.connect() as c:
        row = actions.records.owned(c, ctx, conversation, True)
        prior = c.execute(
            "SELECT m.message_id,f.facts FROM private_conversation.messages m "
            "JOIN private_conversation.message_facts f USING "
            "(tenant_id,security_domain,conversation_id,message_id) "
            "WHERE m.tenant_id=%s AND m.security_domain=%s "
            "AND m.conversation_id=%s AND m.request_key=%s",
            (*actions.records.scope(ctx), conversation, key),
        ).fetchone()
        response = {field: value.get(field) for field in FIELDS}
        if prior:
            facts = prior["facts"]
            if (
                facts.get("source") != source
                or facts.get("assistantResponse") is not True
                or facts.get("requestKey") != request_key
                or facts.get("userMessageId") != message_id
            ):
                raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
            saved = facts["response"]
            if (
                value.get("reasonCode") != "RESULT_CONTENT_NOT_RETAINED"
                and response != saved
            ):
                raise ConversationError("CONVERSATION_IDEMPOTENCY_CONFLICT")
            return {
                **value,
                **saved,
                "reasonCode": value.get("reasonCode")
                if value.get("reasonCode") != "RESULT_CONTENT_NOT_RETAINED"
                else None,
                "conversationDelivery": {
                    "state": "SAVED",
                    "messageId": prior["message_id"],
                    "replayed": True,
                },
            }
        if row["archived_at"]:
            raise ConversationError("CONVERSATION_ARCHIVED")
        if value.get("reasonCode") == "RESULT_CONTENT_NOT_RETAINED":
            return {**value, "conversationDelivery": {"state": "CONTENT_UNAVAILABLE"}}
        kind = value["resultKind"]
        if kind == "DIRECT_ANSWER":
            content = value.get("answer")
        elif kind == "NEEDS_CLARIFICATION":
            content = value.get("clarificationQuestion")
        elif kind == "NEEDS_DATA":
            needs = value.get("dataNeeds")
            content = "需要以下资料:\n" + "\n".join(needs) if needs else None
        elif kind == "DRAFT_READY":
            draft = value.get("draft") or {}
            content = draft.get("description")
        else:
            raise ConversationError("CONVERSATION_RESULT_INVALID")
        if not isinstance(content, str) or not content.strip() or len(content) > 8000:
            raise ConversationError("CONVERSATION_RESULT_CONTENT_UNAVAILABLE")
        facts = {
            "source": source,
            "assistantResponse": True,
            "state": "SUCCEEDED",
            "response": response,
            "invokedBy": ctx.principal_id,
            "requestKey": request_key,
            "userMessageId": message_id,
        }
        identity = actions.insert(
            c, ctx, row, key, content, "SOURCE", facts, digest(facts)
        )
    # Return SAVED only after the transaction has committed successfully.
    return {
        **value,
        "conversationDelivery": {
            "state": "SAVED",
            "messageId": identity,
            "replayed": False,
        },
    }


def read_retained(actions, ctx, conversation, value, *, request_key, message_id):
    """Read an exact request without dispatch, writes or latest-message fallback."""
    if value["state"] != "SUCCEEDED":
        return {**value, "conversationDelivery": {"state": "NOT_COMPLETED"}}
    source = reference("DRAFT", value)
    actions.source_read(ctx, source)
    with actions.records.connect() as c:
        actions.records.owned(c, ctx, conversation)
        prior = c.execute(
            "SELECT m.message_id,f.facts FROM private_conversation.messages m "
            "JOIN private_conversation.message_facts f USING "
            "(tenant_id,security_domain,conversation_id,message_id) "
            "WHERE m.tenant_id=%s AND m.security_domain=%s "
            "AND m.conversation_id=%s AND m.request_key=%s",
            (
                *actions.records.scope(ctx),
                conversation,
                "assistant-response:" + digest(source),
            ),
        ).fetchone()
    if not prior:
        return {**value, "conversationDelivery": {"state": "CONTENT_UNAVAILABLE"}}
    facts = prior["facts"]
    if (
        facts.get("source") != source
        or facts.get("requestKey") != request_key
        or facts.get("userMessageId") != message_id
        or facts.get("assistantResponse") is not True
    ):
        raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
    return {
        **value,
        **facts["response"],
        "reasonCode": None
        if value.get("reasonCode") == "RESULT_CONTENT_NOT_RETAINED"
        else value.get("reasonCode"),
        "conversationDelivery": {
            "state": "SAVED",
            "messageId": prior["message_id"],
            "replayed": True,
        },
    }
