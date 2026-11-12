"""Private records only: no Problem creation, model invocation or Run dispatch."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .request_timing import measured, measured_context


class ConversationError(ValueError):
    def __init__(self, reason, status=409):
        self.reason, self.status = reason, status
        super().__init__(reason)


def source_read_failure(exc):
    """Expose a bounded read failure without leaking owner exception details."""
    reason = getattr(exc, "reason_code", getattr(exc, "reason", str(exc)))
    if reason == "CONVERSATION_SOURCE_MISMATCH":
        return ConversationError(reason, 409)
    if getattr(exc, "status", None) in {401, 403, 404} or reason in {
        "AUTHENTICATION_REQUIRED",
        "AUTHORIZATION_NOT_FOUND",
        "ACCESS_DENIED",
        "FORBIDDEN",
        "DRAFT_ASSISTANCE_NOT_FOUND",
        "DRAFT_AUTHORIZATION_UNAVAILABLE",
        "PLANNING_NOT_FOUND",
        "PLANNING_INVOCATION_NOT_FOUND",
        "CONVERSATION_SOURCE_NOT_READABLE",
    }:
        return ConversationError("CONVERSATION_SOURCE_NOT_READABLE", 404)
    return ConversationError("CONVERSATION_SOURCE_UNAVAILABLE", 503)


def unavailable_message(fact, exc):
    failure = source_read_failure(exc)
    state, content = {
        404: ("ACCESS_RESTRICTED", "当前无法读取这条记录。请核对访问权限。"),
        409: ("SOURCE_MISMATCH", "原记录与来源暂未核对一致。内容暂不展示。"),
        503: (
            "TEMPORARILY_UNAVAILABLE",
            "这条记录暂时加载失败。可重新读取。原内容仍保留。",
        ),
    }[failure.status]
    details = fact["facts"]
    # Only owner-persisted response metadata identifies an assistant. A human
    # request principal or a planned participant never establishes that role.
    assistant = (
        fact["kind"] == "SOURCE"
        and details.get("assistantResponse") is True
        and details.get("state") == "SUCCEEDED"
        and (details.get("source") or {}).get("kind") == "DRAFT"
    )
    return content, {
        "readable": False,
        "readState": state,
        **({"assistantResponse": True} if assistant else {}),
    }


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def disposition(content, focused, link_count):
    # Conservative, deterministic routing hints, never execution authority.
    if re.search(
        r"(?:另外|另一个|新的|独立的).{0,16}(?:目标|问题|分析|任务)|(?:分析|研究).{0,6}另一",
        content,
    ):
        return "NEW_GOAL_REVIEW"
    if not focused and link_count:
        return "CLARIFY_WORK"
    return "FOLLOWUP_RECORDED" if focused else "GOAL_RECORDED"


class PrivateConversations:
    def __init__(self, database_url, resolve_link, administrator_access=None):
        self.database_url, self.resolve_link = database_url, resolve_link
        self.administrator_access = administrator_access or (lambda c, ctx: False)
        self._connection_pool = None

    def start_pool(self):
        """Called once by the application lifespan, never per request."""
        if self._connection_pool is not None:
            return
        pool = ConnectionPool(
            self.database_url,
            name="private-conversation",
            min_size=1,
            max_size=4,
            timeout=5,
            max_idle=60,
            kwargs={"row_factory": dict_row, "autocommit": False, "connect_timeout": 5},
            open=False,
        )
        try:
            pool.open(wait=True, timeout=5)
        except Exception:
            pool.close()
            raise
        self._connection_pool = pool

    def close_pool(self):
        pool, self._connection_pool = self._connection_pool, None
        if pool is not None:
            pool.close()

    @contextmanager
    def pooled_connection(self, pool):
        entered = False
        try:
            with measured_context(pool.connection(timeout=5), "conversation.pool") as c:
                entered = True
                yield c
        except psycopg.Error as exc:
            if not entered:
                exc._conversation_storage_phase = "POOL_ACQUIRE"
            raise

    @measured("conversation.connection")
    def connect(self):
        if self._connection_pool is not None:
            return self.pooled_connection(self._connection_pool)
        try:
            return psycopg.connect(
                self.database_url, row_factory=dict_row, connect_timeout=5
            )
        except psycopg.Error as exc:
            # Fixed phase only; never attach connection details or retry a write.
            exc._conversation_storage_phase = "CONNECT"
            raise

    @staticmethod
    def scope(ctx):
        return (ctx.scope.tenant_id, ctx.scope.security_domain)

    @measured("conversation.ownership")
    def owned(self, c, ctx, identity, lock=False):
        row = c.execute(
            "SELECT * FROM private_conversation.conversations WHERE tenant_id=%s "
            "AND security_domain=%s AND conversation_id=%s AND (owner_id=%s OR %s)"
            + (" FOR UPDATE" if lock else ""),
            (
                *self.scope(ctx),
                identity,
                ctx.principal_id,
                self.administrator_access(c, ctx),
            ),
        ).fetchone()
        if not row:
            raise ConversationError("CONVERSATION_NOT_FOUND", 404)
        if row["schema_version"] != 1:
            raise ConversationError("CONVERSATION_VERSION_UNSUPPORTED")
        return row

    @staticmethod
    def replay(row, hashed):
        if row and row["request_digest"] != hashed:
            raise ConversationError("CONVERSATION_IDEMPOTENCY_CONFLICT")
        return row

    def list(self, ctx):
        with self.connect() as c:
            rows = c.execute(
                "SELECT conversation_id,title,version,created_at,archived_at FROM "
                "private_conversation.conversations WHERE tenant_id=%s AND "
                "security_domain=%s AND (owner_id=%s OR %s) ORDER BY created_at "
                "DESC,conversation_id",
                (*self.scope(ctx), ctx.principal_id, self.administrator_access(c, ctx)),
            ).fetchall()
        return {"items": rows}

    def create(self, ctx, body):
        hashed = digest(body)
        scope = self.scope(ctx)
        with self.connect() as c:
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (json.dumps([*scope, ctx.principal_id, body["idempotencyKey"]]),),
            )
            old = c.execute(
                "SELECT * FROM private_conversation.conversations WHERE "
                "tenant_id=%s AND security_domain=%s AND owner_id=%s AND "
                "request_key=%s",
                (*scope, ctx.principal_id, body["idempotencyKey"]),
            ).fetchone()
            if self.replay(old, hashed):
                return {"conversation_id": old["conversation_id"]}
            identity = str(uuid4())
            c.execute(
                "INSERT INTO private_conversation.conversations "
                "(tenant_id,security_domain,conversation_id,owner_id,title,"
                "request_key,request_digest) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    *scope,
                    identity,
                    ctx.principal_id,
                    body["title"],
                    body["idempotencyKey"],
                    hashed,
                ),
            )
        return {"conversation_id": identity}

    @measured("conversation.head")
    def head(self, ctx, identity):
        """Owned metadata only; message contents still require full source reads."""
        with self.connect() as c:
            row = self.owned(c, ctx, identity)
        return {
            "conversation": {
                k: row[k]
                for k in (
                    "conversation_id",
                    "title",
                    "version",
                    "created_at",
                    "archived_at",
                )
            }
        }

    @measured("conversation.read")
    def read(self, ctx, identity):
        with self.connect() as c:
            row = self.owned(c, ctx, identity)
            scope = (*self.scope(ctx), identity)
            messages = c.execute(
                "SELECT "
                "message_id,sequence,author_id,content,focus_link_id,"
                "disposition,created_at,request_key "
                "FROM private_conversation.messages WHERE tenant_id=%s AND "
                "security_domain=%s AND conversation_id=%s ORDER BY sequence",
                scope,
            ).fetchall()
            links = c.execute(
                "SELECT link_id,target FROM private_conversation.links WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s ORDER "
                "BY created_at,link_id",
                scope,
            ).fetchall()
            facts_reader = getattr(self, "facts_reader", None)
            facts = (
                c.execute(
                    "SELECT message_id,kind,facts FROM "
                    "private_conversation.message_facts "
                    "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                    scope,
                ).fetchall()
                if facts_reader
                else []
            )
            intents = (
                c.execute(
                    "SELECT intent_id,claimed_at,owner_ref FROM "
                    "private_conversation.action_intents "
                    "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                    scope,
                ).fetchall()
                if facts_reader
                else []
            )
        by_id = {f["message_id"]: f for f in facts}
        intent_by_id = {i["intent_id"]: i for i in intents}
        for message in messages:
            fact = by_id.get(message["message_id"])
            if not fact:
                continue
            details = fact["facts"]
            try:
                for source in [
                    details.get("source"),
                    details.get("authorizationSource"),
                ]:
                    if source:
                        facts_reader.source_read(ctx, source)
                message["kind"] = fact["kind"]
                message["facts"] = details
                if fact["kind"] == "ACTION_INTENT":
                    intent = intent_by_id[details["intentId"]]
                    message["facts"] = {
                        **details,
                        "attemptState": "UNKNOWN"
                        if intent["claimed_at"]
                        else "NOT_SUBMITTED",
                    }
            except Exception as exc:
                message["content"], message["facts"] = unavailable_message(fact, exc)
                message["kind"] = fact["kind"]
        visible = self.visible_links(ctx, links)
        return {
            "conversation": {
                k: row[k]
                for k in [
                    "conversation_id",
                    "title",
                    "version",
                    "created_at",
                    "archived_at",
                ]
            },
            "messages": messages,
            "links": visible,
        }

    @measured("conversation.links")
    def visible_links(self, ctx, links):
        visible = []
        for link in links:
            try:
                resolved = self.resolve_link(ctx, link["target"])
                visible.append({**link, "readable": True, "title": resolved["title"]})
            except Exception:
                # Do not reveal revoked target metadata; never use stale snapshots.
                visible.append({"link_id": link["link_id"], "readable": False})
        return visible

    def work_links(self, ctx, identity):
        """Exact authorized links without unrelated message/source projections."""
        with self.connect() as c:
            row = self.owned(c, ctx, identity)
            links = c.execute(
                "SELECT link_id,target FROM private_conversation.links WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s ORDER "
                "BY created_at,link_id",
                (*self.scope(ctx), identity),
            ).fetchall()
        return {
            "conversation": {
                k: row[k]
                for k in [
                    "conversation_id",
                    "title",
                    "version",
                    "created_at",
                    "archived_at",
                ]
            },
            "links": self.visible_links(ctx, links),
        }

    def mutate(self, ctx, identity, body, action):
        hashed = digest(body)
        focus = body.get("focusLinkId")
        if action == "link" or focus:
            with self.connect() as c:
                self.owned(c, ctx, identity)
                target = body.get("target")
                if focus:
                    link = c.execute(
                        "SELECT target FROM private_conversation.links WHERE "
                        "tenant_id=%s AND security_domain=%s AND "
                        "conversation_id=%s AND link_id=%s",
                        (*self.scope(ctx), identity, focus),
                    ).fetchone()
                    if not link:
                        raise ConversationError("CONVERSATION_LINK_NOT_FOUND", 404)
                    target = link["target"]
            self.resolve_link(ctx, target)
        with self.connect() as c:
            row = self.owned(c, ctx, identity, True)
            scope = (*self.scope(ctx), identity)
            table = "messages" if action == "message" else "links"
            old = c.execute(
                f"SELECT * FROM private_conversation.{table} WHERE tenant_id=%s AND "
                f"security_domain=%s AND conversation_id=%s AND request_key=%s",
                (*scope, body["idempotencyKey"]),
            ).fetchone()
            if self.replay(old, hashed):
                return {
                    "identity": old["message_id" if action == "message" else "link_id"],
                    "replayed": True,
                }
            if row["archived_at"] or row["version"] != body["expectedVersion"]:
                raise ConversationError("CONVERSATION_VERSION_CONFLICT")
            identity_new = str(uuid4())
            if action == "link":
                same = c.execute(
                    "SELECT link_id FROM private_conversation.links WHERE tenant_id=%s "
                    "AND security_domain=%s AND conversation_id=%s AND target=%s",
                    (*scope, Jsonb(body["target"])),
                ).fetchone()
                if same:
                    return {"identity": same["link_id"], "replayed": True}
                c.execute(
                    "INSERT INTO private_conversation.links "
                    "(tenant_id,security_domain,conversation_id,link_id,"
                    "target,created_by,request_key,request_digest) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *scope,
                        identity_new,
                        Jsonb(body["target"]),
                        ctx.principal_id,
                        body["idempotencyKey"],
                        hashed,
                    ),
                )
            else:
                focus = body.get("focusLinkId")
                links = c.execute(
                    "SELECT link_id,target FROM private_conversation.links WHERE "
                    "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                    scope,
                ).fetchall()
                if focus:
                    link = next((x for x in links if x["link_id"] == focus), None)
                    if not link:
                        raise ConversationError("CONVERSATION_LINK_NOT_FOUND", 404)
                route = disposition(body["content"], bool(focus), len(links))
                c.execute(
                    "INSERT INTO private_conversation.messages "
                    "(tenant_id,security_domain,conversation_id,message_id,"
                    "sequence,author_id,content,focus_link_id,"
                    "disposition,request_key,request_digest) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        *scope,
                        identity_new,
                        row["version"] + 1,
                        ctx.principal_id,
                        body["content"],
                        focus,
                        route,
                        body["idempotencyKey"],
                        hashed,
                    ),
                )
            c.execute(
                "UPDATE private_conversation.conversations SET version=version+1 "
                "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                scope,
            )
        return {"identity": identity_new, "replayed": False}
