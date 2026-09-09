"""Closed, session-authenticated Workbench BFF route factory.

This module has no startup side effects.  The public listener must explicitly
compose every domain operation with a transactional owner handler.
"""

from __future__ import annotations

import html
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent_console.authority_contracts import (
    AuthorityError,
    ExactGrant,
    TrustedRequestContext,
)
from agent_console.browser_session_application import BrowserSessionService
from agent_console.workbench_bff_schemas import (
    WorkbenchOperationResponse,
    WorkbenchPrincipal,
    WorkbenchSessionMetadata,
    WorkbenchSessionResponse,
)
from agent_console.workbench_owner_authorization import (
    TransactionalOwnerHandler,
    WorkbenchOwnerAuthorization,
    WorkbenchOwnerError,
)

PREFIX = "/api/workbench/v1"
SESSION_COOKIE = "__Host-workbench_session"
UNTRUSTED_IDENTITY_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-principal-id",
        "x-tenant-id",
        "x-security-domain",
        "x-product-read-authorized",
        "x-trusted-request-context",
    }
)
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class WorkbenchBoundaryError(ValueError):
    def __init__(self, reason_code: str, status_code: int) -> None:
        self.reason_code = reason_code
        self.status_code = status_code
        super().__init__(reason_code)


GrantBuilder = Callable[
    [
        TrustedRequestContext,
        Mapping[str, str],
        Mapping[str, Any],
        Mapping[str, Any],
    ],
    Sequence[ExactGrant],
]


@dataclass(frozen=True, slots=True)
class WorkbenchOperation:
    """One immutable browser route and its exact owner authorization contract."""

    name: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    request_model: type[BaseModel] | None
    query_model: type[BaseModel] | None
    grant_builder: GrantBuilder
    handler: TransactionalOwnerHandler[Mapping[str, Any]]
    success_status: int = 200

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.path.startswith(f"{PREFIX}/")
            or "//" in self.path
            or self.path.startswith(f"{PREFIX}/authorization/")
            or self.path in {f"{PREFIX}/login", f"{PREFIX}/session"}
        ):
            raise AuthorityError("WORKBENCH_OPERATION_INVALID")
        if self.method in {"GET", "DELETE"} and self.request_model is not None:
            raise AuthorityError("WORKBENCH_OPERATION_INVALID")
        if self.method in {"POST", "PUT", "PATCH"} and self.request_model is None:
            raise AuthorityError("WORKBENCH_OPERATION_INVALID")
        if self.success_status < 200 or self.success_status >= 300:
            raise AuthorityError("WORKBENCH_OPERATION_INVALID")


@dataclass(frozen=True, slots=True)
class WorkbenchBffPolicy:
    allowed_host: str
    allowed_origin: str
    maximum_body_bytes: int = 128 * 1024

    def __post_init__(self) -> None:
        if (
            not self.allowed_host
            or "/" in self.allowed_host
            or not self.allowed_origin.startswith("https://")
            or self.allowed_origin.rstrip("/") != self.allowed_origin
            or self.maximum_body_bytes < 1024
        ):
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")


def _status_for_authority_error(reason: str) -> int:
    if reason == "AUTHENTICATION_REQUIRED":
        return 401
    if reason == "CSRF_VALIDATION_FAILED":
        return 403
    if reason in {
        "AUTHORITY_STORAGE_UNAVAILABLE",
        "AUTHORITY_RECOVERY_REQUIRED",
        "OWNER_TRANSACTION_UNAVAILABLE",
    }:
        return 503
    if reason in {"INVALID_GRANT_TARGET", "WORKBENCH_OPERATION_INVALID"}:
        return 422
    return 404


def _request_id() -> str:
    return f"workbench-request-{secrets.token_hex(12)}"


def _error(reason: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"reasonCode": reason, "requestId": _request_id()},
    )


