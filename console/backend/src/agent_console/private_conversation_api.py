"""Authenticated private conversation endpoints; only existing owner READ bridges."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

import psycopg
from anyio import to_thread
from fastapi import Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_console.private_conversation import (
    ConversationError,
    PrivateConversations,
    source_read_failure,
)
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
    target: WorkTarget | dict[str, Any]

    @model_validator(mode="after")
    def exact_target(self):
        if isinstance(self.target, dict):
            if set(self.target) == {"source"}:
                self.target = {
                    "source": SourceReference.model_validate(
                        self.target["source"]
                    ).model_dump(exclude_none=True)
                }
            else:
                self.target = WorkTarget.model_validate(self.target)
        return self


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["DRAFT", "PLANNING", "PROBLEM", "CAPABILITY"]
    invocationId: str | None = Field(default=None, min_length=1, max_length=200)
    contextId: str | None = Field(default=None, min_length=1, max_length=200)
    turnId: str | None = Field(default=None, min_length=1, max_length=200)
    turnVersion: int | None = Field(default=None, ge=1)
    requestRevision: int | None = Field(default=None, ge=1)
    target: dict[str, Any] | None = None

    @model_validator(mode="after")
    def shape(self):
        required = {
            "DRAFT": {"kind", "invocationId", "contextId", "turnId", "turnVersion"},
            "PLANNING": {
                "kind",
                "invocationId",
                "contextId",
                "requestRevision",
                "target",
            },
            "PROBLEM": {"kind", "target"},
            "CAPABILITY": {"kind", "target"},
        }[self.kind]
        if {k for k, v in self.model_dump().items() if v is not None} != required:
            raise ValueError("CONVERSATION_SOURCE_INVALID")
        if self.kind == "PROBLEM":
            self.target = WorkTarget.model_validate(self.target).model_dump(
                exclude_none=True
            )
        elif self.kind == "CAPABILITY":
            from .capability_conversation_source import CapabilityConversationTarget

            self.target = CapabilityConversationTarget.model_validate(
                self.target
            ).model_dump()
        elif self.kind == "PLANNING":
            from .plan_suggestion_domain import ProblemTarget

            self.target = ProblemTarget.model_validate(self.target).model_dump(
                mode="json"
            )
        return self


class SourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotencyKey: str = Field(min_length=1, max_length=128)
    expectedVersion: int = Field(ge=0)
    source: SourceReference


class IntentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotencyKey: str = Field(min_length=1, max_length=128)
    expectedVersion: int = Field(ge=0)
    messageId: str = Field(min_length=1, max_length=128)
    action: Literal["DRAFT", "CREATE_PROBLEM", "PLANNING", "PLANNING_CONTINUE"]
    payload: dict[str, Any]
    source: SourceReference | None = None
    expectedOwnerVersion: int = Field(ge=0)
    confirmed: Literal[True]

    @model_validator(mode="after")
    def canonical_payload(self):
        from .draft_assistance_api import BeginDraftAssistance
        from .plan_suggestion_invocation import PlanningRequest
        from .workbench_business_problem import CreateCaseBusinessProblem

        model = {
            "DRAFT": BeginDraftAssistance,
            "CREATE_PROBLEM": CreateCaseBusinessProblem,
            "PLANNING": PlanningRequest,
            "PLANNING_CONTINUE": PlanningRequest,
        }[self.action]
        self.payload = model.model_validate(self.payload).model_dump(
            mode="json", exclude_none=True
        )
        return self


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
        if "source" in target:
            source = SourceReference.model_validate(target["source"]).model_dump(
                exclude_none=True
            )
            facts = source_read(ctx, source)
            return {"title": facts["title"]}
        target = WorkTarget.model_validate(target).model_dump(exclude_none=True)
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
        return {
            "title": revision["title"],
            "ownerVersion": problem.get("problem", {}).get("aggregate_version", 0),
        }

    from .request_timing import measured, span

    @measured("conversation.source_read")
    def source_read(ctx, source):
        from .conversation_actions import reference

        kind = source["kind"]
        if kind == "CAPABILITY":
            from .capability_conversation_source import read_capability_source

            return read_capability_source(ctx, source, owner_read)
        if kind == "PROBLEM":
            value = resolve(ctx, source["target"])
            return {**value, "state": "RECORDED", "receiptState": "SUCCEEDED"}
        reader = getattr(
            app.state,
            "conversation_draft_reader"
            if kind == "DRAFT"
            else "conversation_planning_reader",
            None,
        )
        if reader is None:
            raise ConversationError("CONVERSATION_SOURCE_UNAVAILABLE", 503)
        try:
            value = reader(ctx, source["invocationId"])
        except Exception as exc:
            raise source_read_failure(exc) from exc
        if reference(kind, value) != source:
            raise ConversationError("CONVERSATION_SOURCE_MISMATCH")
        if kind == "DRAFT":
            state, result_kind = value["state"], value.get("resultKind")
            reason, version = value.get("reasonCode"), value["aggregateVersion"]
            content = {"contentDisposition": "RESULT_CONTENT_NOT_RETAINED"}
            content["transport"] = value.get("transport", "NOT_OBSERVED")
        else:
            result = value["result"]
            state, result_kind = result["technical_status"], result.get("kind")
            reason, version = result.get("reason"), source["requestRevision"]
            # Only original-owner retained normalized questions, never a client reply.
            content = {"questions": result.get("questions", [])}
            content["transport"] = value["invocation"].get("transport", "NOT_OBSERVED")
        receipt = (
            "SUCCEEDED"
            if state == "SUCCEEDED"
            else "FAILED"
            if state
            in {
                "FAILED",
                "FAILED_PRE_DISPATCH",
                "REJECTED",
                "REJECTED_BY_USER",
                "CANCELLATION_CONFIRMED",
                "CANCELLED",
                "KNOWN_FAILED",
            }
            else "UNKNOWN"
        )
        return {
            "title": "草稿辅助来源" if kind == "DRAFT" else "规划来源",
            "state": state,
            "receiptState": receipt,
            "resultKind": result_kind,
            "reasonCode": reason,
            "ownerVersion": version,
            **content,
        }

    def planning_request_read(ctx, key, payload):
        reader = getattr(app.state, "conversation_planning_request_reader", None)
        if reader is None:
            raise ConversationError("CONVERSATION_SOURCE_UNAVAILABLE", 503)
        return reader(ctx, key, payload)

    from .development_administrator import authorized

    def administrator_access(connection, context):
        if context.principal_id != "human:development-admin":
            return False
        return authorized(
            authorizer.authorization,
            context,
            generation=authorizer.controller.readiness.generation,
            recovery_epoch=authorizer.controller.readiness.recovery_epoch,
            connection=connection,
        )

    service = (
        PrivateConversations(database_url, resolve, administrator_access)
        if database_url
        else None
    )
    from .conversation_actions import ConversationActions

    actions = (
        ConversationActions(service, source_read, planning_request_read)
        if service
        else None
    )

    @app.get("/api/workbench/v1/development-administrator")
    def read_development_administrator(request: Request):
        _, context = authenticate(request)
        active = administrator_access(None, context)
        return {
            "result": {
                "subject": context.principal_id,
                "enabled": active,
                "role": "DEVELOPMENT_ADMINISTRATOR" if active else None,
                "allConversations": active,
                "allResources": active,
                "resourceApprovalRequired": not active,
            }
        }

    def capability_contract_in_owner_call(call, identity, message_id):
        from dataclasses import replace

        from .capability_conversation_source import read_capability_source
        from .workbench_business_problem import OwnerPrincipal

        def same_transaction_read(ctx, name, path):
            op = reads.get(name)
            if op is None:
                raise ConversationError("CONVERSATION_SOURCE_UNAVAILABLE", 503)
            principal = OwnerPrincipal(
                ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain
            )
            for grant in op.grant_builder(ctx, path, {}, {}):
                call.authority.require(
                    principal, grant.owner, grant.action, grant.exact_resource
                )
            value = op.handler(
                replace(call, operation=op.name, payload={}, path=path, query={})
            )
            return jsonable_encoder(dict(value))

        return actions.capability_contract(
            call.context,
            identity,
            message_id,
            connection=call.connection,
            source_reader=lambda ctx, source: read_capability_source(
                ctx, source, same_transaction_read
            ),
        )

    app.state.capability_execution_contract_reader = (
        capability_contract_in_owner_call if actions else None
    )
    app.state.conversation_actions = actions
    if service:
        service.facts_reader = actions
        previous_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def conversation_lifespan(application):
            await to_thread.run_sync(service.start_pool)
            try:
                async with previous_lifespan(application) as state:
                    yield state
            finally:
                await to_thread.run_sync(service.close_pool)

        app.router.lifespan_context = conversation_lifespan

    def invoke(request, action, write=False):
        with span("conversation.authentication"):
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
        except psycopg.Error as exc:
            diagnostic = getattr(request.state, "diagnostic_id", None)
            # Only fixed categories and SQLSTATE: never exception text, SQL,
            # parameters, database names, connection strings or user content.
            state = exc.sqlstate
            if (
                not isinstance(state, str)
                or len(state) != 5
                or not all(
                    char in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for char in state
                )
            ):
                state = "UNKNOWN"
            category = (
                "POOL_TIMEOUT"
                if isinstance(exc, PoolTimeout)
                else "CONNECTION_TIMEOUT"
                if isinstance(exc, psycopg.errors.ConnectionTimeout)
                else "OPERATIONAL"
                if isinstance(exc, psycopg.OperationalError)
                else "INTEGRITY"
                if isinstance(exc, psycopg.IntegrityError)
                else "PROGRAMMING"
                if isinstance(exc, psycopg.ProgrammingError)
                else "DATABASE"
            )
            logging.getLogger(__name__).warning(
                "conversation_storage_failure request_id=%s route=%s "
                "category=%s sqlstate=%s phase=%s",
                diagnostic,
                getattr(request.scope.get("route"), "path", "UNREGISTERED"),
                category,
                state,
                exc._conversation_storage_phase
                if getattr(exc, "_conversation_storage_phase", None)
                in {"CONNECT", "POOL_ACQUIRE"}
                else "UNKNOWN",
            )
            return JSONResponse(
                status_code=503,
                content={"reasonCode": "CONVERSATION_STORAGE_UNAVAILABLE"},
                headers={"X-Diagnostic-ID": diagnostic} if diagnostic else None,
            )

    if service:
        from .conversation_journey import install as install_journey

        install_journey(app, service, safe)
        if "READ_CAPABILITY_REVISION" in reads:
            from .capability_work_journal import install as install_capability_journal

            install_capability_journal(app, service, actions, safe)

    @app.get(PREFIX + "/conversations/capabilities")
    def capabilities(request: Request):
        _, context = authenticate(request)
        history = getattr(app.state, "conversation_history_access_available", None)
        return {
            "result": {
                "enabled": bool(service),
                "schemaVersion": 1,
                "historyReadPreparation": bool(history and history(context)),
            }
        }

    @app.get(PREFIX + "/conversations")
    def listing(request: Request):
        return safe(request, lambda ctx: service.list(ctx))

    @app.post(PREFIX + "/conversations")
    def create(request: Request, body: CreateConversation):
        return safe(request, lambda ctx: service.create(ctx, body.model_dump()), True)

    @app.get(PREFIX + "/conversations/{identity}")
    def read(request: Request, identity: str):
        return safe(request, lambda ctx: service.read(ctx, identity))

    @app.get(PREFIX + "/conversations/{identity}/sources")
    def conversation_sources(request: Request, identity: str):
        def read_sources(ctx):
            access = getattr(app.state, "conversation_source_access", None)
            if access is None:
                raise ConversationError("CONVERSATION_SOURCE_ACCESS_UNAVAILABLE", 503)
            return access.catalogue(ctx, identity)

        return safe(request, read_sources)

    @app.get(PREFIX + "/conversations/{identity}/create-status")
    def creation_status(
        request: Request,
        identity: str,
        draftInvocationId: str = Query(min_length=1, max_length=200),
        requestKey: str = Query(min_length=1, max_length=200),
    ):
        def observe(ctx):
            reader = getattr(app.state, "owned_business_creation_read", None)
            if reader is None:
                raise ConversationError("CONVERSATION_CREATE_STATUS_UNAVAILABLE", 503)
            return reader.read(ctx, identity, draftInvocationId, requestKey)

        return safe(request, observe)

    @app.get(PREFIX + "/conversations/{identity}/criterion-status")
    def criterion_status(
        request: Request,
        identity: str,
        draftInvocationId: str = Query(min_length=1, max_length=200),
        requestKey: str = Query(min_length=1, max_length=200),
    ):
        def observe(ctx):
            reader = getattr(app.state, "owned_business_criterion_read", None)
            if reader is None:
                raise ConversationError(
                    "CONVERSATION_CRITERION_STATUS_UNAVAILABLE", 503
                )
            return reader.read(ctx, identity, draftInvocationId, requestKey)

        return safe(request, observe)

    @app.get(PREFIX + "/conversations/{identity}/head")
    def head(request: Request, identity: str):
        return safe(request, lambda ctx: service.head(ctx, identity))

    @app.get(PREFIX + "/conversations/{identity}/work-links")
    def work_links(request: Request, identity: str):
        return safe(request, lambda ctx: service.work_links(ctx, identity))

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

    @app.post(PREFIX + "/conversations/{identity}/sources")
    def source(request: Request, identity: str, body: SourceCommand):
        return safe(
            request,
            lambda ctx: actions.source(
                ctx, identity, body.model_dump(exclude_none=True)
            ),
            True,
        )

    @app.get(
        PREFIX + "/conversations/{identity}/sources/{message_id}/execution-contract"
    )
    def capability_contract(request: Request, identity: str, message_id: str):
        return safe(
            request, lambda ctx: actions.capability_contract(ctx, identity, message_id)
        )

    @app.post(PREFIX + "/conversations/{identity}/intents")
    def intent(request: Request, identity: str, body: IntentCommand):
        return safe(
            request,
            lambda ctx: actions.prepare(
                ctx, identity, body.model_dump(exclude_none=True)
            ),
            True,
        )

    @app.get(PREFIX + "/conversations/{identity}/intents/{intent_id}")
    def reconcile(request: Request, identity: str, intent_id: str):
        return safe(request, lambda ctx: actions.reconcile(ctx, identity, intent_id))

    @app.post(PREFIX + "/conversations/{identity}/intents/{intent_id}/receipt")
    def save_receipt(request: Request, identity: str, intent_id: str):
        return safe(
            request,
            lambda ctx: actions.reconcile(ctx, identity, intent_id, persist=True),
            True,
        )
