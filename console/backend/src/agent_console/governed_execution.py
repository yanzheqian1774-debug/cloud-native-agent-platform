"""Trusted entry that joins durable Execution start to governed Skill dispatch."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .execution_application import (
    ApprovedPlanIdentity,
    ExecutionApplicationError,
    ExecutionApplicationService,
    ScopedExecutionAuthorization,
    StartExecutionCommand,
)
from .execution_domain import ScopeIdentity
from .execution_postgres import (
    AssignmentId,
    AttemptId,
    DigitalEmployeeInstanceId,
    PostgresExecutionAuthorityRepository,
)
from .governed_execution_schemas import StartGovernedExecution
from .planning import (
    CanonicalWorkflowRevision,
    IntentRevision,
    PlanningState,
    TaskRequirement,
)
from .problems import TrustedPrincipal
from .resource_use_application import (
    ResourceUseApplicationService,
    ScopedResourceUseAuthorization,
)
from .resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    ResourceUseError,
    canonical_digest,
    stable_id,
)
from .skill_invocation_application import ScopedSkillInvocationAuthorization
from .skill_invocation_composition import SkillInvocationComposition
from .skill_invocation_domain import (
    ExecutorRevision,
    InvocationState,
    SideEffectClass,
    SideEffectPolicy,
    SkillInvocationError,
    SkillInvocationRequest,
    SkillIOLimits,
)
from .workflow_control_domain import PlanStatus
from .workflow_control_postgres import PostgresWorkflowControlRepository


class GovernedExecutionError(ValueError):
    """Stable, non-disclosing failure at the internal control boundary."""


@dataclass(frozen=True, slots=True)
class GovernedExecutionResult:
    replayed: bool
    document: dict[str, Any]


def _decision_id(principal: TrustedPrincipal, key: str) -> str:
    digest = hashlib.sha256(
        "\x00".join(
            (
                principal.tenant_id,
                principal.security_domain,
                principal.principal_id,
                "START_AND_INVOKE_SKILL",
                key,
            )
        ).encode()
    ).hexdigest()
    return f"execution-authorization:{digest}"


def _workflow_from_plan(raw: bytes) -> tuple[CanonicalWorkflowRevision, str, str]:
    try:
        envelope = json.loads(raw)
        workflow = envelope["workflow"]
        intent = workflow["intent_revision"]
        lifecycle = PlanningState(workflow.get("lifecycle", "CANONICALIZED"))
        parsed = CanonicalWorkflowRevision(
            workflow["canonical_workflow_revision_id"],
            workflow["revision"],
            workflow.get("predecessor_revision_id"),
            workflow["tenant_id"],
            workflow["security_domain"],
            workflow["approved_candidate_digest"],
            workflow["approval_id"],
            workflow["policy_version"],
            IntentRevision(**intent),
            tuple(TaskRequirement(**item) for item in workflow["tasks"]),
            tuple(workflow["ordered_task_ids"]),
            tuple(workflow["limitations"]),
            workflow["matching_eligible"],
            lifecycle,
        )
        if envelope["schemaVersion"] != "employee-execution-plan.v1":
            raise ValueError
        return parsed, envelope["assignmentId"], envelope["instanceId"]
    except (KeyError, TypeError, ValueError) as exc:
        raise GovernedExecutionError("GOVERNED_PLAN_CONTENT_INVALID") from exc


class GovernedExecutionApplication:
    """One synchronous, durable start and one managed READ_ONLY Skill slot."""

    def __init__(
        self,
        execution: PostgresExecutionAuthorityRepository,
        workflow_control: PostgresWorkflowControlRepository,
        skill: SkillInvocationComposition,
    ) -> None:
        self.execution = execution
        self.workflow_control = workflow_control
        self.skill = skill

    @staticmethod
    def _scope(principal: TrustedPrincipal) -> ScopeIdentity:
        if not principal.principal_id:
            raise GovernedExecutionError("AUTHENTICATION_REQUIRED")
        if not principal.tenant_id or not principal.security_domain:
            raise GovernedExecutionError("TRUSTED_SCOPE_REQUIRED")
        return ScopeIdentity(principal.tenant_id, principal.security_domain)

    def start(
        self, principal: TrustedPrincipal, command: StartGovernedExecution
    ) -> GovernedExecutionResult:
        scope = self._scope(principal)
        decision_id = _decision_id(principal, command.idempotencyKey)
        # Trusted authorization is established before any protected lookup.
        authorization = ScopedExecutionAuthorization(
            scope, principal.principal_id, frozenset({"START"}), decision_id
        )
        authorization.require(scope, "START", command.assignmentId)
        plan = self.workflow_control.get_plan(
            scope, command.planId, command.planVersion
        )
        if (
            plan is None
            or plan.status is not PlanStatus.APPROVED
            or plan.plan_digest != command.planDigest
            or hashlib.sha256(plan.canonical_bytes).hexdigest() != plan.plan_digest
        ):
            raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
        approvals = self.workflow_control.read_approvals(
            scope, command.planId, command.planVersion
        )
        approval = next(
            (
                item
                for item in approvals
                if item.approval_decision_id == command.approvalId
                and item.decision == "APPROVE"
                and item.plan_digest == command.planDigest
            ),
            None,
        )
        if approval is None:
            raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
        workflow, assignment_id, instance_id = _workflow_from_plan(plan.canonical_bytes)
        if (
            assignment_id != command.assignmentId
            or instance_id != command.digitalEmployeeInstanceId
            or workflow.approval_id != command.approvalId
        ):
            raise GovernedExecutionError("GOVERNED_PLAN_BINDING_MISMATCH")
        approved = ApprovedPlanIdentity(
            workflow.canonical_workflow_revision_id,
            workflow.approved_candidate_digest,
            command.approvalId,
            command.planId,
            command.planVersion,
            command.planDigest,
        )
        try:
            started = ExecutionApplicationService(self.execution, authorization).start(
                StartExecutionCommand(
                    scope,
                    workflow,
                    approved,
                    AssignmentId(command.assignmentId),
                    DigitalEmployeeInstanceId(command.digitalEmployeeInstanceId),
                    command.taskId,
                    command.idempotencyKey,
                )
            )
            request = self._skill_request(scope, decision_id, command, started.identity)
            skill_service = self.skill.service(
                ScopedSkillInvocationAuthorization(
                    scope,
                    principal.principal_id,
                    frozenset({"INVOKE_SKILL", "READ_SKILL_INVOCATION"}),
                    decision_id,
                )
            )
            invocation = skill_service.invoke(request, command.input)
        except (ExecutionApplicationError, SkillInvocationError) as exc:
            raise GovernedExecutionError(str(exc)) from exc
        return GovernedExecutionResult(
            started.disposition.value == "REPLAYED",
            self._projection(started.identity, invocation),
        )

    def read(
        self,
        principal: TrustedPrincipal,
        *,
        workflow_run_id: str,
        attempt_id: str,
        invocation_id: str,
    ) -> dict[str, Any]:
        scope = self._scope(principal)
        decision_id = _decision_id(principal, f"read:{invocation_id}")
        authorization = ScopedExecutionAuthorization(
            scope, principal.principal_id, frozenset({"READ"}), decision_id
        )
        authorization.require(scope, "READ", attempt_id)
        identity = self.execution.get_attempt(scope, AttemptId(attempt_id))
        if (
            identity is None
            or str(identity.workflow_run.workflow_run_id) != workflow_run_id
        ):
            raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
        exact = self._invocation_exact(scope, invocation_id)
        if exact is None:
            if self._attempt_has_invocation(scope, attempt_id):
                raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
            return {
                "schemaVersion": "governed-execution-read.v1",
                "identity": self._identity(identity),
                "invocation": {
                    "invocationId": invocation_id,
                    "state": "NOT_INVOKED",
                    "resultKnown": False,
                    "evidenceId": None,
                    "resourceUseId": None,
                },
                "exactBinding": None,
                "resourceUse": None,
                "evidenceContentDisclosed": False,
                "businessOutcome": None,
            }
        if exact["attempt_id"] != attempt_id:
            raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
        skill_service = self.skill.service(
            ScopedSkillInvocationAuthorization(
                scope,
                principal.principal_id,
                frozenset({"READ_SKILL_INVOCATION"}),
                decision_id,
            )
        )
        try:
            read = skill_service.read(scope, invocation_id)
        except SkillInvocationError as exc:
            raise GovernedExecutionError(str(exc)) from exc
        try:
            resource = ResourceUseApplicationService(
                self.skill.resource_use_repository,
                ScopedResourceUseAuthorization(
                    scope,
                    principal.principal_id,
                    frozenset({"READ"}),
                    decision_id,
                ),
            ).get_snapshot(scope, read["resourceUseId"])
        except ResourceUseError as exc:
            raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND") from exc
        return {
            "schemaVersion": "governed-execution-read.v1",
            "identity": self._identity(identity),
            "invocation": read,
            "exactBinding": {
                "planId": exact["plan_id"],
                "planVersion": exact["plan_version"],
                "planDigest": exact["plan_digest"],
                "approvalId": exact["approval_id"],
                "assignmentId": exact["assignment_id"],
                "digitalEmployeeDefinitionId": exact["digital_employee_definition_id"],
                "digitalEmployeeDefinitionRevisionId": exact[
                    "digital_employee_definition_revision_id"
                ],
                "digitalEmployeeDefinitionDigest": exact[
                    "digital_employee_definition_digest"
                ],
                "digitalEmployeeInstanceId": exact["digital_employee_instance_id"],
                "skillId": exact["skill_id"],
                "skillRevisionId": exact["skill_revision_id"],
                "skillDigest": exact["skill_digest"],
                "operation": exact["operation"],
                "bindingId": exact["binding_id"],
                "bindingDigest": exact["binding_digest"],
                "executorId": exact["executor_id"],
                "executorRevision": exact["executor_revision"],
                "authorizationDecisionId": exact["authorization_decision_id"],
            },
            "resourceUse": {
                "snapshotId": resource.snapshot_id,
                "snapshotDigest": resource.digest,
                "resourceUseId": resource.resource_use_id,
                "highWater": resource.high_water,
                "state": resource.effective_state.value,
                "evidenceIds": list(resource.evidence_references),
                "measurementIds": list(resource.measurement_ids),
                "limitations": list(resource.limitation_codes),
                "conflicts": list(resource.conflicts),
            },
            "evidenceContentDisclosed": False,
            "businessOutcome": None,
        }

    def _invocation_exact(
        self, scope: ScopeIdentity, invocation_id: str
    ) -> dict[str, Any] | None:
        with self.skill.invocation_repository.pool.connection() as connection:
            row = connection.execute(
                """SELECT attempt_id,plan_id,plan_version,plan_digest,approval_id,
                assignment_id,digital_employee_definition_id,
                digital_employee_definition_revision_id,
                digital_employee_definition_digest,digital_employee_instance_id,
                skill_id,skill_revision_id,skill_digest,operation,binding_id,
                binding_digest,executor_id,executor_revision,
                authorization_decision_id
                FROM skill_invocation.invocations WHERE """
                "namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
                (scope.namespace, scope.security_domain, invocation_id),
            ).fetchone()
        return row

    def _attempt_has_invocation(self, scope: ScopeIdentity, attempt_id: str) -> bool:
        with self.skill.invocation_repository.pool.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM skill_invocation.invocations WHERE namespace=%s "
                "AND security_domain=%s AND attempt_id=%s LIMIT 1",
                (scope.namespace, scope.security_domain, attempt_id),
            ).fetchone()
        return row is not None

    def _skill_request(self, scope, decision_id, command, identity):
        attempt_id = str(identity.attempt.attempt_id)
        with self.skill.invocation_repository.pool.connection() as connection:
            binding = connection.execute(
                "SELECT definition_id,revision_id,digest FROM "
                "digital_employee_definition.execution_bindings WHERE namespace=%s "
                "AND security_domain=%s AND attempt_id=%s",
                (scope.namespace, scope.security_domain, attempt_id),
            ).fetchone()
            if binding is None:
                raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
            employee = connection.execute(
                "SELECT record FROM digital_employee_definition.revisions WHERE "
                "namespace=%s AND security_domain=%s AND definition_id=%s "
                "AND revision_id=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    binding["definition_id"],
                    binding["revision_id"],
                ),
            ).fetchone()
            skill = connection.execute(
                "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s "
                "AND security_domain=%s AND kind='skill' AND resource_id=%s",
                (scope.namespace, scope.security_domain, command.skillId),
            ).fetchone()
        if employee is None or skill is None:
            raise GovernedExecutionError("GOVERNED_EXECUTION_NOT_FOUND")
        exact_member = next(
            (
                item
                for item in employee["record"].get("members", ())
                if item.get("kind") == "SKILL"
                and item.get("resource_id") == command.skillId
                and item.get("revision_id") == command.skillRevisionId
                and item.get("digest") == command.skillDigest
            ),
            None,
        )
        record = skill["record"]
        revision = next(
            (
                item
                for item in record.get("revisions", ())
                if item.get("revisionId") == command.skillRevisionId
                and item.get("digest") == command.skillDigest
            ),
            None,
        )
        operation = (
            None
            if revision is None
            else next(
                (
                    item
                    for item in revision.get("content", {}).get("operations", ())
                    if item.get("name") == command.operation
                ),
                None,
            )
        )
        if (
            exact_member is None
            or revision is None
            or record.get("publishedRevisionId") != command.skillRevisionId
            or revision.get("state") != "PUBLISHED"
            or operation is None
        ):
            raise GovernedExecutionError("SKILL_INVOCATION_NOT_ELIGIBLE")
        try:
            policy_data = operation["sideEffectPolicy"]
            policy = SideEffectPolicy(
                policy_data["policyId"],
                policy_data["policyRevision"],
                policy_data["policyDigest"],
                SideEffectClass(operation["sideEffectClass"]),
            )
            limits_data = operation["ioLimits"]
            limits = SkillIOLimits(
                limits_data["policyId"],
                limits_data["policyRevision"],
                limits_data["maxInputBytes"],
                limits_data["maxOutputBytes"],
                limits_data["maxObjectDepth"],
                limits_data["maxProperties"],
                limits_data["timeoutMs"],
            )
            executor = ExecutorRevision(
                operation["executorId"],
                operation["executorRevision"],
                operation["executorConfigurationDigest"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GovernedExecutionError("SKILL_EXECUTION_POLICY_MISMATCH") from exc
        binding_id = stable_id(
            "skill-binding",
            binding["definition_id"],
            binding["revision_id"],
            command.skillId,
            command.skillRevisionId,
        )
        binding_digest = canonical_digest(
            {
                "bindingId": binding_id,
                "employeeDefinitionId": binding["definition_id"],
                "employeeRevisionId": binding["revision_id"],
                "skillId": command.skillId,
                "skillRevisionId": command.skillRevisionId,
                "skillDigest": command.skillDigest,
                "operation": command.operation,
            }
        )
        use_id = stable_id(
            "resource-use",
            scope.namespace,
            scope.security_domain,
            attempt_id,
            "SKILL",
            "skill:primary",
            "1",
        )
        resource_use = ResourceUseBinding(
            scope,
            use_id,
            attempt_id,
            ResourceKind.SKILL,
            "skill:primary",
            1,
            command.skillId,
            command.skillRevisionId,
            command.skillDigest,
            binding_id,
            binding_digest,
            command.planId,
            command.planVersion,
            command.planDigest,
            str(identity.workflow_run.workflow_run_id),
            str(identity.task_run.task_run_id),
            binding["definition_id"],
            binding["revision_id"],
            binding["digest"],
            command.digitalEmployeeInstanceId,
            None,
            None,
            executor.executor_id,
            executor.executor_revision,
            "managed-http-read-only",
            executor.executor_revision,
            decision_id,
            None,
            None,
        )
        return SkillInvocationRequest(
            scope,
            command.idempotencyKey,
            attempt_id,
            str(identity.workflow_run.workflow_run_id),
            str(identity.task_run.task_run_id),
            command.planId,
            command.planVersion,
            command.planDigest,
            command.approvalId,
            command.assignmentId,
            binding["definition_id"],
            binding["revision_id"],
            binding["digest"],
            command.digitalEmployeeInstanceId,
            None,
            None,
            command.skillId,
            command.skillRevisionId,
            command.skillDigest,
            command.operation,
            canonical_digest(operation["inputSchema"]),
            canonical_digest(operation["outputSchema"]),
            binding_id,
            binding_digest,
            executor,
            SideEffectClass.READ_ONLY,
            policy,
            limits,
            decision_id,
            resource_use,
        )

    @staticmethod
    def _identity(identity) -> dict[str, str]:
        return {
            "workflowRunId": str(identity.workflow_run.workflow_run_id),
            "taskRunId": str(identity.task_run.task_run_id),
            "attemptId": str(identity.attempt.attempt_id),
            "assignmentId": str(identity.assignment.assignment_id),
            "digitalEmployeeInstanceId": str(
                identity.assignment.digital_employee_instance_id
            ),
        }

    @classmethod
    def _projection(cls, identity, invocation) -> dict[str, Any]:
        return {
            "schemaVersion": "governed-execution-start.v1",
            "identity": cls._identity(identity),
            "invocation": invocation.canonical_read_model(),
            "executionStarted": True,
            "skillCallSucceeded": invocation.state is InvocationState.SUCCEEDED,
            "businessOutcome": None,
        }
