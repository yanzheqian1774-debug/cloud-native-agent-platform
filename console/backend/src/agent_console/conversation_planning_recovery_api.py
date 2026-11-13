"""Recovery API composes existing Planning and context-approval owners."""

from fastapi import Request

from .authority_contracts import AuthorityError
from .conversation_planning_recovery import (
    RecoveryRequest,
    find,
    old_record,
    prepare_observation,
    projection,
)
from .plan_suggestion_invocation import PlanningRequest


def install(app, invoke, authenticate, require_csrf, reader):
    prefix = "/api/workbench/v1/planning-v2/recoveries"

    def bound(service):
        exact = service.exact_admission
        if (
            exact is None
            or getattr(exact.service, "conversation_experience", None) is None
        ):
            raise AuthorityError("PLANNING_RECOVERY_UNAVAILABLE")
        return exact.service, exact.context

    def saved(service, identity):
        admission, context = bound(service)
        with admission.repository.connection_scope() as c:
            row = find(c, context, identity=identity)
            if row is None:
                raise AuthorityError("PLANNING_RECOVERY_NOT_FOUND")
            return row

    @app.get(prefix + "/for-invocation/{invocation_id}")
    def status(request: Request, invocation_id: str, conversation_id: str):
        def action(service, principal):
            # Exact owner read precedes lookup; no observation, settlement or dispatch.
            old = service.read(principal, invocation_id, settle_receipt=False)
            admission, context = bound(service)
            with admission.repository.connection_scope() as c:
                previous = old_record(c, context, invocation_id)
                source, _, _, _ = admission.conversation_experience.require_source(
                    admission,
                    c,
                    context,
                    previous["invocation"]["target"]["problem"]["problem"][
                        "resource_id"
                    ],
                )
                if source["record"].get("conversation_id") != conversation_id:
                    raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
                if previous["invocation"]["request"].get("source_proposal"):
                    return {
                        "state": "UNSUPPORTED",
                        "original_outcome": "OUTCOME_UNKNOWN",
                    }
                row = c.execute(
                    "SELECT recovery_id FROM "
                    "authorization_admin.conversation_planning_recoveries WHERE "
                    "tenant_id=%s AND security_domain=%s AND subject_id=%s AND "
                    "predecessor_invocation_id=%s AND conversation_id=%s",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        context.principal_id,
                        invocation_id,
                        conversation_id,
                    ),
                ).fetchone()
            if row:
                return projection(admission, context, row["recovery_id"])
            return {
                "state": "NOT_REQUESTED",
                "original_outcome": old["result"]["technical_status"],
            }

        return invoke(request, action)

    @app.post(prefix)
    def prepare(request: Request, body: RecoveryRequest):
        def action(service, principal):
            service.read(principal, body.invocation_id, settle_receipt=False)
            admission, context = bound(service)
            row = prepare_observation(admission, context, body)
            # The recovery adapter always returns pending before any invocation claim.
            state = projection(admission, context, row["recovery_id"])
            if state["state"] == "OBSERVED":
                service.begin(
                    principal,
                    PlanningRequest.model_validate(row["record"]["request"]),
                    prepare_only=True,
                )
            return projection(admission, context, row["recovery_id"])

        return invoke(request, action)

    @app.get(prefix + "/{recovery_id}")
    def read(request: Request, recovery_id: str):
        return invoke(
            request, lambda service, _: projection(*bound(service), recovery_id)
        )

    @app.post(prefix + "/{recovery_id}/continue")
    async def resume(request: Request, recovery_id: str):
        from .model_stream_api import model_response, stream_authorization

        session, _ = authenticate(request)
        require_csrf(request, session)

        def action(service, principal):
            admission, context = bound(service)
            status = projection(admission, context, recovery_id)
            if status["state"] == "DISPATCHED":
                return service.read(
                    principal, status["invocation_id"], settle_receipt=False
                )
            if status["state"] != "AUTHORIZED":
                raise AuthorityError("PLANNING_RECOVERY_APPROVAL_REQUIRED")
            row = saved(service, recovery_id)
            # Exactly one new owner call, not the adaptive retry loop.
            return service.begin(
                principal, PlanningRequest.model_validate(row["record"]["request"])
            )

        return await model_response(
            request,
            lambda: invoke(request, action),
            stream_authorization(request, authenticate, require_csrf, reader),
        )
