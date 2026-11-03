"""Approval-gated application services for durable execution authority.

The services in this module assemble existing planning and execution contracts.
They deliberately own no route, provider, Kubernetes, or Runtime side effect.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from .execution_evidence_import import ExecutionEvidenceRecord
from .execution_postgres import (
    AppendDisposition,
    AssignmentId,
    AssignmentIdentity,
    AttemptId,
    AttemptIdentity,
    DigitalEmployeeInstanceId,
    ExecutionIdentityAggregate,
    NativeDispatchClaim,
    NativeTerminalKind,
    NativeTerminalObservation,
    ScopeIdentity,
    TaskRunId,
    TaskRunIdentity,
    WorkflowRunId,
    WorkflowRunIdentity,
    canonical_bytes,
)
from .planning import CanonicalWorkflowRevision, PlanningState


class ExecutionIdentityRepository(Protocol):
    def save(
        self,
        scope: ScopeIdentity,
        aggregate: ExecutionIdentityAggregate,
        *,
        approved_plan: ApprovedPlanIdentity | None = None,
        plan: CanonicalWorkflowRevision | None = None,
        task_id: str | None = None,
        authorization_decision_id: str,
        request_claim: ExecutionRequestClaim | None = None,
    ) -> ExecutionIdentityAggregate: ...

    def get_attempt(
        self, scope: ScopeIdentity, attempt_id: AttemptId
    ) -> ExecutionIdentityAggregate | None: ...


class ExecutionApplicationError(ValueError):
    """Disclosure-safe rejection raised before a persistence or effect port call."""


class OutcomeWriter(Protocol):
    def append_outcome(
        self,
        scope: ScopeIdentity,
        outcome_id: str,
        workflow_run_id: str,
        record: dict[str, object],
    ) -> AppendDisposition: ...


class CompletionWriter(Protocol):
    def append_completion(
        self,
        scope: ScopeIdentity,
        evidence: tuple[ExecutionEvidenceRecord, ...],
        outcome_id: str,
        workflow_run_id: str,
        outcome: dict[str, object],
    ) -> AppendDisposition: ...


@dataclass(frozen=True, slots=True)
class ApprovedPlanIdentity:
    revision_id: str
    digest: str
    approval_id: str
    plan_id: str | None = None
    plan_version: int | None = None
    plan_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRequestClaim:
    principal_id: str
    idempotency_key: str
    request_digest: str


@dataclass(frozen=True, slots=True)
class StartExecutionCommand:
    scope: ScopeIdentity
    plan: CanonicalWorkflowRevision
    approved_plan: ApprovedPlanIdentity
    assignment_id: AssignmentId
    digital_employee_instance_id: DigitalEmployeeInstanceId
    task_id: str
    replay_identity: str
    predecessor_workflow_run_id: WorkflowRunId | None = None
    correction_of_workflow_run_id: WorkflowRunId | None = None
    request_claim: ExecutionRequestClaim | None = None


@dataclass(frozen=True, slots=True)
class StartExecutionResult:
    disposition: AppendDisposition
    identity: ExecutionIdentityAggregate


@dataclass(frozen=True, slots=True)
class RetryExecutionCommand:
    scope: ScopeIdentity
    previous_attempt_id: AttemptId
    replay_identity: str


@dataclass(frozen=True, slots=True)
class RetryExecutionResult:
    disposition: AppendDisposition
    identity: ExecutionIdentityAggregate


@dataclass(frozen=True, slots=True)
class RecordOutcomeCommand:
    scope: ScopeIdentity
    attempt_id: AttemptId
    outcome_id: str
    record: dict[str, object]


@dataclass(frozen=True, slots=True)
class RecordOutcomeResult:
    disposition: AppendDisposition
    identity: ExecutionIdentityAggregate


@dataclass(frozen=True, slots=True)
class RecordCompletionCommand:
    scope: ScopeIdentity
    attempt_id: AttemptId
    evidence: tuple[ExecutionEvidenceRecord, ...]
    outcome_id: str
    outcome: dict[str, object]


@dataclass(frozen=True, slots=True)
class RecordNativeCompletionCommand:
    claim: NativeDispatchClaim
    observation: NativeTerminalObservation
    evidence: tuple[ExecutionEvidenceRecord, ...]
    outcome_id: str
    outcome: dict[str, object]


def _stable_id(kind: str, *parts: str) -> str:
    if not parts or any(not isinstance(part, str) or not part for part in parts):
        raise ExecutionApplicationError("INVALID_REPLAY_IDENTITY")
    digest = hashlib.sha256("\x00".join(parts).encode()).hexdigest()
    return f"{kind}:{digest}"


def _assert_exact_approval(command: StartExecutionCommand) -> None:
    plan = command.plan
    approved = command.approved_plan
    if not isinstance(plan, CanonicalWorkflowRevision):
        raise ExecutionApplicationError("APPROVED_PLAN_REQUIRED")
    if plan.lifecycle is not PlanningState.CANONICALIZED or not plan.matching_eligible:
        raise ExecutionApplicationError("PLAN_NOT_APPROVED")
    if command.scope.namespace != plan.tenant_id:
        raise ExecutionApplicationError("TENANT_SCOPE_MISMATCH")
    if command.scope.security_domain != plan.security_domain:
        raise ExecutionApplicationError("SECURITY_DOMAIN_SCOPE_MISMATCH")
    if not isinstance(approved, ApprovedPlanIdentity):
        raise ExecutionApplicationError("APPROVED_PLAN_IDENTITY_REQUIRED")
    if approved.revision_id != plan.canonical_workflow_revision_id:
        raise ExecutionApplicationError("PLAN_REVISION_MISMATCH")
    if approved.digest != plan.approved_candidate_digest:
        raise ExecutionApplicationError("PLAN_DIGEST_MISMATCH")
    if approved.approval_id != plan.approval_id:
        raise ExecutionApplicationError("PLAN_APPROVAL_MISMATCH")
    if command.task_id not in plan.ordered_task_ids:
        raise ExecutionApplicationError("PLAN_TASK_MISMATCH")
    if command.correction_of_workflow_run_id is not None and (
        command.predecessor_workflow_run_id != command.correction_of_workflow_run_id
        or plan.predecessor_revision_id is None
    ):
        raise ExecutionApplicationError("CORRECTION_BINDING_MISMATCH")


class ExecutionAuthorization(Protocol):
    def require(self, scope: ScopeIdentity, action: str, identity: str) -> str:
        """Authorize before lookup; return a trusted audit decision ID."""
        ...


@dataclass(frozen=True)
class ScopedExecutionAuthorization:
    """Authenticated internal context, never accepted from a request DTO."""

    scope: ScopeIdentity
    actor_id: str
    permissions: frozenset[str]
    decision_id: str

    def require(self, scope, action, identity):
        if (
            scope != self.scope
            or action not in self.permissions
            or not self.actor_id
            or not self.decision_id
        ):
            raise ExecutionApplicationError("EXECUTION_NOT_FOUND")
        return self.decision_id


def execution_plan_bytes(
    plan, assignment_id, instance_id, *, business_problem_id=None, preparation=None
):
    """New Plan content submitted to the existing Workflow Control approval owner.

    Candidate approval and durable Plan approval retain independent digests.
    Historical Plan content is never inferred or rewritten into this envelope.
    """
    additional = (
        {}
        if business_problem_id is None
        else {
            "businessProblemId": business_problem_id,
            "preparation": preparation,
        }
    )
    return json.dumps(
        {
            **additional,
            "schemaVersion": "employee-execution-plan.v1"
            if not additional
            else "employee-execution-plan.v2",
            "workflow": asdict(plan),
            "assignmentId": str(assignment_id),
            "instanceId": str(instance_id),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


class ExecutionApplicationService:
    """Create and read durable execution identities after exact Plan approval."""

    def __init__(
        self,
        identities: ExecutionIdentityRepository,
        authorization: ExecutionAuthorization | None = None,
    ) -> None:
        self._identities = identities
        self._authorization = authorization

    def _authorize(self, scope, action, identity):
        if self._authorization is None:
            raise ExecutionApplicationError("EXECUTION_NOT_FOUND")
        decision = self._authorization.require(scope, action, str(identity))
        if not decision:
            raise ExecutionApplicationError("EXECUTION_NOT_FOUND")
        return decision

    def start(
        self,
        command: StartExecutionCommand,
    ) -> StartExecutionResult:
        authorization_decision_id = self._authorize(
            command.scope, "START", command.assignment_id
        )
        _assert_exact_approval(command)
        seed = (
            command.scope.namespace,
            command.scope.security_domain,
            command.approved_plan.revision_id,
            command.approved_plan.digest,
            command.approved_plan.approval_id,
            str(command.assignment_id),
            command.task_id,
            command.replay_identity,
        )
        workflow = WorkflowRunIdentity(
            WorkflowRunId(_stable_id("workflow-run", *seed)),
            command.assignment_id,
            command.approved_plan.revision_id,
            command.predecessor_workflow_run_id,
            command.correction_of_workflow_run_id,
        )
        task = TaskRunIdentity(
            TaskRunId(
                _stable_id("task-run", str(workflow.workflow_run_id), command.task_id)
            ),
            workflow.workflow_run_id,
        )
        attempt = AttemptIdentity(
            AttemptId(_stable_id("attempt", str(task.task_run_id), "1")),
            task.task_run_id,
        )
        aggregate = ExecutionIdentityAggregate(
            command.scope,
            AssignmentIdentity(
                command.assignment_id, command.digital_employee_instance_id
            ),
            workflow,
            task,
            attempt,
        )
        existing = self._identities.get_attempt(command.scope, attempt.attempt_id)
        if existing is not None and existing != aggregate:
            raise ExecutionApplicationError("EXECUTION_REPLAY_CONFLICT")
        return StartExecutionResult(
            AppendDisposition.REPLAYED
            if existing is not None
            else AppendDisposition.APPENDED,
            self._identities.save(
                command.scope,
                aggregate,
                approved_plan=command.approved_plan,
                plan=command.plan,
                task_id=command.task_id,
                authorization_decision_id=authorization_decision_id,
                request_claim=command.request_claim,
            ),
        )

    def retry(
        self,
        command: RetryExecutionCommand,
    ) -> RetryExecutionResult:
        authorization_decision_id = self._authorize(
            command.scope, "RETRY", command.previous_attempt_id
        )
        previous = self._identities.get_attempt(
            command.scope, command.previous_attempt_id
        )
        if previous is None:
            raise ExecutionApplicationError("PREVIOUS_ATTEMPT_NOT_FOUND")
        attempt = AttemptIdentity(
            AttemptId(
                _stable_id(
                    "attempt",
                    str(previous.task_run.task_run_id),
                    str(previous.attempt.attempt_id),
                    command.replay_identity,
                )
            ),
            previous.task_run.task_run_id,
            previous.attempt.attempt_id,
        )
        aggregate = ExecutionIdentityAggregate(
            previous.scope,
            previous.assignment,
            previous.workflow_run,
            previous.task_run,
            attempt,
        )
        existing = self._identities.get_attempt(command.scope, attempt.attempt_id)
        if existing is not None and existing != aggregate:
            raise ExecutionApplicationError("EXECUTION_REPLAY_CONFLICT")
        return RetryExecutionResult(
            AppendDisposition.REPLAYED
            if existing is not None
            else AppendDisposition.APPENDED,
            self._identities.save(
                command.scope,
                aggregate,
                authorization_decision_id=authorization_decision_id,
            ),
        )

    def read_attempt(
        self, scope: ScopeIdentity, attempt_id: AttemptId
    ) -> ExecutionIdentityAggregate | None:
        return self._identities.get_attempt(scope, attempt_id)


class ExecutionOutcomeService:
    """Append an immutable Outcome only for an existing scoped Attempt."""

    def __init__(
        self, identities: ExecutionIdentityRepository, outcomes: OutcomeWriter
    ) -> None:
        self._identities = identities
        self._outcomes = outcomes

    def record(self, command: RecordOutcomeCommand) -> RecordOutcomeResult:
        identity = self._identities.get_attempt(command.scope, command.attempt_id)
        if identity is None:
            raise ExecutionApplicationError("ATTEMPT_NOT_FOUND")
        required = {
            "outcome_id": command.outcome_id,
            "workflow_run_id": str(identity.workflow_run.workflow_run_id),
            "task_run_id": str(identity.task_run.task_run_id),
            "attempt_id": str(identity.attempt.attempt_id),
            "approved_plan_revision_id": (
                identity.workflow_run.approved_plan_revision_id
            ),
        }
        if any(command.record.get(key) != value for key, value in required.items()):
            raise ExecutionApplicationError("OUTCOME_IDENTITY_MISMATCH")
        disposition = self._outcomes.append_outcome(
            command.scope,
            command.outcome_id,
            str(identity.workflow_run.workflow_run_id),
            dict(command.record),
        )
        return RecordOutcomeResult(disposition, identity)


class ExecutionCompletionService:
    """Atomically append ordered Event/Evidence facts and their Outcome."""

    def __init__(
        self, identities: ExecutionIdentityRepository, writer: CompletionWriter
    ) -> None:
        self._identities = identities
        self._writer = writer

    def record(self, command: RecordCompletionCommand) -> RecordOutcomeResult:
        identity = self._identities.get_attempt(command.scope, command.attempt_id)
        if identity is None:
            raise ExecutionApplicationError("ATTEMPT_NOT_FOUND")
        expected = (
            command.scope.namespace,
            command.scope.security_domain,
            str(identity.workflow_run.workflow_run_id),
            str(identity.task_run.task_run_id),
            str(identity.attempt.attempt_id),
        )
        if not command.evidence:
            raise ExecutionApplicationError("EXECUTION_EVIDENCE_REQUIRED")
        ordered = tuple(
            sorted(
                command.evidence,
                key=lambda item: (item.attempt_ordinal, item.event_ordinal),
            )
        )
        if ordered != command.evidence:
            raise ExecutionApplicationError("EVIDENCE_ORDER_INVALID")
        if any(
            (
                item.namespace,
                item.security_domain,
                item.workflow_identity,
                item.task_identity,
                item.platform_execution_identity,
            )
            != expected
            for item in ordered
        ):
            raise ExecutionApplicationError("EVIDENCE_IDENTITY_MISMATCH")
        required = {
            "outcome_id": command.outcome_id,
            "workflow_run_id": expected[2],
            "task_run_id": expected[3],
            "attempt_id": expected[4],
            "approved_plan_revision_id": (
                identity.workflow_run.approved_plan_revision_id
            ),
            "evidence_ids": [item.evidence_record_id for item in ordered],
        }
        if any(command.outcome.get(key) != value for key, value in required.items()):
            raise ExecutionApplicationError("OUTCOME_IDENTITY_MISMATCH")
        disposition = self._writer.append_completion(
            command.scope,
            ordered,
            command.outcome_id,
            expected[2],
            dict(command.outcome),
        )
        return RecordOutcomeResult(disposition, identity)

    def record_native(
        self, command: RecordNativeCompletionCommand
    ) -> RecordOutcomeResult:
        claim = command.claim
        observation = command.observation
        if observation.kind not in {
            NativeTerminalKind.SUCCEEDED,
            NativeTerminalKind.FAILED,
        }:
            raise ExecutionApplicationError("AUTHORITATIVE_TERMINAL_REQUIRED")
        if observation.command_id != claim.command.command_id:
            raise ExecutionApplicationError("TERMINAL_COMMAND_MISMATCH")
        identity = self._identities.get_attempt(
            claim.command.scope, claim.command.attempt_id
        )
        if identity is None:
            raise ExecutionApplicationError("ATTEMPT_NOT_FOUND")
        expected = (
            claim.command.scope.namespace,
            claim.command.scope.security_domain,
            str(identity.workflow_run.workflow_run_id),
            str(identity.task_run.task_run_id),
            str(identity.attempt.attempt_id),
        )
        if not command.evidence or any(
            (
                item.namespace,
                item.security_domain,
                item.workflow_identity,
                item.task_identity,
                item.platform_execution_identity,
            )
            != expected
            for item in command.evidence
        ):
            raise ExecutionApplicationError("EVIDENCE_IDENTITY_MISMATCH")
        required = {
            "outcome_id": command.outcome_id,
            "workflow_run_id": expected[2],
            "task_run_id": expected[3],
            "attempt_id": expected[4],
            "approved_plan_revision_id": claim.command.approved_plan_revision_id,
            "evidence_ids": [item.evidence_record_id for item in command.evidence],
            "classification": observation.kind.value,
            "technical": True,
        }
        if any(command.outcome.get(key) != value for key, value in required.items()):
            raise ExecutionApplicationError("OUTCOME_IDENTITY_MISMATCH")
        writer = getattr(self._writer, "append_native_completion", None)
        if writer is None:
            raise ExecutionApplicationError("NATIVE_COMPLETION_WRITER_REQUIRED")
        disposition = writer(
            claim,
            observation,
            command.evidence,
            command.outcome_id,
            expected[2],
            dict(command.outcome),
        )
        return RecordOutcomeResult(disposition, identity)


class PostgresExecutionCompletionWriter:
    """Feature-local atomic writer over the existing migration-0008 authority."""

    def __init__(
        self,
        execution_repository: object,
        *,
        checkpoint: Callable[[str], None] = lambda _name: None,
    ) -> None:
        pool = getattr(execution_repository, "pool", None)
        if pool is None:
            raise ExecutionApplicationError("POSTGRES_EXECUTION_REPOSITORY_REQUIRED")
        self._pool = pool
        self._checkpoint = checkpoint

    @staticmethod
    def _append_evidence(connection, scope, item) -> bool:
        canonical = json.dumps(
            dict(item.canonical_payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        row = connection.execute(
            """INSERT INTO execution_authority.execution_evidence
            (evidence_record_id,schema_version,namespace,security_domain,
            platform_execution_identity,workflow_identity,task_identity,
            attempt_ordinal,event_ordinal,event_type,occurred_at,recorded_at,
            payload_digest,canonical_bytes,record,supersedes_record_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s,%s::jsonb,%s)
            ON CONFLICT (evidence_record_id) DO NOTHING RETURNING storage_sequence""",
            (
                item.evidence_record_id,
                item.schema_version,
                scope.namespace,
                scope.security_domain,
                item.platform_execution_identity,
                item.workflow_identity,
                item.task_identity,
                item.attempt_ordinal,
                item.event_ordinal,
                item.event_type.value,
                item.occurred_at,
                item.payload_digest,
                canonical,
                json.dumps(dict(item.canonical_payload)),
                item.supersedes_record_id,
            ),
        ).fetchone()
        if row is not None:
            return True
        stored = connection.execute(
            "SELECT payload_digest,canonical_bytes FROM "
            "execution_authority.execution_evidence WHERE evidence_record_id=%s",
            (item.evidence_record_id,),
        ).fetchone()
        if (
            stored is None
            or stored["payload_digest"] != item.payload_digest
            or bytes(stored["canonical_bytes"]) != canonical
        ):
            raise ExecutionApplicationError("EVIDENCE_DIGEST_CONFLICT")
        return False

    def append_native_completion(
        self,
        claim: NativeDispatchClaim,
        observation: NativeTerminalObservation,
        evidence: tuple[ExecutionEvidenceRecord, ...],
        outcome_id: str,
        workflow_run_id: str,
        outcome: dict[str, object],
    ) -> AppendDisposition:
        scope = claim.command.scope
        outcome_digest = hashlib.sha256(
            json.dumps(outcome, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        replayed = True
        with self._pool.connection() as connection, connection.transaction():
            row = connection.execute(
                "SELECT state,claim_generation,fencing_token,worker_id,"
                "kubernetes_task_name,kubernetes_task_uid,"
                "terminal_observation_digest FROM "
                "execution_authority.native_dispatch_commands WHERE namespace=%s "
                "AND security_domain=%s AND command_id=%s FOR UPDATE",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(claim.command.command_id),
                ),
            ).fetchone()
            if (
                row is None
                or row["claim_generation"] != claim.claim_generation.value
                or row["fencing_token"] != claim.fencing_token
                or row["worker_id"] != claim.worker_id
                or row["kubernetes_task_name"] != observation.kubernetes_task_name
                or row["kubernetes_task_uid"] != observation.kubernetes_task_uid
            ):
                raise ExecutionApplicationError("NATIVE_DISPATCH_CLAIM_STALE")
            if row["terminal_observation_digest"] is not None:
                if row["terminal_observation_digest"] != observation.digest:
                    raise ExecutionApplicationError("NATIVE_DISPATCH_TERMINAL_CONFLICT")
            elif row["state"] != "EFFECT_STARTED":
                raise ExecutionApplicationError("NATIVE_DISPATCH_EFFECT_NOT_STARTED")
            else:
                terminal = json.loads(canonical_bytes(observation))["payload"]
                connection.execute(
                    "UPDATE execution_authority.native_dispatch_commands SET state=%s,"
                    "terminal_observation_digest=%s,terminal_record=%s::jsonb,"
                    "terminal_at=%s,updated_at=%s WHERE namespace=%s "
                    "AND security_domain=%s AND command_id=%s",
                    (
                        observation.kind.value,
                        observation.digest,
                        json.dumps(terminal),
                        observation.observed_at,
                        observation.observed_at,
                        scope.namespace,
                        scope.security_domain,
                        str(claim.command.command_id),
                    ),
                )
                replayed = False
                self._checkpoint("command_terminal")
                connection.execute(
                    "UPDATE execution_authority.attempts SET control_state=%s,"
                    "aggregate_version=aggregate_version+1 WHERE namespace=%s "
                    "AND security_domain=%s AND attempt_id=%s",
                    (
                        observation.kind.value,
                        scope.namespace,
                        scope.security_domain,
                        str(claim.command.attempt_id),
                    ),
                )
                self._checkpoint("attempt_terminal")
                from .prepared_execution_observations import apply_native

                apply_native(connection, claim.command, observation)
            cutover = connection.execute(
                "SELECT state,authoritative_writer FROM "
                "execution_authority.evidence_cutover WHERE singleton=true FOR UPDATE"
            ).fetchone()
            if cutover != {
                "state": "POSTGRES_ACTIVE",
                "authoritative_writer": "POSTGRES",
            }:
                raise ExecutionApplicationError("POSTGRES_EVIDENCE_WRITER_NOT_ACTIVE")
            for item in evidence:
                if self._append_evidence(connection, scope, item):
                    replayed = False
                self._checkpoint("evidence")
            inserted = connection.execute(
                "INSERT INTO execution_authority.outcomes"
                "(namespace,security_domain,outcome_id,workflow_run_id,digest,record) "
                "VALUES(%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING "
                "RETURNING outcome_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    outcome_id,
                    workflow_run_id,
                    outcome_digest,
                    json.dumps(outcome),
                ),
            ).fetchone()
            if inserted is not None:
                replayed = False
            else:
                stored = connection.execute(
                    "SELECT digest,workflow_run_id FROM execution_authority.outcomes "
                    "WHERE namespace=%s AND security_domain=%s AND outcome_id=%s",
                    (scope.namespace, scope.security_domain, outcome_id),
                ).fetchone()
                if stored != {
                    "digest": outcome_digest,
                    "workflow_run_id": workflow_run_id,
                }:
                    raise ExecutionApplicationError("OUTCOME_CONFLICT")
            self._checkpoint("outcome")
            terminal = json.loads(canonical_bytes(observation))["payload"]
            fact_digest = hashlib.sha256(
                json.dumps(terminal, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            connection.execute(
                "INSERT INTO execution_authority.native_dispatch_facts"
                "(namespace,security_domain,command_id,ordinal,kind,fact_digest,"
                "record) "
                "SELECT %s,%s,%s,COALESCE(MAX(ordinal),0)+1,%s,%s,%s::jsonb FROM "
                "execution_authority.native_dispatch_facts WHERE namespace=%s "
                "AND security_domain=%s AND command_id=%s ON CONFLICT DO NOTHING",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(claim.command.command_id),
                    observation.kind.value,
                    fact_digest,
                    json.dumps(terminal),
                    scope.namespace,
                    scope.security_domain,
                    str(claim.command.command_id),
                ),
            )
        return AppendDisposition.REPLAYED if replayed else AppendDisposition.APPENDED

    def append_completion(
        self,
        scope: ScopeIdentity,
        evidence: tuple[ExecutionEvidenceRecord, ...],
        outcome_id: str,
        workflow_run_id: str,
        outcome: dict[str, object],
    ) -> AppendDisposition:
        outcome_digest = hashlib.sha256(
            json.dumps(outcome, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        replayed = True
        with self._pool.connection() as connection, connection.transaction():
            cutover = connection.execute(
                "SELECT state,authoritative_writer FROM "
                "execution_authority.evidence_cutover "
                "WHERE singleton=true FOR UPDATE"
            ).fetchone()
            if cutover != {
                "state": "POSTGRES_ACTIVE",
                "authoritative_writer": "POSTGRES",
            }:
                raise ExecutionApplicationError("POSTGRES_EVIDENCE_WRITER_NOT_ACTIVE")
            for item in evidence:
                canonical = json.dumps(
                    dict(item.canonical_payload),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                row = connection.execute(
                    """INSERT INTO execution_authority.execution_evidence
                    (evidence_record_id,schema_version,namespace,security_domain,
                    platform_execution_identity,workflow_identity,task_identity,
                    attempt_ordinal,event_ordinal,event_type,occurred_at,recorded_at,
                    payload_digest,canonical_bytes,record,supersedes_record_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s,%s::jsonb,%s)
                    ON CONFLICT (evidence_record_id) DO NOTHING
                    RETURNING storage_sequence""",
                    (
                        item.evidence_record_id,
                        item.schema_version,
                        scope.namespace,
                        scope.security_domain,
                        item.platform_execution_identity,
                        item.workflow_identity,
                        item.task_identity,
                        item.attempt_ordinal,
                        item.event_ordinal,
                        item.event_type.value,
                        item.occurred_at,
                        item.payload_digest,
                        canonical,
                        json.dumps(dict(item.canonical_payload)),
                        item.supersedes_record_id,
                    ),
                ).fetchone()
                if row is not None:
                    replayed = False
                else:
                    stored = connection.execute(
                        "SELECT payload_digest,canonical_bytes FROM "
                        "execution_authority.execution_evidence "
                        "WHERE evidence_record_id=%s",
                        (item.evidence_record_id,),
                    ).fetchone()
                    if (
                        stored is None
                        or stored["payload_digest"] != item.payload_digest
                        or bytes(stored["canonical_bytes"]) != canonical
                    ):
                        raise ExecutionApplicationError("EVIDENCE_DIGEST_CONFLICT")
            row = connection.execute(
                """INSERT INTO execution_authority.outcomes
                (namespace,security_domain,outcome_id,workflow_run_id,digest,record)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING
                RETURNING outcome_id""",
                (
                    scope.namespace,
                    scope.security_domain,
                    outcome_id,
                    workflow_run_id,
                    outcome_digest,
                    json.dumps(outcome),
                ),
            ).fetchone()
            if row is not None:
                replayed = False
            else:
                stored = connection.execute(
                    "SELECT digest,workflow_run_id FROM execution_authority.outcomes "
                    "WHERE namespace=%s AND security_domain=%s AND outcome_id=%s",
                    (scope.namespace, scope.security_domain, outcome_id),
                ).fetchone()
                if stored != {
                    "digest": outcome_digest,
                    "workflow_run_id": workflow_run_id,
                }:
                    raise ExecutionApplicationError("OUTCOME_CONFLICT")
        return AppendDisposition.REPLAYED if replayed else AppendDisposition.APPENDED


def successor_workflow(
    previous: WorkflowRunIdentity,
    new_id: WorkflowRunId,
    *,
    successor_plan_revision_id: str | None = None,
) -> WorkflowRunIdentity:
    """Expose the accepted immutable rerun/correction identity semantics."""
    if successor_plan_revision_id is None:
        return WorkflowRunIdentity(
            new_id,
            previous.assignment_id,
            previous.approved_plan_revision_id,
            predecessor_workflow_run_id=previous.workflow_run_id,
        )
    if successor_plan_revision_id == previous.approved_plan_revision_id:
        raise ExecutionApplicationError("CORRECTION_REQUIRES_SUCCESSOR_PLAN_REVISION")
    return WorkflowRunIdentity(
        new_id,
        previous.assignment_id,
        successor_plan_revision_id,
        predecessor_workflow_run_id=previous.workflow_run_id,
        correction_of_workflow_run_id=previous.workflow_run_id,
    )
