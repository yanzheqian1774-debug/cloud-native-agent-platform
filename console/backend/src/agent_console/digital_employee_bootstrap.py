"""Deterministic bootstrap and projections for the Digital Employee Product API."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from .agent_definition_repository import AgentDefinitionNotFound, DefinitionScope
from .agent_definition_service import AgentDefinitionService
from .digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    DigitalEmployeeApplicationService,
    DigitalEmployeeError,
)
from .digital_employee_postgres import PostgresDigitalEmployeeRepository
from .digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
    CreateDigitalEmployeePlacement,
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


class PublishedDefinitionAuthority:
    """Resolve one exact published revision in one trusted scope."""

    def __init__(self, definitions: AgentDefinitionService) -> None:
        self.definitions = definitions

    def resolve(self, scope, definition_id, revision_id):
        definition_scope = DefinitionScope(scope.namespace, scope.security_domain)
        try:
            record = self.definitions.repository.get(definition_scope, definition_id)
        except AgentDefinitionNotFound:
            return None
        published_id = record.get("publishedRevisionId")
        revision = next(
            (
                item
                for item in record.get("revisions", ())
                if item["revisionId"] == revision_id
            ),
            None,
        )
        if revision is None:
            return None
        eligible = (
            revision_id == published_id
            and revision.get("state") == "PUBLISHED"
            and record.get("enabled") is True
            and record.get("archived") is False
            and record.get("lifecycleState") not in {"DEPRECATED", "ARCHIVED"}
        )
        return DefinitionReference(
            definition_id,
            revision_id,
            revision["digest"],
            revision_id == published_id and revision.get("state") == "PUBLISHED",
            eligible,
        )


class DigitalEmployeeProductAssembly:
    def __init__(
        self,
        definitions: AgentDefinitionService,
        repository: PostgresDigitalEmployeeRepository,
    ) -> None:
        self.definitions = definitions
        self.repository = repository
        self.application = DigitalEmployeeApplicationService(
            repository, PublishedDefinitionAuthority(definitions)
        )

    @staticmethod
    def scope(tenant_id: str, security_domain: str) -> ScopeIdentity:
        if not tenant_id or not security_domain:
            raise DigitalEmployeeError("TRUSTED_SCOPE_REQUIRED")
        return ScopeIdentity(tenant_id, security_domain)

    def list_definitions(self, scope: ScopeIdentity) -> list[dict[str, Any]]:
        return self.definitions.list(
            DefinitionScope(scope.namespace, scope.security_domain)
        )

    def get_definition(self, scope: ScopeIdentity, definition_id: str):
        return self.definitions.get(
            DefinitionScope(scope.namespace, scope.security_domain), definition_id
        )

    def create_instance(
        self,
        scope: ScopeIdentity,
        principal_id: str,
        command: CreateDigitalEmployeeInstance,
    ):
        value, disposition = self.application.create_instance(
            scope=scope,
            instance_id=DigitalEmployeeInstanceId(command.instanceId),
            definition_id=command.definitionId,
            definition_revision_id=command.definitionRevisionId,
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
                    or instance.definition.revision_id != agent_revision_id
                )
            )
        ):
            raise DigitalEmployeeError("PLACEMENT_EXECUTION_NOT_ASSEMBLED")

    def instance_projection(self, value, disposition: str | None = None):
        result = {
            "instanceId": str(value.instance_id),
            "version": value.version,
            "definition": {
                "definitionId": value.definition.definition_id,
                "revisionId": value.definition.revision_id,
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

    def _relationship_projection(self, value):
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


def build_digital_employee_assembly(
    database_url: str,
    definitions: AgentDefinitionService,
    *,
    migration_path: Path,
    min_pool_size: int = 1,
    max_pool_size: int = 4,
    timeout: float = 5,
) -> DigitalEmployeeProductAssembly:
    authority = PostgresExecutionAuthorityRepository(
        database_url,
        migration_path=migration_path,
        min_pool_size=min_pool_size,
        max_pool_size=max_pool_size,
        timeout=timeout,
    )
    try:
        authority.migrate()
    except ExecutionSchemaIncompatible:
        _validate_execution_v8(authority)
    for version, suffix in (
        (9, "workflow_control_persistence"),
        (10, "workflow_control_uow_extension"),
    ):
        control = PostgresWorkflowControlRepository(
            database_url,
            migration_path=migration_path.with_name(f"{version:04d}_{suffix}.sql"),
            min_pool_size=min_pool_size,
            max_pool_size=max_pool_size,
            timeout=timeout,
        )
        try:
            control.migrate()
        finally:
            control.pool.close()
    return DigitalEmployeeProductAssembly(
        definitions, PostgresDigitalEmployeeRepository(authority)
    )


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
