"""Authenticated owner requests; explicit independent signatures remain separate."""

from fastapi import Request

from .bounded_task_policy import TaskAuthorizationRequest, TaskSignature


def install_bounded_task_routes(service):
    from .development_planning_recovery import (
        RecoveryObservation,
        observe,
        read_observation,
    )

    def install(app, authenticate, require_csrf, policy):
        prefix = "/api/workbench/v1/authorization/tasks"

        @app.post(prefix)
        def prepare(request: Request, spec: TaskAuthorizationRequest):
            session, context = authenticate(request)
            require_csrf(request, session)
            return service.prepare(context, spec)

        @app.post(prefix + "/recovery-observations")
        def observe_recovery(request: Request, spec: RecoveryObservation):
            session, context = authenticate(request)
            require_csrf(request, session)
            return observe(service, context, spec)

        @app.get(prefix + "/recovery-observations/{identity}")
        def read_recovery(request: Request, identity: str):
            _, context = authenticate(request)
            return read_observation(service, context, identity)

        @app.get(prefix + "/{identity}")
        def read(request: Request, identity: str):
            _, context = authenticate(request)
            return service.read(context, identity)

        @app.post(prefix + "/{identity}/approve")
        def approve(request: Request, identity: str, spec: TaskSignature):
            session, context = authenticate(request)
            require_csrf(request, session)
            return service.approve(context, identity, spec)

        @app.post(prefix + "/{identity}/decisions/{decision_id}/revoke")
        def revoke(request: Request, identity: str, decision_id: str):
            session, context = authenticate(request)
            require_csrf(request, session)
            return service.revoke(context, identity, decision_id)

    return install
