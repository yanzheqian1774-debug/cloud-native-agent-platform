# ruff: noqa: E501
"""PostgreSQL primary adapter for v0.2.3 Execution Authority Track A."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import Any

from agent_core.execution_contract import (
    AgentInstanceId,
    AssignmentId,
    AssignmentIdentity,
    AttemptId,
    AttemptIdentity,
    CommandId,
    CommandResult,
    DigitalEmployeeInstanceId,
    ExecutionIdentityAggregate,
    Generation,
    InterventionId,
    ObservationId,
    OutcomeId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeHealth,
    RuntimeInstanceId,
    RuntimeObservation,
    RuntimeObservedStateKind,
    RuntimeReadiness,
    ScopeIdentity,
    TaskRunId,
    TaskRunIdentity,
    WorkflowRunId,
    WorkflowRunIdentity,
    canonical_bytes,
    canonical_digest,
)
from agent_core.execution_repositories import AppendDisposition, PlacementResult
from psycopg.errors import DeadlockDetected, SerializationFailure
from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .execution_domain import (
    CommandResultFact,
    CutoverState,
    ExecutionConflict,
    ExecutionPersistenceError,
    ExecutionSchemaIncompatible,
    ExecutionStorageUnavailable,
    ImportCheckpoint,
    VersionedAggregate,
    Writer,
)

ADAPTER = "execution-authority-postgresql-v1"
SCHEMA_VERSION = 8
__all__ = [
    "Generation",
    "PlacementDecisionKind",
    "RuntimeDesiredStateKind",
    "RuntimeHealth",
    "RuntimeObservedStateKind",
    "RuntimeReadiness",
]


class PostgresExecutionAuthorityRepository:
    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout: float = 5.0,
        transaction_retries: int = 2,
    ) -> None:
        if not database_url or not 1 <= min_pool_size <= max_pool_size <= 16:
            raise ExecutionStorageUnavailable("EXECUTION_STORAGE_UNAVAILABLE")
        if not 0 < timeout <= 30 or not 0 <= transaction_retries <= 3:
            raise ExecutionStorageUnavailable("EXECUTION_STORAGE_UNAVAILABLE")
        self.migration_path = migration_path
        self.transaction_retries = transaction_retries
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
            raise ExecutionStorageUnavailable("EXECUTION_STORAGE_UNAVAILABLE") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='10s'")
                connection.execute("SET LOCAL lock_timeout='3s'")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM execution_authority.schema_migrations WHERE version=8"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO execution_authority.schema_migrations(version,checksum,adapter) VALUES (8,%s,%s)",
                        (self.migration_checksum, ADAPTER),
                    )
                elif row != {"checksum": self.migration_checksum, "adapter": ADAPTER}:
                    raise ExecutionSchemaIncompatible("EXECUTION_SCHEMA_INCOMPATIBLE")
        except ExecutionSchemaIncompatible:
            raise
        except PsycopgError as exc:
            raise ExecutionStorageUnavailable(
                "EXECUTION_MIGRATION_UNAVAILABLE"
            ) from exc
        self.compatibility()

    def compatibility(self) -> None:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT checksum,adapter FROM execution_authority.schema_migrations WHERE version=8"
                ).fetchone()
                newer = connection.execute(
                    "SELECT 1 FROM execution_authority.schema_migrations WHERE version>8 LIMIT 1"
                ).fetchone()
                columns = {
                    (item["table_name"], item["column_name"])
                    for item in connection.execute(
                        "SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='execution_authority'"
                    ).fetchall()
                }
                required_columns = {
                    ("attempts", "aggregate_digest"),
                    ("execution_evidence", "import_set_identity"),
                    ("evidence_cutover", "checkpoint_version"),
                    ("agent_instances", "updated_at"),
                    ("runtime_instances", "updated_at"),
                }
                relationship_foreign_keys = connection.execute(
                    "SELECT COUNT(*) AS count FROM information_schema.table_constraints WHERE constraint_schema='execution_authority' AND constraint_type='FOREIGN KEY' AND table_name IN ('workflow_runs','interventions','outcomes')"
                ).fetchone()["count"]
                if (
                    row != {"checksum": self.migration_checksum, "adapter": ADAPTER}
                    or newer
                    or not required_columns <= columns
                    or relationship_foreign_keys < 6
                ):
                    raise ExecutionSchemaIncompatible("EXECUTION_SCHEMA_INCOMPATIBLE")
        except ExecutionSchemaIncompatible:
            raise
        except PsycopgError as exc:
            raise ExecutionSchemaIncompatible("EXECUTION_SCHEMA_INCOMPATIBLE") from exc

    def _transaction(self, operation: Callable[[Any], Any]) -> Any:
        for attempt in range(self.transaction_retries + 1):
            try:
                with self.pool.connection() as connection, connection.transaction():
                    connection.execute("SET LOCAL statement_timeout='10s'")
                    return operation(connection)
            except (SerializationFailure, DeadlockDetected) as exc:
                if attempt == self.transaction_retries:
                    raise ExecutionStorageUnavailable(
                        "EXECUTION_RETRY_EXHAUSTED"
                    ) from exc
                sleep(0.01 * (attempt + 1))
            except ExecutionPersistenceError:
                raise
            except PsycopgError as exc:
                raise ExecutionConflict("EXECUTION_CONFLICT") from exc
        raise AssertionError("unreachable")

    def create_aggregate(
        self, kind: str, aggregate: VersionedAggregate
    ) -> VersionedAggregate:
        table, id_column = self._aggregate_table(kind)
        payload = json.dumps(aggregate.record)
        mandatory = self._aggregate_mandatory_values(kind, aggregate.record)
        columns = ",".join(mandatory)
        placeholders = ",".join("%s" for _ in mandatory)

        def operation(connection):
            connection.execute(
                f"INSERT INTO execution_authority.{table}(namespace,security_domain,{id_column},aggregate_version,record,{columns}) VALUES (%s,%s,%s,%s,%s::jsonb,{placeholders})",
                (
                    aggregate.scope.namespace,
                    aggregate.scope.security_domain,
                    aggregate.aggregate_id,
                    aggregate.aggregate_version,
                    payload,
                    *mandatory.values(),
                ),
            )
            return aggregate

        return self._transaction(operation)

    def get_aggregate(
        self, kind: str, scope: ScopeIdentity, aggregate_id: str
    ) -> VersionedAggregate | None:
        table, id_column = self._aggregate_table(kind)
        with self.pool.connection() as connection:
            row = connection.execute(
                f"SELECT aggregate_version,record FROM execution_authority.{table} "
                f"WHERE namespace=%s AND security_domain=%s AND {id_column}=%s",
                (scope.namespace, scope.security_domain, aggregate_id),
            ).fetchone()
        if row is None:
            return None
        return VersionedAggregate(
            scope, aggregate_id, row["aggregate_version"], row["record"]
        )

    def replace_aggregate(
        self, kind: str, aggregate: VersionedAggregate, *, expected_version: int
    ) -> VersionedAggregate:
        table, id_column = self._aggregate_table(kind)
        mandatory = self._aggregate_mandatory_values(kind, aggregate.record)
        assignments = ",".join(f"{name}=%s" for name in mandatory)

        def operation(connection):
            row = connection.execute(
                f"UPDATE execution_authority.{table} SET aggregate_version=%s,record=%s::jsonb,{assignments},updated_at=now() WHERE namespace=%s AND security_domain=%s AND {id_column}=%s AND aggregate_version=%s RETURNING {id_column}",
                (
                    aggregate.aggregate_version,
                    json.dumps(aggregate.record),
                    *mandatory.values(),
                    aggregate.scope.namespace,
                    aggregate.scope.security_domain,
                    aggregate.aggregate_id,
                    expected_version,
                ),
            ).fetchone()
            if row is None:
                raise ExecutionConflict("STALE_EXECUTION_AGGREGATE")
            return aggregate

        return self._transaction(operation)

    @staticmethod
    def _aggregate_table(kind: str) -> tuple[str, str]:
        allowed = {
            "digital_employee_instance": (
                "digital_employee_instances",
                "digital_employee_instance_id",
            ),
            "agent_instance": ("agent_instances", "agent_instance_id"),
            "runtime_instance": ("runtime_instances", "runtime_instance_id"),
        }
        try:
            return allowed[kind]
        except KeyError as exc:
            raise ExecutionPersistenceError("EXECUTION_AGGREGATE_KIND_INVALID") from exc

    @staticmethod
    def _aggregate_mandatory_values(
        kind: str, record: dict[str, Any]
    ) -> dict[str, object]:
        requirements = {
            "digital_employee_instance": {"definition_revision_id": str},
            "agent_instance": {"agent_revision_id": str},
            "runtime_instance": {"current_generation": int},
        }
        fields = requirements[kind]
        values: dict[str, object] = {}
        for name, expected in fields.items():
            value = record.get(name)
            if type(value) is not expected or (isinstance(value, str) and not value):
                raise ExecutionPersistenceError("EXECUTION_AGGREGATE_FIELD_INVALID")
            if name == "current_generation" and value < 1:
                raise ExecutionPersistenceError("EXECUTION_AGGREGATE_FIELD_INVALID")
            values[name] = value
        if kind == "agent_instance":
            runtime_id = record.get("runtime_instance_id")
            if runtime_id is not None and not isinstance(runtime_id, str):
                raise ExecutionPersistenceError("EXECUTION_AGGREGATE_FIELD_INVALID")
            values["runtime_instance_id"] = runtime_id
        return values

    def save(
        self, scope: ScopeIdentity, aggregate: ExecutionIdentityAggregate
    ) -> ExecutionIdentityAggregate:
        if scope != aggregate.scope:
            raise ExecutionConflict("EXECUTION_IDENTITY_SCOPE_MISMATCH")
        aggregate_payload = json.loads(canonical_bytes(aggregate))["payload"]
        aggregate_digest = canonical_digest(aggregate)

        def operation(connection):
            de_id = str(aggregate.assignment.digital_employee_instance_id)
            values = (
                (
                    "digital_employee_instances",
                    "digital_employee_instance_id",
                    de_id,
                    "definition_revision_id,aggregate_version,record",
                    (
                        aggregate.workflow_run.approved_plan_revision_id,
                        1,
                        {
                            "digital_employee_instance_id": de_id,
                            "definition_revision_id": aggregate.workflow_run.approved_plan_revision_id,
                        },
                    ),
                ),
                (
                    "assignments",
                    "assignment_id",
                    str(aggregate.assignment.assignment_id),
                    "digital_employee_instance_id,approved_input_digest,record",
                    (
                        de_id,
                        canonical_digest(aggregate.assignment),
                        json.loads(canonical_bytes(aggregate.assignment))["payload"],
                    ),
                ),
                (
                    "workflow_runs",
                    "workflow_run_id",
                    str(aggregate.workflow_run.workflow_run_id),
                    "assignment_id,approved_plan_revision_id,predecessor_workflow_run_id,correction_of_workflow_run_id,record",
                    (
                        str(aggregate.workflow_run.assignment_id),
                        aggregate.workflow_run.approved_plan_revision_id,
                        None
                        if aggregate.workflow_run.predecessor_workflow_run_id is None
                        else str(aggregate.workflow_run.predecessor_workflow_run_id),
                        None
                        if aggregate.workflow_run.correction_of_workflow_run_id is None
                        else str(aggregate.workflow_run.correction_of_workflow_run_id),
                        json.loads(canonical_bytes(aggregate.workflow_run))["payload"],
                    ),
                ),
                (
                    "task_runs",
                    "task_run_id",
                    str(aggregate.task_run.task_run_id),
                    "workflow_run_id,record",
                    (
                        str(aggregate.task_run.workflow_run_id),
                        json.loads(canonical_bytes(aggregate.task_run))["payload"],
                    ),
                ),
                (
                    "attempts",
                    "attempt_id",
                    str(aggregate.attempt.attempt_id),
                    "task_run_id,predecessor_attempt_id,aggregate_digest,record",
                    (
                        str(aggregate.attempt.task_run_id),
                        None
                        if aggregate.attempt.predecessor_attempt_id is None
                        else str(aggregate.attempt.predecessor_attempt_id),
                        aggregate_digest,
                        aggregate_payload,
                    ),
                ),
            )
            for table, id_column, identity, columns, extra in values:
                placeholders = ",".join(["%s"] * (len(extra) - 1) + ["%s::jsonb"])
                connection.execute(
                    f"INSERT INTO execution_authority.{table}(namespace,security_domain,{id_column},{columns}) VALUES (%s,%s,%s,{placeholders}) ON CONFLICT DO NOTHING",
                    (
                        scope.namespace,
                        scope.security_domain,
                        identity,
                        *extra[:-1],
                        json.dumps(extra[-1]),
                    ),
                )
                stored = connection.execute(
                    f"SELECT record FROM execution_authority.{table} WHERE namespace=%s AND security_domain=%s AND {id_column}=%s",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchone()
                expected_record = extra[-1]
                if stored is None or stored["record"] != expected_record:
                    raise ExecutionConflict("EXECUTION_IDENTITY_CONFLICT")
            return aggregate

        return self._transaction(operation)

    def get_attempt(
        self, scope: ScopeIdentity, attempt_id: AttemptId
    ) -> ExecutionIdentityAggregate | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM execution_authority.attempts WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
                (scope.namespace, scope.security_domain, str(attempt_id)),
            ).fetchone()
        if row is None:
            return None
        payload = row["record"]
        assignment = payload["assignment"]
        workflow = payload["workflow_run"]
        task = payload["task_run"]
        attempt = payload["attempt"]
        return ExecutionIdentityAggregate(
            scope,
            AssignmentIdentity(
                AssignmentId(assignment["assignment_id"]),
                DigitalEmployeeInstanceId(assignment["digital_employee_instance_id"]),
            ),
            WorkflowRunIdentity(
                WorkflowRunId(workflow["workflow_run_id"]),
                AssignmentId(workflow["assignment_id"]),
                workflow["approved_plan_revision_id"],
                None
                if workflow["predecessor_workflow_run_id"] is None
                else WorkflowRunId(workflow["predecessor_workflow_run_id"]),
                None
                if workflow["correction_of_workflow_run_id"] is None
                else WorkflowRunId(workflow["correction_of_workflow_run_id"]),
            ),
            TaskRunIdentity(
                TaskRunId(task["task_run_id"]), WorkflowRunId(task["workflow_run_id"])
            ),
            AttemptIdentity(
                AttemptId(attempt["attempt_id"]),
                TaskRunId(attempt["task_run_id"]),
                None
                if attempt["predecessor_attempt_id"] is None
                else AttemptId(attempt["predecessor_attempt_id"]),
            ),
        )

    def decide(
        self,
        scope: ScopeIdentity,
        request: PlacementRequest,
        decision: PlacementDecision,
    ) -> PlacementResult:
        if scope != request.scope or decision.request_id != request.request_id:
            raise ExecutionConflict("PLACEMENT_SCOPE_OR_REQUEST_MISMATCH")

        def operation(connection):
            existing = connection.execute(
                "SELECT request_digest FROM execution_authority.placement_requests WHERE namespace=%s AND security_domain=%s AND request_id=%s FOR UPDATE",
                (scope.namespace, scope.security_domain, str(request.request_id)),
            ).fetchone()
            if existing and existing["request_digest"] != request.digest:
                raise ExecutionConflict("PLACEMENT_REQUEST_CONFLICT")
            if not existing:
                connection.execute(
                    "INSERT INTO execution_authority.placement_requests(namespace,security_domain,request_id,request_digest,canonical_bytes,attempt_id,agent_instance_id,requested_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        str(request.request_id),
                        request.digest,
                        request.canonical_bytes,
                        str(request.attempt_id),
                        str(request.agent_instance_id),
                        request.requested_at,
                    ),
                )
            found = connection.execute(
                "SELECT digest,canonical_record FROM execution_authority.placement_decisions WHERE namespace=%s AND security_domain=%s AND request_id=%s",
                (scope.namespace, scope.security_domain, str(request.request_id)),
            ).fetchone()
            if found:
                if found["digest"] != decision.digest:
                    raise ExecutionConflict("PLACEMENT_DECISION_CONFLICT")
                return PlacementResult(AppendDisposition.REPLAYED, decision)
            payload = json.loads(canonical_bytes(decision))["payload"]
            connection.execute(
                "INSERT INTO execution_authority.placement_decisions(namespace,security_domain,placement_id,request_id,decision,runtime_instance_id,digest,canonical_record,decided_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(decision.placement_id),
                    str(decision.request_id),
                    decision.decision.value,
                    None
                    if decision.runtime_instance_id is None
                    else str(decision.runtime_instance_id),
                    decision.digest,
                    json.dumps(payload),
                    decision.decided_at,
                ),
            )
            return PlacementResult(AppendDisposition.APPENDED, decision)

        return self._transaction(operation)

    def get(
        self, scope: ScopeIdentity, placement_id: PlacementId
    ) -> PlacementDecision | None:
        return self._get_decision(scope, "placement_id", str(placement_id))

    def get_by_request(
        self, scope: ScopeIdentity, request_id: PlacementRequestId
    ) -> PlacementDecision | None:
        return self._get_decision(scope, "request_id", str(request_id))

    def _get_decision(self, scope: ScopeIdentity, column: str, value: str):
        with self.pool.connection() as connection:
            row = connection.execute(
                f"SELECT canonical_record FROM execution_authority.placement_decisions WHERE namespace=%s AND security_domain=%s AND {column}=%s",
                (scope.namespace, scope.security_domain, value),
            ).fetchone()
            return (
                None
                if row is None
                else PlacementDecision.from_mapping(row["canonical_record"])
            )

    def append_command(
        self, scope: ScopeIdentity, command: RuntimeDesiredState
    ) -> AppendDisposition:
        payload = json.loads(canonical_bytes(command))["payload"]
        digest = canonical_digest(command)

        def operation(connection):
            row = connection.execute(
                "SELECT command_digest FROM execution_authority.desired_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s FOR UPDATE",
                (scope.namespace, scope.security_domain, str(command.command_id)),
            ).fetchone()
            if row:
                if row["command_digest"] != digest:
                    raise ExecutionConflict("COMMAND_CONFLICT")
                return AppendDisposition.REPLAYED
            connection.execute(
                "INSERT INTO execution_authority.desired_commands(namespace,security_domain,command_id,runtime_instance_id,generation,command_digest,record,requested_at) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(command.command_id),
                    str(command.runtime_instance_id),
                    command.desired_generation.value,
                    digest,
                    json.dumps(payload),
                    command.requested_at,
                ),
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def get_command(
        self, scope: ScopeIdentity, command_id: CommandId
    ) -> RuntimeDesiredState | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM execution_authority.desired_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s",
                (scope.namespace, scope.security_domain, str(command_id)),
            ).fetchone()
            return (
                None if row is None else RuntimeDesiredState.from_mapping(row["record"])
            )

    def read_commands(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[RuntimeDesiredState, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT record FROM execution_authority.desired_commands "
                "WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s "
                "ORDER BY generation,command_id",
                (scope.namespace, scope.security_domain, str(runtime_instance_id)),
            ).fetchall()
            return tuple(
                RuntimeDesiredState.from_mapping(row["record"]) for row in rows
            )

    def append_observation(
        self, scope: ScopeIdentity, observation: RuntimeObservation
    ) -> AppendDisposition:
        payload = json.loads(canonical_bytes(observation))["payload"]
        digest = canonical_digest(observation)

        def operation(connection):
            row = connection.execute(
                "SELECT observation_digest FROM execution_authority.runtime_observations WHERE namespace=%s AND security_domain=%s AND observation_id=%s FOR UPDATE",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(observation.observation_id),
                ),
            ).fetchone()
            if row:
                if row["observation_digest"] != digest:
                    raise ExecutionConflict("OBSERVATION_CONFLICT")
                return AppendDisposition.REPLAYED
            connection.execute(
                "INSERT INTO execution_authority.runtime_observations(namespace,security_domain,observation_id,runtime_instance_id,generation,observation_digest,record,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(observation.observation_id),
                    str(observation.runtime_instance_id),
                    observation.observed_generation.value,
                    digest,
                    json.dumps(payload),
                    observation.observed_at,
                ),
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def read_observations(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[RuntimeObservation, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT record FROM execution_authority.runtime_observations WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s ORDER BY storage_sequence",
                (scope.namespace, scope.security_domain, str(runtime_instance_id)),
            ).fetchall()
            return tuple(RuntimeObservation.from_mapping(row["record"]) for row in rows)

    def get_observation(
        self, scope: ScopeIdentity, observation_id: ObservationId
    ) -> RuntimeObservation | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM execution_authority.runtime_observations WHERE namespace=%s AND security_domain=%s AND observation_id=%s",
                (scope.namespace, scope.security_domain, str(observation_id)),
            ).fetchone()
            return (
                None if row is None else RuntimeObservation.from_mapping(row["record"])
            )

    def append_command_result(
        self, scope: ScopeIdentity, fact: CommandResultFact
    ) -> AppendDisposition:
        digest = canonical_digest(fact.record)

        def operation(connection):
            existing = connection.execute(
                "SELECT fact_digest,result FROM execution_authority.command_results WHERE namespace=%s AND security_domain=%s AND command_id=%s AND ordinal=%s FOR UPDATE",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(fact.command_id),
                    fact.ordinal,
                ),
            ).fetchone()
            if existing:
                if (
                    existing["fact_digest"] != digest
                    or existing["result"] != fact.result.value
                ):
                    raise ExecutionConflict("COMMAND_RESULT_CONFLICT")
                return AppendDisposition.REPLAYED
            connection.execute(
                "INSERT INTO execution_authority.command_results(namespace,security_domain,command_id,ordinal,result,fact_digest,fact) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(fact.command_id),
                    fact.ordinal,
                    fact.result.value,
                    digest,
                    json.dumps(fact.record),
                ),
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def read_command_results(
        self, scope: ScopeIdentity, command_id: CommandId
    ) -> tuple[CommandResultFact, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT ordinal,result,fact FROM execution_authority.command_results WHERE namespace=%s AND security_domain=%s AND command_id=%s ORDER BY ordinal",
                (scope.namespace, scope.security_domain, str(command_id)),
            ).fetchall()
        return tuple(
            CommandResultFact(
                command_id, row["ordinal"], CommandResult(row["result"]), row["fact"]
            )
            for row in rows
        )

    def load_checkpoint(self) -> ImportCheckpoint:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM execution_authority.evidence_cutover WHERE singleton=true"
            ).fetchone()
            if row is None:
                raise ExecutionSchemaIncompatible("CUTOVER_CHECKPOINT_MISSING")
            return ImportCheckpoint(
                CutoverState(row["state"]),
                Writer(row["authoritative_writer"]),
                row["source_backup_identity"],
                row["source_backup_digest"],
                row["last_storage_sequence"],
                row["last_record_id"],
                row["target_high_water"],
                row["importer_version"],
                row["verification_status"],
                row["checkpoint_version"],
            )

    def replace_checkpoint(self, checkpoint: ImportCheckpoint) -> ImportCheckpoint:
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                "UPDATE execution_authority.evidence_cutover SET state=%s,authoritative_writer=%s,source_backup_identity=%s,source_backup_digest=%s,last_storage_sequence=%s,last_record_id=%s,target_high_water=%s,importer_version=%s,verification_status=%s,checkpoint_version=checkpoint_version+1,updated_at=now() WHERE singleton=true AND checkpoint_version=%s RETURNING checkpoint_version",
                (
                    checkpoint.state.value,
                    checkpoint.writer.value,
                    checkpoint.source_backup_identity,
                    checkpoint.source_backup_digest,
                    checkpoint.last_storage_sequence,
                    checkpoint.last_record_id,
                    checkpoint.target_high_water,
                    checkpoint.importer_version,
                    checkpoint.verification_status,
                    checkpoint.checkpoint_version,
                ),
            ).fetchone()
            if row is None:
                raise ExecutionConflict("CUTOVER_CHECKPOINT_CONFLICT")
        return ImportCheckpoint(
            checkpoint.state,
            checkpoint.writer,
            checkpoint.source_backup_identity,
            checkpoint.source_backup_digest,
            checkpoint.last_storage_sequence,
            checkpoint.last_record_id,
            checkpoint.target_high_water,
            checkpoint.importer_version,
            checkpoint.verification_status,
            row["checkpoint_version"],
        )

    def append_outcome(
        self,
        scope: ScopeIdentity,
        outcome_id: str,
        workflow_run_id: str,
        record: dict[str, Any],
    ) -> AppendDisposition:
        digest = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        def operation(connection):
            row = connection.execute(
                "SELECT digest,workflow_run_id FROM execution_authority.outcomes WHERE namespace=%s AND security_domain=%s AND outcome_id=%s FOR UPDATE",
                (scope.namespace, scope.security_domain, outcome_id),
            ).fetchone()
            if row:
                if row["digest"] != digest or row["workflow_run_id"] != workflow_run_id:
                    raise ExecutionConflict("OUTCOME_CONFLICT")
                return AppendDisposition.REPLAYED
            connection.execute(
                "INSERT INTO execution_authority.outcomes(namespace,security_domain,outcome_id,workflow_run_id,digest,record) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    outcome_id,
                    workflow_run_id,
                    digest,
                    json.dumps(record),
                ),
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def read_workflow(
        self, scope: ScopeIdentity, workflow_run_id: WorkflowRunId
    ) -> tuple[OutcomeId, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT outcome_id FROM execution_authority.outcomes WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s ORDER BY outcome_id",
                (scope.namespace, scope.security_domain, str(workflow_run_id)),
            ).fetchall()
        return tuple(OutcomeId(row["outcome_id"]) for row in rows)

    def append_intervention(
        self,
        scope: ScopeIdentity,
        intervention_id: str,
        record: dict[str, Any],
        *,
        runtime_instance_id: str | None = None,
        assignment_id: str | None = None,
    ) -> AppendDisposition:
        digest = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        def operation(connection):
            row = connection.execute(
                "SELECT fact_digest,runtime_instance_id,assignment_id FROM execution_authority.interventions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s FOR UPDATE",
                (scope.namespace, scope.security_domain, intervention_id),
            ).fetchone()
            if row:
                if (
                    row["fact_digest"] != digest
                    or row["runtime_instance_id"] != runtime_instance_id
                    or row["assignment_id"] != assignment_id
                ):
                    raise ExecutionConflict("INTERVENTION_CONFLICT")
                return AppendDisposition.REPLAYED
            connection.execute(
                "INSERT INTO execution_authority.interventions(namespace,security_domain,intervention_id,runtime_instance_id,assignment_id,fact_digest,fact) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    intervention_id,
                    runtime_instance_id,
                    assignment_id,
                    digest,
                    json.dumps(record),
                ),
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def read_runtime(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[InterventionId, ...]:
        return self._read_interventions(
            scope, "runtime_instance_id", str(runtime_instance_id)
        )

    def read_assignment(
        self, scope: ScopeIdentity, assignment_id: AssignmentId
    ) -> tuple[InterventionId, ...]:
        return self._read_interventions(scope, "assignment_id", str(assignment_id))

    def _read_interventions(
        self, scope: ScopeIdentity, column: str, identity: str
    ) -> tuple[InterventionId, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                f"SELECT intervention_id FROM execution_authority.interventions WHERE namespace=%s AND security_domain=%s AND {column}=%s ORDER BY storage_sequence",
                (scope.namespace, scope.security_domain, identity),
            ).fetchall()
        return tuple(InterventionId(row["intervention_id"]) for row in rows)

    def attempts_for_runtime_agent(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        agent_instance_id: AgentInstanceId,
    ) -> tuple[AttemptId, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT request.attempt_id FROM execution_authority.placement_requests request JOIN execution_authority.placement_decisions decision ON decision.namespace=request.namespace AND decision.security_domain=request.security_domain AND decision.request_id=request.request_id WHERE request.namespace=%s AND request.security_domain=%s AND request.agent_instance_id=%s AND decision.runtime_instance_id=%s ORDER BY request.attempt_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(agent_instance_id),
                    str(runtime_instance_id),
                ),
            ).fetchall()
        return tuple(AttemptId(row["attempt_id"]) for row in rows)


class PostgresRuntimeDesiredStateRepository:
    """Exact adapter for the durable RuntimeDesiredStateRepository Port."""

    def __init__(self, authority: PostgresExecutionAuthorityRepository) -> None:
        self.authority = authority

    def append(
        self, scope: ScopeIdentity, command: RuntimeDesiredState
    ) -> AppendDisposition:
        return self.authority.append_command(scope, command)

    def get(
        self, scope: ScopeIdentity, command_id: CommandId
    ) -> RuntimeDesiredState | None:
        return self.authority.get_command(scope, command_id)

    def read_runtime(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[RuntimeDesiredState, ...]:
        return self.authority.read_commands(scope, runtime_instance_id)


class PostgresRuntimeObservationRepository:
    """Exact adapter for the durable RuntimeObservationRepository Port."""

    def __init__(self, authority: PostgresExecutionAuthorityRepository) -> None:
        self.authority = authority

    def append(
        self, scope: ScopeIdentity, observation: RuntimeObservation
    ) -> AppendDisposition:
        return self.authority.append_observation(scope, observation)

    def get(
        self, scope: ScopeIdentity, observation_id: ObservationId
    ) -> RuntimeObservation | None:
        return self.authority.get_observation(scope, observation_id)

    def read_runtime(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[RuntimeObservation, ...]:
        return self.authority.read_observations(scope, runtime_instance_id)
