"""Exact initial-question snapshot for the disabled adoption successor profile."""

import json

from .conversation_relation_context import sealed_snapshot
from .conversation_relation_reader import _journal
from .draft_assistance import DraftInvocationState, DraftResultKind, DraftScope
from .private_conversation import ConversationError, digest


def reader(existing_reader, records, primary, routing, *, retained=()):
    def read(context, conversation, message_id, _service):
        journal = _journal(records, context, conversation, message_id)
        state = journal["state"] or {}
        if state.get("phase") != "CLARIFY":
            existing = existing_reader(context, conversation, message_id, primary)
            owner = (existing.get("target") or {}).get("kind")
            if owner in {"NATIVE", "PLANNING"}:
                current = {
                    k: v
                    for k, v in existing["input"].items()
                    if k not in {"kind", "currentQuestionToken"}
                }
                current["currentQuestionType"] = owner
                return sealed_snapshot(
                    conversation,
                    message_id,
                    existing["target"],
                    current,
                    goal_id=journal.get("goalId"),
                )
            return existing
        if state.get("pending") or state.get("error") or state.get("problem"):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 409)
        identity = (state.get("draft") or {}).get("invocationId")
        raw = primary.repository.get(DraftScope.from_context(context), identity or "")
        if raw is None:
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 409)
        selected = next(
            (
                s
                for s in (primary, routing, *retained)
                if s and s.profile.profile_revision_id == raw.profile_revision_id
            ),
            None,
        )
        if selected is None:
            raise ConversationError("CONVERSATION_ROUTING_SERVICE_UNAVAILABLE", 503)
        response = selected.read(context, identity)
        original = response.invocation
        from .conversation_goal_selection import goal_for_invocation

        with records.connect() as c:
            original_goal = goal_for_invocation(c, context, original)
        if (
            original_goal != journal.get("goalId")
            or original.initiating_principal_id != context.principal_id
            or original.state is not DraftInvocationState.SUCCEEDED
            or not (
                original.result_kind
                in {DraftResultKind.NEEDS_CLARIFICATION, DraftResultKind.NEEDS_DATA}
                or (
                    original.result_kind is DraftResultKind.DRAFT_READY
                    and original.input_source is None
                )
            )
            or original.problem_id is not None
            or selected.repository.get_context_head(original.scope, original.context_id)
            != original
        ):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_CHANGED", 409)
        with records.connect() as c:
            from .understanding_adoption_postgres import read_chain

            records.owned(c, context, conversation)

            def authorize(_, ctx, old, current):
                for invocation in (old, current):
                    owner = next(
                        (
                            service
                            for service in (primary, routing, *retained)
                            if service
                            and service.profile.profile_revision_id
                            == invocation.profile_revision_id
                        ),
                        None,
                    )
                    if owner is None:
                        raise ConversationError(
                            "CONVERSATION_ROUTING_SERVICE_UNAVAILABLE", 503
                        )
                    owner.read(ctx, invocation.invocation_id)

            lineage = read_chain(c, context, original.invocation_id, authorize)
            goal_context = (
                lineage[-1]["target"]["original_context_id"]
                if lineage
                else original.context_id
            )
            binding = c.execute(
                "SELECT record FROM authorization_admin.context_call_requests "
                "WHERE tenant_id=%s AND security_domain=%s AND context_id=%s "
                "AND subject_id=%s AND record->>'conversation_id'=%s",
                (
                    *records.scope(context),
                    goal_context,
                    context.principal_id,
                    conversation,
                ),
            ).fetchone()
            if not binding:
                raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
            goal = c.execute(
                "SELECT m.content FROM private_conversation.messages m "
                "WHERE m.tenant_id=%s "
                "AND m.security_domain=%s AND m.conversation_id=%s AND m.message_id=%s "
                "AND m.author_id=%s AND NOT EXISTS (SELECT 1 FROM "
                "private_conversation.message_facts f WHERE f.tenant_id=m.tenant_id "
                "AND f.security_domain=m.security_domain AND "
                "f.conversation_id=m.conversation_id AND f.message_id=m.message_id)",
                (
                    *records.scope(context),
                    conversation,
                    binding["record"]["first_user_message_id"],
                    context.principal_id,
                ),
            ).fetchone()
            if not goal:
                raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
            replies = c.execute(
                "SELECT facts FROM private_conversation.message_facts "
                "WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s AND "
                "facts->>'assistantResponse'='true' AND "
                "facts#>>'{source,invocationId}'=%s LIMIT 2",
                (*records.scope(context), conversation, original.invocation_id),
            ).fetchall()
            expected_source = {
                "kind": "DRAFT",
                "invocationId": original.invocation_id,
                "contextId": original.context_id,
                "turnId": original.turn_id,
                "turnVersion": original.turn_version,
            }
            if len(replies) != 1:
                raise ConversationError("CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 409)
            facts = replies[0]["facts"]
            saved = facts.get("response", {})
            if (
                facts.get("source") != expected_source
                or facts.get("invokedBy") != context.principal_id
                or facts.get("state") != "SUCCEEDED"
                or saved.get("resultKind") != original.result_kind.value
            ):
                raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID", 409)
            from .understanding_adoption_messages import user_messages

            messages = user_messages(
                c,
                records,
                context,
                conversation,
                original,
                lineage,
                binding["record"]["first_user_message_id"],
            )
        question = saved.get("clarificationQuestion") or "\n".join(
            saved.get("dataNeeds") or []
        )
        if (
            not question
            and original.result_kind is DraftResultKind.DRAFT_READY
            and original.input_source is None
        ):
            # The existing CLARIFY page owns this exact source-selection question.
            # This is not a fabricated model question or permission to replace a source.
            question = "请选择本次要分析的资料范围。"
        if not question:
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE", 409)
        target = {
            "kind": "UNDERSTANDING",
            "invocationId": original.invocation_id,
            "contextId": original.context_id,
            "turnId": original.turn_id,
            "turnVersion": original.turn_version,
            "aggregateVersion": original.aggregate_version,
            "inputSourceDigest": digest(original.input_source),
            "journalVersion": journal["version"],
            "journeyKey": state["key"],
        }
        current = {
            "goal": goal["content"],
            "scope": json.dumps(
                [
                    {k: v for k, v in item.items() if k != "sourceRefs"}
                    for item in (saved.get("understanding") or [])
                ],
                ensure_ascii=False,
            ),
            "serverUserMessages": messages,
            "stage": "CLARIFY",
            "currentQuestion": question,
            "currentQuestionType": "UNDERSTANDING",
        }
        if any(len(v) > 4000 for v in current.values()):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_TOO_LARGE", 422)
        if (
            _journal(records, context, conversation, message_id)["version"]
            != journal["version"]
        ):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_CHANGED", 409)
        return sealed_snapshot(
            conversation, message_id, target, current, goal_id=journal.get("goalId")
        )

    return read
