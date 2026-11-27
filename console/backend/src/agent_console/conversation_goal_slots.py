# ruff: noqa: E501 -- Private exact scoped goal storage.
"""Explicit owned journals. Selection grants no domain or model authority."""

import json
import os
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb
from pydantic import Field

from .private_conversation import ConversationError, digest
from .workbench_bff_schemas import StrictWorkbenchModel

MIGRATION = Path(__file__).parents[2] / "migrations/0077_conversation_goal_slots.sql"


class CreateGoal(StrictWorkbenchModel):
    commandId: str = Field(min_length=1, max_length=128)
    messageId: str = Field(min_length=1, max_length=128)
    expectedConversationVersion: int = Field(ge=0)


def enabled():
    return os.environ.get("CONVERSATION_GOAL_SLOTS_ENABLED") == "1"


def require(value, reason="CONVERSATION_GOAL_BINDING_INVALID"):
    if not value:
        raise ConversationError(reason, 409)


def scope(records, ctx, conversation):
    return (*records.scope(ctx), conversation)


def require_schema(c):
    row = c.execute(
        "SELECT to_regclass('conversation_goals.schema_migrations') t"
    ).fetchone()
    require(row and row["t"], "CONVERSATION_GOALS_UNAVAILABLE")
    rows = c.execute(
        "SELECT version,checksum,adapter FROM conversation_goals.schema_migrations ORDER BY version"
    ).fetchall()
    require(
        rows
        == [
            dict(
                version=77,
                checksum=sha256(MIGRATION.read_bytes()).hexdigest(),
                adapter="conversation-goal-slots.v1",
            )
        ],
        "CONVERSATION_GOALS_SCHEMA_INVALID",
    )

    columns = c.execute(
        "SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='conversation_goals' ORDER BY table_name,column_name"
    ).fetchall()
    expected = {
        "schema_migrations": "version checksum adapter installed_at",
        "slots": "tenant_id security_domain conversation_id goal_id owner_id root_message_id command_key request_digest record record_digest created_at",
        "journals": "tenant_id security_domain conversation_id goal_id version state updated_at",
        "messages": "tenant_id security_domain conversation_id message_id goal_id",
        "claimed_messages": "tenant_id security_domain conversation_id message_id invocation_id goal_id",
        "result_adoptions": "tenant_id security_domain conversation_id invocation_id goal_id owner_id message_id command_key request_digest record record_digest",
    }
    require(
        {(r["table_name"], r["column_name"]) for r in columns}
        == {
            (table, column)
            for table, names in expected.items()
            for column in names.split()
        },
        "CONVERSATION_GOALS_SCHEMA_INVALID",
    )
    from .postgres_schema_compatibility import (
        Column,
        Table,
        foreign,
        primary,
        schema_is_compatible,
        unique,
    )

    chat_key = ("tenant_id", "security_domain", "conversation_id")
    goal_key = (*chat_key, "goal_id")
    message_key = (*chat_key, "message_id")
    root_key = (*chat_key, "root_message_id")
    types = {
        "version": "integer",
        "installed_at": "timestamp with time zone",
        "created_at": "timestamp with time zone",
        "updated_at": "timestamp with time zone",
        "record": "jsonb",
    }
    constraints = {
        "schema_migrations": (primary("version"),),
        "slots": (
            primary(*goal_key),
            unique(*chat_key, "command_key"),
            unique(*root_key),
            foreign(chat_key, "private_conversation.conversations", chat_key),
            foreign(root_key, "private_conversation.messages", message_key),
        ),
        "journals": (
            primary(*goal_key),
            foreign(goal_key, "conversation_goals.slots", goal_key),
        ),
        "messages": (
            primary(*message_key),
            foreign(goal_key, "conversation_goals.slots", goal_key),
            foreign(message_key, "private_conversation.messages", message_key),
        ),
        "result_adoptions": (
            primary("tenant_id", "security_domain", "invocation_id"),
            unique(*chat_key, "command_key"),
            unique(*goal_key),
            foreign(goal_key, "conversation_goals.slots", goal_key),
            foreign(message_key, "private_conversation.messages", message_key),
        ),
        "claimed_messages": (
            primary(*message_key, "invocation_id"),
            foreign(message_key, "private_conversation.messages", message_key),
        ),
    }
    require(
        schema_is_compatible(
            c,
            tuple(
                Table(
                    "conversation_goals." + table,
                    tuple(
                        Column(
                            name,
                            "bigint"
                            if table == "journals" and name == "version"
                            else types.get(name, "text"),
                        )
                        for name in names.split()
                        if name != "state"
                        and not (table == "claimed_messages" and name == "goal_id")
                    ),
                    constraints[table],
                )
                for table, names in expected.items()
            ),
        ),
        "CONVERSATION_GOALS_SCHEMA_INVALID",
    )
    # The common schema checker only describes NOT NULL columns. These two
    # intentionally nullable fields still have exact storage types.
    nullable = c.execute(
        "SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns "
        "WHERE table_schema='conversation_goals' AND ((table_name='journals' AND column_name='state') "
        "OR (table_name='claimed_messages' AND column_name='goal_id'))"
    ).fetchall()
    require(
        {
            (r["table_name"], r["column_name"], r["data_type"], r["is_nullable"])
            for r in nullable
        }
        == {
            ("journals", "state", "jsonb", "YES"),
            ("claimed_messages", "goal_id", "text", "YES"),
        },
        "CONVERSATION_GOALS_SCHEMA_INVALID",
    )
    triggers = c.execute(
        "SELECT r.relname,t.tgname,t.tgtype,t.tgenabled,p.proname,n.nspname FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace s ON s.oid=r.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace WHERE s.nspname='conversation_goals' AND NOT t.tgisinternal"
    ).fetchall()
    require(
        {
            (
                r["relname"],
                r["tgname"],
                r["tgtype"],
                r["tgenabled"],
                r["proname"],
                r["nspname"],
            )
            for r in triggers
        }
        == {
            (table, name, 27, "O", "reject_mutation", "conversation_goals")
            for table, name in (
                ("slots", "immutable_goal_slot"),
                ("messages", "immutable_goal_message"),
                ("claimed_messages", "immutable_goal_claim"),
                ("result_adoptions", "immutable_goal_adoption"),
            )
        },
        "CONVERSATION_GOALS_SCHEMA_INVALID",
    )


