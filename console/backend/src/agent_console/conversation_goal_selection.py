# ruff: noqa: E501 -- Existing journal schema is preserved exactly.
"""Resolve journal from immutable message association, never current-tab state."""

from . import conversation_goal_slots as goals
from .private_conversation import ConversationError


def journal_for_message(
    c, records, ctx, conversation, message, *, lock=False, expected_goal=None
):
    chat = records.owned(c, ctx, conversation, lock=lock)
    goals.require(
        chat["owner_id"] == ctx.principal_id and not chat["archived_at"],
        "CONVERSATION_GOAL_NOT_AVAILABLE",
    )
    original = c.execute(
        "SELECT author_id FROM private_conversation.messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
        (*records.scope(ctx), conversation, message),
    ).fetchone()
    goals.require(
        original and original["author_id"] == ctx.principal_id,
        "CONVERSATION_GOAL_MESSAGE_INVALID",
    )
    selected = goals.message_goal(c, records, ctx, conversation, message)
    if expected_goal is not None and selected != expected_goal:
        raise ConversationError("CONVERSATION_GOAL_BINDING_CHANGED", 409)
    if selected is not None:
        return selected, {
            **goals.read(c, records, ctx, conversation, selected, lock=lock),
            "goalId": selected,
        }
    row = c.execute(
        "SELECT version,state FROM private_conversation.journeys WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s"
        + (" FOR UPDATE" if lock else ""),
        (*records.scope(ctx), conversation),
    ).fetchone()
    return None, row or {"version": 0, "state": None}


def goal_for_invocation(c, ctx, invocation):
    metadata = invocation.conversation_context or {}
    if metadata.get("goalId") is not None:
        return metadata["goalId"]
    from .conversation_goal_origin import result_identity, saved
    from .owned_business_result_link import same_result_after_problem_link

    adopted = saved(c, ctx, invocation.invocation_id)
    if adopted is None:
        return None
    record = adopted["record"]
    goals.require(
        record["result"] == result_identity(invocation)
        and record["conversationId"] == metadata.get("conversationId")
        and record["messageId"] == metadata.get("messageId")
        and same_result_after_problem_link(
            c, ctx, invocation, record["aggregateVersion"], invocation.problem_id
        ),
        "CONVERSATION_GOAL_ADOPTION_CHANGED",
    )
    return record["goalId"]


def journal_for_invocation(c, records, ctx, invocation, *, lock=False):
    metadata = invocation.conversation_context or {}
    goals.require(
        invocation.initiating_principal_id == ctx.principal_id,
        "CONVERSATION_GOAL_SUBJECT_CHANGED",
    )
    conversation, message = metadata.get("conversationId"), metadata.get("messageId")
    goals.require(conversation and message, "CONVERSATION_GOAL_INPUT_REQUIRED")
    expected = goal_for_invocation(c, ctx, invocation)
    selected, journal = journal_for_message(
        c,
        records,
        ctx,
        conversation,
        message,
        lock=lock,
        expected_goal=expected,
    )
    # Old metadata must not acquire a newly associated goal after its original call.
    if selected != expected:
        raise ConversationError("CONVERSATION_GOAL_BINDING_CHANGED", 409)
    return selected, journal


