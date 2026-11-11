"""Private confirmations and read-back facts, never an owner dispatcher.

The existing authenticated owner route claims an intent before its own action.
No route here invokes a model, creates a Problem or dispatches an execution.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

from .private_conversation import ConversationError, digest


def reference(action, result):
    if action == "DRAFT":
        return {
            "kind": "DRAFT",
            "invocationId": result["invocationId"],
            "contextId": result["contextId"],
            "turnId": result["turnId"],
            "turnVersion": result["turnVersion"],
        }
    if action in {"PLANNING", "PLANNING_CONTINUE"}:
        target = result["invocation"]["target"]
        return {
            "kind": "PLANNING",
            "invocationId": target["invocation_id"],
            "contextId": target["suggestion_context_id"],
            "requestRevision": target["request_revision"],
            "target": target["problem"],
        }
    revision = result["revision"]
    return {
        "kind": "PROBLEM",
        "target": {
            "problemId": revision["business_problem_id"],
            "revisionId": revision["revision_id"],
            "problemDigest": revision["digest"],
        },
    }


class ConversationActions:
    def __init__(self, records, source_read, planning_request_read):
        self.records = records
        self.source_read = source_read
        self.planning_request_read = planning_request_read

    def authorize_intent(self, ctx, intent):
        source = intent["source"]
        if source:
            self.source_read(ctx, source)

    def insert(self, c, ctx, row, key, content, kind, facts, request_digest):
        scope = (*self.records.scope(ctx), row["conversation_id"])
        identity = str(uuid4())
        c.execute(
            "INSERT INTO private_conversation.messages "
            "(tenant_id,security_domain,conversation_id,message_id,sequence,author_id,"
            "content,disposition,request_key,request_digest) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *scope,
                identity,
                row["version"] + 1,
                ctx.principal_id,
                content,
                kind,
                key,
                request_digest,
            ),
        )
        c.execute(
            "INSERT INTO private_conversation.message_facts VALUES(%s,%s,%s,%s,%s,%s)",
            (*scope, identity, kind, Jsonb(jsonable_encoder(facts))),
        )
        c.execute(
            "UPDATE private_conversation.conversations SET version=version+1 "
            "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            scope,
        )
        row["version"] += 1
        return identity

    def prior(self, c, ctx, identity, body, table="messages"):
        row = self.records.owned(c, ctx, identity, True)
        old = c.execute(
            f"SELECT * FROM private_conversation.{table} WHERE tenant_id=%s "
            "AND security_domain=%s AND conversation_id=%s AND request_key=%s",
            (*self.records.scope(ctx), identity, body["idempotencyKey"]),
        ).fetchone()
        self.records.replay(old, digest(body))
        if not old and (
            row["archived_at"] or row["version"] != body["expectedVersion"]
        ):
            raise ConversationError("CONVERSATION_VERSION_CONFLICT")
        return row, old

    def source(self, ctx, identity, body):
        with self.records.connect() as c:
            self.prior(c, ctx, identity, body)
        facts = self.source_read(ctx, body["source"])
        with self.records.connect() as c:
            row, old = self.prior(c, ctx, identity, body)
            if old:
                return {"identity": old["message_id"], "replayed": True}
            message = self.insert(
                c,
                ctx,
                row,
                body["idempotencyKey"],
                "业务能力与本次输入已保存"
                if body["source"]["kind"] == "CAPABILITY"
                else "原办理来源记录",
                "SOURCE",
                {"source": body["source"], "observation": facts},
                digest(body),
            )
        return {"identity": message, "replayed": False}

    def capability_contract(
        self, ctx, identity, message_id, *, connection=None, source_reader=None
    ):
        from contextlib import nullcontext

        def connected():
            return (
                nullcontext(connection)
                if connection is not None
                else self.records.connect()
            )

        from .capability_conversation_source import execution_contract

        with connected() as c:
            self.records.owned(c, ctx, identity)
            row = c.execute(
                "SELECT facts FROM private_conversation.message_facts "
                "WHERE tenant_id=%s AND security_domain=%s "
                "AND conversation_id=%s AND message_id=%s AND kind='SOURCE'",
                (*self.records.scope(ctx), identity, message_id),
            ).fetchone()
        if not row or row["facts"].get("source", {}).get("kind") != "CAPABILITY":
            raise ConversationError("CAPABILITY_SOURCE_NOT_FOUND", 404)
        source = row["facts"]["source"]
        observation = (source_reader or self.source_read)(ctx, source)
        with connected() as c:
            self.records.owned(c, ctx, identity)
        return execution_contract(ctx, identity, message_id, source, observation)

    def prepare(self, ctx, identity, body):
        # Owner readers have their own authorization transactions. Never call
        # them while the conversation holds the current-authority lock.
        with self.records.connect() as c:
            self.prior(c, ctx, identity, body, "action_intents")
        source = body.get("source")
        facts = self.source_read(ctx, source) if source else None
        with self.records.connect() as c:
            row, old = self.prior(c, ctx, identity, body, "action_intents")
            if old:
                return {
                    "intentId": old["intent_id"],
                    "claimed": old["claimed_at"] is not None,
                }
            payload, action = body["payload"], body["action"]
            version = body["expectedOwnerVersion"]
            if action == "DRAFT":
                if payload.get("parentContextId"):
                    if (
                        not source
                        or source["kind"] != "DRAFT"
                        or any(
                            [
                                source["contextId"] != payload["parentContextId"],
                                source["turnId"] != payload.get("parentTurnId"),
                                source["turnVersion"]
                                != payload.get("expectedParentVersion"),
                                source["invocationId"]
                                != payload.get("predecessorInvocationId"),
                                version != source["turnVersion"],
                            ]
                        )
                    ):
                        raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
                elif source or version != 0 or payload.get("predecessorInvocationId"):
                    raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
            elif action == "CREATE_PROBLEM":
                if payload["ownerId"] != ctx.principal_id:
                    raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
                if source and source["kind"] == "CAPABILITY":
                    from .capability_conversation_source import execution_contract

                    resolved = execution_contract(
                        ctx, identity, body["messageId"], source, facts
                    )
                    expected = {
                        **resolved["workInput"]["problem"],
                        "ownerId": ctx.principal_id,
                        "idempotencyKey": payload["idempotencyKey"],
                    }
                    if version != 0 or payload != expected:
                        raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
                elif payload.get("draftInvocationId"):
                    if (
                        not source
                        or source["kind"] != "DRAFT"
                        or source["invocationId"] != payload["draftInvocationId"]
                        or facts["ownerVersion"] != version
                        or facts["state"] != "SUCCEEDED"
                    ):
                        raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
                elif source or version != 0:
                    raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
            else:
                target = payload["target"]
                expected = target["problem"]
                if (
                    not source
                    or source["kind"] != "PROBLEM"
                    or source["target"]
                    != {
                        "problemId": expected["resource_id"],
                        "revisionId": expected["revision_id"],
                        "problemDigest": expected["digest"],
                    }
                    or version != target["expected_problem_version"]
                    or facts["ownerVersion"] != version
                ):
                    raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
            capability_creation = (
                action == "CREATE_PROBLEM" and source and source["kind"] == "CAPABILITY"
            )
            # Only capability creation may refer to its exact saved SOURCE.
            # Other actions still require the original user message.
            message = c.execute(
                "SELECT message_id,disposition FROM private_conversation.messages "
                "WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s AND message_id=%s",
                (*self.records.scope(ctx), identity, body["messageId"]),
            ).fetchone()
            if not message or (
                not capability_creation
                and message["disposition"]
                in {"SOURCE", "ACTION_INTENT", "OWNER_RECEIPT"}
            ):
                raise ConversationError("CONVERSATION_MESSAGE_NOT_FOUND", 404)
            if capability_creation:
                saved = c.execute(
                    "SELECT facts FROM private_conversation.message_facts WHERE "
                    "tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                    "AND message_id=%s AND kind='SOURCE'",
                    (*self.records.scope(ctx), identity, body["messageId"]),
                ).fetchone()
                if not saved or saved["facts"].get("source") != source:
                    raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
            key = payload.get("idempotencyKey") or payload["idempotency_key"]
            # Enforce one original owner key even across distinct conversations.
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (digest([*self.records.scope(ctx), ctx.principal_id, action, key]),),
            )
            existing = c.execute(
                "SELECT intent_id FROM private_conversation.action_intents "
                "WHERE tenant_id=%s "
                "AND security_domain=%s AND confirmed_by=%s AND action=%s "
                "AND owner_request_key=%s",
                (*self.records.scope(ctx), ctx.principal_id, action, key),
            ).fetchone()
            if existing:
                raise ConversationError("CONVERSATION_OWNER_KEY_CONFLICT")
            intent_id = str(uuid4())
            confirmed = datetime.now(UTC).isoformat()
            intent = {
                "intentId": intent_id,
                "action": action,
                "messageId": body["messageId"],
                "payloadDigest": digest(payload),
                "ownerRequestKey": key,
                "source": source,
                "expectedOwnerVersion": version,
                "confirmedBy": ctx.principal_id,
                "confirmedAt": confirmed,
            }
            self.insert(
                c,
                ctx,
                row,
                "intent:" + intent_id,
                "已明确确认原入口动作",
                "ACTION_INTENT",
                intent,
                digest(intent),
            )
            c.execute(
                "INSERT INTO private_conversation.action_intents "
                "(tenant_id,security_domain,conversation_id,intent_id,message_id,confirmed_by,"
                "action,payload,payload_digest,owner_request_key,source,expected_owner_version,"
                "request_key,request_digest) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *self.records.scope(ctx),
                    identity,
                    intent_id,
                    body["messageId"],
                    ctx.principal_id,
                    action,
                    Jsonb(payload),
                    digest(payload),
                    key,
                    Jsonb(source),
                    version,
                    body["idempotencyKey"],
                    digest(body),
                ),
            )
        return {"intentId": intent_id, "claimed": False}

    def get(self, c, ctx, conversation_id, intent_id, lock=False):
        self.records.owned(c, ctx, conversation_id, lock)
        row = c.execute(
            "SELECT * FROM private_conversation.action_intents WHERE tenant_id=%s AND "
            "security_domain=%s AND conversation_id=%s AND intent_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (*self.records.scope(ctx), conversation_id, intent_id),
        ).fetchone()
        if not row:
            raise ConversationError("CONVERSATION_INTENT_NOT_FOUND", 404)
        return row

    def claim(self, ctx, conversation_id, intent_id, action, payload):
        with self.records.connect() as c:
            observed = self.get(c, ctx, conversation_id, intent_id)
        self.authorize_intent(ctx, observed)
        with self.records.connect() as c:
            row = self.get(c, ctx, conversation_id, intent_id, True)
            if row["action"] != action or row["payload_digest"] != digest(payload):
                raise ConversationError("CONVERSATION_INTENT_PAYLOAD_MISMATCH")
            if row["claimed_at"]:
                raise ConversationError("CONVERSATION_ACTION_ALREADY_CLAIMED_READ_ONLY")
            c.execute(
                "UPDATE private_conversation.action_intents SET claimed_at=now() WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                "AND intent_id=%s",
                (*self.records.scope(ctx), conversation_id, intent_id),
            )
        return row

    def receipt(self, ctx, conversation_id, intent_id, *, source=None, failure=None):
        observation = self.source_read(ctx, source) if source else None
        state = (
            observation["receiptState"]
            if observation
            else "FAILED"
            if failure
            else "UNKNOWN"
        )
        facts = {
            "intentId": intent_id,
            "state": state,
            "source": source,
            "observation": observation,
            "reasonCode": failure
            or (None if source else "NO_SAFE_OWNER_QUERY_KEEP_UNKNOWN"),
        }
        with self.records.connect() as c:
            intent = self.get(c, ctx, conversation_id, intent_id, True)
            row = self.records.owned(c, ctx, conversation_id, True)
            facts["authorizationSource"] = intent["source"]
            key = "receipt:" + digest(facts)
            prior = c.execute(
                "SELECT message_id FROM private_conversation.messages WHERE "
                "tenant_id=%s AND "
                "security_domain=%s AND conversation_id=%s AND request_key=%s",
                (*self.records.scope(ctx), conversation_id, key),
            ).fetchone()
            if not prior:
                if source:
                    source_key = "source:" + digest(source)
                    exists = c.execute(
                        "SELECT message_id FROM "
                        "private_conversation.messages WHERE tenant_id=%s "
                        "AND security_domain=%s AND conversation_id=%s AND "
                        "request_key=%s",
                        (*self.records.scope(ctx), conversation_id, source_key),
                    ).fetchone()
                    if not exists:
                        self.insert(
                            c,
                            ctx,
                            row,
                            source_key,
                            "原办理来源记录",
                            "SOURCE",
                            {"source": source, "observation": observation},
                            digest(source),
                        )
                self.insert(
                    c,
                    ctx,
                    row,
                    key,
                    "原入口办理回执",
                    "OWNER_RECEIPT",
                    facts,
                    digest(facts),
                )
            if source:
                c.execute(
                    "UPDATE private_conversation.action_intents SET owner_ref=%s WHERE "
                    "tenant_id=%s AND security_domain=%s AND "
                    "conversation_id=%s AND intent_id=%s",
                    (
                        Jsonb(source),
                        *self.records.scope(ctx),
                        conversation_id,
                        intent_id,
                    ),
                )
                if source["kind"] == "PROBLEM":
                    target = source["target"]
                    link_key = "owner-problem:" + digest(target)
                    exists = c.execute(
                        "SELECT link_id FROM private_conversation.links "
                        "WHERE tenant_id=%s "
                        "AND security_domain=%s AND conversation_id=%s AND target=%s",
                        (*self.records.scope(ctx), conversation_id, Jsonb(target)),
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO private_conversation.links "
                            "(tenant_id,security_domain,conversation_id,link_id,target,"
                            "created_by,request_key,request_digest) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                *self.records.scope(ctx),
                                conversation_id,
                                str(uuid4()),
                                Jsonb(target),
                                ctx.principal_id,
                                link_key,
                                digest(target),
                            ),
                        )
                        c.execute(
                            "UPDATE private_conversation.conversations SET "
                            "version=version+1 "
                            "WHERE tenant_id=%s AND security_domain=%s AND "
                            "conversation_id=%s",
                            (*self.records.scope(ctx), conversation_id),
                        )
        return facts

    def remember_owner(self, ctx, conversation_id, intent_id, source):
        # Original-route facts only; there is no client-provided receipt endpoint.
        with self.records.connect() as c:
            self.get(c, ctx, conversation_id, intent_id, True)
            c.execute(
                "UPDATE private_conversation.action_intents SET owner_ref=%s "
                "WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s AND intent_id=%s",
                (Jsonb(source), *self.records.scope(ctx), conversation_id, intent_id),
            )

    def reconcile(self, ctx, conversation_id, intent_id, persist=False):
        with self.records.connect() as c:
            intent = self.get(c, ctx, conversation_id, intent_id)
        self.authorize_intent(ctx, intent)
        source = intent["owner_ref"]
        if not intent["claimed_at"]:
            return {"intentId": intent_id, "state": "NOT_SUBMITTED"}
        if not source and intent["action"] in {"PLANNING", "PLANNING_CONTINUE"}:
            try:
                value = self.planning_request_read(
                    ctx, intent["owner_request_key"], intent["payload"]
                )
                candidate = reference("PLANNING", value)
                if candidate["target"] != intent["payload"]["target"]:
                    raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
                source = candidate
            except Exception:
                # Not-found/unauthorized/unavailable does not prove no effect.
                pass
        if persist:
            return self.receipt(ctx, conversation_id, intent_id, source=source)
        observation = self.source_read(ctx, source) if source else None
        return {
            "intentId": intent_id,
            "state": observation["receiptState"] if observation else "UNKNOWN",
            "source": source,
            "observation": observation,
        }


def original_action(request, ctx, action, payload, invoke):
    """Called only inside an original authenticated, CSRF-checked owner route."""
    identity = request.headers.get("x-conversation-intent")
    conversation = request.headers.get("x-conversation-id")
    if not identity and not conversation:
        return invoke()
    service = getattr(request.app.state, "conversation_actions", None)
    if not service or not identity or not conversation:
        raise ConversationError("CONVERSATIONS_DISABLED", 404)
    service.claim(ctx, conversation, identity, action, payload)
    # A failure after claim is conservative UNKNOWN unless the original route
    # explicitly returns a pre-effect validation/authorization failure.
    result = invoke()
    try:
        if hasattr(result, "status_code"):
            # An HTTP error alone cannot prove the owner made no effect.
            # Terminal failure is established only by the owner's durable state.
            service.receipt(ctx, conversation, identity)
        else:
            value = (
                result
                if any(k in result for k in ("invocation", "revision", "invocationId"))
                else result.get("result", result)
            )
            source = reference(action, value)
            service.remember_owner(ctx, conversation, identity, source)
            service.receipt(ctx, conversation, identity, source=source)
    except Exception:
        # The original owner response is not replaced by a receipt-storage error.
        # A claimed intent remains visible and can only be read/reconciled.
        pass
    return result
