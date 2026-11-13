# ruff: noqa: E501,RUF001 -- Exact owner SQL and business-facing Chinese messages.
"""Explicit source correction before any CREATE fact; no model or execution call."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError, ExactGrant
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
        _, _, now, _, value, _ = owner._source_evidence(
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
        for item in messages:
            stored = c.execute(
                "SELECT content FROM private_conversation.messages WHERE tenant_id=%s AND "
                "security_domain=%s AND conversation_id=%s AND message_id=%s AND author_id=%s",
                (
                    *scope,
                    str(item.get("id", "")).removeprefix("user:"),
                    ctx.principal_id,
                ),
            ).fetchone()
            if not stored or stored["content"] != item.get("text"):
                raise ConversationError(
                    "CONVERSATION_SOURCE_CORRECTION_HISTORY_CHANGED", 409
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
        }
        next_state = {
            "key": "source-correction:" + identity,
            "phase": "UNDERSTAND",
            "understandingProtocol": 3,
            "userMessageId": identity,
            "question": messages[0]["text"],
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
