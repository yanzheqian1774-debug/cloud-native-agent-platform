# ruff: noqa: E501
"""PostgreSQL 15 adapter and atomic Unit of Work for ARCH-208."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .workflow_control_domain import (
    ApprovalDecision,
    AtomicCommandType,
    AtomicControlCommand,
    AtomicControlResult,
    InterventionDecision,
    InterventionRequest,
    InterventionReview,
    InterventionState,
    InterventionTransition,
    PlanRecord,
    PlanStatus,
    ScopeIdentity,
    WorkflowControlConflict,
    WorkflowControlError,
    WorkflowControlNotAuthorized,
    WorkflowControlOperation,
    WorkflowControlOperationResult,
    canonical_digest,
)

ADAPTER = "workflow-control-postgresql-v1"
_TARGETS = {
    "workflow_run_id": ("workflow_runs", "workflow_run_id"),
    "task_run_id": ("task_runs", "task_run_id"),
    "attempt_id": ("attempts", "attempt_id"),
}
_TRANSITIONS = {
    None: {InterventionState.REQUESTED},
    InterventionState.REQUESTED: {
        InterventionState.AUTHORIZED,
        InterventionState.REJECTED,
        InterventionState.EXPIRED,
        InterventionState.CANCELLED,
    },
    InterventionState.AUTHORIZED: {
        InterventionState.APPLICATION_PENDING,
        InterventionState.CANCELLED,
        InterventionState.EXPIRED,
    },
    InterventionState.APPLICATION_PENDING: {
        InterventionState.APPLIED,
        InterventionState.FAILED,
    },
    InterventionState.APPLIED: {InterventionState.OBSERVED, InterventionState.FAILED},
}
_TARGET_TRANSITIONS = {
    "workflow_run_id": {
        "PENDING": {"RUNNING", "CANCELLATION_PENDING", "FAILED", "RECOVERY_REQUIRED"},
        "RUNNING": {
            "PAUSE_REQUESTED",
            "CANCELLATION_PENDING",
            "SUCCEEDED",
            "FAILED",
            "RECOVERY_REQUIRED",
        },
        "PAUSE_REQUESTED": {"PAUSE_PENDING", "FAILED", "RECOVERY_REQUIRED"},
        "PAUSE_PENDING": {"PAUSED", "FAILED", "RECOVERY_REQUIRED"},
        "PAUSED": {"RESUME_REQUESTED", "CANCELLATION_PENDING"},
        "RESUME_REQUESTED": {"RUNNING", "FAILED", "RECOVERY_REQUIRED"},
        "CANCELLATION_PENDING": {"CANCELLED", "FAILED", "RECOVERY_REQUIRED"},
    },
    "task_run_id": {
        "PENDING": {"READY", "BLOCKED", "CANCELLATION_PENDING", "SKIPPED"},
        "READY": {"RUNNING", "BLOCKED", "CANCELLATION_PENDING", "SKIPPED"},
        "RUNNING": {"BLOCKED", "CANCELLATION_PENDING", "SUCCEEDED", "FAILED"},
        "BLOCKED": {"READY", "CANCELLATION_PENDING", "SKIPPED"},
        "CANCELLATION_PENDING": {"CANCELLED"},
    },
    "attempt_id": {
        "PENDING": {
            "PLACED",
            "CANCELLATION_PENDING",
            "FAILED",
            "UNKNOWN",
            "RECOVERY_REQUIRED",
        },
        "PLACED": {
            "RUNNING",
            "CANCELLATION_PENDING",
            "FAILED",
            "UNKNOWN",
            "RECOVERY_REQUIRED",
        },
        "RUNNING": {
            "CANCELLATION_PENDING",
            "SUCCEEDED",
            "FAILED",
            "UNKNOWN",
            "RECOVERY_REQUIRED",
        },
        "CANCELLATION_PENDING": {"CANCELLED", "UNKNOWN", "RECOVERY_REQUIRED"},
        "UNKNOWN": {"RECOVERY_REQUIRED"},
    },
}


class PostgresWorkflowControlRepository:
    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout: float = 5.0,
    ) -> None:
        if not database_url:
            raise WorkflowControlError("WORKFLOW_CONTROL_STORAGE_UNAVAILABLE")
        self.migration_path = migration_path
        self.schema_version = int(migration_path.name[:4])
        try:
            self.pool = ConnectionPool(
                database_url,
                min_size=min_pool_size,
                max_size=max_pool_size,
                timeout=timeout,
                kwargs={"row_factory": dict_row, "autocommit": False},
                open=True,
            )
            self.pool.wait(timeout=timeout)
        except Exception as exc:
            raise WorkflowControlError("WORKFLOW_CONTROL_STORAGE_UNAVAILABLE") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        version = int(self.migration_path.name[:4])
        if version not in {9, 10, 11}:
            raise WorkflowControlError("WORKFLOW_CONTROL_SCHEMA_INCOMPATIBLE")
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='15s'")
                prior = connection.execute(
                    "SELECT 1 FROM execution_authority.schema_migrations WHERE version=%s",
                    (version - 1,),
                ).fetchone()
                if prior is None:
                    raise WorkflowControlError(f"MIGRATION_{version - 1:04d}_REQUIRED")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM execution_authority.schema_migrations WHERE version=%s",
                    (version,),
                ).fetchone()
                expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
                if row is None:
                    connection.execute(
                        "INSERT INTO execution_authority.schema_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (version, self.migration_checksum, ADAPTER),
                    )
                elif row != expected:
                    raise WorkflowControlError("WORKFLOW_CONTROL_SCHEMA_INCOMPATIBLE")
        except WorkflowControlError:
            raise
        except PsycopgError as exc:
            raise WorkflowControlError(
                "WORKFLOW_CONTROL_MIGRATION_UNAVAILABLE"
            ) from exc
        self.compatibility(version=version)

    def compatibility(self, *, version: int | None = None) -> None:
        version = version or int(self.migration_path.name[:4])
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT checksum,adapter FROM execution_authority.schema_migrations WHERE version=%s",
                (version,),
            ).fetchone()
            tables = {
                item["table_name"]
                for item in connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='execution_authority'"
                ).fetchall()
            }
        required = {
            "plans",
            "plan_approval_decisions",
            "intervention_transitions",
            "idempotency_claims",
            "control_commands",
            "intervention_evidence_links",
            "intervention_outcome_links",
        }
        if version >= 10:
            required |= {"intervention_reviews", "intervention_decisions"}
        if version >= 11:
            required |= {"plan_corrections"}
        if (
            row != {"checksum": self.migration_checksum, "adapter": ADAPTER}
            or not required <= tables
        ):
            raise WorkflowControlError("WORKFLOW_CONTROL_SCHEMA_INCOMPATIBLE")

    def create_plan(self, plan: PlanRecord) -> PlanRecord:
        with self.pool.connection() as connection, connection.transaction():
            connection.execute(
                "INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,predecessor_plan_id,predecessor_plan_version,workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,aggregate_version,plan_digest,canonical_bytes,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    plan.scope.namespace,
                    plan.scope.security_domain,
                    plan.plan_id,
                    plan.plan_version,
                    plan.predecessor_plan_id,
                    plan.predecessor_plan_version,
                    plan.workflow_definition_id,
                    plan.workflow_definition_revision_id,
                    plan.workflow_definition_digest,
                    plan.status.value,
                    plan.aggregate_version,
                    plan.plan_digest,
                    plan.canonical_bytes,
                    plan.created_at,
                    plan.updated_at,
                ),
            )
        return plan

    def get_plan(
        self, scope: ScopeIdentity, plan_id: str, plan_version: int
    ) -> PlanRecord | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s",
                (scope.namespace, scope.security_domain, plan_id, plan_version),
            ).fetchone()
        return None if row is None else self._plan(scope, row)

    def replace_plan_status(
        self,
        scope: ScopeIdentity,
        plan_id: str,
        plan_version: int,
        status: PlanStatus,
        *,
        expected_version: int,
    ) -> PlanRecord:
        with self.pool.connection() as connection, connection.transaction():
            current = connection.execute(
                "SELECT status FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s FOR UPDATE",
                (scope.namespace, scope.security_domain, plan_id, plan_version),
            ).fetchone()
            if current is None or current["status"] in (
                "APPROVED",
                "REJECTED",
                "CANCELLED",
                "INVALIDATED",
                "SUPERSEDED",
            ):
                raise WorkflowControlConflict("PLAN_IMMUTABLE_OR_MISSING")
            row = connection.execute(
                "UPDATE execution_authority.plans SET status=%s,aggregate_version=aggregate_version+1,updated_at=now() WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s AND aggregate_version=%s RETURNING *",
                (
                    status.value,
                    scope.namespace,
                    scope.security_domain,
                    plan_id,
                    plan_version,
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
        return self._plan(scope, row)

    def append_approval(
        self, scope: ScopeIdentity, decision: ApprovalDecision
    ) -> ApprovalDecision:
        with self.pool.connection() as connection, connection.transaction():
            plan = connection.execute(
                "SELECT status,plan_digest FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s FOR UPDATE",
                (
                    scope.namespace,
                    scope.security_domain,
                    decision.plan_id,
                    decision.plan_version,
                ),
            ).fetchone()
            if (
                plan is None
                or plan["plan_digest"] != decision.plan_digest
                or plan["status"] != "PENDING_APPROVAL"
            ):
                raise WorkflowControlConflict("PLAN_NOT_APPROVABLE")
            connection.execute(
                "INSERT INTO execution_authority.plan_approval_decisions(namespace,security_domain,approval_decision_id,plan_id,plan_version,plan_digest,ordinal,decision,actor_id,authority_basis,reason_category,decision_digest,decided_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    decision.approval_decision_id,
                    decision.plan_id,
                    decision.plan_version,
                    decision.plan_digest,
                    decision.ordinal,
                    decision.decision,
                    decision.actor_id,
                    decision.authority_basis,
                    decision.reason_category,
                    decision.decision_digest,
                    decision.decided_at,
                ),
            )
            connection.execute(
                "UPDATE execution_authority.plans SET status=%s,aggregate_version=aggregate_version+1,updated_at=now() WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s",
                (
                    "APPROVED" if decision.decision == "APPROVE" else "REJECTED",
                    scope.namespace,
                    scope.security_domain,
                    decision.plan_id,
                    decision.plan_version,
                ),
            )
        return decision

    def read_approvals(
        self, scope: ScopeIdentity, plan_id: str, plan_version: int
    ) -> tuple[ApprovalDecision, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM execution_authority.plan_approval_decisions WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s ORDER BY ordinal,approval_decision_id",
                (scope.namespace, scope.security_domain, plan_id, plan_version),
            ).fetchall()
        return tuple(
            ApprovalDecision(
                **{key: row[key] for key in ApprovalDecision.__dataclass_fields__}
            )
            for row in rows
        )

    def read_successor_plans(
        self, scope: ScopeIdentity, plan_id: str, plan_version: int
    ) -> tuple[PlanRecord, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND predecessor_plan_id=%s AND predecessor_plan_version=%s ORDER BY plan_version,plan_id",
                (scope.namespace, scope.security_domain, plan_id, plan_version),
            ).fetchall()
        return tuple(self._plan(scope, row) for row in rows)

    def request_intervention(
        self, scope: ScopeIdentity, request: InterventionRequest
    ) -> InterventionRequest:
        transition = InterventionTransition(
            f"{request.intervention_id}:requested",
            request.intervention_id,
            1,
            None,
            InterventionState.REQUESTED,
            request.actor_id,
            request.authority_basis,
            request.reason_category,
            request.requested_at,
        )
        with self.pool.connection() as connection, connection.transaction():
            self._insert_request(connection, scope, request)
            self._insert_transition(connection, scope, transition)
        return request

    def append_transition(
        self,
        scope: ScopeIdentity,
        transition: InterventionTransition,
        *,
        expected_version: int,
    ) -> InterventionTransition:
        with self.pool.connection() as connection, connection.transaction():
            self._validate_transition(transition)
            row = connection.execute(
                "UPDATE execution_authority.interventions SET current_state=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND intervention_id=%s AND aggregate_version=%s AND current_state IS NOT DISTINCT FROM %s RETURNING aggregate_version",
                (
                    transition.to_state.value,
                    scope.namespace,
                    scope.security_domain,
                    transition.intervention_id,
                    expected_version,
                    None
                    if transition.from_state is None
                    else transition.from_state.value,
                ),
            ).fetchone()
            if row is None:
                raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
            self._insert_transition(connection, scope, transition)
        return transition

    def read_transitions(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[InterventionTransition, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM execution_authority.intervention_transitions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s ORDER BY ordinal,transition_id",
                (scope.namespace, scope.security_domain, intervention_id),
            ).fetchall()
        return tuple(
            InterventionTransition(
                row["transition_id"],
                intervention_id,
                row["ordinal"],
                None
                if row["from_state"] is None
                else InterventionState(row["from_state"]),
                InterventionState(row["to_state"]),
                row["actor_id"],
                row["authority_basis"],
                row["reason_category"],
                row["transitioned_at"],
            )
            for row in rows
        )

    def append_review(
        self, scope: ScopeIdentity, review: InterventionReview
    ) -> InterventionReview:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "SELECT current_state FROM execution_authority.interventions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s FOR UPDATE",
                    (scope.namespace, scope.security_domain, review.intervention_id),
                ).fetchone()
                if row is None or row["current_state"] != "REQUESTED":
                    raise WorkflowControlConflict("INTERVENTION_NOT_REVIEWABLE")
                connection.execute(
                    "INSERT INTO execution_authority.intervention_reviews(namespace,security_domain,review_id,intervention_id,actor_id,authority_basis,review_digest,reviewed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        review.review_id,
                        review.intervention_id,
                        review.actor_id,
                        review.authority_basis,
                        review.digest,
                        review.reviewed_at,
                    ),
                )
            return review
        except WorkflowControlError:
            raise
        except PsycopgError as exc:
            raise WorkflowControlConflict("WORKFLOW_CONTROL_CONFLICT") from exc

    def append_decision(
        self, scope: ScopeIdentity, decision: InterventionDecision
    ) -> InterventionDecision:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "SELECT i.current_state,i.aggregate_version FROM execution_authority.interventions i JOIN execution_authority.intervention_reviews r ON r.namespace=i.namespace AND r.security_domain=i.security_domain AND r.intervention_id=i.intervention_id WHERE i.namespace=%s AND i.security_domain=%s AND i.intervention_id=%s AND r.review_id=%s FOR UPDATE OF i",
                    (
                        scope.namespace,
                        scope.security_domain,
                        decision.intervention_id,
                        decision.review_id,
                    ),
                ).fetchone()
                if row is None or row["current_state"] != "REQUESTED":
                    raise WorkflowControlConflict("INTERVENTION_NOT_DECIDABLE")
                to_state = (
                    InterventionState.AUTHORIZED
                    if decision.decision == "AUTHORIZE"
                    else InterventionState.REJECTED
                )
                ordinal = row["aggregate_version"] + 1
                connection.execute(
                    "INSERT INTO execution_authority.intervention_decisions(namespace,security_domain,decision_id,intervention_id,review_id,decision,actor_id,authority_basis,reason_category,decision_digest,decided_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        decision.decision_id,
                        decision.intervention_id,
                        decision.review_id,
                        decision.decision,
                        decision.actor_id,
                        decision.authority_basis,
                        decision.reason_category,
                        decision.digest,
                        decision.decided_at,
                    ),
                )
                transition = InterventionTransition(
                    decision.decision_id,
                    decision.intervention_id,
                    ordinal,
                    InterventionState.REQUESTED,
                    to_state,
                    decision.actor_id,
                    decision.authority_basis,
                    decision.reason_category,
                    decision.decided_at,
                )
                self._insert_transition(connection, scope, transition)
                changed = connection.execute(
                    "UPDATE execution_authority.interventions SET current_state=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND intervention_id=%s AND aggregate_version=%s RETURNING aggregate_version",
                    (
                        to_state.value,
                        scope.namespace,
                        scope.security_domain,
                        decision.intervention_id,
                        row["aggregate_version"],
                    ),
                ).fetchone()
                if changed is None:
                    raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
            return decision
        except WorkflowControlError:
            raise
        except PsycopgError as exc:
            raise WorkflowControlConflict("WORKFLOW_CONTROL_CONFLICT") from exc

    def persist(
        self, command: AtomicControlCommand, *, authorized: bool
    ) -> AtomicControlResult:
        if not authorized:
            raise WorkflowControlNotAuthorized("NOT_AUTHORIZED")
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                replay = self._claim(connection, command)
                if replay is not None:
                    return replay
                self._insert_request(connection, command.scope, command.request)
                requested = replace(
                    command.transition,
                    transition_id=f"{command.request.intervention_id}:requested",
                    ordinal=1,
                    from_state=None,
                    to_state=InterventionState.REQUESTED,
                )
                self._insert_transition(connection, command.scope, requested)
                target_column, target_id = self._target(command.request)
                table, id_column = _TARGETS[target_column]
                current = connection.execute(
                    f"SELECT control_state,aggregate_version FROM execution_authority.{table} WHERE namespace=%s AND security_domain=%s AND {id_column}=%s FOR UPDATE",
                    (command.scope.namespace, command.scope.security_domain, target_id),
                ).fetchone()
                if (
                    current is None
                    or current["aggregate_version"]
                    != command.request.expected_target_version
                ):
                    raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
                if command.target_state not in _TARGET_TRANSITIONS[target_column].get(
                    current["control_state"], set()
                ):
                    raise WorkflowControlConflict("INVALID_TARGET_STATE_TRANSITION")
                row = connection.execute(
                    f"UPDATE execution_authority.{table} SET control_state=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND {id_column}=%s AND aggregate_version=%s AND control_state=%s RETURNING aggregate_version",
                    (
                        command.target_state,
                        command.scope.namespace,
                        command.scope.security_domain,
                        target_id,
                        command.request.expected_target_version,
                        current["control_state"],
                    ),
                ).fetchone()
                if row is None:
                    raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
                applied = replace(
                    command.transition,
                    ordinal=2,
                    from_state=InterventionState.REQUESTED,
                )
                self._validate_transition(applied)
                self._insert_transition(connection, command.scope, applied)
                connection.execute(
                    "UPDATE execution_authority.interventions SET current_state=%s,aggregate_version=2 WHERE namespace=%s AND security_domain=%s AND intervention_id=%s",
                    (
                        applied.to_state.value,
                        command.scope.namespace,
                        command.scope.security_domain,
                        command.request.intervention_id,
                    ),
                )
                values = command.request.target.values()
                if command.successor_plan is not None:
                    self._insert_plan(connection, command.successor_plan)
                if command.successor_workflow_run is not None:
                    successor = command.successor_workflow_run
                    connection.execute(
                        "INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,assignment_id,approved_plan_revision_id,predecessor_workflow_run_id,correction_of_workflow_run_id,record,aggregate_version,control_state,plan_id,plan_version,approved_plan_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,1,%s,%s,%s,%s)",
                        (
                            command.scope.namespace,
                            command.scope.security_domain,
                            successor["workflow_run_id"],
                            successor["assignment_id"],
                            successor["approved_plan_revision_id"],
                            successor.get("predecessor_workflow_run_id"),
                            successor.get("correction_of_workflow_run_id"),
                            json.dumps(successor["record"]),
                            successor["control_state"],
                            successor["plan_id"],
                            successor["plan_version"],
                            successor["approved_plan_digest"],
                        ),
                    )
                for evidence in command.evidence_records:
                    connection.execute(
                        "INSERT INTO execution_authority.execution_evidence(evidence_record_id,schema_version,namespace,security_domain,platform_execution_identity,workflow_identity,task_identity,attempt_ordinal,event_ordinal,event_type,occurred_at,recorded_at,payload_digest,canonical_bytes,record) VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            evidence["evidence_record_id"],
                            command.scope.namespace,
                            command.scope.security_domain,
                            evidence["platform_execution_identity"],
                            evidence["workflow_identity"],
                            evidence["task_identity"],
                            evidence["attempt_ordinal"],
                            evidence["event_ordinal"],
                            evidence["event_type"],
                            evidence["occurred_at"],
                            evidence["recorded_at"],
                            evidence["payload_digest"],
                            evidence["canonical_bytes"],
                            json.dumps(evidence["record"]),
                        ),
                    )
                for outcome in command.outcome_records:
                    connection.execute(
                        "INSERT INTO execution_authority.outcomes(namespace,security_domain,outcome_id,workflow_run_id,digest,record) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            command.scope.namespace,
                            command.scope.security_domain,
                            outcome["outcome_id"],
                            outcome["workflow_run_id"],
                            outcome["digest"],
                            json.dumps(outcome["record"]),
                        ),
                    )
                evidence_ids = command.evidence_ids + tuple(
                    item["evidence_record_id"] for item in command.evidence_records
                )
                outcome_ids = command.outcome_ids + tuple(
                    item["outcome_id"] for item in command.outcome_records
                )
                connection.execute(
                    "INSERT INTO execution_authority.control_commands(namespace,security_domain,control_command_id,command_type,intervention_id,transition_ordinal,workflow_run_id,task_run_id,attempt_id,expected_target_version,successor_plan_id,successor_plan_version,successor_workflow_run_id,command_digest,canonical_record,requested_at) VALUES (%s,%s,%s,%s,%s,2,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                    (
                        command.scope.namespace,
                        command.scope.security_domain,
                        command.control_command_id,
                        command.command_type,
                        command.request.intervention_id,
                        *values,
                        command.request.expected_target_version,
                        None
                        if command.successor_plan is None
                        else command.successor_plan.plan_id,
                        None
                        if command.successor_plan is None
                        else command.successor_plan.plan_version,
                        None
                        if command.successor_workflow_run is None
                        else command.successor_workflow_run["workflow_run_id"],
                        command.payload_digest,
                        json.dumps(command.command_record),
                        command.request.requested_at,
                    ),
                )
                for ordinal, evidence_id in enumerate(evidence_ids, 1):
                    connection.execute(
                        "INSERT INTO execution_authority.intervention_evidence_links(namespace,security_domain,intervention_id,transition_ordinal,ordinal,evidence_record_id) VALUES (%s,%s,%s,2,%s,%s)",
                        (
                            command.scope.namespace,
                            command.scope.security_domain,
                            command.request.intervention_id,
                            ordinal,
                            evidence_id,
                        ),
                    )
                for ordinal, outcome_id in enumerate(outcome_ids, 1):
                    connection.execute(
                        "INSERT INTO execution_authority.intervention_outcome_links(namespace,security_domain,intervention_id,transition_ordinal,ordinal,outcome_id) VALUES (%s,%s,%s,2,%s,%s)",
                        (
                            command.scope.namespace,
                            command.scope.security_domain,
                            command.request.intervention_id,
                            ordinal,
                            outcome_id,
                        ),
                    )
                result = AtomicControlResult(
                    False,
                    command.request.intervention_id,
                    applied.transition_id,
                    command.control_command_id,
                    row["aggregate_version"],
                )
                connection.execute(
                    "UPDATE execution_authority.idempotency_claims SET state='COMPLETED',intervention_id=%s,control_command_id=%s,result_identity=%s,completed_at=now() WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key=%s",
                    (
                        result.intervention_id,
                        result.control_command_id,
                        str(result.target_version),
                        command.scope.namespace,
                        command.scope.security_domain,
                        command.request.actor_id,
                        command.command_type,
                        command.idempotency_key,
                    ),
                )
                readback = connection.execute(
                    "SELECT c.control_command_id,i.current_state FROM execution_authority.control_commands c JOIN execution_authority.interventions i USING(namespace,security_domain,intervention_id) WHERE c.namespace=%s AND c.security_domain=%s AND c.control_command_id=%s",
                    (
                        command.scope.namespace,
                        command.scope.security_domain,
                        command.control_command_id,
                    ),
                ).fetchone()
                if (
                    readback is None
                    or readback["current_state"] != applied.to_state.value
                ):
                    raise WorkflowControlConflict("AUTHORITATIVE_READBACK_MISMATCH")
                return result
        except WorkflowControlError:
            raise
        except PsycopgError as exc:
            raise WorkflowControlConflict("WORKFLOW_CONTROL_CONFLICT") from exc

    def persist_operation(
        self, operation: WorkflowControlOperation, *, authorized: bool
    ) -> WorkflowControlOperationResult:
        """Persist one bounded successor/decision command as one transaction."""
        if not authorized:
            raise WorkflowControlNotAuthorized("NOT_AUTHORIZED")
        if self.schema_version >= 11 and not operation.evidence_records:
            raise WorkflowControlConflict("OPERATION_EVIDENCE_REQUIRED")
        target_column, target_id = next(
            (key, value)
            for key, value in zip(
                ("workflow_run_id", "task_run_id", "attempt_id"),
                operation.target.values(),
                strict=True,
            )
            if value is not None
        )
        key = (
            operation.scope.namespace,
            operation.scope.security_domain,
            operation.actor_id,
            operation.command_type.value,
            operation.idempotency_key,
        )
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                claim = connection.execute(
                    "SELECT payload_digest,state,result_record FROM execution_authority.idempotency_claims WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key=%s FOR UPDATE",
                    key,
                ).fetchone()
                if claim is not None:
                    if claim["payload_digest"] != operation.payload_digest:
                        raise WorkflowControlConflict("IDEMPOTENCY_PAYLOAD_MISMATCH")
                    if claim["state"] != "COMPLETED":
                        raise WorkflowControlConflict("COMMAND_IN_PROGRESS")
                    return self._operation_result(claim["result_record"], replayed=True)
                connection.execute(
                    "INSERT INTO execution_authority.idempotency_claims(namespace,security_domain,actor_id,command_type,idempotency_key,payload_digest,state,claimed_at,retain_until) VALUES (%s,%s,%s,%s,%s,%s,'IN_PROGRESS',%s,%s)",
                    (
                        *key,
                        operation.payload_digest,
                        operation.requested_at,
                        operation.retain_until,
                    ),
                )
                if operation.intervention_id is None:
                    raise WorkflowControlConflict("INTERVENTION_REQUIRED")
                if operation.command_type is AtomicCommandType.REQUEST_INTERVENTION:
                    if (
                        operation.request is None
                        or operation.request.intervention_id
                        != operation.intervention_id
                        or operation.request.target != operation.target
                        or operation.request.expected_target_version
                        != operation.target_expected_version
                    ):
                        raise WorkflowControlConflict(
                            "EXACT_INTERVENTION_REQUEST_REQUIRED"
                        )
                    self._insert_request(connection, operation.scope, operation.request)
                    self._insert_transition(
                        connection,
                        operation.scope,
                        InterventionTransition(
                            operation.transition_id
                            or f"{operation.intervention_id}:requested",
                            operation.intervention_id,
                            1,
                            None,
                            InterventionState.REQUESTED,
                            operation.request.actor_id,
                            operation.request.authority_basis,
                            operation.request.reason_category,
                            operation.request.requested_at,
                        ),
                    )
                intervention = connection.execute(
                    "SELECT current_state,aggregate_version,workflow_run_id,task_run_id,attempt_id FROM execution_authority.interventions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s FOR UPDATE",
                    (*key[:2], operation.intervention_id),
                ).fetchone()
                if intervention is None:
                    raise WorkflowControlConflict("INTERVENTION_REQUIRED")
                if (
                    tuple(
                        intervention[name]
                        for name in ("workflow_run_id", "task_run_id", "attempt_id")
                    )
                    != operation.target.values()
                ):
                    raise WorkflowControlConflict("INTERVENTION_TARGET_MISMATCH")

                transition_ordinal = intervention["aggregate_version"]
                transition_id = operation.transition_id
                if operation.review is not None:
                    if (
                        operation.review.intervention_id != operation.intervention_id
                        or intervention["current_state"] != "REQUESTED"
                    ):
                        raise WorkflowControlConflict("INTERVENTION_NOT_REVIEWABLE")
                    connection.execute(
                        "INSERT INTO execution_authority.intervention_reviews(namespace,security_domain,review_id,intervention_id,actor_id,authority_basis,review_digest,reviewed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            *key[:2],
                            operation.review.review_id,
                            operation.intervention_id,
                            operation.review.actor_id,
                            operation.review.authority_basis,
                            operation.review.digest,
                            operation.review.reviewed_at,
                        ),
                    )
                if operation.decision is not None:
                    if (
                        (
                            operation.review is not None
                            and operation.decision.review_id
                            != operation.review.review_id
                        )
                        or operation.decision.intervention_id
                        != operation.intervention_id
                        or intervention["current_state"] != "REQUESTED"
                    ):
                        raise WorkflowControlConflict("INTERVENTION_NOT_DECIDABLE")
                    stored_review = connection.execute(
                        "SELECT review_id FROM execution_authority.intervention_reviews WHERE namespace=%s AND security_domain=%s AND intervention_id=%s AND review_id=%s",
                        (
                            *key[:2],
                            operation.intervention_id,
                            operation.decision.review_id,
                        ),
                    ).fetchone()
                    if stored_review is None:
                        raise WorkflowControlConflict("INTERVENTION_NOT_DECIDABLE")
                    to_state = (
                        InterventionState.AUTHORIZED
                        if operation.decision.decision == "AUTHORIZE"
                        else InterventionState.REJECTED
                    )
                    transition_ordinal += 1
                    transition_id = operation.decision.decision_id
                    connection.execute(
                        "INSERT INTO execution_authority.intervention_decisions(namespace,security_domain,decision_id,intervention_id,review_id,decision,actor_id,authority_basis,reason_category,decision_digest,decided_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            *key[:2],
                            operation.decision.decision_id,
                            operation.intervention_id,
                            operation.decision.review_id,
                            operation.decision.decision,
                            operation.decision.actor_id,
                            operation.decision.authority_basis,
                            operation.decision.reason_category,
                            operation.decision.digest,
                            operation.decision.decided_at,
                        ),
                    )
                    decision_transition = InterventionTransition(
                        transition_id,
                        operation.intervention_id,
                        transition_ordinal,
                        InterventionState.REQUESTED,
                        to_state,
                        operation.decision.actor_id,
                        operation.decision.authority_basis,
                        operation.decision.reason_category,
                        operation.decision.decided_at,
                    )
                    self._insert_transition(
                        connection, operation.scope, decision_transition
                    )
                    connection.execute(
                        "UPDATE execution_authority.interventions SET current_state=%s,aggregate_version=%s WHERE namespace=%s AND security_domain=%s AND intervention_id=%s",
                        (
                            to_state.value,
                            transition_ordinal,
                            *key[:2],
                            operation.intervention_id,
                        ),
                    )
                    intervention["current_state"] = to_state.value

                table, id_column = _TARGETS[target_column]
                target = connection.execute(
                    f"SELECT * FROM execution_authority.{table} WHERE namespace=%s AND security_domain=%s AND {id_column}=%s FOR UPDATE",
                    (*key[:2], target_id),
                ).fetchone()
                if (
                    target is None
                    or target["aggregate_version"] != operation.target_expected_version
                ):
                    raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")

                target_version = target["aggregate_version"]
                successor_attempt_id = None
                successor_run_id = None
                runtime_command_id = None
                approval_decision_id = None
                kind = operation.command_type
                successor_plan_id = None
                successor_plan_version = None
                if kind in {
                    AtomicCommandType.APPROVE_AND_CONTINUE,
                    AtomicCommandType.REJECT_PLAN,
                }:
                    target_version, approval_decision_id = self._persist_plan_operation(
                        connection, operation, target_column, target
                    )
                elif kind is AtomicCommandType.CORRECT_PLAN:
                    successor_plan_id, successor_plan_version = (
                        self._persist_correction(connection, operation)
                    )
                elif kind is AtomicCommandType.REQUEST_INTERVENTION:
                    if (
                        operation.request is None
                        or intervention["current_state"] != "REQUESTED"
                    ):
                        raise WorkflowControlConflict(
                            "EXACT_INTERVENTION_REQUEST_REQUIRED"
                        )
                    transition_ordinal = 1
                    transition_id = (
                        operation.transition_id
                        or f"{operation.intervention_id}:requested"
                    )
                elif kind is AtomicCommandType.REVIEW_INTERVENTION:
                    if (
                        operation.review is None
                        or intervention["current_state"] != "REQUESTED"
                    ):
                        raise WorkflowControlConflict("INTERVENTION_NOT_REVIEWABLE")
                    transition_ordinal = intervention["aggregate_version"]
                    transition = connection.execute(
                        "SELECT transition_id FROM execution_authority.intervention_transitions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s AND ordinal=%s",
                        (*key[:2], operation.intervention_id, transition_ordinal),
                    ).fetchone()
                    if transition is None:
                        raise WorkflowControlConflict(
                            "INTERVENTION_TRANSITION_REQUIRED"
                        )
                    transition_id = transition["transition_id"]
                elif kind is AtomicCommandType.RETRY_ATTEMPT:
                    if (
                        target_column != "attempt_id"
                        or target["control_state"] != "FAILED"
                        or operation.successor_id is None
                    ):
                        raise WorkflowControlConflict("ATTEMPT_NOT_RETRYABLE")
                    next_ordinal = (
                        target["attempt_ordinal"] + 1
                        if target["attempt_ordinal"]
                        else None
                    )
                    if next_ordinal is None:
                        raise WorkflowControlConflict("ATTEMPT_ORDINAL_REQUIRED")
                    connection.execute(
                        "INSERT INTO execution_authority.attempts(namespace,security_domain,attempt_id,task_run_id,predecessor_attempt_id,aggregate_digest,record,aggregate_version,control_state,attempt_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,1,'PENDING',%s)",
                        (
                            *key[:2],
                            operation.successor_id,
                            target["task_run_id"],
                            target_id,
                            operation.payload_digest,
                            json.dumps(operation.payload),
                            next_ordinal,
                        ),
                    )
                    successor_attempt_id = operation.successor_id
                elif kind is AtomicCommandType.CREATE_SUCCESSOR_RUN:
                    if (
                        target_column != "workflow_run_id"
                        or target["control_state"]
                        not in {"SUCCEEDED", "FAILED", "CANCELLED"}
                        or operation.successor_id is None
                    ):
                        raise WorkflowControlConflict("RUN_NOT_RERUNNABLE")
                    plan = connection.execute(
                        "SELECT status,plan_digest,workflow_definition_revision_id FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s FOR SHARE",
                        (*key[:2], target["plan_id"], target["plan_version"]),
                    ).fetchone()
                    if (
                        plan is None
                        or plan["status"] != "APPROVED"
                        or plan["plan_digest"] != target["approved_plan_digest"]
                    ):
                        raise WorkflowControlConflict("EXACT_APPROVED_PLAN_REQUIRED")
                    connection.execute(
                        "INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,assignment_id,approved_plan_revision_id,predecessor_workflow_run_id,record,aggregate_version,control_state,plan_id,plan_version,approved_plan_digest) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,1,'PENDING',%s,%s,%s)",
                        (
                            *key[:2],
                            operation.successor_id,
                            target["assignment_id"],
                            plan["workflow_definition_revision_id"],
                            target_id,
                            json.dumps(operation.payload),
                            target["plan_id"],
                            target["plan_version"],
                            target["approved_plan_digest"],
                        ),
                    )
                    successor_run_id = operation.successor_id
                elif kind is AtomicCommandType.REPLACE_RUNTIME:
                    runtime_command_id = self._validate_runtime_replacement(
                        connection, operation, key[:2], target_column, target_id
                    )
                elif kind is AtomicCommandType.CANCEL_CONTROLLED_EXECUTION:
                    if target["control_state"] in {
                        "SUCCEEDED",
                        "FAILED",
                        "SKIPPED",
                        "CANCELLED",
                        "RECOVERY_REQUIRED",
                    }:
                        raise WorkflowControlConflict("TERMINAL_TARGET_IMMUTABLE")
                    changed = connection.execute(
                        f"UPDATE execution_authority.{table} SET control_state='CANCELLATION_PENDING',aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND {id_column}=%s AND aggregate_version=%s RETURNING aggregate_version",
                        (*key[:2], target_id, operation.target_expected_version),
                    ).fetchone()
                    if changed is None:
                        raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
                    target_version = changed["aggregate_version"]
                elif kind is AtomicCommandType.COMPLETE_EXECUTION_WITH_OUTCOME:
                    target_version = self._complete_terminal_target(
                        connection, operation, target_column, target_id, target
                    )
                elif kind is AtomicCommandType.APPLY_INTERVENTION_DECISION:
                    if intervention["current_state"] != "AUTHORIZED":
                        raise WorkflowControlConflict("APPROVED_DECISION_REQUIRED")
                    decision = connection.execute(
                        "SELECT decision_id FROM execution_authority.intervention_decisions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s AND decision='AUTHORIZE'",
                        (*key[:2], operation.intervention_id),
                    ).fetchone()
                    if decision is None:
                        raise WorkflowControlConflict("APPROVED_DECISION_REQUIRED")
                    transition_ordinal += 1
                    transition_id = (
                        operation.transition_id
                        or f"{operation.control_command_id}:application-pending"
                    )
                    self._insert_transition(
                        connection,
                        operation.scope,
                        InterventionTransition(
                            transition_id,
                            operation.intervention_id,
                            transition_ordinal,
                            InterventionState.AUTHORIZED,
                            InterventionState.APPLICATION_PENDING,
                            operation.actor_id,
                            "authorized-decision",
                            "OPERATIONAL_RECOVERY",
                            operation.requested_at,
                        ),
                    )
                    connection.execute(
                        "UPDATE execution_authority.interventions SET current_state='APPLICATION_PENDING',aggregate_version=%s WHERE namespace=%s AND security_domain=%s AND intervention_id=%s",
                        (transition_ordinal, *key[:2], operation.intervention_id),
                    )
                    wanted_state = operation.payload.get("target_state")
                    if wanted_state not in _TARGET_TRANSITIONS[target_column].get(
                        target["control_state"], set()
                    ):
                        raise WorkflowControlConflict("INVALID_TARGET_STATE_TRANSITION")
                    changed = connection.execute(
                        f"UPDATE execution_authority.{table} SET control_state=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND {id_column}=%s AND aggregate_version=%s RETURNING aggregate_version",
                        (
                            wanted_state,
                            *key[:2],
                            target_id,
                            operation.target_expected_version,
                        ),
                    ).fetchone()
                    if changed is None:
                        raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
                    target_version = changed["aggregate_version"]
                    applied_id = f"{operation.control_command_id}:applied"
                    transition_ordinal += 1
                    self._insert_transition(
                        connection,
                        operation.scope,
                        InterventionTransition(
                            applied_id,
                            operation.intervention_id,
                            transition_ordinal,
                            InterventionState.APPLICATION_PENDING,
                            InterventionState.APPLIED,
                            operation.actor_id,
                            "authorized-decision",
                            "OPERATIONAL_RECOVERY",
                            operation.requested_at,
                        ),
                    )
                    transition_id = applied_id
                    connection.execute(
                        "UPDATE execution_authority.interventions SET current_state='APPLIED',aggregate_version=%s WHERE namespace=%s AND security_domain=%s AND intervention_id=%s",
                        (transition_ordinal, *key[:2], operation.intervention_id),
                    )
                else:
                    raise WorkflowControlConflict("UNSUPPORTED_CONTROL_COMMAND")

                if transition_id is None:
                    transition = connection.execute(
                        "SELECT transition_id,ordinal FROM execution_authority.intervention_transitions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s ORDER BY ordinal DESC LIMIT 1",
                        (*key[:2], operation.intervention_id),
                    ).fetchone()
                    if transition is None:
                        raise WorkflowControlConflict(
                            "INTERVENTION_TRANSITION_REQUIRED"
                        )
                    transition_id, transition_ordinal = (
                        transition["transition_id"],
                        transition["ordinal"],
                    )
                self._create_operation_facts(
                    connection, operation, target_column, target_id
                )
                connection.execute(
                    "INSERT INTO execution_authority.control_commands(namespace,security_domain,control_command_id,command_type,intervention_id,transition_ordinal,workflow_run_id,task_run_id,attempt_id,expected_target_version,successor_plan_id,successor_plan_version,successor_workflow_run_id,successor_attempt_id,affected_attempt_id,runtime_command_id,placement_id,command_digest,canonical_record,requested_at,result_record) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,'{}'::jsonb)",
                    (
                        *key[:2],
                        operation.control_command_id,
                        kind.value,
                        operation.intervention_id,
                        transition_ordinal,
                        *operation.target.values(),
                        operation.target_expected_version,
                        successor_plan_id,
                        successor_plan_version,
                        successor_run_id,
                        successor_attempt_id,
                        operation.affected_attempt_id
                        or (target_id if target_column == "attempt_id" else None),
                        runtime_command_id,
                        operation.placement_id,
                        operation.payload_digest,
                        json.dumps(operation.payload),
                        operation.requested_at,
                    ),
                )
                self._link_operation_facts(connection, operation, transition_ordinal)
                result = WorkflowControlOperationResult(
                    False,
                    kind,
                    operation.control_command_id,
                    target_id,
                    target_version,
                    operation.intervention_id,
                    transition_id,
                    approval_decision_id,
                    successor_attempt_id,
                    successor_run_id,
                    runtime_command_id,
                    successor_plan_id,
                    successor_plan_version,
                    operation.evidence_ids
                    + tuple(
                        item["evidence_record_id"]
                        for item in operation.evidence_records
                    ),
                    operation.outcome_ids
                    + tuple(item["outcome_id"] for item in operation.outcome_records),
                )
                record = result.record()
                connection.execute(
                    "UPDATE execution_authority.control_commands SET result_record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND control_command_id=%s",
                    (json.dumps(record), *key[:2], operation.control_command_id),
                )
                connection.execute(
                    "UPDATE execution_authority.idempotency_claims SET state='COMPLETED',intervention_id=%s,control_command_id=%s,result_identity=%s,result_record=%s::jsonb,completed_at=now() WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key=%s",
                    (
                        operation.intervention_id,
                        operation.control_command_id,
                        operation.control_command_id,
                        json.dumps(record),
                        *key,
                    ),
                )
                readback = connection.execute(
                    "SELECT result_record FROM execution_authority.control_commands WHERE namespace=%s AND security_domain=%s AND control_command_id=%s",
                    (*key[:2], operation.control_command_id),
                ).fetchone()
                if readback is None or readback["result_record"] != record:
                    raise WorkflowControlConflict("AUTHORITATIVE_READBACK_MISMATCH")
                return result
        except WorkflowControlError:
            raise
        except PsycopgError as exc:
            raise WorkflowControlConflict("WORKFLOW_CONTROL_CONFLICT") from exc

    @staticmethod
    def _operation_result(
        record: dict[str, Any], *, replayed: bool
    ) -> WorkflowControlOperationResult:
        if not record:
            raise WorkflowControlConflict("AUTHORITATIVE_READBACK_MISMATCH")
        return WorkflowControlOperationResult(
            replayed,
            AtomicCommandType(record["command_type"]),
            record["control_command_id"],
            record["target_id"],
            record["target_version"],
            record.get("intervention_id"),
            record.get("transition_id"),
            record.get("approval_decision_id"),
            record.get("successor_attempt_id"),
            record.get("successor_workflow_run_id"),
            record.get("runtime_command_id"),
            record.get("successor_plan_id"),
            record.get("successor_plan_version"),
            tuple(record.get("evidence_ids", ())),
            tuple(record.get("outcome_ids", ())),
        )

    @staticmethod
    def _persist_correction(
        connection: Any, operation: WorkflowControlOperation
    ) -> tuple[str, int]:
        correction = operation.correction
        successor = operation.successor_plan
        if (
            correction is None
            or successor is None
            or operation.plan_id is None
            or operation.plan_version is None
            or operation.plan_digest is None
            or successor.scope != operation.scope
            or successor.status is not PlanStatus.PENDING_APPROVAL
            or successor.predecessor_plan_id != operation.plan_id
            or successor.predecessor_plan_version != operation.plan_version
            or successor.source_plan_revision != operation.plan_version
            or successor.source_plan_digest != operation.plan_digest
            or correction.predecessor_plan_id != operation.plan_id
            or correction.predecessor_plan_version != operation.plan_version
            or correction.successor_plan_id != successor.plan_id
            or correction.successor_plan_version != successor.plan_version
            or correction.actor_id != operation.actor_id
            or correction.authority_classification != successor.authority_classification
            or correction.reason_category != successor.correction_reason_category
        ):
            raise WorkflowControlConflict("EXACT_SUCCESSOR_PLAN_REQUIRED")
        predecessor = connection.execute(
            "SELECT * FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s FOR UPDATE",
            (
                operation.scope.namespace,
                operation.scope.security_domain,
                operation.plan_id,
                operation.plan_version,
            ),
        ).fetchone()
        expected_plan_version = operation.payload.get("expected_plan_aggregate_version")
        if (
            predecessor is None
            or predecessor["plan_digest"] != operation.plan_digest
            or predecessor["aggregate_version"] != expected_plan_version
            or predecessor["status"]
            in {"SUPERSEDED", "REJECTED", "CANCELLED", "INVALIDATED"}
            or successor.workflow_definition_id != predecessor["workflow_definition_id"]
        ):
            raise WorkflowControlConflict("SOURCE_PLAN_NOT_CORRECTABLE")
        connection.execute(
            "INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,predecessor_plan_id,predecessor_plan_version,workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,aggregate_version,plan_digest,canonical_bytes,created_at,updated_at,source_plan_revision,source_plan_digest,actor_id,authority_classification,correction_reason_category) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                successor.scope.namespace,
                successor.scope.security_domain,
                successor.plan_id,
                successor.plan_version,
                successor.predecessor_plan_id,
                successor.predecessor_plan_version,
                successor.workflow_definition_id,
                successor.workflow_definition_revision_id,
                successor.workflow_definition_digest,
                successor.status.value,
                successor.aggregate_version,
                successor.plan_digest,
                successor.canonical_bytes,
                successor.created_at,
                successor.updated_at,
                successor.source_plan_revision,
                successor.source_plan_digest,
                successor.actor_id,
                successor.authority_classification,
                successor.correction_reason_category,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.plan_corrections(namespace,security_domain,correction_id,predecessor_plan_id,predecessor_plan_version,successor_plan_id,successor_plan_version,actor_id,authority_classification,reason_category,correction_digest,normalized_correction,corrected_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (
                operation.scope.namespace,
                operation.scope.security_domain,
                correction.correction_id,
                correction.predecessor_plan_id,
                correction.predecessor_plan_version,
                correction.successor_plan_id,
                correction.successor_plan_version,
                correction.actor_id,
                correction.authority_classification,
                correction.reason_category,
                correction.digest,
                json.dumps(correction.normalized_correction),
                correction.corrected_at,
            ),
        )
        changed = connection.execute(
            "UPDATE execution_authority.plans SET status='SUPERSEDED',aggregate_version=aggregate_version+1,updated_at=%s WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s AND aggregate_version=%s RETURNING aggregate_version",
            (
                operation.requested_at,
                operation.scope.namespace,
                operation.scope.security_domain,
                operation.plan_id,
                operation.plan_version,
                expected_plan_version,
            ),
        ).fetchone()
        if changed is None:
            raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
        return successor.plan_id, successor.plan_version

    @staticmethod
    def _complete_terminal_target(
        connection: Any,
        operation: WorkflowControlOperation,
        target_column: str,
        target_id: str,
        target: dict[str, Any],
    ) -> int:
        allowed = {
            "workflow_run_id": {"SUCCEEDED", "FAILED", "CANCELLED"},
            "task_run_id": {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"},
            "attempt_id": {"SUCCEEDED", "FAILED", "CANCELLED"},
        }
        if (
            operation.terminal_state not in allowed[target_column]
            or target["control_state"]
            in {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED", "RECOVERY_REQUIRED"}
            or len(operation.outcome_records) != 1
            or not operation.evidence_records
        ):
            raise WorkflowControlConflict("ACTUAL_TERMINAL_RESULT_REQUIRED")
        table, id_column = _TARGETS[target_column]
        row = connection.execute(
            f"UPDATE execution_authority.{table} SET control_state=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND {id_column}=%s AND aggregate_version=%s RETURNING aggregate_version",
            (
                operation.terminal_state,
                operation.scope.namespace,
                operation.scope.security_domain,
                target_id,
                operation.target_expected_version,
            ),
        ).fetchone()
        if row is None:
            raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
        return row["aggregate_version"]

    @staticmethod
    def _create_operation_facts(
        connection: Any,
        operation: WorkflowControlOperation,
        target_column: str,
        target_id: str,
    ) -> None:
        if (
            operation.outcome_records
            and operation.command_type
            is not AtomicCommandType.COMPLETE_EXECUTION_WITH_OUTCOME
        ):
            raise WorkflowControlConflict("OUTCOME_ONLY_FOR_TERMINAL_COMPLETION")
        prohibited = {
            "prompt",
            "credentials",
            "credential",
            "request_body",
            "logs",
            "log",
            "diagnostic_text",
            "secret",
            "token",
        }

        def safe(value: Any) -> bool:
            if isinstance(value, dict):
                return not any(
                    term in str(key).lower() for key in value for term in prohibited
                ) and all(safe(item) for item in value.values())
            if isinstance(value, (list, tuple)):
                return all(safe(item) for item in value)
            return True

        for evidence in operation.evidence_records:
            required = {
                "evidence_record_id",
                "platform_execution_identity",
                "workflow_identity",
                "task_identity",
                "attempt_ordinal",
                "event_ordinal",
                "event_type",
                "occurred_at",
                "recorded_at",
                "payload_digest",
                "canonical_bytes",
                "record",
            }
            canonical_bytes = json.dumps(
                evidence["record"], sort_keys=True, separators=(",", ":")
            ).encode()
            if (
                not required <= evidence.keys()
                or not safe(evidence["record"])
                or evidence["canonical_bytes"] != canonical_bytes
                or evidence["payload_digest"]
                != hashlib.sha256(canonical_bytes).hexdigest()
            ):
                raise WorkflowControlConflict("INVALID_MINIMUM_DISCLOSURE_EVIDENCE")
            connection.execute(
                "INSERT INTO execution_authority.execution_evidence(evidence_record_id,schema_version,namespace,security_domain,platform_execution_identity,workflow_identity,task_identity,attempt_ordinal,event_ordinal,event_type,occurred_at,recorded_at,payload_digest,canonical_bytes,record) VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    evidence["evidence_record_id"],
                    operation.scope.namespace,
                    operation.scope.security_domain,
                    evidence["platform_execution_identity"],
                    evidence["workflow_identity"],
                    evidence["task_identity"],
                    evidence["attempt_ordinal"],
                    evidence["event_ordinal"],
                    evidence["event_type"],
                    evidence["occurred_at"],
                    evidence["recorded_at"],
                    evidence["payload_digest"],
                    evidence["canonical_bytes"],
                    json.dumps(evidence["record"]),
                ),
            )
        for outcome in operation.outcome_records:
            if not safe(outcome.get("record", {})) or outcome.get(
                "digest"
            ) != canonical_digest(outcome.get("record", {})):
                raise WorkflowControlConflict("INVALID_MINIMUM_DISCLOSURE_OUTCOME")
            kind = {
                "workflow_run_id": "RUN",
                "task_run_id": "TASK_RUN",
                "attempt_id": "ATTEMPT",
            }[target_column]
            if (
                outcome.get("terminal_target_id") != target_id
                or outcome.get("terminal_state") != operation.terminal_state
            ):
                raise WorkflowControlConflict("ACTUAL_TERMINAL_RESULT_REQUIRED")
            if target_column == "workflow_run_id":
                run_id, task_id, attempt_id = target_id, None, None
            elif target_column == "task_run_id":
                row = connection.execute(
                    "SELECT workflow_run_id FROM execution_authority.task_runs WHERE namespace=%s AND security_domain=%s AND task_run_id=%s",
                    (
                        operation.scope.namespace,
                        operation.scope.security_domain,
                        target_id,
                    ),
                ).fetchone()
                run_id, task_id, attempt_id = row["workflow_run_id"], target_id, None
            else:
                row = connection.execute(
                    "SELECT tr.workflow_run_id,a.task_run_id FROM execution_authority.attempts a JOIN execution_authority.task_runs tr USING(namespace,security_domain,task_run_id) WHERE a.namespace=%s AND a.security_domain=%s AND a.attempt_id=%s",
                    (
                        operation.scope.namespace,
                        operation.scope.security_domain,
                        target_id,
                    ),
                ).fetchone()
                run_id, task_id, attempt_id = (
                    row["workflow_run_id"],
                    row["task_run_id"],
                    target_id,
                )
            connection.execute(
                "INSERT INTO execution_authority.outcomes(namespace,security_domain,outcome_id,workflow_run_id,digest,record,task_run_id,attempt_id,terminal_target_kind,terminal_target_id,terminal_state) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)",
                (
                    operation.scope.namespace,
                    operation.scope.security_domain,
                    outcome["outcome_id"],
                    run_id,
                    outcome["digest"],
                    json.dumps(outcome["record"]),
                    task_id,
                    attempt_id,
                    kind,
                    target_id,
                    operation.terminal_state,
                ),
            )

    @staticmethod
    def _persist_plan_operation(
        connection: Any,
        operation: WorkflowControlOperation,
        target_column: str,
        target: dict[str, Any],
    ) -> tuple[int, str]:
        if (
            target_column != "workflow_run_id"
            or operation.approval is None
            or operation.plan_id is None
            or operation.plan_version is None
            or operation.plan_digest is None
        ):
            raise WorkflowControlConflict("EXACT_PLAN_APPROVAL_REQUIRED")
        plan = connection.execute(
            "SELECT status,aggregate_version,plan_digest FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s FOR UPDATE",
            (
                operation.scope.namespace,
                operation.scope.security_domain,
                operation.plan_id,
                operation.plan_version,
            ),
        ).fetchone()
        if (
            plan is None
            or plan["status"] != "PENDING_APPROVAL"
            or plan["plan_digest"] != operation.plan_digest
            or operation.approval.plan_digest != operation.plan_digest
            or operation.approval.plan_id != operation.plan_id
            or operation.approval.plan_version != operation.plan_version
        ):
            raise WorkflowControlConflict("EXACT_PLAN_APPROVAL_REQUIRED")
        wanted = (
            "APPROVE"
            if operation.command_type is AtomicCommandType.APPROVE_AND_CONTINUE
            else "REJECT"
        )
        if operation.approval.decision != wanted:
            raise WorkflowControlConflict("APPROVAL_DECISION_MISMATCH")
        connection.execute(
            "INSERT INTO execution_authority.plan_approval_decisions(namespace,security_domain,approval_decision_id,plan_id,plan_version,plan_digest,ordinal,decision,actor_id,authority_basis,reason_category,decision_digest,decided_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                operation.scope.namespace,
                operation.scope.security_domain,
                operation.approval.approval_decision_id,
                operation.plan_id,
                operation.plan_version,
                operation.plan_digest,
                operation.approval.ordinal,
                wanted,
                operation.approval.actor_id,
                operation.approval.authority_basis,
                operation.approval.reason_category,
                operation.approval.decision_digest,
                operation.approval.decided_at,
            ),
        )
        connection.execute(
            "UPDATE execution_authority.plans SET status=%s,aggregate_version=aggregate_version+1,updated_at=%s WHERE namespace=%s AND security_domain=%s AND plan_id=%s AND plan_version=%s AND aggregate_version=%s",
            (
                "APPROVED" if wanted == "APPROVE" else "REJECTED",
                operation.requested_at,
                operation.scope.namespace,
                operation.scope.security_domain,
                operation.plan_id,
                operation.plan_version,
                plan["aggregate_version"],
            ),
        )
        version = target["aggregate_version"]
        if wanted == "APPROVE":
            if target["control_state"] != "PAUSED":
                raise WorkflowControlConflict("RUN_NOT_CONTINUABLE")
            row = connection.execute(
                "UPDATE execution_authority.workflow_runs SET control_state='RESUME_REQUESTED',aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s AND aggregate_version=%s RETURNING aggregate_version",
                (
                    operation.scope.namespace,
                    operation.scope.security_domain,
                    operation.target.workflow_run_id,
                    operation.target_expected_version,
                ),
            ).fetchone()
            if row is None:
                raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
            version = row["aggregate_version"]
        return version, operation.approval.approval_decision_id

    @staticmethod
    def _validate_runtime_replacement(
        connection: Any,
        operation: WorkflowControlOperation,
        scope: tuple[str, str],
        target_column: str,
        target_id: str,
    ) -> str:
        if (
            target_column != "attempt_id"
            or operation.affected_attempt_id != target_id
            or operation.placement_id is None
            or operation.runtime_command_id is None
        ):
            raise WorkflowControlConflict("RUNTIME_REPLACEMENT_LINKAGE_REQUIRED")
        placement = connection.execute(
            "SELECT pr.attempt_id,pd.runtime_instance_id FROM execution_authority.placement_decisions pd JOIN execution_authority.placement_requests pr ON pr.namespace=pd.namespace AND pr.security_domain=pd.security_domain AND pr.request_id=pd.request_id WHERE pd.namespace=%s AND pd.security_domain=%s AND pd.placement_id=%s AND pd.decision='PLACED'",
            (*scope, operation.placement_id),
        ).fetchone()
        command = connection.execute(
            "SELECT runtime_instance_id FROM execution_authority.desired_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (*scope, operation.runtime_command_id),
        ).fetchone()
        if (
            placement is None
            or command is None
            or placement["attempt_id"] != target_id
            or placement["runtime_instance_id"] != command["runtime_instance_id"]
        ):
            raise WorkflowControlConflict("INELIGIBLE_PLACEMENT")
        return operation.runtime_command_id

    @staticmethod
    def _link_operation_facts(
        connection: Any, operation: WorkflowControlOperation, transition_ordinal: int
    ) -> None:
        evidence_ids = operation.evidence_ids + tuple(
            item["evidence_record_id"] for item in operation.evidence_records
        )
        outcome_ids = operation.outcome_ids + tuple(
            item["outcome_id"] for item in operation.outcome_records
        )
        for ordinal, evidence_id in enumerate(evidence_ids, 1):
            connection.execute(
                "INSERT INTO execution_authority.intervention_evidence_links(namespace,security_domain,intervention_id,transition_ordinal,control_command_id,ordinal,evidence_record_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    operation.scope.namespace,
                    operation.scope.security_domain,
                    operation.intervention_id,
                    transition_ordinal,
                    operation.control_command_id,
                    ordinal,
                    evidence_id,
                ),
            )
        for ordinal, outcome_id in enumerate(outcome_ids, 1):
            connection.execute(
                "INSERT INTO execution_authority.intervention_outcome_links(namespace,security_domain,intervention_id,transition_ordinal,control_command_id,ordinal,outcome_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    operation.scope.namespace,
                    operation.scope.security_domain,
                    operation.intervention_id,
                    transition_ordinal,
                    operation.control_command_id,
                    ordinal,
                    outcome_id,
                ),
            )

    def read_linked_evidence(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[str, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT evidence_record_id FROM execution_authority.intervention_evidence_links WHERE namespace=%s AND security_domain=%s AND intervention_id=%s ORDER BY transition_ordinal,ordinal,evidence_record_id",
                (scope.namespace, scope.security_domain, intervention_id),
            ).fetchall()
        return tuple(row["evidence_record_id"] for row in rows)

    def read_linked_outcomes(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[str, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT outcome_id FROM execution_authority.intervention_outcome_links WHERE namespace=%s AND security_domain=%s AND intervention_id=%s ORDER BY transition_ordinal,ordinal,outcome_id",
                (scope.namespace, scope.security_domain, intervention_id),
            ).fetchall()
        return tuple(row["outcome_id"] for row in rows)

    def compare_and_swap_target(
        self,
        scope: ScopeIdentity,
        target_kind: str,
        target_id: str,
        target_state: str,
        *,
        expected_version: int,
    ) -> int:
        if target_kind not in _TARGETS:
            raise WorkflowControlConflict("INVALID_TARGET_KIND")
        table, id_column = _TARGETS[target_kind]
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                f"UPDATE execution_authority.{table} SET control_state=%s,aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND {id_column}=%s AND aggregate_version=%s RETURNING aggregate_version",
                (
                    target_state,
                    scope.namespace,
                    scope.security_domain,
                    target_id,
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise WorkflowControlConflict("STALE_AGGREGATE_VERSION")
        return row["aggregate_version"]

    def lookup_idempotency(
        self,
        scope: ScopeIdentity,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            return connection.execute(
                "SELECT payload_digest,state,intervention_id,control_command_id,result_identity FROM execution_authority.idempotency_claims WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    actor_id,
                    command_type,
                    idempotency_key,
                ),
            ).fetchone()

    def read_pending_commands(self, scope: ScopeIdentity) -> tuple[dict[str, Any], ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT control_command_id,command_type,intervention_id,transition_ordinal,canonical_record,requested_at FROM execution_authority.control_commands WHERE namespace=%s AND security_domain=%s AND runtime_command_id IS NULL ORDER BY requested_at,control_command_id",
                (scope.namespace, scope.security_domain),
            ).fetchall()
        return tuple(rows)

    def read_successor_runs(
        self, scope: ScopeIdentity, workflow_run_id: str
    ) -> tuple[str, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT workflow_run_id FROM execution_authority.workflow_runs WHERE namespace=%s AND security_domain=%s AND (predecessor_workflow_run_id=%s OR correction_of_workflow_run_id=%s) ORDER BY workflow_run_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    workflow_run_id,
                    workflow_run_id,
                ),
            ).fetchall()
        return tuple(row["workflow_run_id"] for row in rows)

    def read_successor_attempts(
        self, scope: ScopeIdentity, attempt_id: str
    ) -> tuple[str, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT attempt_id FROM execution_authority.attempts WHERE namespace=%s AND security_domain=%s AND predecessor_attempt_id=%s ORDER BY attempt_ordinal,attempt_id",
                (scope.namespace, scope.security_domain, attempt_id),
            ).fetchall()
        return tuple(row["attempt_id"] for row in rows)

    @staticmethod
    def _plan(scope: ScopeIdentity, row: dict[str, Any]) -> PlanRecord:
        return PlanRecord(
            scope,
            row["plan_id"],
            row["plan_version"],
            row["workflow_definition_id"],
            row["workflow_definition_revision_id"],
            row["workflow_definition_digest"],
            PlanStatus(row["status"]),
            row["aggregate_version"],
            row["plan_digest"],
            bytes(row["canonical_bytes"]),
            row["created_at"],
            row["updated_at"],
            row["predecessor_plan_id"],
            row["predecessor_plan_version"],
            row.get("source_plan_revision"),
            row.get("source_plan_digest"),
            row.get("actor_id"),
            row.get("authority_classification"),
            row.get("correction_reason_category"),
        )

    @staticmethod
    def _insert_plan(connection: Any, plan: PlanRecord) -> None:
        connection.execute(
            "INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,predecessor_plan_id,predecessor_plan_version,workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,aggregate_version,plan_digest,canonical_bytes,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                plan.scope.namespace,
                plan.scope.security_domain,
                plan.plan_id,
                plan.plan_version,
                plan.predecessor_plan_id,
                plan.predecessor_plan_version,
                plan.workflow_definition_id,
                plan.workflow_definition_revision_id,
                plan.workflow_definition_digest,
                plan.status.value,
                plan.aggregate_version,
                plan.plan_digest,
                plan.canonical_bytes,
                plan.created_at,
                plan.updated_at,
            ),
        )

    @staticmethod
    def _target(request: InterventionRequest) -> tuple[str, str]:
        values = {
            "workflow_run_id": request.target.workflow_run_id,
            "task_run_id": request.target.task_run_id,
            "attempt_id": request.target.attempt_id,
        }
        return next((key, value) for key, value in values.items() if value is not None)

    def _insert_request(
        self, connection: Any, scope: ScopeIdentity, request: InterventionRequest
    ) -> None:
        values = request.target.values()
        connection.execute(
            "INSERT INTO execution_authority.interventions(namespace,security_domain,intervention_id,fact_digest,fact,workflow_run_id,task_run_id,attempt_id,action_type,reason_category,actor_id,authority_basis,expected_target_version,current_state,aggregate_version,requested_at) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,'REQUESTED',1,%s)",
            (
                scope.namespace,
                scope.security_domain,
                request.intervention_id,
                request.digest,
                json.dumps(request.fact),
                *values,
                request.action_type,
                request.reason_category,
                request.actor_id,
                request.authority_basis,
                request.expected_target_version,
                request.requested_at,
            ),
        )

    @staticmethod
    def _insert_transition(
        connection: Any, scope: ScopeIdentity, transition: InterventionTransition
    ) -> None:
        connection.execute(
            "INSERT INTO execution_authority.intervention_transitions(namespace,security_domain,intervention_id,ordinal,transition_id,from_state,to_state,actor_id,authority_basis,reason_category,transition_digest,transitioned_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                transition.intervention_id,
                transition.ordinal,
                transition.transition_id,
                None if transition.from_state is None else transition.from_state.value,
                transition.to_state.value,
                transition.actor_id,
                transition.authority_basis,
                transition.reason_category,
                transition.digest,
                transition.transitioned_at,
            ),
        )

    @staticmethod
    def _validate_transition(transition: InterventionTransition) -> None:
        if transition.to_state not in _TRANSITIONS.get(transition.from_state, set()):
            raise WorkflowControlConflict("INVALID_INTERVENTION_TRANSITION")

    @staticmethod
    def _claim(
        connection: Any, command: AtomicControlCommand
    ) -> AtomicControlResult | None:
        key = (
            command.scope.namespace,
            command.scope.security_domain,
            command.request.actor_id,
            command.command_type,
            command.idempotency_key,
        )
        row = connection.execute(
            "SELECT * FROM execution_authority.idempotency_claims WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_type=%s AND idempotency_key=%s FOR UPDATE",
            key,
        ).fetchone()
        if row is not None:
            if row["payload_digest"] != command.payload_digest:
                raise WorkflowControlConflict("IDEMPOTENCY_PAYLOAD_MISMATCH")
            if row["state"] == "IN_PROGRESS":
                raise WorkflowControlConflict("COMMAND_IN_PROGRESS")
            return AtomicControlResult(
                True,
                row["intervention_id"],
                command.transition.transition_id,
                row["control_command_id"],
                int(row["result_identity"]),
            )
        connection.execute(
            "INSERT INTO execution_authority.idempotency_claims(namespace,security_domain,actor_id,command_type,idempotency_key,payload_digest,state,claimed_at,retain_until) VALUES (%s,%s,%s,%s,%s,%s,'IN_PROGRESS',%s,%s)",
            (
                *key,
                command.payload_digest,
                command.request.requested_at,
                command.retain_until,
            ),
        )
        return None
