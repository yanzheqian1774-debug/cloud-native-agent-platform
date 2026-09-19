"""Session and CSRF protected planning invocation routes; no default provider."""

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
                    request, lambda service, principal: service.begin(principal, body)
                ),
            )

        @app.get(f"{PREFIX}/planning-v2/invocations/{{invocation_id}}")
        def read(request: Request, invocation_id: str):
            return invoke(
                request,
                lambda service, principal: service.read(principal, invocation_id),
            )

    return install
