"""Trusted Workbench read adapter for exact Workflow Definition facts."""

from __future__ import annotations

from typing import Any

from psycopg import Error as PostgresError

from agent_console.authority_contracts import ExactGrant
from agent_console.workbench_bff import PREFIX, WorkbenchOperation
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workflow_definition_repository import (
    WorkflowDefinitionRepositoryError,
)
from agent_console.workflow_definition_service import (
    WorkflowDefinitionFailure,
    WorkflowDefinitionService,
)


class WorkflowOwnerAdapter:
    """Read Workflow facts on the authorization transaction's connection."""

    def __init__(self, service: WorkflowDefinitionService) -> None:
        self.service = service

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        scope = self.service.scope(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            if call.operation == "LIST_WORKFLOWS":
                return self.service.list_for_workbench(
                    call.connection, scope, authorized=True
                )
            if call.operation == "READ_WORKFLOW_REVISION":
                return self.service.read_revision_for_workbench(
                    call.connection,
                    scope,
                    call.path["workflow_definition_id"],
                    call.path["revision_id"],
                    authorized=True,
                )
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        except WorkbenchOwnerError:
            raise
        except WorkflowDefinitionFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc
        except WorkflowDefinitionRepositoryError as exc:
            raise WorkbenchOwnerError(
                "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE", 503
            ) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError(
                "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE", 503
            ) from exc


def _workflow_list(context, path, payload, query):
    return (ExactGrant("WORKFLOW", "LIST", "workflow:collection"),)


def _workflow_revision_read(context, path, payload, query):
    return (
        ExactGrant(
            "WORKFLOW",
            "READ",
            f"workflow:{path['workflow_definition_id']}:{path['revision_id']}",
        ),
    )


def workflow_operations(
    service: WorkflowDefinitionService,
) -> tuple[WorkbenchOperation, ...]:
    handler = WorkflowOwnerAdapter(service)
    return (
        WorkbenchOperation(
            "LIST_WORKFLOWS",
            "GET",
            f"{PREFIX}/workflows",
            None,
            None,
            _workflow_list,
            handler,
        ),
        WorkbenchOperation(
            "READ_WORKFLOW_REVISION",
            "GET",
            f"{PREFIX}/workflows/{{workflow_definition_id}}/revisions/{{revision_id}}",
            None,
            None,
            _workflow_revision_read,
            handler,
        ),
    )
