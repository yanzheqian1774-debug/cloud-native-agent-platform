"""Deterministic bootstrap and projections for the Digital Employee Product API."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from .agent_definition_repository import AgentDefinitionNotFound, DefinitionScope
from .agent_definition_service import AgentDefinitionService
from .digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DigitalEmployeeApplicationService,
    DigitalEmployeeError,
)
from .digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionService,
    EmployeeRevision,
    MemberKind,
    PublishedEmployeeDefinitionAuthority,
    ScopedEmployeeAuthorization,
)
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .digital_employee_postgres import PostgresDigitalEmployeeRepository
from .digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
    CreateDigitalEmployeePlacement,
    CreateEmployeeDefinition,
    DecideEmployeeDefinition,
)
from .execution_domain import ExecutionSchemaIncompatible
from .execution_postgres import (
    AgentInstanceId,
    AssignmentId,
    AttemptId,
    DigitalEmployeeInstanceId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    PostgresExecutionAuthorityRepository,
    RuntimeInstanceId,
    ScopeIdentity,
    TaskRunId,
    WorkflowRunId,
)
from .workflow_control_postgres import PostgresWorkflowControlRepository


class DigitalEmployeeProductAssembly:
    def __init__(
        self,
        definitions: AgentDefinitionService,
        repository: PostgresDigitalEmployeeRepository,
    ) -> None:
        self.definitions = definitions
        self.repository = repository
        self.employee_definitions = PostgresEmployeeDefinitionRepository(
            repository.authority
        )
        self.application = DigitalEmployeeApplicationService(repository, None)

    @staticmethod
    def scope(tenant_id: str, security_domain: str) -> ScopeIdentity:
        if not tenant_id or not security_domain:
            raise DigitalEmployeeError("TRUSTED_SCOPE_REQUIRED")
        return ScopeIdentity(tenant_id, security_domain)

    @staticmethod
    def _employee_authorization(scope, principal_id, permissions, decision_id):
        return ScopedEmployeeAuthorization(
            scope, principal_id, frozenset(permissions), decision_id
        )

    def _employee_service(self, scope, principal_id, permissions, decision_id):
        return EmployeeDefinitionService(
            self.employee_definitions,
            self._employee_authorization(scope, principal_id, permissions, decision_id),
        )

    def list_definitions(self, scope: ScopeIdentity, principal_id: str):
        service = self._employee_service(
            scope, principal_id, {"LIST"}, f"list:{principal_id}"
        )
        return [self.employee_definition_projection(row) for row in service.list(scope)]

    def get_definition(
        self,
        scope: ScopeIdentity,
        principal_id: str,
        definition_id: str,
        revision_id: str,
    ):
        service = self._employee_service(
            scope,
            principal_id,
            {"READ"},
            f"read:{principal_id}:{definition_id}:{revision_id}",
        )
        return self.employee_definition_projection(
            service.read(scope, definition_id, revision_id)
        )

    def create_definition(
        self, scope: ScopeIdentity, principal_id: str, command: CreateEmployeeDefinition
    ):
        service = self._employee_service(
            scope,
            principal_id,
            {"CREATE"},
            f"create:{principal_id}:{command.commandId}",
        )
        revision = EmployeeRevision(
            scope,
            command.employeeDefinitionId,
            command.employeeDefinitionRevisionId,
            command.role,
            tuple(command.responsibilities),
            tuple(
                CompositionMember(
                    MemberKind(member.kind),
                    member.resourceId,
                    member.revisionId,
                    member.digest,
                )
                for member in command.members
            ),
            command.predecessorEmployeeRevisionId,
        )
        return self.employee_definition_projection(
            service.create(
                revision,
                expected_version=command.expectedVersion,
                command_id=command.commandId,
            )
        )

    def decide_definition(
        self,
        scope: ScopeIdentity,
        principal_id: str,
        definition_id: str,
        action: str,
        command: DecideEmployeeDefinition,
    ):
        service = self._employee_service(
            scope,
            principal_id,
            {action, "READ_MEMBER"},
            f"{action.lower()}:{principal_id}:{command.commandId}",
        )
        return self.employee_definition_projection(
            service.decide(
                scope,
                definition_id,
                command.employeeDefinitionRevisionId,
                command.employeeDefinitionDigest,
                action,
                expected_version=command.expectedVersion,
                command_id=command.commandId,
            )
        )

    def create_instance(
        self,
        scope: ScopeIdentity,
        principal_id: str,
        command: CreateDigitalEmployeeInstance,
    ):
        authorization = ScopedEmployeeAuthorization(
            scope,
            principal_id,
            frozenset({"INSTANTIATE", "READ_MEMBER"}),
            f"instantiate:{command.commandId}",
        )
        service = DigitalEmployeeApplicationService(
            self.repository,
            PublishedEmployeeDefinitionAuthority(
                self.employee_definitions, authorization
            ),
        )
        value, disposition = service.create_instance(
            scope=scope,
            instance_id=DigitalEmployeeInstanceId(command.instanceId),
            definition_id=command.employeeDefinitionId,
            definition_revision_id=command.employeeDefinitionRevisionId,
            owner_id=principal_id,
            organization_id=scope.namespace,
            command_id=command.commandId,
            workspace_reference=command.workspaceReference,
            model_reference=command.modelReference,
            policy_references=tuple(command.policyReferences),
        )
        return self.instance_projection(value, disposition.value)

    def get_instance(self, scope: ScopeIdentity, instance_id: str):
        value = self.repository.get_instance(
            scope, DigitalEmployeeInstanceId(instance_id)
        )
        if value is None:
            raise DigitalEmployeeError("INSTANCE_NOT_FOUND")
        return self.instance_projection(value)

    def create_assignment(
        self,
        scope: ScopeIdentity,
        instance_id: str,
        command: CreateDigitalEmployeeAssignment,
    ):
        value = AssignmentRecord(
            scope,
            AssignmentId(command.assignmentId),
            DigitalEmployeeInstanceId(instance_id),
            command.assigneeId,
            command.businessRole,
            AssignmentLifecycle.ACTIVE,
            command.effectiveFrom,
            command.effectiveUntil,
            1,
            command.commandId,
        )
        disposition = self.application.assign(value)
        return self.assignment_projection(value, disposition.value)

    def get_assignment(self, scope, instance_id: str, assignment_id: str):
        values = self.repository.assignments_for_instance(
            scope, DigitalEmployeeInstanceId(instance_id)
        )
        value = next(
            (item for item in values if str(item.assignment_id) == assignment_id), None
        )
        if value is None:
            raise DigitalEmployeeError("ASSIGNMENT_NOT_FOUND")
        return self.assignment_projection(value)

    def create_placement(
        self,
        scope: ScopeIdentity,
        instance_id: str,
        assignment_id: str,
        command: CreateDigitalEmployeePlacement,
    ):
        self._verify_execution_chain(
            scope,
            instance_id,
            assignment_id,
            command.attemptId,
            command.agentInstanceId,
            command.agentRevisionId,
            command.workflowRunId,
            command.taskRunId,
        )
        request = PlacementRequest(
            PlacementRequestId(command.requestId),
            scope,
            WorkflowRunId(command.workflowRunId),
            TaskRunId(command.taskRunId),
            AttemptId(command.attemptId),
            AgentInstanceId(command.agentInstanceId),
            command.agentRevisionId,
            command.runtimeProfileRevisionId,
            tuple(command.capabilityRequirements),
            tuple(command.resourceRequirements),
            tuple(command.isolationRequirements),
            tuple(command.stateRequirements),
            command.requestedAt,
        )
        decision = PlacementDecision.create(
            placement_id=PlacementId(command.placementId),
            request_id=request.request_id,
            decision=PlacementDecisionKind.PLACED,
            runtime_instance_id=RuntimeInstanceId(command.runtimeInstanceId),
            policy_version=command.policyVersion,
            compatibility_facts=command.compatibilityFacts,
            limitation_codes=command.limitationCodes,
            decided_at=command.decidedAt,
        )
        facts = self.application.place(
            scope, request, decision, freshness_window=timedelta(seconds=30)
        )
        return self.placement_projection(
            facts.result.decision, facts, facts.result.disposition.value
        )

    def get_placement(
        self, scope, instance_id, assignment_id, placement_id, attempt_id, agent_id
    ):
        self._verify_execution_chain(
            scope, instance_id, assignment_id, attempt_id, agent_id
        )
        decision = self.repository.authority.get(scope, PlacementId(placement_id))
        if decision is None:
            raise DigitalEmployeeError("PLACEMENT_NOT_FOUND")
        if decision.runtime_instance_id is None:
            raise DigitalEmployeeError("PLACEMENT_NOT_ASSEMBLED")
        if not self.repository.placement_request_matches(
            scope,
            decision.placement_id,
            AttemptId(attempt_id),
            AgentInstanceId(agent_id),
        ):
            raise DigitalEmployeeError("PLACEMENT_NOT_FOUND")
        active = self.repository.active_attempts(
            scope, decision.runtime_instance_id, AgentInstanceId(agent_id)
        )
        if AttemptId(attempt_id) not in active:
            raise DigitalEmployeeError("PLACEMENT_NOT_FOUND")
        return self.placement_projection(decision)

    def _verify_execution_chain(
        self,
        scope,
        instance_id,
        assignment_id,
        attempt_id,
        agent_id,
        agent_revision_id=None,
        workflow_run_id=None,
        task_run_id=None,
    ):
        assignment = self.get_assignment(scope, instance_id, assignment_id)
        instance = self.repository.get_instance(
            scope, DigitalEmployeeInstanceId(instance_id)
        )
        aggregate = self.repository.authority.get_attempt(scope, AttemptId(attempt_id))
        agent = self.repository.authority.get_aggregate(
            "agent_instance", scope, agent_id
        )
        if aggregate is None:
            raise DigitalEmployeeError("PLACEMENT_EXECUTION_NOT_ASSEMBLED")
        if (
            instance is None
            or str(aggregate.assignment.assignment_id) != assignment["assignmentId"]
            or str(aggregate.assignment.digital_employee_instance_id) != instance_id
            or agent is None
            or (
                instance.definition.authority_kind == "DIGITAL_EMPLOYEE_DEFINITION_V1"
                and (
                    agent.record.get("agent_definition_id"),
                    agent.record.get("agent_revision_id"),
                    agent.record.get("agent_digest"),
                )
                != (
                    instance.definition.primary_agent_id,
                    instance.definition.primary_agent_revision_id,
                    instance.definition.primary_agent_digest,
                )
            )
            or (
                workflow_run_id is not None
                and str(aggregate.workflow_run.workflow_run_id) != workflow_run_id
            )
            or (
                task_run_id is not None
                and str(aggregate.task_run.task_run_id) != task_run_id
            )
            or (
                agent_revision_id is not None
                and (
                    agent.record.get("agent_revision_id") != agent_revision_id
                    or instance.definition.authority_kind
                    != "DIGITAL_EMPLOYEE_DEFINITION_V1"
                    or instance.definition.primary_agent_revision_id
                    != agent_revision_id
                )
            )
        ):
            raise DigitalEmployeeError("PLACEMENT_EXECUTION_NOT_ASSEMBLED")

    def instance_projection(self, value, disposition: str | None = None):
        definition_key = (
            "employeeDefinition"
            if value.definition.authority_kind == "DIGITAL_EMPLOYEE_DEFINITION_V1"
            else "legacyDefinitionReference"
        )
        result = {
            "instanceId": str(value.instance_id),
            "version": value.version,
            definition_key: {
                "authorityKind": value.definition.authority_kind,
                "employeeDefinitionId": value.definition.definition_id,
                "employeeDefinitionRevisionId": value.definition.revision_id,
                "digest": value.definition.digest,
            },
            "ownerId": value.owner_id,
            "organizationId": value.organization_id,
            "lifecycle": value.lifecycle.value,
            "workspaceReference": value.workspace_reference,
            "modelReference": value.model_reference,
            "policyReferences": list(value.policy_references),
            "relationships": self._relationship_projection(value),
            "createdAt": value.created_at,
            "updatedAt": value.updated_at,
            "execution": {
                "state": "UNAVAILABLE",
                "reasonCode": "EXECUTION_NOT_ASSEMBLED",
            },
            "health": {"state": "UNAVAILABLE", "reasonCode": "HEALTH_NOT_OBSERVED"},
        }
        if disposition:
            result["disposition"] = disposition
        return result

    @staticmethod
    def employee_definition_projection(value):
        revision = value["revision"]
        return {
            "resourceKind": "DIGITAL_EMPLOYEE_DEFINITION",
            "employeeDefinitionId": revision["definitionId"],
            "employeeDefinitionRevisionId": revision["revisionId"],
            "employeeDefinitionDigest": value["digest"],
            "aggregateVersion": value["aggregateVersion"],
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
            "predecessorEmployeeRevisionId": revision["predecessorRevisionId"],
            "published": value["published"],
            "matchable": value["matchable"],
            "facts": [
                {
                    "action": fact["action"],
                    "decisionId": fact["decision_id"],
                    "ordinal": fact["ordinal"],
                }
                for fact in value["facts"]
            ],
        }

    def _relationship_projection(self, value):
        if value.definition.authority_kind == "DIGITAL_EMPLOYEE_DEFINITION_V1":
            current = self.employee_definitions.read(
                value.scope,
                value.definition.definition_id,
                value.definition.revision_id,
            )
            return {
                "directComposition": current["revision"]["members"],
                "compositionDigest": current["digest"],
            }
        scope = DefinitionScope(value.scope.namespace, value.scope.security_domain)
        try:
            record = self.definitions.repository.get(
                scope, value.definition.definition_id
            )
        except AgentDefinitionNotFound:
            return {}
        revision = next(
            (
                item
                for item in record.get("revisions", ())
                if item.get("revisionId") == value.definition.revision_id
                and item.get("digest") == value.definition.digest
            ),
            None,
        )
        if revision is None:
            return {}
        content = revision.get("content", {})
        bindings = content.get("bindings", {})
        relationships = {}
        for source, target in (
            ("capabilities", "capabilities"),
            ("knowledge", "knowledge"),
        ):
            selected = (
                content.get(source)
                if source == "capabilities"
                else bindings.get(source)
            )
            if selected:
                relationships[target] = selected
        for name in ("workflow", "runtimeProfile"):
            if bindings.get(name):
                relationships[name] = bindings[name]
        return relationships

    @staticmethod
    def assignment_projection(value, disposition: str | None = None):
        result = {
            "assignmentId": str(value.assignment_id),
            "instanceId": str(value.instance_id),
            "assigneeId": value.assignee_id,
            "businessRole": value.business_role,
            "lifecycle": value.lifecycle.value,
            "effectiveFrom": value.effective_from,
            "effectiveUntil": value.effective_until,
            "version": value.version,
            "commandId": value.command_id,
            "binding": {
                "state": "UNAVAILABLE",
                "reasonCode": "WORKFLOW_BINDING_NOT_ASSEMBLED",
            },
        }
        if disposition:
            result["disposition"] = disposition
        return result

    @staticmethod
    def placement_projection(decision, facts=None, disposition: str | None = None):
        result = {
            "placementId": str(decision.placement_id),
            "requestId": str(decision.request_id),
            "decision": decision.decision.value,
            "runtimeInstanceId": str(decision.runtime_instance_id),
            "policyVersion": decision.policy_version,
            "compatibilityFacts": list(decision.compatibility_facts),
            "limitationCodes": list(decision.limitation_codes),
            "decidedAt": decision.decided_at,
            "digest": decision.digest,
            "execution": {
                "state": "UNAVAILABLE",
                "reasonCode": "RUNTIME_EXECUTION_NOT_STARTED",
            },
            "outcome": {"state": "UNAVAILABLE", "reasonCode": "OUTCOME_NOT_RECORDED"},
        }
        if facts is not None:
            result["observation"] = {
                "freshness": facts.freshness.value,
                "observationId": facts.observation_id,
            }
        if disposition:
            result["disposition"] = disposition
        return result


def migrate_execution_authority(
    authority: PostgresExecutionAuthorityRepository,
    *,
    already_recorded: bool = False,
) -> None:
    if already_recorded:
        _validate_execution_v8(authority)
        return
    try:
        authority.migrate()
    except ExecutionSchemaIncompatible:
        _validate_execution_v8(authority)


def migrate_workflow_controls(
    controls: tuple[PostgresWorkflowControlRepository, ...],
    *,
    recorded_versions: frozenset[int] | None = None,
) -> None:
    recorded_versions = recorded_versions or frozenset()
    for control in controls:
        try:
            version = int(control.migration_path.name[:4])
            if version in recorded_versions:
                control.compatibility(version=version)
            else:
                control.migrate()
        finally:
            control.pool.close()


def complete_digital_employee_assembly(
    definitions: AgentDefinitionService,
    authority: PostgresExecutionAuthorityRepository,
    migration_path: Path,
    *,
    already_recorded: bool = False,
) -> DigitalEmployeeProductAssembly:
    employee_definitions = PostgresEmployeeDefinitionRepository(authority)
    identity_migration = migration_path.with_name("0014_digital_employee_identity.sql")
    if already_recorded:
        employee_definitions.compatibility(identity_migration)
    else:
        employee_definitions.migrate(identity_migration)
    return DigitalEmployeeProductAssembly(
        definitions, PostgresDigitalEmployeeRepository(authority)
    )


def build_digital_employee_assembly(
    database_url: str,
    definitions: AgentDefinitionService,
    *,
    migration_path: Path,
    min_pool_size: int = 1,
    max_pool_size: int = 4,
    timeout: float = 5,
    authority: PostgresExecutionAuthorityRepository | None = None,
    workflow_controls: tuple[PostgresWorkflowControlRepository, ...] | None = None,
) -> DigitalEmployeeProductAssembly:
    authority = authority or PostgresExecutionAuthorityRepository(
        database_url,
        migration_path=migration_path,
        min_pool_size=min_pool_size,
        max_pool_size=max_pool_size,
        timeout=timeout,
    )
    controls = workflow_controls
    if controls is None:
        controls = tuple(
            PostgresWorkflowControlRepository(
                database_url,
                migration_path=migration_path.with_name(f"{version:04d}_{suffix}.sql"),
                min_pool_size=min_pool_size,
                max_pool_size=max_pool_size,
                timeout=timeout,
            )
            for version, suffix in (
                (9, "workflow_control_persistence"),
                (10, "workflow_control_uow_extension"),
            )
        )
    migrate_execution_authority(authority)
    migrate_workflow_controls(controls)
    return complete_digital_employee_assembly(definitions, authority, migration_path)


def _validate_execution_v8(authority: PostgresExecutionAuthorityRepository) -> None:
    """Validate the exact v8 base before accepting additive v9/v10 migrations."""
    with authority.pool.connection() as connection:
        row = connection.execute(
            "SELECT checksum,adapter FROM execution_authority.schema_migrations "
            "WHERE version=8"
        ).fetchone()
    if row != {
        "checksum": authority.migration_checksum,
        "adapter": "execution-authority-postgresql-v1",
    }:
        raise ExecutionSchemaIncompatible("EXECUTION_SCHEMA_INCOMPATIBLE")
