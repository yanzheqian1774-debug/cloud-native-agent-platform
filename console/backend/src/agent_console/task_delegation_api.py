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

        @app.post(prefix + "/{identity}/timeout-revision")
        async def timeout_revision(identity: str, request: Request):
            from .task_timeout_revision import TimeoutRevision
            from .task_timeout_revision import revise as revise_timeout

            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = TimeoutRevision.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_TIMEOUT_REVISION_INVALID") from None
            return revise_timeout(service, context, identity, spec)

        @app.get(prefix + "/{identity}/identity-continuity/preflight")
        def continuity_preflight(identity: str, request: Request):
            from .task_identity_continuity import preflight

            _, context = authenticate(request)
            return preflight(service, context, identity)

        @app.post(prefix + "/{identity}/identity-continuity")
        async def continuity_approval(identity: str, request: Request):
            from .task_identity_continuity import ContinuityApproval, approve

            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                spec = ContinuityApproval.model_validate_json(await request.body())
            except ValidationError:
                raise AuthorityError("TASK_CONTINUITY_INVALID") from None
            return approve(service, context, identity, spec)

        @app.post(prefix + "/{identity}/identity-continuity/{continuity_id}/revoke")
        def continuity_revoke(identity: str, continuity_id: str, request: Request):
            from .task_identity_continuity import revoke

            session, context = authenticate(request)
            require_csrf(request, session)
            return revoke(service, context, identity, continuity_id)

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
