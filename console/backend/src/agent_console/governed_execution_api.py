"""Internal HTTP surface for exact governed execution and Skill readback."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from .execution_domain import ExecutionPersistenceError
from .governed_execution import GovernedExecutionApplication, GovernedExecutionError
from .governed_execution_authorization import (
    GovernedAuthorizationError,
    GovernedPrincipal,
)
from .governed_execution_schemas import StartGovernedExecution
from .resource_use_domain import ResourceUseError
from .skill_invocation_domain import SkillInvocationError
from .workflow_control_domain import WorkflowControlError

router = APIRouter(prefix="/api/internal/v0.2.3/executions")


def get_service() -> GovernedExecutionApplication:
    from .app import get_governed_execution_application

    return get_governed_execution_application()


def get_principal(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> GovernedPrincipal:
    from .app import get_governed_execution_authority

    try:
        return get_governed_execution_authority().authenticate(authorization)
    except GovernedAuthorizationError as exc:
        reason = str(exc)
        status = 503 if reason == "GOVERNED_AUTHORITY_UNAVAILABLE" else 401
        raise HTTPException(status, detail={"reasonCode": reason}) from exc


Service = Annotated[GovernedExecutionApplication, Depends(get_service)]
Principal = Annotated[GovernedPrincipal, Depends(get_principal)]


def _http_error(exc: GovernedExecutionError) -> HTTPException:
    reason = str(exc)
    if reason in {
        "GOVERNED_EXECUTION_NOT_FOUND",
        "EXECUTION_NOT_FOUND",
        "SKILL_INVOCATION_NOT_FOUND",
    } or reason.endswith("_NOT_FOUND"):
        status = 404
        reason = "GOVERNED_EXECUTION_NOT_FOUND"
    elif reason in {"AUTHENTICATION_REQUIRED"}:
        status = 401
    elif reason in {"TRUSTED_SCOPE_REQUIRED"}:
        status = 403
    elif reason in {
        "SKILL_INPUT_TOO_LARGE",
        "SKILL_IO_DEPTH_EXCEEDED",
        "SKILL_IO_PROPERTIES_EXCEEDED",
        "SKILL_IO_KEY_INVALID",
        "SKILL_IO_TYPE_INVALID",
        "SKILL_INPUT_NOT_CANONICAL_JSON",
        "SKILL_INPUT_SCHEMA_MISMATCH",
    }:
        status = 422
    elif (
        "STORAGE" in reason
        or "SCHEMA_INCOMPATIBLE" in reason
        or reason == "GOVERNED_AUTHORITY_UNAVAILABLE"
    ):
        status = 503
        reason = "GOVERNED_EXECUTION_STORAGE_UNAVAILABLE"
    else:
        status = 409
    return HTTPException(status, detail={"reasonCode": reason})


@router.post("")
def start_execution(
    command: StartGovernedExecution,
    response: Response,
    principal: Principal,
    service: Service,
):
    try:
        result = service.start(principal, command)
    except (GovernedExecutionError, GovernedAuthorizationError) as exc:
        raise _http_error(exc) from exc
    except (
        ExecutionPersistenceError,
        ResourceUseError,
        SkillInvocationError,
        WorkflowControlError,
    ) as exc:
        raise _http_error(GovernedExecutionError(str(exc))) from exc
    response.status_code = 200 if result.replayed else 201
    return result.document


@router.get(
    "/{workflow_run_id}/attempts/{attempt_id}/skill-invocations/{invocation_id}"
)
def read_execution(
    workflow_run_id: str,
    attempt_id: str,
    invocation_id: str,
    principal: Principal,
    service: Service,
):
    try:
        return service.read(
            principal,
            workflow_run_id=workflow_run_id,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
        )
    except (GovernedExecutionError, GovernedAuthorizationError) as exc:
        raise _http_error(exc) from exc
    except (
        ExecutionPersistenceError,
        ResourceUseError,
        SkillInvocationError,
        WorkflowControlError,
    ) as exc:
        raise _http_error(GovernedExecutionError(str(exc))) from exc
