"""Session and CSRF protected planning invocation routes; no default provider."""

from typing import Literal

from fastapi import Request
from fastapi.responses import JSONResponse

from .authority_contracts import AuthorityError
from .draft_assistance import DraftAssistanceError
from .model_binding_resolution import ModelBindingResolutionFailure
from .plan_suggestion_domain import PlanningConflict, PlanningError
from .plan_suggestion_invocation import PlanningRequest
from .workbench_bff import PREFIX
from .workbench_business_problem import OwnerPrincipal


def install_planning_invocations(
    service_factory, unavailable_reason="PLANNING_NOT_CONFIGURED"
):
    def install(app, authenticate, require_csrf, policy):
        def invoke(request, action):
            session, context = authenticate(request)
            if request.method != "GET":
                require_csrf(request, session)
            if service_factory is None:
                return JSONResponse(
                    status_code=503, content={"reasonCode": unavailable_reason}
                )
            service = service_factory(context)
            principal = OwnerPrincipal(
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            )
            try:
                return {"result": action(service, principal)}
            except PlanningConflict as exc:
                return JSONResponse(status_code=409, content={"reasonCode": str(exc)})
            except (
                PlanningError,
                AuthorityError,
                DraftAssistanceError,
                ModelBindingResolutionFailure,
            ) as exc:
                return JSONResponse(status_code=404, content={"reasonCode": str(exc)})

        @app.post(f"{PREFIX}/planning-v2/invocations", status_code=201)
        async def begin(request: Request, body: PlanningRequest):
            from .responses_deadline import cancellable_request

            return await cancellable_request(
                request,
                lambda: invoke(
                    request,
                    lambda service, principal: (
                        service.begin_adaptive(principal, body)
                        if body.output_language
                        else service.begin(principal, body)
                    ),
                ),
            )

        @app.post(f"{PREFIX}/planning-v2/diagnostics/{'{'}layer{'}'}", status_code=201)
        async def diagnose(
            request: Request,
            body: PlanningRequest,
            layer: Literal["MINIMAL", "STRUCTURED", "ADAPTER"],
        ):
            from .responses_deadline import cancellable_request

            return await cancellable_request(
                request,
                lambda: invoke(
                    request,
                    lambda service, principal: service.begin(
                        principal, body, diagnostic_layer=layer
                    ),
                ),
            )

        @app.get(f"{PREFIX}/planning-v2/invocations/{{invocation_id}}/usage")
        def usage(request: Request, invocation_id: str):
            def read_usage(service, principal):
                try:
                    return service.read_usage(principal, invocation_id)
                except (PlanningError, AuthorityError, DraftAssistanceError):
                    raise AuthorityError("PROVIDER_USAGE_NOT_FOUND") from None

            return invoke(request, read_usage)

        @app.get(f"{PREFIX}/planning-v2/requests/{{request_key}}")
        def recover_request(request: Request, request_key: str):
            def recover(service, principal):
                identity = service.invocations.find_request(
                    service.application.scope(principal),
                    principal.principal_id,
                    request_key,
                )
                if identity is None:
                    raise PlanningError("PLANNING_NOT_FOUND")
                from .planning_adaptive import recovery

                return recovery(
                    service, principal, request_key, service.read(principal, identity)
                )

            return invoke(request, recover)

        @app.post(f"{PREFIX}/planning-v2/preflight")
        def preflight(request: Request, body: PlanningRequest):
            def check(service, principal):
                app = service.application
                app.authority.require(
                    principal,
                    "PLAN",
                    "PREPARE",
                    f"plan:prepare:{body.target.problem.resource_id}",
                )
                with app.repository.transaction(
                    app.scope(principal),
                    body.target.problem.resource_id,
                    authorized=True,
                ) as cursor:
                    app.validate_target(principal, body.target, cursor.connection)
                return {
                    "policy": body.policy.model_dump(mode="json")
                    if body.policy
                    else None,
                    "status": "EXPLICIT_CONSTRAINTS_VALID",
                    "natural_language_conflicts": "NOT_EXHAUSTIVELY_DETECTABLE",
                    "dispatch_count": 0,
                }

            return invoke(request, check)

        @app.get(f"{PREFIX}/planning-v2/invocations/{{invocation_id}}")
        def read(request: Request, invocation_id: str):
            return invoke(
                request,
                lambda service, principal: service.read(principal, invocation_id),
            )

    return install
