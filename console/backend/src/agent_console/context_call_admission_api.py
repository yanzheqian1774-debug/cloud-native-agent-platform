"""Authenticated, CSRF-protected independent context signature routes."""

from fastapi import Request
from pydantic import ValidationError

from .authority_contracts import AuthorityError
from .context_call_admission import ContextApproval


def install_context_call_admission(service):
    def install(app, authenticate, require_csrf, policy):
        prefix = "/api/workbench/v1/authorization/context-admissions/{context_id}"

        @app.get(prefix)
        def read(context_id: str, request: Request):
            _, context = authenticate(request)
            return service.read(context, context_id)

        @app.post(prefix)
        async def approve(context_id: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = ContextApproval.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("CONTEXT_ADMISSION_INVALID") from None
            return service.approve(context, context_id, spec)

        @app.post(prefix + "/{admission_id}/revoke")
        def revoke(context_id: str, admission_id: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            return service.revoke(context, context_id, admission_id)

    return install
