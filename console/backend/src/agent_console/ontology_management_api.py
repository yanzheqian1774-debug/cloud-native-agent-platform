"""Optional session/CSRF routes; disabled unless explicitly installed by operator."""

from dataclasses import replace

from fastapi import Request

from .ontology_domain import OntologyError
from .ontology_management_policy import MaintenanceCommand
from .workbench_bff import PREFIX, WorkbenchBoundaryError
from .workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)


def install_ontology_management(manager, authorizer):
    def install(app, authenticate, require_csrf, policy):
        def run(request, operation):
            if request.query_params:
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422)
            with (
                authorizer.controller.protected_request() as generation,
                authorizer.repository.connection_scope() as connection,
            ):
                session, context = authenticate(request)
                if request.method != "GET":
                    require_csrf(request, session)
                connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                authority = AuthorizedOwnerAuthority(
                    authorizer, context, connection, generation.generation, ()
                )
                call = AuthorizedOwnerCall(
                    "ONTOLOGY_MAINTENANCE",
                    context,
                    connection,
                    {},
                    {},
                    {},
                    (),
                    authority,
                    generation.generation,
                    authorizer.controller.readiness.recovery_epoch,
                )
                try:
                    return {"result": operation(call)}
                except OntologyError as exc:
                    raise WorkbenchOwnerError(str(exc), 409) from exc

        root = PREFIX + "/ontology-maintenance"

        @app.get(root + "/capabilities/{identity}")
        def capabilities(request: Request, identity: str):
            return run(request, lambda call: manager.capabilities(call, identity))

        @app.post(root + "/commands")
        def command(request: Request, body: MaintenanceCommand):
            return run(
                request,
                lambda call: manager.handle(
                    replace(call, payload=body.model_dump(mode="json"))
                ),
            )

        @app.get(root + "/commands/{key}")
        def receipt(request: Request, key: str):
            return run(request, lambda call: manager.receipt(call, key))

    return install
