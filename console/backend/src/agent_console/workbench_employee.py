"""Trusted Workbench read adapter for exact Employee Definition facts."""

from __future__ import annotations

from typing import Any

from psycopg import Error as PostgresError

from agent_console.authority_contracts import ExactGrant
from agent_console.digital_employee_application import (
    DigitalEmployeeError,
    DigitalEmployeeRepository,
)
from agent_console.digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeDefinitionRepository,
)
from agent_console.execution_domain import ExecutionPersistenceError, ScopeIdentity
from agent_console.execution_postgres import (
    AssignmentId,
    DigitalEmployeeInstanceId,
)
from agent_console.workbench_bff import PREFIX, WorkbenchOperation
from agent_console.workbench_bff_schemas import (
    WorkbenchEmployeePage,
    WorkbenchEmployeeRevision,
    WorkbenchEmployeeSummary,
    WorkbenchPageQuery,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec


class EmployeeDefinitionOwnerAdapter:
    """Read one Employee revision on the authorization transaction."""

    def __init__(self, repository: EmployeeDefinitionRepository) -> None:
        self.repository = repository

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        if call.operation != "READ_EMPLOYEE_REVISION":
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        scope = ScopeIdentity(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            value = self.repository.read_revision_for_workbench(
                call.connection,
                scope,
                call.path["employee_definition_id"],
                call.path["revision_id"],
                authorized=True,
            )
        except EmployeeDefinitionError as exc:
            reason = str(exc)
            if reason == "EMPLOYEE_RECORD_CORRUPT":
                reason, status = "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            elif reason.startswith("INVALID_"):
                status = 422
            else:
                reason, status = "EMPLOYEE_NOT_FOUND", 404
            raise WorkbenchOwnerError(reason, status) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError(
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            ) from exc

        revision = value["revision"]
        return WorkbenchEmployeeRevision(
            resourceKind="DIGITAL_EMPLOYEE_DEFINITION",
            employeeDefinitionId=revision["definitionId"],
            employeeDefinitionRevisionId=revision["revisionId"],
            employeeDefinitionDigest=value["digest"],
            role=revision["role"],
            responsibilities=list(revision["responsibilities"]),
            members=[
                {
                    "kind": member["kind"],
                    "resourceId": member["resource_id"],
                    "revisionId": member["revision_id"],
                    "digest": member["digest"],
                }
                for member in revision["members"]
            ],
            publicationState=value["publicationState"],
        ).model_dump(mode="json")


class EmployeeDefinitionListOwnerAdapter:
    """List bounded revision summaries on the authorization transaction."""

    ROUTE = "EMPLOYEE_LIST"

    def __init__(
        self,
        repository: EmployeeDefinitionRepository,
        cursors: WorkbenchCursorCodec,
    ) -> None:
        self.repository = repository
        self.cursors = cursors

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        if call.operation != "LIST_EMPLOYEES":
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        page_size = call.query["pageSize"]
        after = None
        if cursor := call.query.get("cursor"):
            resolved = self.cursors.resolve(
                cursor,
                route=self.ROUTE,
                context=call.context,
                page_size=page_size,
                key_size=2,
            )
            after = (resolved[0], resolved[1])
        scope = ScopeIdentity(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            values = self.repository.list_revisions_for_workbench(
                call.connection,
                scope,
                after=after,
                limit=page_size + 1,
                authorized=True,
            )
            items = tuple(
                WorkbenchEmployeeSummary(
                    employeeDefinitionId=value["revision"]["definitionId"],
                    employeeDefinitionRevisionId=value["revision"]["revisionId"],
                    employeeDefinitionDigest=value["digest"],
                    role=value["revision"]["role"],
                    publicationState=value["publicationState"],
                )
                for value in values[:page_size]
            )
            keys = [
                (item.employeeDefinitionId, item.employeeDefinitionRevisionId)
                for item in items
            ]
            if keys != sorted(
                keys,
                key=lambda key: (key[0].encode("utf-8"), key[1].encode("utf-8")),
            ) or len(keys) != len(set(keys)):
                raise EmployeeDefinitionError("EMPLOYEE_RECORD_CORRUPT")
        except EmployeeDefinitionError as exc:
            reason = str(exc)
            if reason.startswith("INVALID_"):
                raise WorkbenchOwnerError("REQUEST_INVALID", 422) from exc
            raise WorkbenchOwnerError(
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            ) from exc
        except (PostgresError, KeyError, TypeError, ValueError) as exc:
            raise WorkbenchOwnerError(
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            ) from exc
        next_cursor = None
        if len(values) > page_size:
            last = items[-1]
            next_cursor = self.cursors.mint(
                route=self.ROUTE,
                context=call.context,
                page_size=page_size,
                last_key=(
                    last.employeeDefinitionId,
                    last.employeeDefinitionRevisionId,
                ),
            )
        return WorkbenchEmployeePage(items=items, nextCursor=next_cursor).model_dump(
            mode="json", exclude_none=True
        )


class DigitalEmployeeOwnerAdapter:
    """Read Instance and Assignment facts on the authorization transaction."""

    def __init__(self, repository: DigitalEmployeeRepository) -> None:
        self.repository = repository

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        scope = ScopeIdentity(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            if call.operation == "READ_EMPLOYEE_INSTANCE":
                value = self.repository.read_instance_for_workbench(
                    call.connection,
                    scope,
                    DigitalEmployeeInstanceId(call.path["instance_id"]),
                    authorized=True,
                )
                if value is None:
                    raise DigitalEmployeeError("INSTANCE_NOT_FOUND")
                reference_name = (
                    "employeeDefinition"
                    if value.definition.authority_kind
                    == "DIGITAL_EMPLOYEE_DEFINITION_V1"
                    else "legacyDefinitionReference"
                )
                return {
                    "instanceId": str(value.instance_id),
                    reference_name: {
                        "authorityKind": value.definition.authority_kind,
                        "employeeDefinitionId": value.definition.definition_id,
                        "employeeDefinitionRevisionId": value.definition.revision_id,
                        "digest": value.definition.digest,
                    },
                    "ownerId": value.owner_id,
                    "organizationId": value.organization_id,
                    "lifecycle": value.lifecycle.value,
                    "execution": {
                        "state": "UNAVAILABLE",
                        "reasonCode": "EXECUTION_NOT_ASSEMBLED",
                    },
                    "health": {
                        "state": "UNAVAILABLE",
                        "reasonCode": "HEALTH_NOT_ASSEMBLED",
                    },
                }
            if call.operation == "READ_EMPLOYEE_ASSIGNMENT":
                value = self.repository.read_assignment_for_workbench(
                    call.connection,
                    scope,
                    DigitalEmployeeInstanceId(call.path["instance_id"]),
                    AssignmentId(call.path["assignment_id"]),
                    authorized=True,
                )
                if value is None:
                    raise DigitalEmployeeError("ASSIGNMENT_NOT_FOUND")
                return {
                    "assignmentId": str(value.assignment_id),
                    "instanceId": str(value.instance_id),
                    "assigneeId": value.assignee_id,
                    "businessRole": value.business_role,
                    "lifecycle": value.lifecycle.value,
                    "effectiveFrom": value.effective_from,
                    "effectiveUntil": value.effective_until,
                    "binding": {
                        "state": "UNAVAILABLE",
                        "reasonCode": "WORKFLOW_BINDING_NOT_ASSEMBLED",
                    },
                }
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        except (DigitalEmployeeError, ExecutionPersistenceError) as exc:
            reason = str(exc)
            if reason in {
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE",
                "EXECUTION_STORAGE_UNAVAILABLE",
            }:
                status = 503
            elif call.operation == "READ_EMPLOYEE_INSTANCE":
                reason, status = "INSTANCE_NOT_FOUND", 404
            elif call.operation == "READ_EMPLOYEE_ASSIGNMENT":
                reason, status = "ASSIGNMENT_NOT_FOUND", 404
            else:
                reason, status = "WORKBENCH_OPERATION_INVALID", 500
            raise WorkbenchOwnerError(reason, status) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError(
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            ) from exc


def _employee_revision_read(context, path, payload, query):
    return (
        ExactGrant(
            "EMPLOYEE",
            "READ",
            f"employee:{path['employee_definition_id']}:{path['revision_id']}",
        ),
    )


def _employee_list(context, path, payload, query):
    return (ExactGrant("EMPLOYEE", "LIST", "employee:collection"),)


def _instance_read(context, path, payload, query):
    return (ExactGrant("INSTANCE", "READ", f"instance:{path['instance_id']}"),)


def _assignment_read(context, path, payload, query):
    return (ExactGrant("ASSIGNMENT", "READ", f"assignment:{path['assignment_id']}"),)


def employee_operations(
    repository: EmployeeDefinitionRepository,
    cursors: WorkbenchCursorCodec,
) -> tuple[WorkbenchOperation, ...]:
    return (
        WorkbenchOperation(
            "LIST_EMPLOYEES",
            "GET",
            f"{PREFIX}/employees",
            None,
            WorkbenchPageQuery,
            _employee_list,
            EmployeeDefinitionListOwnerAdapter(repository, cursors),
        ),
        WorkbenchOperation(
            "READ_EMPLOYEE_REVISION",
            "GET",
            f"{PREFIX}/employees/{{employee_definition_id}}/revisions/{{revision_id}}",
            None,
            None,
            _employee_revision_read,
            EmployeeDefinitionOwnerAdapter(repository),
        ),
    )


def digital_employee_operations(
    repository: DigitalEmployeeRepository,
) -> tuple[WorkbenchOperation, ...]:
    adapter = DigitalEmployeeOwnerAdapter(repository)
    return (
        WorkbenchOperation(
            "READ_EMPLOYEE_INSTANCE",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}",
            None,
            None,
            _instance_read,
            adapter,
        ),
        WorkbenchOperation(
            "READ_EMPLOYEE_ASSIGNMENT",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}/assignments/{{assignment_id}}",
            None,
            None,
            _assignment_read,
            adapter,
        ),
    )
