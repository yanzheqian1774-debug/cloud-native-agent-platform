"""Atomic command boundary for trusted workflow authoring (registration separate)."""

from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from .resource_use_domain import canonical_digest
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service
from .workflow_definition_schemas import WorkflowContent


class WorkflowAuthoringCommand(StrictWorkbenchModel):
    action: Literal["create", "edit", "validate", "review", "publish", "successor"]
    commandKey: str = Field(min_length=1, max_length=200)
    workflowId: str | None = Field(default=None, min_length=1, max_length=200)
    expectedVersion: int | None = Field(default=None, strict=True, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    content: WorkflowContent | None = None
    digest: str | None = Field(default=None, pattern=r"^(?:sha256:)?[a-f0-9]{64}$")
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    reviewId: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def required_fields(self):
        allowed = {"action", "commandKey"}
        if self.action == "create":
            allowed |= {"name", "content"}
        else:
            allowed |= {"workflowId", "expectedVersion"}
            allowed |= {
                "edit": {"content"},
                "review": {"digest", "reason"},
                "publish": {"digest", "reviewId"},
            }.get(self.action, set())
        if self.content and self.content.runtimeProfile.kind != "RUNTIME_PROFILE":
            raise ValueError("WORKFLOW_RUNTIME_PROFILE_REQUIRED")
        values = self.model_dump(exclude_none=True)
        if set(values) != allowed or any(
            isinstance(v, str) and not v.strip() for v in values.values()
        ):
            raise ValueError("WORKFLOW_COMMAND_FIELDS_INVALID")
        return self


def command_target(command):
    if command.action == "create":
        return "CREATE", "workflow:collection"
    action = "REVIEW_PUBLISH" if command.action in {"review", "publish"} else "MANAGE"
    return action, "workflow:aggregate:" + command.workflowId


class WorkflowAuthoring:
    """Reference checker must read exact owners using this same authorized call."""

    def __init__(self, service, reference_checker):
        self.service = service
        self.reference_checker = reference_checker

    def handle(self, call):
        command = WorkflowAuthoringCommand.model_validate(call.payload)
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        action, target = command_target(command)
        call.authority.require(principal, "WORKFLOW", action, target)
        if command.action in {
            "review",
            "publish",
        } and not principal.principal_id.startswith("human:"):
            raise WorkbenchOwnerError("WORKFLOW_HUMAN_REVIEW_REQUIRED", 403)
        key = "workflow-authoring:" + command.commandKey
        scope_key = (
            principal.tenant_id,
            principal.security_domain,
            principal.principal_id,
            key,
        )
        payload_digest = canonical_digest(
            command.model_dump(mode="json", exclude_none=True)
        )
        call.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (canonical_digest(scope_key),),
        )
        old = call.connection.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s "
            "AND actor_id=%s AND command_key=%s",
            scope_key,
        ).fetchone()
        if old:
            if old["digest"] != payload_digest:
                raise WorkbenchOwnerError("WORKFLOW_COMMAND_CONFLICT", 409)
            return {**old["result"], "replayed": True}
        service = bind_service(self.service, call.connection)
        scope = service.scope(principal.tenant_id, principal.security_domain)
        # Every owner read remains in the authorized transaction; no global resolver.
        service.reference_resolver = lambda _, ref: self.reference_checker(
            call, ref, True
        )
        content = (
            command.content.model_dump(exclude_none=True) if command.content else None
        )
        if content:
            for ref in [
                content["runtimeProfile"],
                *(
                    ref
                    for task in content["tasks"]
                    for ref in task.get("references", [])
                ),
            ]:
                if not self.reference_checker(call, ref, False):
                    raise WorkbenchOwnerError("WORKFLOW_REFERENCE_UNAVAILABLE", 409)
        if command.action in {"review", "publish"}:
            current = service.repository.get(scope, command.workflowId)
            draft = service._draft(current)
            service._validate_content(scope, draft["content"], resolve=True)
        actor = principal.principal_id
        if command.action == "create":
            record = service.create(scope, actor, command.name, content)
        else:
            args = (scope, command.workflowId, actor, command.expectedVersion)
            if command.action == "edit":
                record = service.edit(*args, content)
            elif command.action == "review":
                record = service.review(
                    *args, command.digest, "APPROVE", command.reason
                )
            elif command.action == "publish":
                record = service.publish(*args, command.digest, command.reviewId)
            elif command.action == "validate":
                record = service.validate(*args)
            else:
                record = service.successor(*args)
        result = {
            "schemaVersion": "workflow-authoring-receipt.v1",
            "commandKey": command.commandKey,
            "action": command.action,
            "workflowId": record["workflowDefinitionId"],
            "aggregateVersion": record["aggregateVersion"],
            "revisionId": record.get("currentDraftRevisionId")
            or record.get("publishedRevisionId"),
            "replayed": False,
            "executionAuthorized": False,
        }
        call.connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands"
            "(namespace,security_domain,actor_id,command_key,digest,result) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (*scope_key, payload_digest, Jsonb(result)),
        )
        return result
