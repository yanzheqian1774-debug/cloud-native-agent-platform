# ruff: noqa: E501,RUF001 -- Exact owner SQL and business-facing Chinese messages.
"""Explicit source correction before any CREATE fact; no model or execution call."""

from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError, ExactGrant
from .context_call_admission import request_row
from .execution_domain import ScopeIdentity
from .plan_suggestion_domain import ExactReference
from .planning_candidates import read_published
from .private_conversation import ConversationError, digest, disposition
from .workbench_prepared_resources import reference


def correct(reader, records, ctx, conversation, body):
    owner = reader.owner
    with (
        reader.authorizer.controller.protected_request(),
        owner.root.repository.connection_scope() as c,
    ):
        owner._policy(c, ctx)
        row = records.owned(c, ctx, conversation, lock=True)
        if row["archived_at"]:
            raise ConversationError("CONVERSATION_ARCHIVED", 409)
        scope = (*records.scope(ctx), conversation)
        hashed = digest({"operation": "CORRECT_UNCREATED_SOURCE", **body})
        message = c.execute(
            "SELECT author_id,message_id,request_digest FROM private_conversation.messages "
            "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND request_key=%s",
            (*scope, body["idempotencyKey"]),
        ).fetchone()
        journal = c.execute(
            "SELECT version,state FROM private_conversation.journeys WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR UPDATE",
            scope,
        ).fetchone()
        if message:
            if (
                message["author_id"] != ctx.principal_id
                or message["request_digest"] != hashed
            ):
                raise ConversationError("CONVERSATION_IDEMPOTENCY_CONFLICT", 409)
            return {**journal, "replayed": True}
        if not journal or journal["version"] != body["expectedVersion"]:
            raise ConversationError("JOURNEY_VERSION_CONFLICT", 409)
        state = journal["state"]
        status = reader._read(
            c, ctx, conversation, body["draftInvocationId"], body["requestKey"]
        )
        if status["state"] != "NOT_CREATED":
            raise ConversationError("CONVERSATION_SOURCE_CORRECTION_NOT_SAFE", 409)
        _, _, now, _, value, ancestry = owner._source_evidence(
            c, ctx, body["draftInvocationId"]
        )
        try:
            owner.policy.selected(value.input_source)
        except AuthorityError as exc:
            if exc.reason_code != "OWNED_BUSINESS_SOURCE_NOT_AUTHORIZED":
                raise
        else:
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_NOT_APPLICABLE", 409
            )
        selected = owner.policy.selected(body["source"])
        ref = ExactReference.model_validate(body["source"]["source"])
        grant = ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", ref.resource_id, ref.revision_id),
        )
        allowed = owner.grants.authorization.has_current_grants(
            ctx,
            (grant,),
            now=now,
            generation=owner.grants.generation.generation,
            recovery_epoch=owner.grants.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )
        if len(allowed) != 1 or not allowed[0]:
            raise ConversationError("CONVERSATION_SOURCE_NOT_READABLE", 403)
        content, name = read_published(
            c, ScopeIdentity(*records.scope(ctx)), "KNOWLEDGE", selected.source
        )
        owner.policy.validate_source(body["source"], content)
        # Carry only actual original user messages, never browser-invented history.
        messages = state.get("messages", [])
        if not messages or len(messages) > 100:
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
            )
        messages, repairs = canonical_history(
            c, ctx, scope, state, messages, value, ancestry
        )
        identity = str(uuid4())
        text = f"更正本次资料为“{name}”。替换此前选择的资料，保留原问题与已补充的要求；请重新核对这份资料后继续，旧资料与草案保留为历史。"
        c.execute(
            "INSERT INTO private_conversation.messages (tenant_id,security_domain,conversation_id,"
            "message_id,sequence,author_id,content,focus_link_id,disposition,request_key,request_digest) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)",
            (
                *scope,
                identity,
                row["version"] + 1,
                ctx.principal_id,
                text,
                disposition(text, False, 0),
                body["idempotencyKey"],
                hashed,
            ),
        )
        c.execute(
            "UPDATE private_conversation.conversations SET version=version+1 WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            scope,
        )
        source = {
            "source": ref.model_dump(mode="json"),
            "sourceContentDigest": selected.sourceContentDigest,
            "sourceSchema": body["source"]["sourceSchema"],
            "name": name,
            "periods": [],
            "synthetic": True,
            "businessEligibility": {
                "state": "SOURCE_SCOPE_MATCHED",
                "executionReady": False,
            },
        }
        previous = {
            "key": state["key"],
            "draftInvocationId": body["draftInvocationId"],
            "source": value.input_source,
            "requestKey": body["requestKey"],
            "correctionMessageId": identity,
            "state": "NOT_CREATED",
            "messageIdentityRepairs": repairs,
        }
        next_state = {
            "key": "source-correction:" + identity,
            "phase": "UNDERSTAND",
            "understandingProtocol": 3,
            "userMessageId": identity,
            "question": state["question"],
            "messages": [*messages, {"id": "user:" + identity, "text": text}],
            "source": source,
            "sourceCorrections": [*state.get("sourceCorrections", []), previous],
            "log": [
                *state.get("log", []),
                "已核实尚未创建工作，并按你的确认更正资料；原记录保留。",
            ],
        }
        c.execute(
            "UPDATE private_conversation.journeys SET version=version+1,state=%s,updated_at=now() "
            "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND version=%s",
            (Jsonb(next_state), *scope, journal["version"]),
        )
        return {
            "version": journal["version"] + 1,
            "state": next_state,
            "replayed": False,
        }


