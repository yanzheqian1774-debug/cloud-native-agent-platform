"""Authorization-first internal Product API for durable Digital Employees."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .agent_definition_repository import AgentDefinitionRepositoryError
from .agent_definition_service import AgentDefinitionFailure
from .digital_employee_application import DigitalEmployeeError
from .digital_employee_bootstrap import DigitalEmployeeProductAssembly
from .digital_employee_definition import EmployeeDefinitionError
from .digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
    CreateDigitalEmployeePlacement,
    CreateEmployeeDefinition,
    DecideEmployeeDefinition,
)
from .execution_domain import ExecutionPersistenceError
from .problems import TrustedPrincipal

router = APIRouter(prefix="/api/internal/v0.2.3/digital-employees")


def get_assembly() -> DigitalEmployeeProductAssembly:
    from .app import get_digital_employee_assembly

    return get_digital_employee_assembly()


def get_principal(
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    security_domain: Annotated[str | None, Header(alias="X-Security-Domain")] = None,
    principal_id: Annotated[str | None, Header(alias="X-Principal-ID")] = None,
) -> TrustedPrincipal:
    if not principal_id:
        raise HTTPException(401, detail={"reasonCode": "AUTHENTICATION_REQUIRED"})
    if not tenant_id or not security_domain:
        raise HTTPException(403, detail={"reasonCode": "TRUSTED_SCOPE_REQUIRED"})
    return TrustedPrincipal(tenant_id, security_domain, principal_id)


Assembly = Annotated[DigitalEmployeeProductAssembly, Depends(get_assembly)]
Principal = Annotated[TrustedPrincipal, Depends(get_principal)]


def _scope(principal: TrustedPrincipal, assembly: DigitalEmployeeProductAssembly):
    return assembly.scope(principal.tenant_id, principal.security_domain)


def _call(operation):
    try:
        return operation()
    except HTTPException:
        raise
    except DigitalEmployeeError as exc:
        reason = str(exc)
        status = 404 if reason.endswith("_NOT_FOUND") else 409
        if reason == "TRUSTED_SCOPE_REQUIRED":
            status = 403
        raise HTTPException(status, detail={"reasonCode": reason}) from exc
    except EmployeeDefinitionError as exc:
        reason = str(exc)
        if reason in {"EMPLOYEE_NOT_FOUND", "BOUND_RESOURCE_NOT_FOUND"}:
            status = 404
            reason = "EMPLOYEE_NOT_FOUND"
        elif reason == "EMPLOYEE_RECORD_CORRUPT":
            status = 503
            reason = "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE"
        elif reason.startswith("INVALID_"):
            status = 422
        else:
            status = 409
        raise HTTPException(status, detail={"reasonCode": reason}) from exc
    except AgentDefinitionFailure as exc:
        raise HTTPException(exc.status, detail={"reasonCode": exc.reason}) from exc
    except ValueError as exc:
        raise HTTPException(422, detail={"reasonCode": str(exc)}) from exc
    except AgentDefinitionRepositoryError as exc:
        raise HTTPException(
            503, detail={"reasonCode": "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE"}
        ) from exc
    except ExecutionPersistenceError as exc:
        raise HTTPException(
            503, detail={"reasonCode": "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE"}
        ) from exc


@router.get("/definitions")
def list_definitions(principal: Principal, assembly: Assembly):
    return _call(
        lambda: assembly.list_definitions(
            _scope(principal, assembly), principal.principal_id
        )
    )


@router.post("/definitions", status_code=201)
def create_definition(
    command: CreateEmployeeDefinition, principal: Principal, assembly: Assembly
):
    return _call(
        lambda: assembly.create_definition(
            _scope(principal, assembly), principal.principal_id, command
        )
    )


@router.get("/definitions/{employee_definition_id}")
def read_definition(
    employee_definition_id: str,
    principal: Principal,
    assembly: Assembly,
    revision_id: Annotated[
        str, Query(alias="employeeDefinitionRevisionId", min_length=1, max_length=200)
    ],
):
    return _call(
        lambda: assembly.get_definition(
            _scope(principal, assembly),
            principal.principal_id,
            employee_definition_id,
            revision_id,
        )
    )


def _decide_definition(
    action: str,
    employee_definition_id: str,
    command: DecideEmployeeDefinition,
    principal: TrustedPrincipal,
    assembly: DigitalEmployeeProductAssembly,
):
    return _call(
        lambda: assembly.decide_definition(
            _scope(principal, assembly),
            principal.principal_id,
            employee_definition_id,
            action,
            command,
        )
    )


@router.post("/definitions/{employee_definition_id}/validate")
def validate_definition(
    employee_definition_id: str,
    command: DecideEmployeeDefinition,
    principal: Principal,
    assembly: Assembly,
):
    return _decide_definition(
        "VALIDATE", employee_definition_id, command, principal, assembly
    )


@router.post("/definitions/{employee_definition_id}/approve")
def approve_definition(
    employee_definition_id: str,
    command: DecideEmployeeDefinition,
    principal: Principal,
    assembly: Assembly,
):
    return _decide_definition(
        "APPROVE", employee_definition_id, command, principal, assembly
    )


@router.post("/definitions/{employee_definition_id}/publish")
def publish_definition(
    employee_definition_id: str,
    command: DecideEmployeeDefinition,
    principal: Principal,
    assembly: Assembly,
):
    return _decide_definition(
        "PUBLISH", employee_definition_id, command, principal, assembly
    )


@router.post("/instances", status_code=201)
def create_instance(
    command: CreateDigitalEmployeeInstance,
    principal: Principal,
    assembly: Assembly,
):
    return _call(
        lambda: assembly.create_instance(
            _scope(principal, assembly), principal.principal_id, command
        )
    )


@router.get("/instances/{instance_id}")
def read_instance(instance_id: str, principal: Principal, assembly: Assembly):
    return _call(
        lambda: assembly.get_instance(_scope(principal, assembly), instance_id)
    )


@router.post("/instances/{instance_id}/assignments", status_code=201)
def create_assignment(
    instance_id: str,
    command: CreateDigitalEmployeeAssignment,
    principal: Principal,
    assembly: Assembly,
):
    return _call(
        lambda: assembly.create_assignment(
            _scope(principal, assembly), instance_id, command
        )
    )


@router.get("/instances/{instance_id}/assignments/{assignment_id}")
def read_assignment(
    instance_id: str,
    assignment_id: str,
    principal: Principal,
    assembly: Assembly,
):
    return _call(
        lambda: assembly.get_assignment(
            _scope(principal, assembly), instance_id, assignment_id
        )
    )


@router.post(
    "/instances/{instance_id}/assignments/{assignment_id}/placements",
    status_code=201,
)
def create_placement(
    instance_id: str,
    assignment_id: str,
    command: CreateDigitalEmployeePlacement,
    principal: Principal,
    assembly: Assembly,
):
    return _call(
        lambda: assembly.create_placement(
            _scope(principal, assembly), instance_id, assignment_id, command
        )
    )


@router.get(
    "/instances/{instance_id}/assignments/{assignment_id}/placements/{placement_id}"
)
def read_placement(
    instance_id: str,
    assignment_id: str,
    placement_id: str,
    principal: Principal,
    assembly: Assembly,
    attempt_id: Annotated[str, Query(alias="attemptId", min_length=1, max_length=200)],
    agent_id: Annotated[
        str, Query(alias="agentInstanceId", min_length=1, max_length=200)
    ],
):
    return _call(
        lambda: assembly.get_placement(
            _scope(principal, assembly),
            instance_id,
            assignment_id,
            placement_id,
            attempt_id,
            agent_id,
        )
    )
