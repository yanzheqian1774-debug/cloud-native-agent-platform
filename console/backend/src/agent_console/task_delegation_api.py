"""Task delegation routes use the existing authenticated session/CSRF boundary."""

from fastapi import Request
from pydantic import ValidationError

from .authority_contracts import AuthorityError
from .task_delegation import TaskApproval
from .task_development import (
    DevelopmentRevision,
    DevelopmentStop,
    DiagnosticAdmission,
    admit,
    revise,
    stop,
)


def install_task_delegation_routes(service):
    def install(app, authenticate, require_csrf, policy):
        prefix = "/api/workbench/v1/authorization/task-delegations"

        @app.get(prefix + "/configuration")
        def configuration(request: Request):
            _, context = authenticate(request)
            service._admin(context)
            return {
                "configurations": service.configurations,
                "purpose_policy": "problem-to-plan-task.v1",
            }

        @app.post(prefix)
        async def approve(request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = TaskApproval.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_DELEGATION_INVALID") from None
            identity = service.approve(context, spec)
            return service.read(context, identity)

        @app.get(prefix + "/{identity}")
        def read(identity: str, request: Request):
            _, context = authenticate(request)
            return service.read(context, identity)

        @app.post(prefix + "/{identity}/development-revision")
        async def development_revision(identity: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = DevelopmentRevision.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_DEVELOPMENT_INVALID") from None
            return revise(service, context, identity, spec)

        @app.post(prefix + "/{identity}/diagnostic-admissions")
        async def diagnostic_admission(identity: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = DiagnosticAdmission.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_DIAGNOSTIC_INVALID") from None
            return admit(service, context, identity, spec)

        @app.post(prefix + "/{identity}/development-stop")
        async def development_stop(identity: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = DevelopmentStop.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_DEVELOPMENT_INVALID") from None
            return stop(service, context, identity, spec)

        @app.post(prefix + "/{identity}/cases")
        async def enroll_case(identity: str, request: Request):
            from .task_cases import CaseEnrollment, enroll

            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = CaseEnrollment.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_CASE_INVALID") from None
            return enroll(service, context, identity, spec)

        @app.post(prefix + "/{identity}/revoke")
        def revoke(identity: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            service.revoke(context, identity)
            return {"revoked": True}

        @app.post(prefix + "/{identity}/grant-requests/{request_id}")
        def authorize(identity: str, request_id: str, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            return {"decision_id": service.authorize(context, identity, request_id)}

    return install
