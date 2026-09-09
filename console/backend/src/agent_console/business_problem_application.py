"""Deterministic durable Product entry over independently authorized owner ports."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from .business_problem_authorization import (
    criteria_resource,
    criterion_resource,
    criterion_revision_resource,
    plan_resource,
    problem_resource,
    reference_grants,
)
from .business_problem_domain import (
    BusinessProblemConflict,
    BusinessProblemError,
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    PlanProblemBinding,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
    canonical_digest,
)
from .business_problem_schemas import PreparePlan
from .execution_domain import ScopeIdentity
from .planning import CanonicalWorkflowRevision, IntentRevision, TaskRequirement
from .workflow_control_domain import ApprovalDecision, PlanRecord, PlanStatus


class BusinessProblemApplication:
    def __init__(self, uow, authority, workflows, employees, instances):
        self.uow = uow
        self.problems = uow.problems
        self.control = uow.control
        self.authority = authority
        self.workflows = workflows
        self.employees = employees
        self.instances = instances

    @staticmethod
    def scope(principal):
        return ScopeIdentity(principal.tenant_id, principal.security_domain)

    def require(self, principal, owner, action, resource):
        return self.authority.require(principal, owner, action, resource)

    @staticmethod
    def identity(principal, command, key, target=""):
        return str(
            uuid5(
                NAMESPACE_URL,
                canonical_digest(
                    [
                        "business-entry.v1",
                        principal.tenant_id,
                        principal.security_domain,
                        principal.principal_id,
                        command,
                        key,
                        target,
                    ]
                ),
            )
        )

    @staticmethod
    def payload(command, target=""):
        return canonical_digest(
            {
                "schemaVersion": "business-entry-command.v1",
                "target": target,
                "request": command.model_dump(),
            }
        )

    def read_problem(self, principal, problem_id, *, connection=None):
        self.require(
            principal, "BUSINESS_PROBLEM", "READ", problem_resource(problem_id)
        )
        scope = self.scope(principal)
        with self.uow.transaction(connection) as connection:
            return {
                "problem": asdict(
                    self.problems.get_aggregate(
                        scope, problem_id, authorized=True, connection=connection
                    )
                ),
                "revisions": [
                    asdict(r)
                    for r in self.problems.get_problem(
                        scope, problem_id, authorized=True, connection=connection
                    )
                ],
                "lifecycle": [
                    asdict(r)
                    for r in self.problems.get_lifecycle(
                        scope, problem_id, authorized=True, connection=connection
                    )
                ],
            }

    def list_problems(self, principal, *, connection=None):
        self.require(principal, "BUSINESS_PROBLEM", "LIST", problem_resource())
        return {
            "problems": [
                asdict(r)
                for r in self.problems.list_problems(
                    self.scope(principal), authorized=True, connection=connection
                )
            ]
        }

    def create_problem(self, principal, command, *, connection=None):
        self.require(principal, "BUSINESS_PROBLEM", "CREATE", problem_resource())
        self.require(principal, "BUSINESS_PROBLEM", "READ", problem_resource())
        identity = self.identity(principal, "CREATE_PROBLEM", command.idempotencyKey)
        revision = BusinessProblemRevision(
            self.scope(principal),
            identity,
            f"{identity}:1",
            1,
            None,
            command.title,
            command.description,
            command.ownerId,
            principal.principal_id,
            datetime.now(UTC),
        )
        value = self.problems.create_problem(
            revision,
            idempotency_key=command.idempotencyKey,
            payload_digest=self.payload(command),
            authorized=True,
            connection=connection,
        )
        return {"revision": asdict(value)}

    def revise_problem(self, principal, problem_id, command, *, connection=None):
        self.require(
            principal, "BUSINESS_PROBLEM", "REVISE", problem_resource(problem_id)
        )
        self.require(
            principal, "BUSINESS_PROBLEM", "READ", problem_resource(problem_id)
        )
        scope = self.scope(principal)
        previous = next(
            (
                r
                for r in self.problems.get_problem(
                    scope, problem_id, authorized=True, connection=connection
                )
                if r.revision_id == command.predecessorRevisionId
            ),
            None,
        )
        if previous is None:
            raise BusinessProblemConflict("BUSINESS_PROBLEM_REVISION_STALE")
        value = BusinessProblemRevision(
            scope,
            problem_id,
            self.identity(
                principal, "REVISE_PROBLEM", command.idempotencyKey, problem_id
            ),
            previous.revision + 1,
            previous.revision_id,
            command.title,
            command.description,
            command.ownerId,
            principal.principal_id,
            datetime.now(UTC),
        )
        return {
            "revision": asdict(
                self.problems.add_problem_revision(
                    value,
                    expected_version=command.expectedVersion,
                    idempotency_key=command.idempotencyKey,
                    payload_digest=self.payload(command, problem_id),
                    authorized=True,
                    connection=connection,
                )
            )
        }

    def transition(self, principal, problem_id, command, *, connection=None):
        self.require(
            principal, "BUSINESS_PROBLEM", "TRANSITION", problem_resource(problem_id)
        )
        self.require(
            principal, "BUSINESS_PROBLEM", "READ", problem_resource(problem_id)
        )
        version = self.problems.transition(
            self.scope(principal),
            problem_id,
            BusinessProblemState(command.toState),
            actor_id=principal.principal_id,
            expected_version=command.expectedVersion,
            event_id=self.identity(
                principal, "TRANSITION", command.idempotencyKey, problem_id
            ),
            idempotency_key=command.idempotencyKey,
            payload_digest=self.payload(command, problem_id),
            authorized=True,
            connection=connection,
        )
        return {"businessProblemId": problem_id, "aggregateVersion": version}

    def criterion(self, principal, command, *, connection=None):
        revising = command.predecessorRevisionId is not None
        target = (
            criterion_resource(command.successCriterionId)
            if revising
            else criterion_resource()
        )
        self.require(
            principal, "SUCCESS_CRITERION", "REVISE" if revising else "CREATE", target
        )
        self.require(principal, "SUCCESS_CRITERION", "READ", target)
        scope = self.scope(principal)
        if revising:
            self.require(
                principal,
                "SUCCESS_CRITERION",
                "READ",
                criterion_revision_resource(command.predecessorRevisionId),
            )
            previous = self.problems.get_criterion_revision(
                scope,
                command.predecessorRevisionId,
                authorized=True,
                connection=connection,
            )
            if (
                previous.success_criterion_id != command.successCriterionId
                or command.expectedVersion is None
            ):
                raise BusinessProblemConflict("SUCCESS_CRITERION_IDENTITY_MISMATCH")
            identity, version = previous.success_criterion_id, previous.revision + 1
        else:
            if (
                command.successCriterionId is not None
                or command.expectedVersion is not None
            ):
                raise BusinessProblemConflict("SUCCESS_CRITERION_IDENTITY_MISMATCH")
            identity = self.identity(
                principal, "CREATE_CRITERION", command.idempotencyKey
            )
            version = 1
        revision = SuccessCriterionRevision(
            scope,
            identity,
            self.identity(principal, "CRITERION_REVISION", command.idempotencyKey),
            version,
            command.predecessorRevisionId,
            CriterionType(command.criterionType),
            command.measurement,
            tuple(command.requiredEvidenceKinds),
            command.evaluatorType,
            command.evaluatorVersion,
            command.applicability,
            principal.principal_id,
            datetime.now(UTC),
        )
        return {
            "revision": asdict(
                self.problems.add_criterion_revision(
                    revision,
                    expected_version=command.expectedVersion,
                    idempotency_key=command.idempotencyKey,
                    payload_digest=self.payload(command),
                    authorized=True,
                    connection=connection,
                )
            )
        }

    def read_criterion(self, principal, revision_id, *, connection=None):
        self.require(
            principal,
            "SUCCESS_CRITERION",
            "READ",
            criterion_revision_resource(revision_id),
        )
        return {
            "revision": asdict(
                self.problems.get_criterion_revision(
                    self.scope(principal),
                    revision_id,
                    authorized=True,
                    connection=connection,
                )
            )
        }

    def criteria_set(self, principal, problem_id, command, *, connection=None):
        action = "REVISE" if command.predecessorSetRevisionId else "CREATE"
        self.require(
            principal, "SUCCESS_CRITERIA_SET", action, criteria_resource(problem_id)
        )
        self.require(
            principal, "SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)
        )
        self.require(
            principal, "BUSINESS_PROBLEM", "READ", problem_resource(problem_id)
        )
        for identity in command.orderedCriterionRevisionIds:
            self.require(
                principal,
                "SUCCESS_CRITERION",
                "READ",
                criterion_revision_resource(identity),
            )
        scope = self.scope(principal)
        with self.uow.transaction(connection) as connection:
            revisions = self.problems.get_problem(
                scope, problem_id, authorized=True, connection=connection
            )
            if command.problemRevisionId not in {r.revision_id for r in revisions}:
                raise BusinessProblemConflict("PLAN_PROBLEM_BINDING_MISMATCH")
            sets = self.problems.list_criteria_set_revisions(
                scope, problem_id, authorized=True, connection=connection
            )
            predecessor = next(
                (
                    r
                    for r in sets
                    if r.set_revision_id == command.predecessorSetRevisionId
                ),
                None,
            )
            if command.predecessorSetRevisionId and predecessor is None:
                raise BusinessProblemConflict("CRITERIA_SET_PREDECESSOR_MISMATCH")
            revision = SuccessCriteriaSetRevision(
                scope,
                self.identity(
                    principal, "CRITERIA_SET", command.idempotencyKey, problem_id
                ),
                problem_id,
                command.problemRevisionId,
                1 if predecessor is None else predecessor.revision + 1,
                command.predecessorSetRevisionId,
                tuple(command.orderedCriterionRevisionIds),
                principal.principal_id,
                datetime.now(UTC),
            )
            value = self.problems.add_criteria_set_revision(
                revision,
                expected_version=command.expectedVersion,
                idempotency_key=command.idempotencyKey,
                payload_digest=self.payload(command, problem_id),
                authorized=True,
                connection=connection,
            )
        return {"revision": asdict(value)}

    def read_sets(self, principal, problem_id, *, connection=None):
        self.require(
            principal, "SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)
        )
        return {
            "revisions": [
                asdict(r)
                for r in self.problems.list_criteria_set_revisions(
                    self.scope(principal),
                    problem_id,
                    authorized=True,
                    connection=connection,
                )
            ]
        }

    def read_criteria(self, principal, problem_id, *, connection=None):
        self.require(
            principal, "SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)
        )
        self.require(
            principal, "BUSINESS_PROBLEM", "READ", problem_resource(problem_id)
        )
        scope = self.scope(principal)
        with self.uow.transaction(connection) as connection:
            self.problems.get_aggregate(
                scope, problem_id, authorized=True, connection=connection
            )
            sets = self.problems.list_criteria_set_revisions(
                scope, problem_id, authorized=True, connection=connection
            )
            for identity in {
                i for row in sets for i in row.ordered_criterion_revision_ids
            }:
                self.require(
                    principal,
                    "SUCCESS_CRITERION",
                    "READ",
                    criterion_revision_resource(identity),
                )
            return {
                "revisions": [
                    asdict(row)
                    for row in self.problems.list_criterion_revisions(
                        scope, problem_id, authorized=True, connection=connection
                    )
                ]
            }

    def _authorize_plan(self, principal, problem_id, command, *, connection=None):
        self.require(
            principal, "BUSINESS_PROBLEM", "READ", problem_resource(problem_id)
        )
        self.require(
            principal, "SUCCESS_CRITERIA_SET", "READ", criteria_resource(problem_id)
        )
        for grant in reference_grants(command):
            self.require(principal, *grant)
        # Set read grants membership disclosure; each member has its own read grant.
        criteria = self.problems.get_criteria_set_revision(
            self.scope(principal),
            command.criteriaSetRevisionId,
            authorized=True,
            business_problem_id=problem_id,
            connection=connection,
        )
        if criteria.business_problem_id != problem_id:
            raise BusinessProblemError("BUSINESS_PROBLEM_NOT_FOUND")
        for identity in criteria.ordered_criterion_revision_ids:
            self.require(
                principal,
                "SUCCESS_CRITERION",
                "READ",
                criterion_revision_resource(identity),
            )

    def _resources(self, connection, scope, command):
        workflow = self.workflows.read_for_plan(
            connection,
            scope,
            command.workflowDefinitionId,
            command.workflowDefinitionRevisionId,
            command.workflowDefinitionDigest,
            authorized=True,
        )
        employee = self.employees.read_for_plan(
            connection,
            scope,
            command.employeeDefinitionId,
            command.employeeDefinitionRevisionId,
            command.employeeDefinitionDigest,
            authorized=True,
        )
        members = employee["revision"]["members"]
        required = [
            (
                "WORKFLOW",
                command.workflowDefinitionId,
                command.workflowDefinitionRevisionId,
                command.workflowDefinitionDigest,
            )
        ]
        for task in workflow["content"]["tasks"]:
            for binding in task.get("skillOperationBindings", ()):
                required.append(
                    (
                        "SKILL",
                        binding["skillId"],
                        binding["skillRevisionId"],
                        binding["skillDigest"],
                    )
                )
        for kind, identity, revision, digest in required:
            if not any(
                m["kind"] == kind
                and m["resource_id"] == identity
                and m["revision_id"] == revision
                and m["digest"].removeprefix("sha256:")
                == digest.removeprefix("sha256:")
                for m in members
            ):
                raise BusinessProblemConflict("EMPLOYEE_PLAN_BINDING_MISMATCH")
        self.instances.validate_plan_identity(
            connection,
            scope,
            command.digitalEmployeeInstanceId,
            command.assignmentId,
            command.employeeDefinitionId,
            command.employeeDefinitionRevisionId,
            command.employeeDefinitionDigest,
            authorized=True,
        )
        return workflow

    @staticmethod
    def _binding(scope, problem_id, command, plan_id, plan_digest, actor):
        return PlanProblemBinding(
            scope,
            f"{plan_id}:problem",
            plan_id,
            1,
            plan_digest,
            problem_id,
            command.problemRevisionId,
            command.problemRevisionDigest,
            command.criteriaSetRevisionId,
            command.criteriaSetDigest,
            actor,
            datetime.now(UTC),
        )

    def prepare(self, principal, problem_id, command, *, connection=None):
        self.require(principal, "PLAN", "PREPARE", f"plan:prepare:{problem_id}")
        self.require(principal, "PLAN", "READ", f"plan:prepared:{problem_id}")
        caller_owned = connection is not None
        if not caller_owned:
            # Preserve the existing private Bearer route's transaction order.
            self._authorize_plan(principal, problem_id, command)
        scope = self.scope(principal)
        digest = self.payload(command, problem_id)
        with self.uow.transaction(connection) as connection:
            if caller_owned:
                self._authorize_plan(
                    principal, problem_id, command, connection=connection
                )
            replay = self.control.claim_plan_entry(
                connection,
                scope,
                principal.principal_id,
                "PLAN_ENTRY_PREPARE_V1",
                command.idempotencyKey,
                digest,
                authorized=True,
            )
            if replay:
                return self._read_plan(
                    connection,
                    scope,
                    replay["planId"],
                    replay["planVersion"],
                    replayed=True,
                )
            workflow = self._resources(connection, scope, command)
            plan_id = self.identity(
                principal, "PREPARE_PLAN", command.idempotencyKey, problem_id
            )
            approval_id = f"{plan_id}:approval"
            content = workflow["content"]
            target = self._binding(
                scope, problem_id, command, plan_id, "0" * 64, principal.principal_id
            )
            problem, _ = self.problems.validate_plan_target(
                connection, target, command.expectedProblemVersion, authorized=True
            )
            intent = IntentRevision(
                problem_id,
                command.problemRevisionId,
                problem.revision,
                problem.predecessor_revision_id,
                "explicit-plan.v1",
                "explicit-plan.v1",
                problem_id,
                "Explicit business plan",
                (),
                (command.criteriaSetDigest,),
                command.problemRevisionDigest,
            )
            tasks = tuple(
                TaskRequirement(
                    f"{plan_id}:{task['taskId']}",
                    task["taskId"],
                    command.problemRevisionId,
                    "EXPLICIT",
                    task["name"],
                    tuple(task.get("inputs", ())),
                    tuple(task.get("outputs", ())),
                    tuple(task.get("dependsOn", ())),
                    tuple(task.get("capabilityRequirements", ())),
                    (command.criteriaSetDigest,),
                    "LOW",
                    "REQUIRED",
                    (),
                    ordinal,
                )
                for ordinal, task in enumerate(content["tasks"])
            )
            from .workflow_definition_service import WorkflowDefinitionService

            order = tuple(WorkflowDefinitionService._stable_order(content["tasks"]))
            canonical = CanonicalWorkflowRevision(
                command.workflowDefinitionRevisionId,
                1,
                None,
                scope.namespace,
                scope.security_domain,
                command.workflowDefinitionDigest.removeprefix("sha256:"),
                approval_id,
                "explicit-plan.v1",
                intent,
                tasks,
                order,
                (),
                True,
            )
            from .execution_application import execution_plan_bytes

            raw = execution_plan_bytes(
                canonical,
                command.assignmentId,
                command.digitalEmployeeInstanceId,
                business_problem_id=problem_id,
                preparation=command.model_dump(exclude={"idempotencyKey"}),
            )

            import hashlib

            plan_digest = hashlib.sha256(raw).hexdigest()
            now = datetime.now(UTC)
            plan = PlanRecord(
                scope,
                plan_id,
                1,
                command.workflowDefinitionId,
                command.workflowDefinitionRevisionId,
                command.workflowDefinitionDigest.removeprefix("sha256:"),
                PlanStatus.PENDING_APPROVAL,
                1,
                plan_digest,
                raw,
                now,
                now,
            )
            binding = self._binding(
                scope, problem_id, command, plan_id, plan_digest, principal.principal_id
            )
            self.control.prepare_plan_entry(connection, plan, authorized=True)
            self.problems.bind_prepared_plan(
                connection,
                binding,
                expected_problem_version=command.expectedProblemVersion,
                idempotency_key=f"plan-entry:{plan_id}",
                payload_digest=canonical_digest(
                    {
                        "binding": binding.digest_contract(),
                        "expectedProblemVersion": command.expectedProblemVersion,
                    }
                ),
                authorized=True,
            )
            self.control.complete_plan_entry(
                connection,
                scope,
                principal.principal_id,
                "PLAN_ENTRY_PREPARE_V1",
                command.idempotencyKey,
                digest,
                {"planId": plan_id, "planVersion": 1, "bindingId": binding.binding_id},
                authorized=True,
            )
            return self._read_plan(connection, scope, plan_id, 1)

    def approve(self, principal, plan_id, command, *, connection=None):
        decision_basis = self.require(
            principal, "PLAN", "APPROVE", plan_resource(plan_id, command.planVersion)
        )
        self.require(
            principal, "PLAN", "READ", plan_resource(plan_id, command.planVersion)
        )
        scope = self.scope(principal)
        # Plan read permission precedes discovering the bound Problem identity.
        caller_owned = connection is not None
        if not caller_owned:
            plan = self.control.get_plan(scope, plan_id, command.planVersion)
            if plan is None:
                raise BusinessProblemError("PLAN_NOT_FOUND")
            envelope = json.loads(plan.canonical_bytes)
            problem_id = envelope.get("businessProblemId")
            if not problem_id or envelope.get("preparation") != command.model_dump(
                include=set(PreparePlan.model_fields) - {"idempotencyKey"}
            ):
                raise BusinessProblemConflict("PLAN_PREPARATION_MISMATCH")
            self._authorize_plan(principal, problem_id, command)
        digest = self.payload(command, plan_id)
        with self.uow.transaction(connection) as connection:
            if caller_owned:
                plan = self.control.get_plan(
                    scope, plan_id, command.planVersion, connection=connection
                )
                if plan is None:
                    raise BusinessProblemError("PLAN_NOT_FOUND")
                envelope = json.loads(plan.canonical_bytes)
                problem_id = envelope.get("businessProblemId")
                if not problem_id or envelope.get("preparation") != command.model_dump(
                    include=set(PreparePlan.model_fields) - {"idempotencyKey"}
                ):
                    raise BusinessProblemConflict("PLAN_PREPARATION_MISMATCH")
                self._authorize_plan(
                    principal, problem_id, command, connection=connection
                )
            replay = self.control.claim_plan_entry(
                connection,
                scope,
                principal.principal_id,
                "PLAN_ENTRY_APPROVE_V1",
                command.idempotencyKey,
                digest,
                authorized=True,
            )
            if replay:
                return self._read_plan(
                    connection,
                    scope,
                    replay["planId"],
                    replay["planVersion"],
                    replayed=True,
                )
            if plan.plan_digest != command.planDigest:
                raise BusinessProblemConflict("PLAN_DIGEST_MISMATCH")
            self._resources(connection, scope, command)
            binding = self.problems.get_plan_binding(
                scope, f"{plan_id}:problem", authorized=True, connection=connection
            )
            self.problems.validate_approval_binding(
                connection,
                binding,
                expected_problem_version=command.expectedProblemVersion,
                authorized=True,
            )
            approval_id = envelope["workflow"]["approval_id"]
            decision = ApprovalDecision(
                approval_id,
                plan_id,
                command.planVersion,
                command.planDigest,
                1,
                command.decision,
                principal.principal_id,
                "HUMAN_REVIEW",
                command.reasonCategory,
                canonical_digest(
                    {"request": digest, "authority": decision_basis.decision_id}
                ),
                datetime.now(UTC),
            )
            self.control.approve_plan_entry(
                connection,
                scope,
                decision,
                expected_version=command.expectedVersion,
                authorized=True,
            )
            self.control.complete_plan_entry(
                connection,
                scope,
                principal.principal_id,
                "PLAN_ENTRY_APPROVE_V1",
                command.idempotencyKey,
                digest,
                {
                    "planId": plan_id,
                    "planVersion": command.planVersion,
                    "approvalId": approval_id,
                },
                authorized=True,
            )
            return self._read_plan(connection, scope, plan_id, command.planVersion)

    def read_plan(self, principal, plan_id, version, *, connection=None):
        self.require(principal, "PLAN", "READ", plan_resource(plan_id, version))
        with self.uow.transaction(connection) as connection:
            return self._read_plan(connection, self.scope(principal), plan_id, version)

    def _read_plan(self, connection, scope, plan_id, version, replayed=False):
        plan = self.control.get_plan(scope, plan_id, version, connection=connection)
        if plan is None:
            raise BusinessProblemError("PLAN_NOT_FOUND")
        approvals = self.control.read_approvals(
            scope, plan_id, version, connection=connection
        )
        return {
            "planId": plan_id,
            "planVersion": version,
            "planDigest": plan.plan_digest,
            "aggregateVersion": plan.aggregate_version,
            "status": plan.status.value,
            "content": json.loads(plan.canonical_bytes),
            "approvals": [asdict(d) for d in approvals],
            "replayed": replayed,
        }