def migrate(c):
    c.execute("SELECT pg_advisory_xact_lock(3240077)")
    if not c.execute(
        "SELECT to_regclass('conversation_goals.schema_migrations') t"
    ).fetchone()["t"]:
        c.execute(MIGRATION.read_text())
        c.execute(
            "INSERT INTO conversation_goals.schema_migrations(version,checksum,adapter) VALUES(77,%s,%s)",
            (sha256(MIGRATION.read_bytes()).hexdigest(), "conversation-goal-slots.v1"),
        )
    require_schema(c)


def owned(c, records, ctx, conversation, goal, *, lock=False):
    require_schema(c)
    chat = records.owned(c, ctx, conversation, lock=lock)
    require(
        chat["owner_id"] == ctx.principal_id and not chat["archived_at"],
        "CONVERSATION_GOAL_NOT_AVAILABLE",
    )
    row = c.execute(
        "SELECT * FROM conversation_goals.slots WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND goal_id=%s",
        (*scope(records, ctx, conversation), goal),
    ).fetchone()
    require(row is not None, "CONVERSATION_GOAL_NOT_FOUND")
    record = row["record"]
    require(
        record["schemaVersion"] == "conversation-goal-slot.v1"
        and digest(record) == row["record_digest"]
        and all(
            record[k] == row[v]
            for k, v in [
                ("tenantId", "tenant_id"),
                ("securityDomain", "security_domain"),
                ("conversationId", "conversation_id"),
                ("goalId", "goal_id"),
                ("ownerId", "owner_id"),
                ("rootMessageId", "root_message_id"),
                ("commandId", "command_key"),
                ("requestDigest", "request_digest"),
            ]
        )
        and row["owner_id"] == ctx.principal_id
    )
    return row


def create(c, records, ctx, conversation, body):
    require_schema(c)
    chat = records.owned(c, ctx, conversation, lock=True)
    require(
        chat["owner_id"] == ctx.principal_id and not chat["archived_at"],
        "CONVERSATION_GOAL_NOT_AVAILABLE",
    )
    key = scope(records, ctx, conversation)
    prior = c.execute(
        "SELECT * FROM conversation_goals.slots WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND command_key=%s",
        (*key, body.commandId),
    ).fetchone()
    request = digest(body.model_dump())
    if prior:
        require(
            prior["request_digest"] == request, "CONVERSATION_GOAL_COMMAND_CONFLICT"
        )
        value = owned(c, records, ctx, conversation, prior["goal_id"])
        return {
            "goalId": value["goal_id"],
            "goalDigest": value["record_digest"],
            "replayed": True,
        }
    require(
        chat["version"] == body.expectedConversationVersion,
        "CONVERSATION_VERSION_CONFLICT",
    )
    message = c.execute(
        "SELECT m.author_id,m.focus_link_id,m.created_at FROM private_conversation.messages m WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s AND NOT EXISTS(SELECT 1 FROM private_conversation.message_facts f WHERE f.tenant_id=m.tenant_id AND f.security_domain=m.security_domain AND f.conversation_id=m.conversation_id AND f.message_id=m.message_id)",
        (*key, body.messageId),
    ).fetchone()
    require(
        message
        and message["author_id"] == ctx.principal_id
        and message["focus_link_id"] is None,
        "CONVERSATION_GOAL_ROOT_MESSAGE_INVALID",
    )
    installed = c.execute(
        "SELECT installed_at FROM conversation_goals.schema_migrations WHERE version=77"
    ).fetchone()
    # Pre-cutover failed/unknown legacy calls did not persist a message claim.
    # They cannot be retroactively rebound. This endpoint starts new messages.
    require(
        message["created_at"] >= installed["installed_at"],
        "CONVERSATION_GOAL_ROOT_MESSAGE_PREDATES_SUPPORT",
    )
    prior_goal = c.execute(
        "SELECT goal_id FROM conversation_goals.messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
        (*key, body.messageId),
    ).fetchone()
    require(prior_goal is None, "CONVERSATION_GOAL_MESSAGE_ALREADY_USED")
    claimed = c.execute(
        "SELECT 1 FROM conversation_goals.claimed_messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s LIMIT 1",
        (*key, body.messageId),
    ).fetchone()
    require(claimed is None, "CONVERSATION_GOAL_MESSAGE_ALREADY_USED")
    prior_use = c.execute(
        "SELECT 1 FROM private_conversation.action_intents WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s LIMIT 1",
        (*key, body.messageId),
    ).fetchone()
    require(prior_use is None, "CONVERSATION_GOAL_MESSAGE_ALREADY_USED")
    if c.execute(
        "SELECT to_regclass('draft_assistance.invocation_versions') t"
    ).fetchone()["t"]:
        prior_call = c.execute(
            "SELECT 1 FROM draft_assistance.invocation_versions WHERE namespace=%s AND security_domain=%s AND record#>>'{conversationContext,conversationId}'=%s AND record#>>'{conversationContext,messageId}'=%s LIMIT 1",
            (*key, body.messageId),
        ).fetchone()
        require(prior_call is None, "CONVERSATION_GOAL_MESSAGE_ALREADY_USED")
    return append_verified(c, records, ctx, conversation, body, request)