def require_claim_binding(c, invocation):
    """Claim-time fence; call before other per-context locks on new draft claims."""
    metadata = invocation.conversation_context or {}
    conversation, message = metadata.get("conversationId"), metadata.get("messageId")
    if not conversation or not message:
        from .conversation_experience_admission import _binding

        binding = _binding.get()
        if binding is not None:
            conversation, message = binding[:2]
    if not conversation or not message:
        if metadata.get("goalId") is not None:
            raise ConversationError("CONVERSATION_GOAL_INPUT_REQUIRED", 409)
        return
    if not c.execute("SELECT to_regclass('conversation_goals.messages') t").fetchone()[
        "t"
    ]:
        if metadata.get("goalId") is not None:
            raise ConversationError("CONVERSATION_GOALS_UNAVAILABLE", 409)
        return
    scope = (invocation.scope.namespace, invocation.scope.security_domain, conversation)
    owned = c.execute(
        "SELECT owner_id,archived_at FROM private_conversation.conversations WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR UPDATE",
        scope,
    ).fetchone()
    goals.require(
        owned
        and owned["owner_id"] == invocation.initiating_principal_id
        and owned["archived_at"] is None,
        "CONVERSATION_GOAL_NOT_AVAILABLE",
    )
    mapped = c.execute(
        "SELECT goal_id FROM conversation_goals.messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
        (*scope, message),
    ).fetchone()
    goals.require(
        (mapped["goal_id"] if mapped else None) == metadata.get("goalId"),
        "CONVERSATION_GOAL_BINDING_CHANGED",
    )
    previous_claims = c.execute(
        "SELECT invocation_id,goal_id FROM conversation_goals.claimed_messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
        (*scope, message),
    ).fetchall()
    if previous_claims and metadata.get("goalId") is not None:
        # Ordinary replay returned the original claim before reaching this port.
        # Only the separate existing settled-failure owner can validate a fresh
        # successor; an UNKNOWN or a different request key is never a retry.
        goals.require(
            len(previous_claims) == 1
            and metadata.get("failedRetryOf") == previous_claims[0]["invocation_id"]
            and metadata.get("goalId") == previous_claims[0]["goal_id"],
            "CONVERSATION_GOAL_MESSAGE_ALREADY_CLAIMED",
        )
    if invocation.predecessor_invocation_id is not None:
        from .draft_assistance_postgres import PostgresDraftAssistanceRepository

        predecessor = PostgresDraftAssistanceRepository._latest(
            c, invocation.scope, invocation.predecessor_invocation_id
        )
        goals.require(
            predecessor is not None
            and predecessor.context_id == invocation.context_id
            and predecessor.initiating_principal_id
            == invocation.initiating_principal_id
            and (predecessor.conversation_context or {}).get("goalId")
            == metadata.get("goalId"),
            "CONVERSATION_GOAL_PREDECESSOR_CHANGED",
        )
    c.execute(
        "INSERT INTO conversation_goals.claimed_messages VALUES(%s,%s,%s,%s,%s,%s)",
        (*scope, message, invocation.invocation_id, metadata.get("goalId")),
    )


class _OwnedScope:
    """Same-connection owner port; no connection pool or administrator bypass."""

    @staticmethod
    def scope(ctx):
        return ctx.scope.tenant_id, ctx.scope.security_domain

    def owned(self, c, ctx, conversation, lock=False):
        row = c.execute(
            "SELECT * FROM private_conversation.conversations WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND owner_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (*self.scope(ctx), conversation, ctx.principal_id),
        ).fetchone()
        goals.require(
            row and row["schema_version"] == 1, "CONVERSATION_GOAL_NOT_AVAILABLE"
        )
        return row


PORT = _OwnedScope()


def legacy_journal(c, ctx, conversation, *, lock=False):
    return c.execute(
        "SELECT version,state FROM private_conversation.journeys WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s"
        + (" FOR UPDATE" if lock else ""),
        (*PORT.scope(ctx), conversation),
    ).fetchone()


def selected_journal(
    c,
    ctx,
    conversation,
    *,
    message_id=None,
    invocation=None,
    context_record=None,
    lock=False,
):
    """Exact saved input chooses a journal; missing explicit bindings never fall back."""
    if invocation is not None:
        metadata = invocation.conversation_context or {}
        if goal_for_invocation(c, ctx, invocation) is not None:
            goals.require(metadata.get("conversationId") == conversation)
            return journal_for_invocation(c, PORT, ctx, invocation, lock=lock)[1]
        # Older immutable invocations keep their original default journal.
        return legacy_journal(c, ctx, conversation, lock=lock)
    if context_record is not None:
        goals.require(context_record.get("conversation_id") == conversation)
        message_id = context_record.get("first_user_message_id")
    if message_id is not None:
        selected = goals.message_goal(c, PORT, ctx, conversation, message_id)
        if selected is not None:
            return journal_for_message(
                c,
                PORT,
                ctx,
                conversation,
                message_id,
                lock=lock,
                expected_goal=selected,
            )[1]
    return legacy_journal(c, ctx, conversation, lock=lock)


def journal_relation(c):
    """Observation-only union. Callers retain original per-work authorization."""
    if not c.execute("SELECT to_regclass('conversation_goals.journals') t").fetchone()[
        "t"
    ]:
        return "private_conversation.journeys"
    goals.require_schema(c)
    return "(SELECT tenant_id,security_domain,conversation_id,version,state FROM private_conversation.journeys UNION ALL SELECT tenant_id,security_domain,conversation_id,version,state FROM conversation_goals.journals)"


def invocation_journal(c, ctx, conversation, invocation_id, *, lock=False):
    from .draft_assistance import DraftScope
    from .draft_assistance_postgres import PostgresDraftAssistanceRepository

    value = PostgresDraftAssistanceRepository._latest(
        c, DraftScope.from_context(ctx), invocation_id
    )
    goals.require(
        value is not None and value.initiating_principal_id == ctx.principal_id
    )
    return selected_journal(c, ctx, conversation, invocation=value, lock=lock), value
