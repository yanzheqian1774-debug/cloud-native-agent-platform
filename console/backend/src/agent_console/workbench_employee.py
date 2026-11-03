"""Trusted Workbench read adapter for exact Employee Definition facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from psycopg import Error as PostgresError

from agent_console.authority_contracts import ExactGrant
from agent_console.digital_employee_application import (
    DigitalEmployeeError,
    DigitalEmployeeRepository,
)
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionError,
    EmployeeDefinitionRepository,
    EmployeeRevision,
    MemberKind,
)
from agent_console.execution_domain import ExecutionPersistenceError, ScopeIdentity
from agent_console.execution_postgres import (
    AgentInstanceId,
    AssignmentId,
    AttemptId,
    DigitalEmployeeInstanceId,
    PlacementId,
)
from agent_console.workbench_bff import PREFIX, WorkbenchOperation
from agent_console.workbench_bff_schemas import (
    WorkbenchCreateEmployeeDefinition,
    WorkbenchDecideEmployeeDefinition,
    WorkbenchEmployeeCommandResult,
    WorkbenchEmployeePage,
    WorkbenchEmployeeRevision,
    WorkbenchEmployeeSummary,
    WorkbenchPageQuery,
    WorkbenchPlacement,
    WorkbenchPlacementQuery,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec


@dataclass(frozen=True, slots=True)
class _OwnerPrincipal:
    principal_id: str
    tenant_id: str
    security_domain: str


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
            aggregateVersion=value["aggregateVersion"],
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
            lifecycleState=value["lifecycleState"],
            publicationState=value["publicationState"],
        ).model_dump(mode="json")


class EmployeeDefinitionCommandOwnerAdapter:
    """Run bounded Employee commands on the authorization transaction."""

    _ACTIONS: ClassVar[dict[str, str]] = {
        "VALIDATE_EMPLOYEE_REVISION": "VALIDATE",
        "APPROVE_EMPLOYEE_REVISION": "APPROVE",
        "PUBLISH_EMPLOYEE_REVISION": "PUBLISH",
    }
    _MEMBER_READ_OWNERS: ClassVar[dict[MemberKind, str]] = {
        MemberKind.AGENT: "AGENT",
        MemberKind.WORKFLOW: "WORKFLOW",
    }

    def __init__(
        self, repository: EmployeeDefinitionRepository, *, prepared_resource_reads=False
    ) -> None:
        self.repository = repository
        self.prepared_resource_reads = prepared_resource_reads

    @staticmethod
    def _scope(call: AuthorizedOwnerCall) -> ScopeIdentity:
        return ScopeIdentity(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )

    @staticmethod
    def _decision_id(call: AuthorizedOwnerCall, action: str, resource: str) -> str:
        decision = next(
            (
                item
                for item in call.decisions
                if item.owner == "EMPLOYEE"
                and item.action == action
                and item.exact_resource == resource
            ),
            None,
        )
        if decision is None:
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        return decision.decision_id

    @staticmethod
    def _result(value: dict[str, Any]) -> dict[str, Any]:
        revision = value["revision"]
        return WorkbenchEmployeeCommandResult(
            employeeDefinitionId=revision["definitionId"],
            employeeDefinitionRevisionId=revision["revisionId"],
            employeeDefinitionDigest=value["digest"],
            aggregateVersion=value["aggregateVersion"],
            lifecycleState=value["lifecycleState"],
        ).model_dump(mode="json")

    def _require_member_reads(
        self,
        call: AuthorizedOwnerCall,
        revision: EmployeeRevision,
    ) -> None:
        principal = _OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        for member in revision.members:
            if self.prepared_resource_reads and member.kind in {
                MemberKind.SKILL,
                MemberKind.KNOWLEDGE,
                MemberKind.RUNTIME_PROFILE,
            }:
                from .workbench_prepared_resources import OWNERS, reference

                kind = {
                    MemberKind.SKILL: "skill",
                    MemberKind.KNOWLEDGE: "knowledge",
                    MemberKind.RUNTIME_PROFILE: "runtime",
                }[member.kind]
                call.authority.require(
                    principal,
                    OWNERS[kind],
                    "READ_RESOURCE",
                    reference(kind, member.resource_id, member.revision_id),
                )
                continue
            owner = self._MEMBER_READ_OWNERS.get(member.kind)
            if owner is None:
                raise WorkbenchOwnerError("EMPLOYEE_MEMBER_AUTHORITY_UNAVAILABLE", 409)
            call.authority.require(
                principal,
                owner,
                "READ",
                f"{owner.lower()}:{member.resource_id}:{member.revision_id}",
            )

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        scope = self._scope(call)
        try:
            if call.operation == "CREATE_EMPLOYEE_REVISION":
                revision = EmployeeRevision(
                    scope,
                    str(call.payload["employeeDefinitionId"]),
                    str(call.payload["employeeDefinitionRevisionId"]),
                    str(call.payload["role"]),
                    tuple(call.payload["responsibilities"]),
                    tuple(
                        CompositionMember(
                            MemberKind(member["kind"]),
                            member["resourceId"],
                            member["revisionId"],
                            member["digest"],
                        )
                        for member in call.payload["members"]
                    ),
                    call.payload.get("predecessorEmployeeRevisionId"),
                )
                value = self.repository.create_for_workbench(
                    call.connection,
                    revision,
                    expected_version=int(call.payload["expectedVersion"]),
                    decision_id=self._decision_id(
                        call, "CREATE", "employee:collection"
                    ),
                    command_id=str(call.payload["commandId"]),
                    authorized=True,
                )
                return self._result(value)

            action = self._ACTIONS.get(call.operation)
            if action is None:
                raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
            definition_id = call.path["employee_definition_id"]
            revision_id = call.path["revision_id"]
            current = self.repository.read_revision_for_workbench(
                call.connection,
                scope,
                definition_id,
                revision_id,
                authorized=True,
            )
            self._require_member_reads(
                call, EmployeeRevision.from_record(current["revision"])
            )
            resource = f"employee:{definition_id}:aggregate"
            value = self.repository.decide_for_workbench(
                call.connection,
                scope,
                definition_id,
                revision_id,
                str(call.payload["employeeDefinitionDigest"]),
                action,
                expected_version=int(call.payload["expectedVersion"]),
                decision_id=self._decision_id(call, action, resource),
                command_id=str(call.payload["commandId"]),
                authorized=True,
            )
            return self._result(value)
        except WorkbenchOwnerError:
            raise
        except EmployeeDefinitionError as exc:
            reason = str(exc)
            if reason == "EMPLOYEE_RECORD_CORRUPT":
                reason, status = "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            elif reason in {"EMPLOYEE_NOT_FOUND", "BOUND_RESOURCE_NOT_FOUND"}:
                status = 404
            elif reason.startswith("INVALID_") or reason in {
                "PRIMARY_AGENT_CARDINALITY",
                "DEFAULT_RUNTIME_CARDINALITY",
                "DUPLICATE_COMPOSITION_MEMBER",
            }:
                status = 422
            else:
                status = 409
            raise WorkbenchOwnerError(reason, status) from exc
        except (PostgresError, KeyError, TypeError) as exc:
            raise WorkbenchOwnerError(
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            ) from exc


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
            if call.operation == "READ_EMPLOYEE_PLACEMENT":
                decision = self.repository.read_placement_for_workbench(
                    call.connection,
                    scope,
                    DigitalEmployeeInstanceId(call.path["instance_id"]),
                    AssignmentId(call.path["assignment_id"]),
                    PlacementId(call.path["placement_id"]),
                    AttemptId(call.query["attemptId"]),
                    AgentInstanceId(call.query["agentInstanceId"]),
                    authorized=True,
                )
                if decision is None:
                    raise DigitalEmployeeError("PLACEMENT_NOT_FOUND")
                return WorkbenchPlacement(
                    placementId=str(decision.placement_id),
                    requestId=str(decision.request_id),
                    decision=decision.decision.value,
                    runtimeInstanceId=str(decision.runtime_instance_id),
                    policyVersion=decision.policy_version,
                    compatibilityFacts=decision.compatibility_facts,
                    limitationCodes=decision.limitation_codes,
                    decidedAt=decision.decided_at,
                    digest=decision.digest,
                    binding={
                        "instanceId": call.path["instance_id"],
                        "assignmentId": call.path["assignment_id"],
                        "attemptId": call.query["attemptId"],
                        "agentInstanceId": call.query["agentInstanceId"],
                    },
                ).model_dump(mode="json")
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
            elif call.operation == "READ_EMPLOYEE_PLACEMENT":
                reason, status = "PLACEMENT_NOT_FOUND", 404
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


def _employee_create(context, path, payload, query):
    return (ExactGrant("EMPLOYEE", "CREATE", "employee:collection"),)


def _employee_lifecycle(action: str):
    def build(context, path, payload, query):
        return (
            ExactGrant(
                "EMPLOYEE",
                action,
                f"employee:{path['employee_definition_id']}:aggregate",
            ),
        )

    return build


def _instance_read(context, path, payload, query):
    return (ExactGrant("INSTANCE", "READ", f"instance:{path['instance_id']}"),)


def _assignment_read(context, path, payload, query):
    return (ExactGrant("ASSIGNMENT", "READ", f"assignment:{path['assignment_id']}"),)


def _placement_read(context, path, payload, query):
    return (ExactGrant("PLACEMENT", "READ", f"placement:{path['placement_id']}"),)


def employee_operations(
    repository: EmployeeDefinitionRepository,
    cursors: WorkbenchCursorCodec,
    *,
    prepared_resource_reads=False,
) -> tuple[WorkbenchOperation, ...]:
    command_handler = EmployeeDefinitionCommandOwnerAdapter(
        repository, prepared_resource_reads=prepared_resource_reads
    )
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
            "CREATE_EMPLOYEE_REVISION",
            "POST",
            f"{PREFIX}/employees",
            WorkbenchCreateEmployeeDefinition,
            None,
            _employee_create,
            command_handler,
            201,
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
        WorkbenchOperation(
            "VALIDATE_EMPLOYEE_REVISION",
            "POST",
            f"{PREFIX}/employees/{{employee_definition_id}}/revisions/"
            "{revision_id}/validation",
            WorkbenchDecideEmployeeDefinition,
            None,
            _employee_lifecycle("VALIDATE"),
            command_handler,
        ),
        WorkbenchOperation(
            "APPROVE_EMPLOYEE_REVISION",
            "POST",
            f"{PREFIX}/employees/{{employee_definition_id}}/revisions/"
            "{revision_id}/approvals",
            WorkbenchDecideEmployeeDefinition,
            None,
            _employee_lifecycle("APPROVE"),
            command_handler,
        ),
        WorkbenchOperation(
            "PUBLISH_EMPLOYEE_REVISION",
            "POST",
            f"{PREFIX}/employees/{{employee_definition_id}}/revisions/"
            "{revision_id}/publication",
            WorkbenchDecideEmployeeDefinition,
            None,
            _employee_lifecycle("PUBLISH"),
            command_handler,
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
        WorkbenchOperation(
            "READ_EMPLOYEE_PLACEMENT",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}/assignments/{{assignment_id}}/"
            "placements/{placement_id}",
            None,
            WorkbenchPlacementQuery,
            _placement_read,
            adapter,
        ),
    )
