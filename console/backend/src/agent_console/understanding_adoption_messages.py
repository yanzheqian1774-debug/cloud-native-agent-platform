"""Bounded real user-message provenance for the same current understanding chain."""

from .draft_assistance import DraftScope
from .draft_assistance_postgres import PostgresDraftAssistanceRepository
from .private_conversation import ConversationError


def user_messages(connection, records, context, conversation, original, lineage, goal):
    identities = {goal}
    pending = [original.invocation_id]
    pending.extend(edge["target"]["original_invocation_id"] for edge in lineage)
    seen = set()
    scope = DraftScope.from_context(context)
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        if len(seen) >= 32:
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_TOO_LARGE", 422)
        seen.add(identity)
        invocation = PostgresDraftAssistanceRepository._latest(
            connection, scope, identity
        )
        if (
            invocation is None
            or invocation.initiating_principal_id != context.principal_id
        ):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
        binding = connection.execute(
            "SELECT 1 FROM authorization_admin.context_call_requests WHERE "
            "tenant_id=%s AND security_domain=%s AND context_id=%s AND subject_id=%s "
            "AND record->>'conversation_id'=%s",
            (
                *records.scope(context),
                invocation.context_id,
                context.principal_id,
                conversation,
            ),
        ).fetchone()
        rows = connection.execute(
            "SELECT facts FROM private_conversation.message_facts WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s AND "
            "facts->>'assistantResponse'='true' "
            "AND facts#>>'{source,invocationId}'=%s LIMIT 2",
            (*records.scope(context), conversation, identity),
        ).fetchall()
        if not binding or len(rows) != 1:
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
        facts = rows[0]["facts"]
        if (
            facts.get("invokedBy") != context.principal_id
            or facts.get("source")
            != {
                "kind": "DRAFT",
                "invocationId": identity,
                "contextId": invocation.context_id,
                "turnId": invocation.turn_id,
                "turnVersion": invocation.turn_version,
            }
            or not isinstance(facts.get("userMessageId"), str)
        ):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
        identities.add(facts["userMessageId"])
        if invocation.predecessor_invocation_id:
            pending.append(invocation.predecessor_invocation_id)
    if not 1 <= len(identities) <= 32:
        raise ConversationError("CONVERSATION_ROUTING_CONTEXT_TOO_LARGE", 422)
    rows = connection.execute(
        "SELECT m.message_id,m.content FROM private_conversation.messages m WHERE "
        "m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s "
        "AND m.message_id=ANY(%s) AND m.author_id=%s AND NOT EXISTS "
        "(SELECT 1 FROM private_conversation.message_facts f WHERE "
        "f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain "
        "AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id) "
        "ORDER BY m.sequence",
        (*records.scope(context), conversation, list(identities), context.principal_id),
    ).fetchall()
    if len(rows) != len(identities) or sum(len(r["content"]) for r in rows) > 12000:
        raise ConversationError("CONVERSATION_ROUTING_CONTEXT_TOO_LARGE", 422)
    return [
        {"id": "server-message:" + r["message_id"], "text": r["content"]} for r in rows
    ]
