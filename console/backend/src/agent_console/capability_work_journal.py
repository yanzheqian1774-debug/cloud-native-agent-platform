"""Append-only source-specific UI continuation, never domain execution authority."""

import hashlib
import json
from pathlib import Path

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .postgres_schema_compatibility import (
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)
from .private_conversation import ConversationError, digest

MIGRATION = Path(__file__).parents[2] / "migrations/0054_capability_work_journal.sql"
KEY = ("tenant_id", "security_domain", "conversation_id", "source_message_id")
STRUCTURE = (
    Table(
        "private_conversation.schema_migrations",
        columns(("version", "integer"), ("checksum", "text")),
        (primary("version"),),
    ),
    Table(
        "private_conversation.capability_work_journal",
        columns(
            *((k, "text") for k in KEY),
            ("version", "bigint"),
            ("contract_digest", "text"),
            ("state", "jsonb"),
            ("command_id", "text"),
            ("payload_digest", "text"),
            ("actor_id", "text"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary(*KEY, "version"),
            unique(*KEY, "command_id"),
            foreign(KEY, "private_conversation.messages", (*KEY[:3], "message_id")),
        ),
        ("immutable_capability_work_journal",),
    ),
)


def compatibility(connection):
    row = connection.execute(
        "SELECT checksum FROM private_conversation.schema_migrations WHERE version=54"
    ).fetchone()
    if (
        not row
        or row["checksum"] != hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
        or not schema_is_compatible(connection, STRUCTURE)
    ):
        raise ConversationError("CAPABILITY_JOURNAL_SCHEMA_INCOMPATIBLE", 503)


def migrate(connection):
    connection.execute("SELECT pg_advisory_xact_lock(2760054)")
    connection.execute(MIGRATION.read_text())
    connection.execute(
        "INSERT INTO private_conversation.schema_migrations "
        "(version,checksum) VALUES(54,%s) "
        "ON CONFLICT DO NOTHING",
        (hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),),
    )
    compatibility(connection)


class SaveCapabilityJourney(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(ge=0)
    idempotencyKey: str = Field(min_length=1, max_length=128)
    contractDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: dict


class CapabilityWorkJournal:
    def __init__(self, records, actions):
        self.records, self.actions = records, actions

    def read(self, ctx, identity, message):
        resolved = self.actions.capability_contract(ctx, identity, message)
        with self.records.connect() as c:
            self.records.owned(c, ctx, identity)
            row = c.execute(
                "SELECT version,state,contract_digest "
                "FROM private_conversation.capability_work_journal "
                "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                "AND source_message_id=%s ORDER BY version DESC LIMIT 1",
                (*self.records.scope(ctx), identity, message),
            ).fetchone()
        if row and row["contract_digest"] != resolved["contractDigest"]:
            raise ConversationError("CAPABILITY_JOURNAL_CONTRACT_MISMATCH", 409)
        return {
            "version": row["version"] if row else 0,
            "state": row["state"] if row else None,
            "contractDigest": resolved["contractDigest"],
            "sourceMessageId": message,
        }

    def save(self, ctx, identity, message, body):
        if len(json.dumps(body.state, ensure_ascii=False).encode()) > 262144:
            raise ConversationError("JOURNEY_STATE_TOO_LARGE", 422)
        resolved = self.actions.capability_contract(ctx, identity, message)
        if body.contractDigest != resolved["contractDigest"]:
            raise ConversationError("CAPABILITY_JOURNAL_CONTRACT_MISMATCH", 409)
        hashed = digest(body.model_dump(mode="json"))
        with self.records.connect() as c:
            conversation = self.records.owned(c, ctx, identity, lock=True)
            key = (*self.records.scope(ctx), identity, message)
            old = c.execute(
                "SELECT version,state,payload_digest "
                "FROM private_conversation.capability_work_journal "
                "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                "AND source_message_id=%s AND command_id=%s",
                (*key, body.idempotencyKey),
            ).fetchone()
            if old:
                if old["payload_digest"] != hashed:
                    raise ConversationError("CAPABILITY_JOURNAL_COMMAND_CONFLICT", 409)
                return {
                    "version": old["version"],
                    "state": old["state"],
                    "replayed": True,
                }
            if conversation["archived_at"]:
                raise ConversationError("CONVERSATION_ARCHIVED", 409)
            latest = c.execute(
                "SELECT version FROM private_conversation.capability_work_journal "
                "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s "
                "AND source_message_id=%s ORDER BY version DESC LIMIT 1",
                key,
            ).fetchone()
            version = latest["version"] if latest else 0
            if version != body.expectedVersion:
                raise ConversationError("JOURNEY_VERSION_CONFLICT", 409)
            version += 1
            c.execute(
                "INSERT INTO private_conversation.capability_work_journal "
                "(tenant_id,security_domain,conversation_id,source_message_id,version,"
                "contract_digest,state,command_id,payload_digest,actor_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    version,
                    body.contractDigest,
                    Jsonb(body.state),
                    body.idempotencyKey,
                    hashed,
                    ctx.principal_id,
                ),
            )
        return {"version": version, "state": body.state, "replayed": False}


def install(app, records, actions, safe):
    from fastapi import Request

    with records.connect() as c:
        compatibility(c)
    journal = CapabilityWorkJournal(records, actions)
    route = "/api/workbench/v1/conversations/{identity}/sources/{message_id}/journey"

    @app.get(route)
    def read(request: Request, identity: str, message_id: str):
        return safe(request, lambda ctx: journal.read(ctx, identity, message_id))

    @app.post(route)
    def save(
        request: Request, identity: str, message_id: str, body: SaveCapabilityJourney
    ):
        return safe(
            request, lambda ctx: journal.save(ctx, identity, message_id, body), True
        )
