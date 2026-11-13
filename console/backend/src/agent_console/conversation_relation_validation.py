"""Read-only relation revalidation. It never submits or retargets an owner answer."""

from fastapi import Request
from fastapi.responses import JSONResponse

from .authority_contracts import AuthorityError
from .conversation_answer_retention import read_retained, require_target
from .draft_assistance import DraftAssistanceError, DraftScope
from .private_conversation import ConversationError, digest
from .workbench_bff import PREFIX


def validated_target(invocation, value, current, *, initial_adoption=False):
    metadata = invocation.conversation_context
    route = invocation.conversation_route
    if (
        not metadata
        or not route
        or value.get("conversationDelivery", {}).get("state") != "SAVED"
        or value.get("conversationRoute") != route
        or route.get("contextDigest") != metadata.get("contextDigest")
    ):
        raise ConversationError("CONVERSATION_ROUTING_RESULT_UNAVAILABLE", 409)
    if route["relation"] != "CURRENT_QUESTION":
        return None
    # A full result is only eligible for the separately configured adoption owner.
    # Returning this target does not consume the old question or authorize work.
    initial = (
        initial_adoption
        and (metadata.get("target") or {}).get("kind") == "UNDERSTANDING"
    )
    allowed = (
        {"DRAFT_READY", "NEEDS_DATA", "NEEDS_CLARIFICATION"}
        if initial
        else {"CURRENT_QUESTION_ANSWER"}
    )
    if (
        value.get("resultKind") not in allowed
        or not metadata.get("target")
        or route.get("currentQuestionToken") != metadata.get("currentQuestionToken")
        or current["contextDigest"] != metadata["contextDigest"]
        or current["target"] != metadata["target"]
    ):
        raise ConversationError("CONVERSATION_ROUTING_CONTEXT_CHANGED", 409)
    return current["target"]


def install(app, authenticate, service, service_for, payload, status):
    @app.get(
        f"{PREFIX}/conversations/{{conversation}}/understanding-results/{{message_id}}/route"
    )
    def revalidate(
        request: Request, conversation: str, message_id: str, requestKey: str
    ):
        _, context = authenticate(request)
        try:
            actions = getattr(app.state, "conversation_actions", None)
            reader = getattr(app.state, "conversation_relation_reader", None)
            if not actions or not reader or not 1 <= len(requestKey) <= 128:
                raise ConversationError("CONVERSATION_ROUTING_RESULT_UNAVAILABLE", 404)
            require_target(actions, context, conversation, message_id)
            invocation = service.repository.get_by_key(
                DraftScope.from_context(context),
                context.principal_id,
                "conversation:" + digest([conversation, message_id, requestKey]),
            )
            if (
                invocation is None
                or invocation.initiating_principal_id != context.principal_id
                or (invocation.conversation_context or {}).get("conversationId")
                != conversation
                or invocation.conversation_context.get("messageId") != message_id
            ):
                raise ConversationError("CONVERSATION_ROUTING_RESULT_UNAVAILABLE", 404)
            active_service = service_for(context, invocation.invocation_id)
            value = payload(active_service.read(context, invocation.invocation_id))[
                "result"
            ]
            value = read_retained(
                actions,
                context,
                conversation,
                value,
                request_key=requestKey,
                message_id=message_id,
            )
            current = (
                reader(context, conversation, message_id, service)
                if (invocation.conversation_route or {}).get("relation")
                == "CURRENT_QUESTION"
                else {}
            )
            target = validated_target(
                invocation,
                value,
                current,
                initial_adoption=active_service.profile.adapter_revision
                == "v3-relation-adoption"
                and getattr(app.state, "understanding_adoption", None) is not None,
            )
            with actions.records.connect() as c:
                actions.records.owned(c, context, conversation)
                original = c.execute(
                    "SELECT content FROM private_conversation.messages "
                    "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                    "AND message_id=%s AND author_id=%s",
                    (
                        *actions.records.scope(context),
                        conversation,
                        message_id,
                        context.principal_id,
                    ),
                ).fetchone()
            if not original:
                raise ConversationError("CONVERSATION_ROUTING_RESULT_UNAVAILABLE", 404)
            return {
                "result": {
                    "relation": invocation.conversation_route["relation"],
                    "originalText": original["content"],
                    "messageId": message_id,
                    "target": target,
                }
            }
        except ConversationError as exc:
            return JSONResponse(
                status_code=exc.status, content={"reasonCode": exc.reason}
            )
        except DraftAssistanceError as exc:
            return JSONResponse(
                status_code=status(exc.reason_code),
                content={"reasonCode": exc.reason_code},
            )
        except AuthorityError:
            return JSONResponse(
                status_code=403,
                content={"reasonCode": "CONVERSATION_ROUTING_ACCESS_DENIED"},
            )
