"""Trusted authoring routes; workflow publication never grants execution."""

from typing import Literal

from psycopg import Error as PostgresError
from pydantic import Field, model_validator

from .authority_contracts import ExactGrant
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service
from .workflow_authoring import (
    WorkflowAuthoring,
    WorkflowAuthoringCommand,
    command_target,
)
from .workflow_authoring_references import WorkflowReferenceChecker
from .workflow_definition_repository import WorkflowDefinitionRepositoryError
from .workflow_definition_service import WorkflowDefinitionFailure


class WorkflowComparisonQuery(StrictWorkbenchModel):
    leftRevisionId: str = Field(min_length=1, max_length=200)
    rightRevisionId: str = Field(min_length=1, max_length=200)


class WorkflowReceiptQuery(StrictWorkbenchModel):
    action: Literal["create", "edit", "validate", "review", "publish", "successor"]
    workflowId: str | None = None

    @model_validator(mode="after")
    def exact_target(self):
        if (self.action == "create" and self.workflowId is not None) or (
            self.action != "create"
            and (not self.workflowId or len(self.workflowId) > 200)
        ):
            raise ValueError("WORKFLOW_RECEIPT_TARGET_REQUIRED")
        return self


class WorkflowAuthoringTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if grant.owner != "WORKFLOW" or connection is None:
            return False
        if grant.action == "CREATE":
            return grant.exact_resource == "workflow:collection"
        if grant.action not in {"MANAGE", "REVIEW_PUBLISH"}:
            return False
        return (
            connection.execute(
                "SELECT 1 FROM workflow_definition.definitions WHERE namespace=%s "
                "AND security_domain=%s "
                "AND 'workflow:aggregate:' || workflow_definition_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    grant.exact_resource,
                ),
            ).fetchone()
            is not None
        )


def authoring_operations(service, services):
    author = WorkflowAuthoring(service, WorkflowReferenceChecker(services))

    def grants(context, path, payload, query):
        command = WorkflowAuthoringCommand.model_validate(payload)
        action, target = command_target(command)
        return (ExactGrant("WORKFLOW", action, target),)

    def aggregate_grants(context, path, payload, query):
        return (
            ExactGrant(
                "WORKFLOW", "MANAGE", "workflow:aggregate:" + path["workflow_id"]
            ),
        )

    def receipt_grants(context, path, payload, query):
        action, target = command_target(WorkflowReceiptQuery.model_validate(query))
        return (ExactGrant("WORKFLOW", action, target),)

    def comparison_grants(context, path, payload, query):
        return tuple(
            ExactGrant("WORKFLOW", "READ", f"workflow:{path['workflow_id']}:{revision}")
            for revision in dict.fromkeys(
                (query["leftRevisionId"], query["rightRevisionId"])
            )
        )

    def handle(call):
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            if call.operation == "COMMAND_WORKFLOW":
                return author.handle(call)
            if call.operation == "READ_WORKFLOW_COMMAND":
                row = call.connection.execute(
                    "SELECT result FROM execution_authority.prepared_resource_commands "
                    "WHERE namespace=%s AND security_domain=%s "
                    "AND actor_id=%s AND command_key=%s",
                    (
                        principal.tenant_id,
                        principal.security_domain,
                        principal.principal_id,
                        "workflow-authoring:" + call.path["command_key"],
                    ),
                ).fetchone()
                if row is None:
                    raise WorkbenchOwnerError("WORKFLOW_COMMAND_NOT_FOUND", 404)
                result = row["result"]
                if result["action"] != call.query["action"] or (
                    call.query["action"] != "create"
                    and result["workflowId"] != call.query["workflowId"]
                ):
                    raise WorkbenchOwnerError("WORKFLOW_COMMAND_NOT_FOUND", 404)
                action = (
                    "CREATE"
                    if result["action"] == "create"
                    else "REVIEW_PUBLISH"
                    if result["action"] in {"review", "publish"}
                    else "MANAGE"
                )
                target = (
                    "workflow:collection"
                    if action == "CREATE"
                    else "workflow:aggregate:" + result["workflowId"]
                )
                call.authority.require(principal, "WORKFLOW", action, target)
                return result
            bound = bind_service(service, call.connection)
            scope = bound.scope(principal.tenant_id, principal.security_domain)
            if call.operation == "COMPARE_WORKFLOW_REVISIONS":
                return bound.compare(
                    scope,
                    call.path["workflow_id"],
                    call.query["leftRevisionId"],
                    call.query["rightRevisionId"],
                )
            record = bound.repository.get(scope, call.path["workflow_id"])
            for revision in record["revisions"]:
                call.authority.require(
                    principal,
                    "WORKFLOW",
                    "READ",
                    f"workflow:{record['workflowDefinitionId']}:{revision['revisionId']}",
                )
            return bound.project(record)
        except WorkflowDefinitionFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc
        except (WorkflowDefinitionRepositoryError, PostgresError) as exc:
            raise WorkbenchOwnerError("WORKFLOW_AUTHORING_UNAVAILABLE", 503) from exc

    return (
        WorkbenchOperation(
            "COMPARE_WORKFLOW_REVISIONS",
            "GET",
            PREFIX + "/workflows/{workflow_id}/comparison",
            None,
            WorkflowComparisonQuery,
            comparison_grants,
            handle,
        ),
        WorkbenchOperation(
            "COMMAND_WORKFLOW",
            "POST",
            PREFIX + "/workflows/commands",
            WorkflowAuthoringCommand,
            None,
            grants,
            handle,
        ),
        WorkbenchOperation(
            "READ_WORKFLOW_COMMAND",
            "GET",
            PREFIX + "/workflows/commands/{command_key}",
            None,
            WorkflowReceiptQuery,
            receipt_grants,
            handle,
        ),
        WorkbenchOperation(
            "READ_WORKFLOW_AUTHORING",
            "GET",
            PREFIX + "/workflows/{workflow_id}/authoring",
            None,
            None,
            aggregate_grants,
            handle,
        ),
    )
