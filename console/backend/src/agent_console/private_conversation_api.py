"""Authenticated private conversation endpoints; only existing owner READ bridges."""

import psycopg
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from agent_console.private_conversation import ConversationError, PrivateConversations
from agent_console.workbench_bff import PREFIX


class CreateConversation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    idempotencyKey: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)


class MessageCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    idempotencyKey: str = Field(min_length=1, max_length=128)
    expectedVersion: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=2048)
    focusLinkId: str | None = Field(default=None, min_length=1, max_length=128)


class WorkTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problemId: str = Field(min_length=1, max_length=128)
    revisionId: str = Field(min_length=1, max_length=128)
    problemDigest: str = Field(pattern=r"^[0-9a-f]{64}$")
    executionDigest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class LinkCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotencyKey: str = Field(min_length=1, max_length=128)
    expectedVersion: int = Field(ge=0)
    target: WorkTarget


def install_private_conversations(
    app, authenticate, require_csrf, authorizer, operations, database_url
):
    reads = {op.name: op for op in operations if op.method == "GET"}

    def owner_read(ctx, name, path):
        op = reads.get(name)
        if op is None:
            raise ConversationError("CONVERSATION_SOURCE_UNAVAILABLE", 503)
        result = authorizer.execute(
            ctx,
            tuple(op.grant_builder(ctx, path, {}, {})),
            operation=op.name,
            payload={},
            path=path,
            query={},
            handler=op.handler,
        )
        return jsonable_encoder(dict(result))

    def resolve(ctx, target):
        problem = owner_read(ctx, "READ_PROBLEM", {"problem_id": target["problemId"]})
        revision = next(
            (
                r
                for r in problem["revisions"]
                if r["revision_id"] == target["revisionId"]
                and r["digest"] == target["problemDigest"]
            ),
            None,
        )
        if revision is None:
            raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
        if target.get("executionDigest"):
            execution = owner_read(
                ctx, "READ_PREPARED_EXECUTION", {"digest": target["executionDigest"]}
            )
            ref = execution["preparation"]["semantics"]["target"]["problem"]
            if (
                execution["digest"] != target["executionDigest"]
                or ref["resource_id"] != target["problemId"]
                or ref["revision_id"] != target["revisionId"]
                or ref["digest"] != target["problemDigest"]
            ):
                raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
        return {"title": revision["title"]}

    service = PrivateConversations(database_url, resolve) if database_url else None

    def invoke(request, action, write=False):
        session, ctx = authenticate(request)
        if write:
            require_csrf(request, session)
        if not service:
            raise ConversationError("CONVERSATIONS_DISABLED", 404)
        return {"result": jsonable_encoder(action(ctx))}

    @app.exception_handler(ConversationError)
    async def failure(_, exc):
        return JSONResponse(status_code=exc.status, content={"reasonCode": exc.reason})

    # Catch storage failures locally; never mask an authority error as an empty list.
    def safe(request, action, write=False):
        try:
            return invoke(request, action, write)
        except psycopg.Error:
            return JSONResponse(
                status_code=503,
                content={"reasonCode": "CONVERSATION_STORAGE_UNAVAILABLE"},
            )

    @app.get(PREFIX + "/conversations/capabilities")
    def capabilities(request: Request):
        authenticate(request)
        return {"result": {"enabled": bool(service), "schemaVersion": 1}}

    @app.get(PREFIX + "/conversations")
    def listing(request: Request):
        return safe(request, lambda ctx: service.list(ctx))

    @app.post(PREFIX + "/conversations")
    def create(request: Request, body: CreateConversation):
        return safe(request, lambda ctx: service.create(ctx, body.model_dump()), True)

    @app.get(PREFIX + "/conversations/{identity}")
    def read(request: Request, identity: str):
        return safe(request, lambda ctx: service.read(ctx, identity))

    @app.post(PREFIX + "/conversations/{identity}/messages")
    def append(request: Request, identity: str, body: MessageCommand):
        return safe(
            request,
            lambda ctx: service.mutate(ctx, identity, body.model_dump(), "message"),
            True,
        )

    @app.post(PREFIX + "/conversations/{identity}/links")
    def link(request: Request, identity: str, body: LinkCommand):
        return safe(
            request,
            lambda ctx: service.mutate(
                ctx, identity, body.model_dump(exclude_none=True), "link"
            ),
            True,
        )
