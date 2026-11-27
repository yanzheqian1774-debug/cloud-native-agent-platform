"""Private BOUND background for an unrelated message, never execution authority.

Kept behind a separate disabled gate until independent-result adoption is composed.
No cycle or execution content is exposed and no model operation is performed.
"""

import os
from types import SimpleNamespace

from .conversation_goal_slots import message_goal, require
from .conversation_relation_context import sealed_snapshot
from .fixed_chat_facts import binding_facts
from .fixed_work_authoring_postgres import read as read_work
from .fixed_work_sources_postgres import compatible
from .plan_suggestion_domain import ExactReference
from .private_conversation import digest


def read(records, context, conversation, message_id):
    if os.environ.get("CONVERSATION_GOAL_NATURAL_ENABLED") != "1":
        return None
    with records.connect() as c:
        chat = records.owned(c, context, conversation)
        require(chat["owner_id"] == context.principal_id and not chat["archived_at"])
        key = (*records.scope(context), conversation)
        message = c.execute(
            "SELECT author_id,focus_link_id FROM private_conversation.messages "
            "WHERE tenant_id=%s AND security_domain=%s "
            "AND conversation_id=%s AND message_id=%s "
            "AND NOT EXISTS (SELECT 1 FROM private_conversation.message_facts f "
            "WHERE f.tenant_id=messages.tenant_id "
            "AND f.security_domain=messages.security_domain "
            "AND f.conversation_id=messages.conversation_id "
            "AND f.message_id=messages.message_id)",
            (*key, message_id),
        ).fetchone()
        require(message and message["author_id"] == context.principal_id)
        if message["focus_link_id"] or message_goal(
            c, records, context, conversation, message_id
        ):
            return None
        if (
            c.execute("SELECT to_regclass('fixed_work_sources.bindings') t").fetchone()[
                "t"
            ]
            is None
        ):
            return None
        compatible(c)
        from .fixed_work_sources_postgres import (
            conversation_binding,
        )
        from .fixed_work_sources_postgres import (
            read as read_source,
        )

        scope = records.scope(context)
        bound = conversation_binding(c, scope, conversation)
        if not bound:
            return None
        handoff = read_source(
            c, scope, "handoffs", bound["work_id"], bound["revision_id"]
        )
        work = ExactReference.model_validate(bound["record"]["work"])
        saved = read_work(c, scope, work.resource_id, work.revision_id)
        permit = SimpleNamespace(
            tenantId=scope[0],
            securityDomain=scope[1],
            subjectId=context.principal_id,
            conversationId=conversation,
            work=work,
            bindingDigest=bound["digest"],
        )
        binding = binding_facts(bound, handoff, saved, permit)
        from .fixed_chat_provenance import require_retained

        require_retained(c, context, binding)
        # Existence and provenance of the user's own fixed-work binding are the
        # only facts supplied. Reading a resource title/instruction still needs
        # that resource's exact READ; this neutral port deliberately loads none
        # into the model snapshot.
        result = sealed_snapshot(
            conversation,
            message_id,
            None,
            {
                "goal": None,
                "scope": None,
                "stage": "FIXED_WORK_BACKGROUND",
                "naturalGoalIntentVersion": "v1",
                "currentQuestion": None,
            },
        )
        identity = {
            "schemaVersion": "conversation-neutral-binding.v1",
            "conversationId": conversation,
            "subjectId": context.principal_id,
            "bindingDigest": bound["digest"],
            "handoffDigest": handoff["digest"],
            "work": work.model_dump(mode="json"),
        }
        result["neutralBinding"] = identity
        result["contextDigest"] = digest(
            {
                "snapshotDigest": result["contextDigest"],
                "neutralBinding": identity,
            }
        )
        return result
