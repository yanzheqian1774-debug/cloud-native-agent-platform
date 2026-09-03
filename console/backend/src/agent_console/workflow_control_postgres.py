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
    AtomicControlCommand,
    AtomicControlResult,
    InterventionRequest,
    InterventionState,
    InterventionTransition,
    PlanRecord,
    PlanStatus,
    ScopeIdentity,
    WorkflowControlConflict,
    WorkflowControlError,
    WorkflowControlNotAuthorized,
)

ADAPTER = "workflow-control-postgresql-v1"
SCHEMA_VERSION = 9
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
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='15s'")
                prior = connection.execute(
                    "SELECT 1 FROM execution_authority.schema_migrations WHERE version=8"
                ).fetchone()
                if prior is None:
                    raise WorkflowControlError("MIGRATION_0008_REQUIRED")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM execution_authority.schema_migrations WHERE version=9"
                ).fetchone()
                expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
                if row is None:
                    connection.execute(
                        "INSERT INTO execution_authority.schema_migrations(version,checksum,adapter) VALUES (9,%s,%s)",
                        (self.migration_checksum, ADAPTER),
                    )
                elif row != expected:
                    raise WorkflowControlError("WORKFLOW_CONTROL_SCHEMA_INCOMPATIBLE")
        except WorkflowControlError:
            raise
        except PsycopgError as exc:
            raise WorkflowControlError(
                "WORKFLOW_CONTROL_MIGRATION_UNAVAILABLE"
            ) from exc
        self.compatibility()

    def compatibility(self) -> None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT checksum,adapter FROM execution_authority.schema_migrations WHERE version=9"
            ).fetchone()
            newer = connection.execute(
                "SELECT 1 FROM execution_authority.schema_migrations WHERE version>9 LIMIT 1"
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
        if (
            row != {"checksum": self.migration_checksum, "adapter": ADAPTER}
            or newer
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
