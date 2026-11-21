# ruff: noqa: E501 -- Exact scoped SQL and bounded policy predicates.
"""Browser-only multi-transaction orchestration. No legacy header authentication."""

from fastapi import Request
from pydantic import ValidationError

from . import mcp_tool_test_postgres as store
from .authority_contracts import AuthorityError
from .mcp_tool_test_owner import TestCommand, ToolBinding, read_grant
from .mcp_tool_test_policy import require
from .workbench_bff import PREFIX, WorkbenchBoundaryError


def install(owner):
    def installer(app, authenticate, require_csrf, policy):
        root = PREFIX + "/resource-management/mcp/{identity}/tool-tests"

        def context(request):
            if request.query_params:
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422)
            session, ctx = authenticate(request)
            if request.method != "GET":
                require_csrf(request, session)
            return ctx

        def run(ctx, b, identity, key, handler, *, payload=None):
            return owner.authorizer.execute(
                ctx,
                (read_grant(b),),
                operation="MCP_TOOL_TEST",
                payload=payload or {"commandKey": key},
                path={"identity": identity, "key": key},
                query={},
                handler=handler,
            )

        def saved_binding(ctx, identity, key):
            # Internal lookup only; no existence/details returned before current READ.
            with owner.authorizer.repository.connection_scope() as c:
                row = store.read(c, ctx, key)
            require(row is not None, "REQUEST_NOT_FOUND")
            b = ToolBinding.model_validate(row["request"]["binding"])
            require(b.mcp.resource_id == identity, "RESOURCE_CHANGED")
            return b

        @app.get(root)
        def history(request: Request, identity: str):
            ctx = context(request)
            options = []
            # Each advertised policy option still passes current exact READ/source/ownership.
            for b in owner.policy().bindings:
                if (
                    b.subject != ctx.principal_id
                    or b.namespace != ctx.scope.tenant_id
                    or b.securityDomain != ctx.scope.security_domain
                    or b.mcp.resource_id != identity
                ):
                    continue
                try:
                    owner.binding(ctx, b.digest)
                    run(
                        ctx,
                        b,
                        identity,
                        "",
                        lambda call, binding=b: owner.exact(call, binding),
                    )
                except AuthorityError:
                    continue
                options.append(
                    {
                        "bindingDigest": b.digest,
                        "publishedReference": b.mcp.model_dump(),
                        "toolName": b.toolName,
                        "input": b.arguments,
                    }
                )
            with owner.authorizer.repository.connection_scope() as c:
                rows = c.execute(
                    "SELECT command_key,request FROM authorization_admin.mcp_tool_test_requests WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND request->'binding'->'mcp'->>'resource_id'=%s ORDER BY created_at DESC,command_key LIMIT 50",
                    (*store.scope(ctx), identity),
                ).fetchall()
            results = []
            for row in rows:
                b = ToolBinding.model_validate(row["request"]["binding"])
                try:
                    results.append(
                        run(ctx, b, identity, row["command_key"], owner.read)
                    )
                except AuthorityError:
                    continue
            return {
                "result": {
                    "options": options,
                    "history": results,
                    "publishedOnly": True,
                    "automaticRetry": False,
                }
            }

        @app.post(root)
        async def prepare(request: Request, identity: str):
            ctx = context(request)
            body = await request.body()
            if len(body) > policy.maximum_body_bytes:
                raise WorkbenchBoundaryError("REQUEST_TOO_LARGE", 413)
            try:
                cmd = TestCommand.model_validate_json(body)
            except ValidationError as exc:
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422) from exc
            b = owner.binding(ctx, cmd.bindingDigest)
            return {
                "result": run(
                    ctx,
                    b,
                    identity,
                    cmd.commandKey,
                    owner.prepare,
                    payload=cmd.model_dump(),
                )
            }

        @app.get(root + "/{key}")
        def receipt(request: Request, identity: str, key: str):
            ctx = context(request)
            b = saved_binding(ctx, identity, key)
            return {"result": run(ctx, b, identity, key, owner.read)}

        @app.post(root + "/{key}/dispatch")
        async def dispatch(request: Request, identity: str, key: str):
            ctx = context(request)
            if (await request.body()) not in (b"", b"{}"):
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422)
            b = saved_binding(ctx, identity, key)
            claimed = run(ctx, b, identity, key, owner.claim)
            ticket = claimed["ticket"]
            if ticket is None:
                return {"result": claimed["receipt"]}
            # Claim transaction has COMMITTED before this authorization/HTTP transaction.
            try:
                result = run(
                    ctx, b, identity, key, lambda call: owner.transport(call, ticket)
                )
            except AuthorityError:
                # May include an error after a transport callback in future adapters;
                # conservatively never assert NOT_DISPATCHED from broad exceptions.
                result = {
                    "state": "UNKNOWN",
                    "reasonCode": "MCP_DISPATCH_NOT_CONFIRMED",
                }
            except Exception:
                result = {
                    "state": "UNKNOWN",
                    "reasonCode": "MCP_DISPATCH_NOT_CONFIRMED",
                }
            owner.finalize(ctx, key, ticket, result)
            return {"result": run(ctx, b, identity, key, owner.read)}

    return installer