def canonical_history(c, ctx, scope, state, messages, value, ancestry):
    """Repair only legacy first-ID loss using the authorized root owner binding."""
    origin_id = (
        ancestry[-1]["target"]["original_context_id"] if ancestry else value.context_id
    )
    origin = request_row(c, origin_id)
    record = origin["record"] if origin else {}
    canonical_id = record.get("first_user_message_id")
    canonical_present = any(
        item.get("id") == "user:" + str(canonical_id) for item in messages
    )
    result, repairs = [], []
    for index, item in enumerate(messages):
        message_id = str(item.get("id", "")).removeprefix("user:")
        stored = c.execute(
            "SELECT author_id,content,EXISTS (SELECT 1 FROM private_conversation.message_facts f "
            "WHERE f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain "
            "AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id) AS is_fact "
            "FROM private_conversation.messages m WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
            (*scope, message_id),
        ).fetchone()
        if stored and stored["is_fact"]:
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
            )
        if (
            stored
            and stored["author_id"] == ctx.principal_id
            and stored["content"] == item.get("text")
        ):
            if index == 0 and not canonical_present and canonical_id != message_id:
                raise ConversationError(
                    "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
                )
            result.append(item)
            continue
        if (
            stored
            or canonical_present
            or index != 0
            or not str(item.get("id", "")).startswith("user:")
        ):
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
            )
        try:
            UUID(message_id)
        except ValueError as exc:
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
            ) from exc
        # _source_evidence already locked and reauthorized every ancestry context.
        if not (
            record.get("conversation_id") == scope[2]
            and record.get("subject_id") == ctx.principal_id
            and record.get("first_invocation_id")
            and canonical_id
            and item.get("text") == state.get("question")
        ):
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
            )
        bound = c.execute(
            "SELECT content FROM private_conversation.messages m WHERE "
            "m.tenant_id=%s AND m.security_domain=%s AND m.conversation_id=%s "
            "AND m.message_id=%s AND m.author_id=%s AND NOT EXISTS "
            "(SELECT 1 FROM private_conversation.message_facts f WHERE "
            "f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain "
            "AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id)",
            (*scope, canonical_id, ctx.principal_id),
        ).fetchone()
        if not bound or bound["content"] != item.get("text"):
            raise ConversationError(
                "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
            )
        # Text confirms the exact bound message; it is never used to find one.
        repaired = {"id": "user:" + canonical_id, "text": bound["content"]}
        result.append(repaired)
        repairs.append(
            {
                "oldId": item["id"],
                "newId": repaired["id"],
                "originContextId": origin_id,
                "originInvocationId": record["first_invocation_id"],
                "basis": "OWNED_ROOT_CONTEXT_FIRST_USER_MESSAGE",
            }
        )
    return result, repairs
