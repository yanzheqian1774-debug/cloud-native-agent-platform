"""Formal same-transaction Workbench adapter for Business Problem and Plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Error as PostgresError
from pydantic import BaseModel, ConfigDict, Field

from agent_console.authority_contracts import ExactGrant
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_authorization import (
    criteria_resource,
    criterion_resource,
    criterion_revision_resource,
    plan_resource,
    problem_resource,
    reference_grants,
)
from agent_console.business_problem_domain import BusinessProblemError
from agent_console.business_problem_schemas import (
    CreateBusinessProblem,
    CreateCriteriaSetRevision,
    CreateCriterionRevision,
    DecidePlan,
    PreparePlan,
    ReviseBusinessProblem,
    TransitionBusinessProblem,
)
from agent_console.digital_employee_application import DigitalEmployeeError
from agent_console.digital_employee_definition import EmployeeDefinitionError
from agent_console.workbench_bff import PREFIX, WorkbenchOperation
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workflow_control_domain import WorkflowControlError
from agent_console.workflow_definition_repository import (
    WorkflowDefinitionRepositoryError,
)


class PlanVersionQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)


@dataclass(frozen=True, slots=True)
class OwnerPrincipal:
    principal_id: str
    tenant_id: str
    security_domain: str


class BusinessProblemOwnerAdapter:
    """Invoke the existing owner with its authority and UoW bound to one connection."""

    def __init__(self, application: BusinessProblemApplication) -> None:
        self.application = application

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        service = BusinessProblemApplication(
            self.application.uow,
            call.authority,
            self.application.workflows,
            self.application.employees,
            self.application.instances,
        )
        try:
            if call.operation == "CREATE_PROBLEM":
                return service.create_problem(
                    principal,
                    CreateBusinessProblem.model_validate(call.payload),
                    connection=call.connection,
                )
            if call.operation == "LIST_PROBLEMS":
                return service.list_problems(principal, connection=call.connection)
            if call.operation == "READ_PROBLEM":
                return service.read_problem(
                    principal, call.path["problem_id"], connection=call.connection
                )
            if call.operation == "REVISE_PROBLEM":
                return service.revise_problem(
                    principal,
                    call.path["problem_id"],
                    ReviseBusinessProblem.model_validate(call.payload),
                    connection=call.connection,
                )
            if call.operation == "TRANSITION_PROBLEM":
                return service.transition(
                    principal,
                    call.path["problem_id"],
                    TransitionBusinessProblem.model_validate(call.payload),
                    connection=call.connection,
                )
            if call.operation == "WRITE_CRITERION":
                return service.criterion(
                    principal,
                    CreateCriterionRevision.model_validate(call.payload),
                    connection=call.connection,
                )
            if call.operation == "READ_CRITERION":
                return service.read_criterion(
                    principal, call.path["revision_id"], connection=call.connection
                )
            if call.operation == "WRITE_CRITERIA_SET":
                return service.criteria_set(
                    principal,
                    call.path["problem_id"],
                    CreateCriteriaSetRevision.model_validate(call.payload),
                    connection=call.connection,
                )
            if call.operation == "LIST_CRITERIA_SETS":
                return service.read_sets(
                    principal, call.path["problem_id"], connection=call.connection
                )
            if call.operation == "LIST_PROBLEM_CRITERIA":
                return service.read_criteria(
                    principal, call.path["problem_id"], connection=call.connection
                )
            if call.operation == "PREPARE_PLAN":
                return service.prepare(
                    principal,
                    call.path["problem_id"],
                    PreparePlan.model_validate(call.payload),
                    connection=call.connection,
                )
            if call.operation == "READ_PLAN":
                return service.read_plan(
                    principal,
                    call.path["plan_id"],
                    int(call.query["version"]),
                    connection=call.connection,
                )
            if call.operation == "APPROVE_PLAN":
                return service.approve(
                    principal,
                    call.path["plan_id"],
                    DecidePlan.model_validate(call.payload),
                    connection=call.connection,
                )
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        except WorkbenchOwnerError:
            raise
        except (
            BusinessProblemError,
            WorkflowControlError,
            DigitalEmployeeError,
            EmployeeDefinitionError,
            WorkflowDefinitionRepositoryError,
        ) as exc:
            reason = str(exc)
            if "UNAVAILABLE" in reason or "INCOMPATIBLE" in reason:
                raise WorkbenchOwnerError(
                    "BUSINESS_PROBLEM_STORAGE_UNAVAILABLE", 503
                ) from exc
            if reason.endswith("NOT_FOUND"):
                raise WorkbenchOwnerError("BUSINESS_PROBLEM_NOT_FOUND", 404) from exc
            raise WorkbenchOwnerError("BUSINESS_PROBLEM_CONFLICT", 409) from exc
        except PostgresError as exc:
            status = 409 if exc.sqlstate and exc.sqlstate.startswith("23") else 503
            reason = (
                "BUSINESS_PROBLEM_CONFLICT"
                if status == 409
                else "BUSINESS_PROBLEM_STORAGE_UNAVAILABLE"
            )
            raise WorkbenchOwnerError(reason, status) from exc


def _grant(owner: str, action: str, resource: str) -> ExactGrant:
    return ExactGrant(owner, action, resource)


def _problem_collection(context, path, payload, query):
    return (
        _grant("BUSINESS_PROBLEM", "CREATE", problem_resource()),
        _grant("BUSINESS_PROBLEM", "READ", problem_resource()),
    )


def _problem_list(context, path, payload, query):
    return (_grant("BUSINESS_PROBLEM", "LIST", problem_resource()),)


def _problem_read(context, path, payload, query):
    return (_grant("BUSINESS_PROBLEM", "READ", problem_resource(path["problem_id"])),)


def _problem_write(action: str):
    def build(context, path, payload, query):
        resource = problem_resource(path["problem_id"])
        return (
            _grant("BUSINESS_PROBLEM", action, resource),
            _grant("BUSINESS_PROBLEM", "READ", resource),
        )

    return build


def _criterion_write(context, path, payload, query):
    revising = payload.get("predecessorRevisionId") is not None
    resource = (
        criterion_resource(str(payload["successCriterionId"]))
        if revising
        else criterion_resource()
    )
    values = [
        _grant("SUCCESS_CRITERION", "REVISE" if revising else "CREATE", resource),
        _grant("SUCCESS_CRITERION", "READ", resource),
    ]
    if revising:
        values.append(
            _grant(
                "SUCCESS_CRITERION",
                "READ",
                criterion_revision_resource(str(payload["predecessorRevisionId"])),
            )
        )
    return tuple(values)


def _criterion_read(context, path, payload, query):
    return (
        _grant(
            "SUCCESS_CRITERION",
            "READ",
            criterion_revision_resource(path["revision_id"]),
        ),
    )


def _criteria_set_write(context, path, payload, query):
    action = "REVISE" if payload.get("predecessorSetRevisionId") else "CREATE"
    problem_id = path["problem_id"]
    return (
        _grant("SUCCESS_CRITERIA_SET", action, criteria_resource(problem_id)),
        _grant("SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)),
        _grant("BUSINESS_PROBLEM", "READ", problem_resource(problem_id)),
        *(
            _grant(
                "SUCCESS_CRITERION", "READ", criterion_revision_resource(revision_id)
            )
            for revision_id in payload["orderedCriterionRevisionIds"]
        ),
    )


def _criteria_set_read(context, path, payload, query):
    return (
        _grant("SUCCESS_CRITERIA_SET", "READ", criteria_resource(path["problem_id"])),
    )


def _problem_criteria(context, path, payload, query):
    problem_id = path["problem_id"]
    return (
        _grant("SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)),
        _grant("BUSINESS_PROBLEM", "READ", problem_resource(problem_id)),
    )


def _plan_prepare(context, path, payload, query):
    problem_id = path["problem_id"]
    return (
        _grant("PLAN", "PREPARE", f"plan:prepare:{problem_id}"),
        _grant("PLAN", "READ", f"plan:prepared:{problem_id}"),
        _grant("BUSINESS_PROBLEM", "READ", problem_resource(problem_id)),
        _grant("SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)),
        *(_grant(*grant) for grant in reference_grants(_Payload(payload))),
    )


class _Payload:
    def __init__(self, values: dict[str, Any]) -> None:
        self.__dict__.update(values)


def _plan_read(context, path, payload, query):
    return (_grant("PLAN", "READ", plan_resource(path["plan_id"], query["version"])),)


def _plan_approve(context, path, payload, query):
    plan_id = path["plan_id"]
    version = payload["planVersion"]
    return (
        _grant("PLAN", "APPROVE", plan_resource(plan_id, version)),
        _grant("PLAN", "READ", plan_resource(plan_id, version)),
    )


def business_problem_operations(
    application: BusinessProblemApplication,
) -> tuple[WorkbenchOperation, ...]:
    handler = BusinessProblemOwnerAdapter(application)
    return (
        WorkbenchOperation(
            "CREATE_PROBLEM",
            "POST",
            f"{PREFIX}/problems",
            CreateBusinessProblem,
            None,
            _problem_collection,
            handler,
            201,
        ),
        WorkbenchOperation(
            "LIST_PROBLEMS",
            "GET",
            f"{PREFIX}/problems",
            None,
            None,
            _problem_list,
            handler,
        ),
        WorkbenchOperation(
            "READ_PROBLEM",
            "GET",
            f"{PREFIX}/problems/{{problem_id}}",
            None,
            None,
            _problem_read,
            handler,
        ),
        WorkbenchOperation(
            "REVISE_PROBLEM",
            "POST",
            f"{PREFIX}/problems/{{problem_id}}/revisions",
            ReviseBusinessProblem,
            None,
            _problem_write("REVISE"),
            handler,
        ),
        WorkbenchOperation(
            "TRANSITION_PROBLEM",
            "POST",
            f"{PREFIX}/problems/{{problem_id}}/lifecycle",
            TransitionBusinessProblem,
            None,
            _problem_write("TRANSITION"),
            handler,
        ),
        WorkbenchOperation(
            "WRITE_CRITERION",
            "POST",
            f"{PREFIX}/success-criteria",
            CreateCriterionRevision,
            None,
            _criterion_write,
            handler,
            201,
        ),
        WorkbenchOperation(
            "READ_CRITERION",
            "GET",
            f"{PREFIX}/success-criteria/revisions/{{revision_id}}",
            None,
            None,
            _criterion_read,
            handler,
        ),
        WorkbenchOperation(
            "WRITE_CRITERIA_SET",
            "POST",
            f"{PREFIX}/problems/{{problem_id}}/criteria-sets",
            CreateCriteriaSetRevision,
            None,
            _criteria_set_write,
            handler,
            201,
        ),
        WorkbenchOperation(
            "LIST_CRITERIA_SETS",
            "GET",
            f"{PREFIX}/problems/{{problem_id}}/criteria-sets",
            None,
            None,
            _criteria_set_read,
            handler,
        ),
        WorkbenchOperation(
            "LIST_PROBLEM_CRITERIA",
            "GET",
            f"{PREFIX}/problems/{{problem_id}}/criteria",
            None,
            None,
            _problem_criteria,
            handler,
        ),
        WorkbenchOperation(
            "PREPARE_PLAN",
            "POST",
            f"{PREFIX}/problems/{{problem_id}}/plans",
            PreparePlan,
            None,
            _plan_prepare,
            handler,
        ),
        WorkbenchOperation(
            "READ_PLAN",
            "GET",
            f"{PREFIX}/plans/{{plan_id}}",
            None,
            PlanVersionQuery,
            _plan_read,
            handler,
        ),
        WorkbenchOperation(
            "APPROVE_PLAN",
            "POST",
            f"{PREFIX}/plans/{{plan_id}}/approvals",
            DecidePlan,
            None,
            _plan_approve,
            handler,
        ),
    )
