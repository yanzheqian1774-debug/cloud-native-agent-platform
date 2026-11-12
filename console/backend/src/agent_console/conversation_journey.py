# ruff: noqa: E501 -- Exact parameterized owner SQL.
"""Versioned UI journey journal; never an authority for domain operations."""

import json

from psycopg.types.json import Jsonb

from .private_conversation import ConversationError
from .request_timing import measured


def install(app, service, safe):
    from fastapi import Request
    from pydantic import BaseModel, ConfigDict, Field

    class SaveJourney(BaseModel):
        model_config = ConfigDict(extra="forbid")
        expectedVersion: int = Field(ge=0)
        state: dict

    with service.connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS private_conversation.journeys (
            tenant_id text NOT NULL, security_domain text NOT NULL,
            conversation_id text NOT NULL, version bigint NOT NULL,
            state jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY(tenant_id,security_domain,conversation_id))""")

    @measured("conversation.journal_read")
    def read(ctx, identity):
        with service.connect() as c:
            service.owned(c, ctx, identity)
            row = c.execute(
                "SELECT version,state FROM private_conversation.journeys WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
                (*service.scope(ctx), identity),
            ).fetchone()
        return row or {"version": 0, "state": None}

    def save(ctx, identity, body):
        if len(json.dumps(body.state).encode()) > 262144:
            raise ConversationError("JOURNEY_STATE_TOO_LARGE", 422)
        with service.connect() as c:
            service.owned(c, ctx, identity, lock=True)
            row = c.execute(
                "SELECT version FROM private_conversation.journeys WHERE "
                "tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR UPDATE",
                (*service.scope(ctx), identity),
            ).fetchone()
            if (row["version"] if row else 0) != body.expectedVersion:
                raise ConversationError("JOURNEY_VERSION_CONFLICT")
            version = body.expectedVersion + 1
            c.execute(
                "INSERT INTO private_conversation.journeys VALUES(%s,%s,%s,%s,%s,now()) "
                "ON CONFLICT(tenant_id,security_domain,conversation_id) DO UPDATE "
                "SET version=excluded.version,state=excluded.state,updated_at=now()",
                (*service.scope(ctx), identity, version, Jsonb(body.state)),
            )
        return {"version": version, "state": body.state}

    @app.get("/api/workbench/v1/conversations/{identity}/journey")
    def get(request: Request, identity: str):
        return safe(request, lambda ctx: read(ctx, identity))

    @app.post("/api/workbench/v1/conversations/{identity}/journey")
    def put(request: Request, identity: str, body: SaveJourney):
        return safe(request, lambda ctx: save(ctx, identity, body), True)
