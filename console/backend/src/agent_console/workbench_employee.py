"""Trusted Workbench read adapter for exact Employee Definition facts."""

from __future__ import annotations

from typing import Any

from psycopg import Error as PostgresError

from agent_console.authority_contracts import ExactGrant
from agent_console.digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.workbench_bff import PREFIX, WorkbenchOperation
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)


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
        return {
            "resourceKind": "DIGITAL_EMPLOYEE_DEFINITION",
            "employeeDefinitionId": revision["definitionId"],
            "employeeDefinitionRevisionId": revision["revisionId"],
            "employeeDefinitionDigest": value["digest"],
            "role": revision["role"],
            "responsibilities": list(revision["responsibilities"]),
            "members": [
                {
                    "kind": member["kind"],
                    "resourceId": member["resource_id"],
                    "revisionId": member["revision_id"],
                    "digest": member["digest"],
                }
                for member in revision["members"]
            ],
        }


def _employee_revision_read(context, path, payload, query):
    return (
        ExactGrant(
            "EMPLOYEE",
            "READ",
            f"employee:{path['employee_definition_id']}:{path['revision_id']}",
        ),
    )


def employee_operations(
    repository: EmployeeDefinitionRepository,
) -> tuple[WorkbenchOperation, ...]:
    return (
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