def create_workbench_bff(
    sessions: BrowserSessionService,
    authorizer: WorkbenchOwnerAuthorization,
    policy: WorkbenchBffPolicy,
    *,
    operations: Sequence[WorkbenchOperation] = (),
) -> FastAPI:
    """Build the public route set from an explicit, duplicate-free registry."""

    identities = {(item.method, item.path) for item in operations}
    names = {item.name for item in operations}
    if len(identities) != len(operations) or len(names) != len(operations):
        raise AuthorityError("WORKBENCH_OPERATION_INVALID")

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def browser_boundary(request: Request, call_next):
        if request.headers.get("host") != policy.allowed_host:
            response = _error("WORKBENCH_HOST_REJECTED", 400)
        elif UNTRUSTED_IDENTITY_HEADERS.intersection(request.headers.keys()):
            response = _error("UNTRUSTED_IDENTITY_HEADER", 400)
        elif request.method in UNSAFE_METHODS and (
            request.headers.get("origin") != policy.allowed_origin
            or request.headers.get("sec-fetch-site", "same-origin") != "same-origin"
        ):
            response = _error("CSRF_VALIDATION_FAILED", 403)
        else:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    too_large = int(content_length) > policy.maximum_body_bytes
                except ValueError:
                    too_large = True
                if too_large:
                    response = _error("REQUEST_TOO_LARGE", 413)
                else:
                    response = await call_next(request)
            else:
                response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(AuthorityError)
    async def authority_failure(_: Request, exc: AuthorityError):
        return _error(exc.reason_code, _status_for_authority_error(exc.reason_code))

    @app.exception_handler(WorkbenchBoundaryError)
    async def boundary_failure(_: Request, exc: WorkbenchBoundaryError):
        return _error(exc.reason_code, exc.status_code)

    @app.exception_handler(WorkbenchOwnerError)
    async def owner_failure(_: Request, exc: WorkbenchOwnerError):
        return _error(exc.reason_code, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def request_validation_failure(_: Request, __: RequestValidationError):
        return _error("REQUEST_INVALID", 422)

    @app.exception_handler(StarletteHTTPException)
    async def route_failure(_: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return _error("WORKBENCH_ROUTE_NOT_FOUND", 404)
        if exc.status_code == 405:
            return _error("WORKBENCH_METHOD_NOT_ALLOWED", 405)
        return _error("REQUEST_INVALID", exc.status_code)

    def authenticate(request: Request):
        value = request.cookies.get(SESSION_COOKIE)
        if not value:
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return sessions.authenticate_session(value)

    def require_csrf(request: Request, session) -> None:
        token = request.headers.get("x-csrf-token", "")
        sessions.verify_csrf(token, session)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{PREFIX}/login", response_class=HTMLResponse)
    def login_form() -> HTMLResponse:
        nonce = html.escape(sessions.issue_login_nonce(), quote=True)
        document = (
            '<!doctype html><html><body><form method="post" '
            f'action="{PREFIX}/session">'
            f'<input type="hidden" name="loginNonce" value="{nonce}">'
            '<input type="password" name="bootstrapCredential" '
            'autocomplete="current-password" required>'
            '<button type="submit">Sign in</button></form></body></html>'
        )
        return HTMLResponse(document)

    @app.post(f"{PREFIX}/session", status_code=303)
    async def create_session(request: Request) -> Response:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise WorkbenchBoundaryError("REQUEST_INVALID", 422)
        body = await request.body()
        if len(body) > policy.maximum_body_bytes:
            raise WorkbenchBoundaryError("REQUEST_TOO_LARGE", 413)
        try:
            values = parse_qs(body.decode("utf-8"), strict_parsing=True)
            if set(values) != {"loginNonce", "bootstrapCredential"} or any(
                len(item) != 1 for item in values.values()
            ):
                raise ValueError
            login_nonce = values["loginNonce"][0]
            credential = values["bootstrapCredential"][0]
        except (UnicodeDecodeError, ValueError, KeyError) as exc:
            raise WorkbenchBoundaryError("REQUEST_INVALID", 422) from exc
        secret = sessions.create_session(login_nonce, credential)
        response = RedirectResponse("/workbench", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            secret.value,
            max_age=max(0, int((secret.expires_at - sessions.clock()).total_seconds())),
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.get(f"{PREFIX}/session", response_model=WorkbenchSessionResponse)
    def read_session(request: Request) -> WorkbenchSessionResponse:
        session, context = authenticate(request)
        return WorkbenchSessionResponse(
            principal=WorkbenchPrincipal(
                principalId=context.principal_id,
                tenantId=context.scope.tenant_id,
                securityDomain=context.scope.security_domain,
            ),
            session=WorkbenchSessionMetadata(
                expiresAt=session.absolute_expires_at,
                idleExpiresAt=session.idle_expires_at,
            ),
            csrfToken=sessions.issue_csrf(session),
        )

    @app.post(f"{PREFIX}/session/rotate", status_code=204)
    def rotate_session(request: Request) -> Response:
        session, _ = authenticate(request)
        require_csrf(request, session)
        current_value = request.cookies[SESSION_COOKIE]
        secret = sessions.rotate_session(current_value)
        response = Response(status_code=204)
        response.set_cookie(
            SESSION_COOKIE,
            secret.value,
            max_age=max(0, int((secret.expires_at - sessions.clock()).total_seconds())),
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.delete(f"{PREFIX}/session", status_code=204)
    def delete_session(request: Request) -> Response:
        session, context = authenticate(request)
        require_csrf(request, session)
        sessions.logout(request.cookies[SESSION_COOKIE], actor_id=context.principal_id)
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True)
        return response

    def operation_endpoint(operation: WorkbenchOperation):
        async def endpoint(request: Request):
            session, context = authenticate(request)
            if request.method in UNSAFE_METHODS:
                require_csrf(request, session)
            payload: Mapping[str, Any] = {}
            if operation.request_model is not None:
                body = await request.body()
                if len(body) > policy.maximum_body_bytes:
                    raise WorkbenchBoundaryError("REQUEST_TOO_LARGE", 413)
                try:
                    model = operation.request_model.model_validate_json(body)
                except ValidationError as exc:
                    raise WorkbenchBoundaryError("REQUEST_INVALID", 422) from exc
                payload = model.model_dump(mode="json", exclude_none=True)
            try:
                query = (
                    {}
                    if operation.query_model is None
                    else operation.query_model.model_validate(
                        dict(request.query_params)
                    ).model_dump(mode="json", exclude_none=True)
                )
            except ValidationError as exc:
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422) from exc
            if operation.query_model is None and request.query_params:
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422)
            grants = tuple(
                operation.grant_builder(context, request.path_params, payload, query)
            )
            result = authorizer.execute(
                context,
                grants,
                operation=operation.name,
                payload=payload,
                path=request.path_params,
                query=query,
                handler=operation.handler,
            )
            return JSONResponse(
                status_code=operation.success_status,
                content=WorkbenchOperationResponse(result=dict(result)).model_dump(
                    mode="json"
                ),
            )

        endpoint.__name__ = f"workbench_{operation.name.lower()}"
        return endpoint

    for operation in operations:
        app.add_api_route(
            operation.path,
            operation_endpoint(operation),
            methods=[operation.method],
            name=operation.name,
        )

    return app
