# ruff: noqa: E501 -- Exact persisted message/link query.
"""Private focus writer and current-authority reader; no model dispatch."""

from fastapi import Request

from .authority_contracts import ExactGrant
from .fixed_chat_delivery import FixedChatDelivery
from .fixed_chat_focus import FocusCommand, create, read_basis, status
from .private_conversation import ConversationError


def install(app, execute, policy, authorizer, automation, cursors):
    @app.post(
        "/api/workbench/v1/conversations/{conversation}/fixed-work-activity/focus"
    )
    def focus(conversation: str, request: Request, body: FocusCommand):
        if request.query_params:
            raise ConversationError("FIXED_CHAT_QUERY_INVALID", 400)
        return execute(
            request,
            conversation,
            lambda call, owner: create(call, owner, conversation, body),
            write=True,
        )

    @app.get("/api/workbench/v1/conversations/{conversation}/fixed-work-activity/focus")
    def read_status(conversation: str, request: Request, commandId: str):
        if set(request.query_params) != {"commandId"} or not 1 <= len(commandId) <= 128:
            raise ConversationError("FIXED_CHAT_QUERY_INVALID", 400)
        return execute(
            request,
            conversation,
            lambda call, owner: status(call, owner, conversation, commandId),
        )

    def read(context, conversation, *, target=None, message_id=None):
        actions = app.state.conversation_actions
        records = actions.records
        if message_id is not None:
            with records.connect() as c:
                records.owned(c, context, conversation)
                row = c.execute(
                    "SELECT l.target FROM private_conversation.messages m LEFT JOIN private_conversation.links l ON l.tenant_id=m.tenant_id AND l.security_domain=m.security_domain AND l.conversation_id=m.conversation_id AND l.link_id=m.focus_link_id WHERE m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s AND m.message_id=%s AND m.author_id=%s AND NOT EXISTS(SELECT 1 FROM private_conversation.message_facts f WHERE f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id)",
                    (
                        *records.scope(context),
                        conversation,
                        message_id,
                        context.principal_id,
                    ),
                ).fetchone()
                if not row:
                    raise ConversationError("CONVERSATION_REQUEST_MESSAGE_MISMATCH")
                target = row["target"]
            if not target or "fixedCycleFocus" not in target:
                return None
        if not target or set(target) != {"fixedCycleFocus"}:
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID")
        basis = target["fixedCycleFocus"]
        if conversation != basis.get("conversationId"):
            raise ConversationError("CONVERSATION_ROUTING_CONTEXT_INVALID")
        digest = basis["identity"]["preparationDigest"]
        return authorizer.execute(
            context,
            (ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + digest),),
            operation="READ_FIXED_CYCLE_FOCUS",
            payload={},
            path={},
            query={},
            handler=lambda call: read_basis(
                call,
                FixedChatDelivery(policy, records, automation, cursors),
                conversation,
                target,
            ),
        )

    app.state.fixed_cycle_focus_reader = read

    actions = app.state.conversation_actions
    if actions is not None:
        actions.fixed_focus_for_message = lambda ctx, conversation, message: read(
            ctx, conversation, message_id=message
        )
        actions.fixed_focus_read = lambda ctx, conversation, target: read(
            ctx, conversation, target=target
        )
