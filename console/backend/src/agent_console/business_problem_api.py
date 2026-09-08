"""Normal durable Product/Plan HTTP entry, separate from process-local preview."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from psycopg import Error as PostgresError

from .business_problem_application import BusinessProblemApplication
from .business_problem_domain import BusinessProblemError
from .business_problem_schemas import (
    CreateBusinessProblem,
    CreateCriteriaSetRevision,
    CreateCriterionRevision,
    DecidePlan,
    PreparePlan,
    ReviseBusinessProblem,
    TransitionBusinessProblem,
)
from .digital_employee_application import DigitalEmployeeError
from .digital_employee_definition import EmployeeDefinitionError
from .governed_execution_authorization import (
    GovernedAuthorizationError,
    GovernedExecutionAuthority,
)
from .workflow_control_domain import WorkflowControlError
from .workflow_definition_repository import WorkflowDefinitionRepositoryError

router = APIRouter(prefix="/api/internal/v0.2.3")


def context(authorization: Annotated[str | None, Header()] = None):
    from .app import _business_problem_application

    try:
        authority = GovernedExecutionAuthority.from_file(
            os.environ.get("GOVERNED_EXECUTION_AUTHORITY_FILE", "")
        )
        principal = authority.authenticate(authorization)
    except GovernedAuthorizationError as exc:
        code = str(exc)
        raise HTTPException(
            503 if code.endswith("UNAVAILABLE") else 401, detail={"reasonCode": code}
        ) from exc
    base = _business_problem_application
    if base is None:
        raise HTTPException(
            503, detail={"reasonCode": "BUSINESS_PROBLEM_STORAGE_UNAVAILABLE"}
        )
    # Reload trusted configuration per request: revocation also applies to replay.
    service = BusinessProblemApplication(
        base.uow, authority, base.workflows, base.employees, base.instances
    )
    return service, principal


Context = Annotated[tuple, Depends(context)]


def invoke(ctx, method, *args):
    service, principal = ctx
    try:
        return getattr(service, method)(principal, *args)
    except (
        BusinessProblemError,
        GovernedAuthorizationError,
        WorkflowControlError,
        DigitalEmployeeError,
        EmployeeDefinitionError,
        WorkflowDefinitionRepositoryError,
    ) as exc:
        reason = str(exc)
        status = 404 if reason.endswith("NOT_FOUND") else 409
        if "UNAVAILABLE" in reason or "INCOMPATIBLE" in reason:
            status, reason = 503, "BUSINESS_PROBLEM_STORAGE_UNAVAILABLE"
        if status == 404:
            reason = "BUSINESS_PROBLEM_NOT_FOUND"
        raise HTTPException(status, detail={"reasonCode": reason}) from exc
    except PostgresError as exc:
        status = 409 if exc.sqlstate and exc.sqlstate.startswith("23") else 503
        raise HTTPException(
            status,
            detail={
                "reasonCode": "BUSINESS_PROBLEM_CONFLICT"
                if status == 409
                else "BUSINESS_PROBLEM_STORAGE_UNAVAILABLE"
            },
        ) from exc


@router.post("/business-problems")
def create_problem(command: CreateBusinessProblem, ctx: Context):
    return invoke(ctx, "create_problem", command)


@router.get("/business-problems")
def list_problems(ctx: Context):
    return invoke(ctx, "list_problems")


@router.get("/business-problems/{problem_id}")
def get_problem(problem_id: str, ctx: Context):
    return invoke(ctx, "read_problem", problem_id)


@router.post("/business-problems/{problem_id}/revisions")
def revise_problem(problem_id: str, command: ReviseBusinessProblem, ctx: Context):
    return invoke(ctx, "revise_problem", problem_id, command)


@router.post("/business-problems/{problem_id}/lifecycle")
def transition(problem_id: str, command: TransitionBusinessProblem, ctx: Context):
    return invoke(ctx, "transition", problem_id, command)


@router.post("/success-criteria")
def criterion(command: CreateCriterionRevision, ctx: Context):
    return invoke(ctx, "criterion", command)


@router.get("/success-criteria/revisions/{revision_id}")
def read_criterion(revision_id: str, ctx: Context):
    return invoke(ctx, "read_criterion", revision_id)


@router.post("/business-problems/{problem_id}/criteria-sets")
def criteria_set(problem_id: str, command: CreateCriteriaSetRevision, ctx: Context):
    return invoke(ctx, "criteria_set", problem_id, command)


@router.get("/business-problems/{problem_id}/criteria-sets")
def read_sets(problem_id: str, ctx: Context):
    return invoke(ctx, "read_sets", problem_id)


@router.post("/business-problems/{problem_id}/plans")
def prepare(problem_id: str, command: PreparePlan, response: Response, ctx: Context):
    value = invoke(ctx, "prepare", problem_id, command)
    response.status_code = 200 if value["replayed"] else 201
    return value


@router.get("/plans/{plan_id}")
def read_plan(plan_id: str, ctx: Context, version: int = Query(ge=1)):
    return invoke(ctx, "read_plan", plan_id, version)


@router.post("/plans/{plan_id}/approvals")
def approve(plan_id: str, command: DecidePlan, response: Response, ctx: Context):
    value = invoke(ctx, "approve", plan_id, command)
    response.status_code = 200 if value["replayed"] else 201
    return value


@router.get("/business-problems/{problem_id}/criteria")
def read_criteria(problem_id: str, ctx: Context):
    return invoke(ctx, "read_criteria", problem_id)
