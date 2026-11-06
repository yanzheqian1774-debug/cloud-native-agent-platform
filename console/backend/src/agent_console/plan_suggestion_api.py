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
        def reader(context, identity, by_key=False):
            if service_factory is None:
                raise PlanningError("PLANNING_NOT_CONFIGURED")
            service = service_factory(context)
            principal = OwnerPrincipal(
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            )
            if by_key:
                identity = service.invocations.find_request(
                    service.application.scope(principal),
                    principal.principal_id,
                    identity,
                )
                if identity is None:
                    raise PlanningError("PLANNING_NOT_FOUND")
            return service.read(principal, identity)

        app.state.conversation_planning_reader = reader

        def read_access_metadata(context, key):
            if service_factory is None or not key or len(key) > 200:
                raise PlanningError("PLANNING_READ_TARGET_NOT_FOUND")
            service = service_factory(context)
            principal = OwnerPrincipal(
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            )
            return service.invocations.read_access_metadata(
                service.application.scope(principal), principal.principal_id, key
            )

        app.state.planning_read_access_metadata = read_access_metadata

        def read_exact_request(context, key, expected_payload):
            value = reader(context, key, True)
            stored = value["invocation"].get("request")
            if not stored:
                raise PlanningError("PLANNING_REQUEST_PAYLOAD_NOT_RETAINED")
            actual = PlanningRequest.model_validate(
                {k: v for k, v in stored.items() if k in PlanningRequest.model_fields}
            ).model_dump(mode="json", exclude_none=True)
            if actual != expected_payload:
                raise PlanningConflict("PLANNING_IDEMPOTENCY_CONFLICT")
            from .planning_adaptive import recovery

            service = service_factory(context)
            principal = OwnerPrincipal(
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            )
            return recovery(service, principal, key, value)

        app.state.conversation_planning_request_reader = read_exact_request

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
            from .conversation_actions import original_action
            from .responses_deadline import cancellable_request

            def submit():
                _, context = authenticate(request)
                return original_action(
                    request,
                    context,
                    "PLANNING",
                    body.model_dump(mode="json", exclude_none=True),
                    lambda: invoke(
                        request,
                        lambda service, principal: (
                            service.begin_adaptive(principal, body)
                            if body.output_language
                            else service.begin(principal, body)
                        ),
                    ),
                )

            # CSRF is checked before any private intent can be claimed.
            session, _ = authenticate(request)
            require_csrf(request, session)

            return await cancellable_request(
                request,
                submit,
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
                    if service.exact_admission is not None:
                        prepared = service.exact_admission.recover(request_key)
                        if prepared is not None:
                            return prepared
                    raise PlanningError("PLANNING_NOT_FOUND")
                from .planning_adaptive import recovery

                return recovery(
                    service, principal, request_key, service.read(principal, identity)
                )

            return invoke(request, recover)

        @app.get(f"{PREFIX}/planning-v2/requests/{{request_key}}/read-only")
        def read_original_failure(request: Request, request_key: str):
            def read(service, principal):
                metadata = service.invocations.read_access_metadata(
                    service.application.scope(principal),
                    principal.principal_id,
                    request_key,
                )
                # Original owner READ and exact target checks, without settlement,
                # continuation, adaptive recovery or provider observation.
                return service.read(
                    principal, metadata["invocationId"], settle_receipt=False
                )

            return invoke(request, read)

        @app.post(f"{PREFIX}/planning-v2/requests/{{request_key}}/continue")
        async def continue_prepared(request: Request, request_key: str):
            from .responses_deadline import cancellable_request

            def resume(service, principal):
                if service.exact_admission is None:
                    raise PlanningError("PLANNING_NOT_FOUND")
                prepared = service.exact_admission.recover(request_key)
                if prepared is None:
                    raise PlanningError("PLANNING_NOT_FOUND")
                document = prepared["invocation"].get("request", {})
                body = PlanningRequest.model_validate(
                    {
                        key: value
                        for key, value in document.items()
                        if key in PlanningRequest.model_fields
                    }
                )
                from .conversation_actions import original_action

                _, context = authenticate(request)
                return original_action(
                    request,
                    context,
                    "PLANNING_CONTINUE",
                    body.model_dump(mode="json", exclude_none=True),
                    lambda: (
                        service.begin_adaptive(principal, body)
                        if body.output_language
                        else service.begin(principal, body)
                    ),
                )

            return await cancellable_request(request, lambda: invoke(request, resume))

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