def append_verified(c, records, ctx, conversation, body, request):
    """Internal append after either pre-dispatch checks or verified result adoption."""
    key = scope(records, ctx, conversation)
    goal = str(uuid5(NAMESPACE_URL, digest([*key, ctx.principal_id, body.commandId])))
    record = dict(
        schemaVersion="conversation-goal-slot.v1",
        tenantId=key[0],
        securityDomain=key[1],
        conversationId=conversation,
        goalId=goal,
        ownerId=ctx.principal_id,
        rootMessageId=body.messageId,
        commandId=body.commandId,
        requestDigest=request,
    )
    c.execute(
        "INSERT INTO conversation_goals.slots(tenant_id,security_domain,conversation_id,goal_id,owner_id,root_message_id,command_key,request_digest,record,record_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *key,
            goal,
            ctx.principal_id,
            body.messageId,
            body.commandId,
            request,
            Jsonb(record),
            digest(record),
        ),
    )
    c.execute(
        "INSERT INTO conversation_goals.journals(tenant_id,security_domain,conversation_id,goal_id,version,state) VALUES(%s,%s,%s,%s,0,NULL)",
        (*key, goal),
    )
    c.execute(
        "INSERT INTO conversation_goals.messages VALUES(%s,%s,%s,%s,%s)",
        (*key, body.messageId, goal),
    )
    return {"goalId": goal, "goalDigest": digest(record), "replayed": False}


def read(c, records, ctx, conversation, goal, *, lock=False):
    owned(c, records, ctx, conversation, goal, lock=lock)
    row = c.execute(
        "SELECT version,state FROM conversation_goals.journals WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND goal_id=%s"
        + (" FOR UPDATE" if lock else ""),
        (*scope(records, ctx, conversation), goal),
    ).fetchone()
    require(row is not None)
    return row


def save(c, records, ctx, conversation, goal, expected_version, state):
    require(len(json.dumps(state).encode()) <= 262144, "JOURNEY_STATE_TOO_LARGE")
    current = read(c, records, ctx, conversation, goal, lock=True)
    require(current["version"] == expected_version, "JOURNEY_VERSION_CONFLICT")
    c.execute(
        "UPDATE conversation_goals.journals SET version=version+1,state=%s,updated_at=now() WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND goal_id=%s",
        (Jsonb(state), *scope(records, ctx, conversation), goal),
    )
    return {"version": expected_version + 1, "state": state, "goalId": goal}


def message_goal(c, records, ctx, conversation, message_id):
    """No association means legacy; an explicit corrupt association never falls back."""
    if not c.execute("SELECT to_regclass('conversation_goals.messages') t").fetchone()[
        "t"
    ]:
        return None
    row = c.execute(
        "SELECT goal_id FROM conversation_goals.messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
        (*scope(records, ctx, conversation), message_id),
    ).fetchone()
    if row is None:
        return None
    owned(c, records, ctx, conversation, row["goal_id"])
    return row["goal_id"]


def attach_message(c, records, ctx, conversation, goal, message_id):
    owned(c, records, ctx, conversation, goal, lock=True)
    m = c.execute(
        "SELECT author_id FROM private_conversation.messages WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s AND message_id=%s",
        (*scope(records, ctx, conversation), message_id),
    ).fetchone()
    require(
        m and m["author_id"] == ctx.principal_id, "CONVERSATION_GOAL_MESSAGE_INVALID"
    )
    c.execute(
        "INSERT INTO conversation_goals.messages VALUES(%s,%s,%s,%s,%s)",
        (*scope(records, ctx, conversation), message_id, goal),
    )
