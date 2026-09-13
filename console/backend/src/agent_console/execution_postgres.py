# ruff: noqa: E501
"""PostgreSQL primary adapter for v0.2.3 Execution Authority Track A."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
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
from agent_core.openclaw_binding import (
    AssociationStatus,
    OpenClawBindingObservation,
    OpenClawGenerationBinding,
    OpenClawRuntimeBinding,
    canonical_payload_digest,
)
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
GOVERNED_EXECUTION_ADAPTER = "governed-execution-claim-postgresql-v17"
OPENCLAW_BINDING_ADAPTER = "execution-openclaw-binding-postgresql-v21"
OPENCLAW_BINDING_SCHEMA_VERSION = 21
__all__ = [
    "Generation",
    "PlacementDecisionKind",
    "RuntimeDesiredStateKind",
    "RuntimeHealth",
    "RuntimeObservedStateKind",
    "RuntimeReadiness",
]


def _openclaw_runtime_record(value: OpenClawRuntimeBinding) -> dict[str, object]:
    return {
        "namespace": value.scope.namespace,
        "security_domain": value.scope.security_domain,
        "runtime_instance_id": str(value.runtime_instance_id),
        "placement_id": str(value.placement_id),
        "gateway_digest": value.gateway_digest,
        "agent_id": value.agent_id,
        "canonical_workspace": value.canonical_workspace,
        "workspace_host": value.workspace_host,
        "workspace_storage_domain": value.workspace_storage_domain,
        "source_version": value.source_version,
        "authorization_decision_id": value.authorization_decision_id,
        "recorded_at": value.recorded_at.isoformat(),
    }


def _openclaw_generation_record(
    value: OpenClawGenerationBinding,
) -> dict[str, object]:
    return {
        "namespace": value.scope.namespace,
        "security_domain": value.scope.security_domain,
        "runtime_instance_id": str(value.runtime_instance_id),
        "generation": value.generation.value,
        "session_key": value.session_key,
        "session_id": value.session_id,
        "command_id": str(value.command_id),
        "idempotency_key": value.idempotency_key,
        "command_payload_digest": value.command_payload_digest,
        "association_status": value.association_status.value,
        "observation_high_water": value.observation_high_water,
        "recorded_at": value.recorded_at.isoformat(),
    }


def _openclaw_observation_record(
    value: OpenClawBindingObservation,
) -> dict[str, object]:
    return {
        "namespace": value.scope.namespace,
        "security_domain": value.scope.security_domain,
        "runtime_instance_id": str(value.runtime_instance_id),
        "generation": value.generation.value,
        "high_water": value.high_water,
        "association_status": value.association_status.value,
        "observed_at": value.observed_at.isoformat(),
        "freshness_deadline": value.freshness_deadline.isoformat(),
        "source_version": value.source_version,
        "reason_code": value.reason_code,
        "gateway_matched": value.gateway_matched,
        "agent_matched": value.agent_matched,
        "workspace_matched": value.workspace_matched,
        "session_matched": value.session_matched,
    }


def _openclaw_runtime_from_record(record: dict[str, object]) -> OpenClawRuntimeBinding:
    return OpenClawRuntimeBinding(
        ScopeIdentity(str(record["namespace"]), str(record["security_domain"])),
        RuntimeInstanceId(str(record["runtime_instance_id"])),
        PlacementId(str(record["placement_id"])),
        str(record["gateway_digest"]),
        str(record["agent_id"]),
        str(record["canonical_workspace"]),
        str(record["workspace_host"]),
        str(record["workspace_storage_domain"]),
        str(record["source_version"]),
        str(record["authorization_decision_id"]),
        datetime.fromisoformat(str(record["recorded_at"])),
    )


def _openclaw_generation_from_record(
    record: dict[str, object],
    *,
    association_status: str | None = None,
    observation_high_water: int | None = None,
) -> OpenClawGenerationBinding:
    return OpenClawGenerationBinding(
        ScopeIdentity(str(record["namespace"]), str(record["security_domain"])),
        RuntimeInstanceId(str(record["runtime_instance_id"])),
        Generation(int(record["generation"])),
        str(record["session_key"]),
        str(record["session_id"]),
        CommandId(str(record["command_id"])),
        str(record["idempotency_key"]),
        str(record["command_payload_digest"]),
        AssociationStatus(association_status or str(record["association_status"])),
        observation_high_water
        if observation_high_water is not None
        else int(record["observation_high_water"]),
        datetime.fromisoformat(str(record["recorded_at"])),
    )


def _openclaw_observation_from_record(
    record: dict[str, object],
) -> OpenClawBindingObservation:
    return OpenClawBindingObservation(
        ScopeIdentity(str(record["namespace"]), str(record["security_domain"])),
        RuntimeInstanceId(str(record["runtime_instance_id"])),
        Generation(int(record["generation"])),
        int(record["high_water"]),
        AssociationStatus(str(record["association_status"])),
        datetime.fromisoformat(str(record["observed_at"])),
        datetime.fromisoformat(str(record["freshness_deadline"])),
        str(record["source_version"]),
        str(record["reason_code"]),
        bool(record["gateway_matched"]),
        bool(record["agent_matched"]),
        bool(record["workspace_matched"]),
        bool(record["session_matched"]),
    )


def _append_openclaw_command_result(
    connection,
    scope: ScopeIdentity,
    command_id: CommandId,
    result: CommandResult,
    record: dict[str, object],
) -> None:
    connection.execute(
        "SELECT command_id FROM execution_authority.desired_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s FOR UPDATE",
        (scope.namespace, scope.security_domain, str(command_id)),
    ).fetchone()
    row = connection.execute(
        "SELECT ordinal FROM execution_authority.command_results WHERE namespace=%s AND security_domain=%s AND command_id=%s ORDER BY ordinal DESC LIMIT 1",
        (scope.namespace, scope.security_domain, str(command_id)),
    ).fetchone()
    ordinal = 1 if row is None else row["ordinal"] + 1
    connection.execute(
        "INSERT INTO execution_authority.command_results(namespace,security_domain,command_id,ordinal,result,fact_digest,fact) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
        (
            scope.namespace,
            scope.security_domain,
            str(command_id),
            ordinal,
            result.value,
            canonical_digest(record),
            json.dumps(record),
        ),
    )


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

    def migrate_governed_execution_claims(self, migration_path: Path) -> None:
        checksum = hashlib.sha256(migration_path.read_bytes()).hexdigest()
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='10s'")
                connection.execute("SET LOCAL lock_timeout='3s'")
                connection.execute(migration_path.read_text())
                newer = connection.execute(
                    "SELECT version FROM governed_execution.schema_migrations "
                    "WHERE version>17 ORDER BY version LIMIT 1"
                ).fetchone()
                if newer is not None:
                    raise ExecutionSchemaIncompatible(
                        "GOVERNED_EXECUTION_SCHEMA_INCOMPATIBLE"
                    )
                row = connection.execute(
                    "SELECT checksum,adapter FROM governed_execution.schema_migrations WHERE version=17"
                ).fetchone()
                expected = {
                    "checksum": checksum,
                    "adapter": GOVERNED_EXECUTION_ADAPTER,
                }
                if row is None:
                    connection.execute(
                        "INSERT INTO governed_execution.schema_migrations(version,checksum,adapter) VALUES(17,%s,%s)",
                        (checksum, GOVERNED_EXECUTION_ADAPTER),
                    )
                elif row != expected:
                    raise ExecutionSchemaIncompatible(
                        "GOVERNED_EXECUTION_SCHEMA_INCOMPATIBLE"
                    )
        except ExecutionSchemaIncompatible:
            raise
        except PsycopgError as exc:
            raise ExecutionStorageUnavailable(
                "GOVERNED_EXECUTION_MIGRATION_UNAVAILABLE"
            ) from exc

    def migrate_openclaw_bindings(self, migration_path: Path) -> None:
        checksum = hashlib.sha256(migration_path.read_bytes()).hexdigest()
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='10s'")
                connection.execute("SET LOCAL lock_timeout='3s'")
                connection.execute(migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM execution_authority.openclaw_binding_migrations WHERE version=%s",
                    (OPENCLAW_BINDING_SCHEMA_VERSION,),
                ).fetchone()
                expected = {
                    "checksum": checksum,
                    "adapter": OPENCLAW_BINDING_ADAPTER,
                }
                if row is None:
                    connection.execute(
                        "INSERT INTO execution_authority.openclaw_binding_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (
                            OPENCLAW_BINDING_SCHEMA_VERSION,
                            checksum,
                            OPENCLAW_BINDING_ADAPTER,
                        ),
                    )
                elif row != expected:
                    raise ExecutionSchemaIncompatible(
                        "OPENCLAW_BINDING_SCHEMA_INCOMPATIBLE"
                    )
        except ExecutionSchemaIncompatible:
            raise
        except (OSError, PsycopgError) as exc:
            raise ExecutionStorageUnavailable(
                "OPENCLAW_BINDING_MIGRATION_UNAVAILABLE"
            ) from exc

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
        self,
        scope: ScopeIdentity,
        aggregate: ExecutionIdentityAggregate,
        *,
        approved_plan=None,
        plan=None,
        task_id=None,
        authorization_decision_id: str | None = None,
        request_claim=None,
    ) -> ExecutionIdentityAggregate:
        if not authorization_decision_id:
            raise ExecutionConflict("EXECUTION_NOT_FOUND")
        if scope != aggregate.scope:
            raise ExecutionConflict("EXECUTION_IDENTITY_SCOPE_MISMATCH")
        aggregate_payload = json.loads(canonical_bytes(aggregate))["payload"]
        aggregate_digest = canonical_digest(aggregate)

        def operation(connection):
            from .execution_lineage import append_lineage, validate_lineage

            employee, stored_plan, approval_id, ordinal = validate_lineage(
                connection,
                aggregate,
                approved_plan,
                authorization_decision_id,
                plan,
                task_id,
            )
            if request_claim is not None:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (
                        json.dumps(
                            (
                                scope.namespace,
                                scope.security_domain,
                                request_claim.principal_id,
                                request_claim.idempotency_key,
                            )
                        ),
                    ),
                )
                claimed = connection.execute(
                    "SELECT request_digest,workflow_run_id,task_run_id,attempt_id,state "
                    "FROM execution_authority.governed_execution_claims "
                    "WHERE namespace=%s AND security_domain=%s AND principal_id=%s "
                    "AND idempotency_key=%s FOR UPDATE",
                    (
                        scope.namespace,
                        scope.security_domain,
                        request_claim.principal_id,
                        request_claim.idempotency_key,
                    ),
                ).fetchone()
                expected_claim = {
                    "request_digest": request_claim.request_digest,
                    "workflow_run_id": str(aggregate.workflow_run.workflow_run_id),
                    "task_run_id": str(aggregate.task_run.task_run_id),
                    "attempt_id": str(aggregate.attempt.attempt_id),
                    "state": "EXECUTION_CREATED",
                }
                if claimed is not None and claimed != expected_claim:
                    raise ExecutionConflict("GOVERNED_EXECUTION_PAYLOAD_MISMATCH")
                if claimed is None:
                    existing_identity = connection.execute(
                        "SELECT EXISTS(SELECT 1 FROM execution_authority.workflow_runs "
                        "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s) "
                        "OR EXISTS(SELECT 1 FROM execution_authority.task_runs "
                        "WHERE namespace=%s AND security_domain=%s AND task_run_id=%s) "
                        "OR EXISTS(SELECT 1 FROM execution_authority.attempts "
                        "WHERE namespace=%s AND security_domain=%s AND attempt_id=%s) AS present",
                        (
                            scope.namespace,
                            scope.security_domain,
                            str(aggregate.workflow_run.workflow_run_id),
                            scope.namespace,
                            scope.security_domain,
                            str(aggregate.task_run.task_run_id),
                            scope.namespace,
                            scope.security_domain,
                            str(aggregate.attempt.attempt_id),
                        ),
                    ).fetchone()
                    if existing_identity["present"]:
                        raise ExecutionConflict("GOVERNED_EXECUTION_CLAIM_REQUIRED")
            values = (
                (
                    "workflow_runs",
                    "workflow_run_id",
                    str(aggregate.workflow_run.workflow_run_id),
                    "assignment_id,approved_plan_revision_id,predecessor_workflow_run_id,correction_of_workflow_run_id,plan_id,plan_version,approved_plan_digest,control_state,record",
                    (
                        str(aggregate.workflow_run.assignment_id),
                        aggregate.workflow_run.approved_plan_revision_id,
                        None
                        if aggregate.workflow_run.predecessor_workflow_run_id is None
                        else str(aggregate.workflow_run.predecessor_workflow_run_id),
                        None
                        if aggregate.workflow_run.correction_of_workflow_run_id is None
                        else str(aggregate.workflow_run.correction_of_workflow_run_id),
                        stored_plan["plan_id"],
                        stored_plan["plan_version"],
                        stored_plan["plan_digest"],
                        "PENDING",
                        json.loads(canonical_bytes(aggregate.workflow_run))["payload"],
                    ),
                ),
                (
                    "task_runs",
                    "task_run_id",
                    str(aggregate.task_run.task_run_id),
                    "workflow_run_id,workflow_node_id,control_state,record",
                    (
                        str(aggregate.task_run.workflow_run_id),
                        stored_plan["task_id"],
                        "READY",
                        json.loads(canonical_bytes(aggregate.task_run))["payload"],
                    ),
                ),
                (
                    "attempts",
                    "attempt_id",
                    str(aggregate.attempt.attempt_id),
                    "task_run_id,predecessor_attempt_id,aggregate_digest,attempt_ordinal,control_state,record",
                    (
                        str(aggregate.attempt.task_run_id),
                        None
                        if aggregate.attempt.predecessor_attempt_id is None
                        else str(aggregate.attempt.predecessor_attempt_id),
                        aggregate_digest,
                        ordinal,
                        "PENDING",
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
                    f"SELECT {columns} FROM execution_authority.{table} WHERE namespace=%s AND security_domain=%s AND {id_column}=%s",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchone()
                if stored is None or any(
                    stored[column] != expected
                    for column, expected in zip(columns.split(","), extra, strict=True)
                    if column != "control_state"
                ):
                    raise ExecutionConflict("EXECUTION_IDENTITY_CONFLICT")
            append_lineage(
                connection,
                aggregate,
                employee,
                stored_plan,
                approval_id,
                authorization_decision_id,
            )
            if request_claim is not None:
                connection.execute(
                    "INSERT INTO execution_authority.governed_execution_claims("
                    "namespace,security_domain,principal_id,idempotency_key,request_digest,"
                    "workflow_run_id,task_run_id,attempt_id,state) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'EXECUTION_CREATED') "
                    "ON CONFLICT DO NOTHING",
                    (
                        scope.namespace,
                        scope.security_domain,
                        request_claim.principal_id,
                        request_claim.idempotency_key,
                        request_claim.request_digest,
                        str(aggregate.workflow_run.workflow_run_id),
                        str(aggregate.task_run.task_run_id),
                        str(aggregate.attempt.attempt_id),
                    ),
                )
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
        return self.identity_from_record(scope, row["record"])

    @staticmethod
    def identity_from_record(scope, payload):
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
        *,
        require_employee_lineage: bool = False,
    ) -> PlacementResult:
        if scope != request.scope or decision.request_id != request.request_id:
            raise ExecutionConflict("PLACEMENT_SCOPE_OR_REQUEST_MISMATCH")

        def operation(connection):
            from .execution_lineage import validate_placement

            validate_placement(
                connection, scope, request, decision, required=require_employee_lineage
            )
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

    def save_openclaw_binding(
        self,
        binding: OpenClawRuntimeBinding,
        generation: OpenClawGenerationBinding,
    ) -> AppendDisposition:
        if (
            binding.scope != generation.scope
            or binding.runtime_instance_id != generation.runtime_instance_id
        ):
            raise ExecutionConflict("OPENCLAW_BINDING_SCOPE_OR_RUNTIME_MISMATCH")
        binding_record = _openclaw_runtime_record(binding)
        generation_record = _openclaw_generation_record(generation)
        binding_digest = canonical_payload_digest(binding)
        generation_digest = canonical_payload_digest(generation)

        def operation(connection):
            placement = connection.execute(
                "SELECT decision,runtime_instance_id FROM execution_authority.placement_decisions WHERE namespace=%s AND security_domain=%s AND placement_id=%s FOR SHARE",
                (
                    binding.scope.namespace,
                    binding.scope.security_domain,
                    str(binding.placement_id),
                ),
            ).fetchone()
            if placement != {
                "decision": PlacementDecisionKind.PLACED.value,
                "runtime_instance_id": str(binding.runtime_instance_id),
            }:
                raise ExecutionConflict("OPENCLAW_PLACEMENT_NOT_VALID")
            desired = connection.execute(
                "SELECT runtime_instance_id,generation,command_digest FROM execution_authority.desired_commands WHERE namespace=%s AND security_domain=%s AND command_id=%s FOR SHARE",
                (
                    binding.scope.namespace,
                    binding.scope.security_domain,
                    str(generation.command_id),
                ),
            ).fetchone()
            if desired != {
                "runtime_instance_id": str(binding.runtime_instance_id),
                "generation": generation.generation.value,
                "command_digest": generation.command_payload_digest,
            }:
                raise ExecutionConflict("OPENCLAW_COMMAND_NOT_VALID")
            existing_binding = connection.execute(
                "SELECT binding_digest FROM execution_authority.openclaw_runtime_bindings WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s FOR UPDATE",
                (
                    binding.scope.namespace,
                    binding.scope.security_domain,
                    str(binding.runtime_instance_id),
                ),
            ).fetchone()
            if (
                existing_binding
                and existing_binding["binding_digest"] != binding_digest
            ):
                raise ExecutionConflict("OPENCLAW_RUNTIME_BINDING_CONFLICT")
            if existing_binding is None:
                connection.execute(
                    "INSERT INTO execution_authority.openclaw_runtime_bindings(namespace,security_domain,runtime_instance_id,placement_id,gateway_digest,agent_id,canonical_workspace,workspace_host,workspace_storage_domain,source_version,authorization_decision_id,binding_digest,record,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                    (
                        binding.scope.namespace,
                        binding.scope.security_domain,
                        str(binding.runtime_instance_id),
                        str(binding.placement_id),
                        binding.gateway_digest,
                        binding.agent_id,
                        binding.canonical_workspace,
                        binding.workspace_host,
                        binding.workspace_storage_domain,
                        binding.source_version,
                        binding.authorization_decision_id,
                        binding_digest,
                        json.dumps(binding_record),
                        binding.recorded_at,
                    ),
                )
            replay = connection.execute(
                "SELECT generation_digest,command_payload_digest FROM execution_authority.openclaw_generation_bindings WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s AND generation=%s FOR UPDATE",
                (
                    generation.scope.namespace,
                    generation.scope.security_domain,
                    str(generation.runtime_instance_id),
                    generation.generation.value,
                ),
            ).fetchone()
            by_key = connection.execute(
                "SELECT command_payload_digest,generation_digest FROM execution_authority.openclaw_generation_bindings WHERE namespace=%s AND security_domain=%s AND idempotency_key=%s FOR UPDATE",
                (
                    generation.scope.namespace,
                    generation.scope.security_domain,
                    generation.idempotency_key,
                ),
            ).fetchone()
            if (
                by_key
                and by_key["command_payload_digest"]
                != generation.command_payload_digest
            ):
                raise ExecutionConflict("OPENCLAW_IDEMPOTENCY_KEY_CONFLICT")
            if replay:
                if replay != {
                    "generation_digest": generation_digest,
                    "command_payload_digest": generation.command_payload_digest,
                }:
                    raise ExecutionConflict("OPENCLAW_GENERATION_BINDING_CONFLICT")
                return AppendDisposition.REPLAYED
            if by_key:
                raise ExecutionConflict("OPENCLAW_IDEMPOTENCY_KEY_BINDING_CONFLICT")
            connection.execute(
                "INSERT INTO execution_authority.openclaw_generation_bindings(namespace,security_domain,runtime_instance_id,generation,gateway_digest,session_key,session_id,command_id,idempotency_key,command_payload_digest,association_status,observation_high_water,generation_digest,record,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    generation.scope.namespace,
                    generation.scope.security_domain,
                    str(generation.runtime_instance_id),
                    generation.generation.value,
                    binding.gateway_digest,
                    generation.session_key,
                    generation.session_id,
                    str(generation.command_id),
                    generation.idempotency_key,
                    generation.command_payload_digest,
                    generation.association_status.value,
                    generation.observation_high_water,
                    generation_digest,
                    json.dumps(generation_record),
                    generation.recorded_at,
                ),
            )
            _append_openclaw_command_result(
                connection,
                generation.scope,
                generation.command_id,
                CommandResult.REQUESTED,
                {
                    "kind": "OPENCLAW_BINDING_RECORDED",
                    "runtime_instance_id": str(generation.runtime_instance_id),
                    "generation": generation.generation.value,
                    "command_payload_digest": generation.command_payload_digest,
                    "idempotency_key_digest": hashlib.sha256(
                        generation.idempotency_key.encode()
                    ).hexdigest(),
                },
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def get_openclaw_binding(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        generation: Generation,
    ) -> tuple[OpenClawRuntimeBinding, OpenClawGenerationBinding] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT runtime.record AS runtime_record,generation.record AS generation_record,generation.association_status,generation.observation_high_water FROM execution_authority.openclaw_runtime_bindings runtime JOIN execution_authority.openclaw_generation_bindings generation USING(namespace,security_domain,runtime_instance_id) WHERE runtime.namespace=%s AND runtime.security_domain=%s AND runtime.runtime_instance_id=%s AND generation.generation=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(runtime_instance_id),
                    generation.value,
                ),
            ).fetchone()
        if row is None:
            return None
        return (
            _openclaw_runtime_from_record(row["runtime_record"]),
            _openclaw_generation_from_record(
                row["generation_record"],
                association_status=row["association_status"],
                observation_high_water=row["observation_high_water"],
            ),
        )

    def append_openclaw_observation(
        self, observation: OpenClawBindingObservation
    ) -> AppendDisposition:
        record = _openclaw_observation_record(observation)
        digest = canonical_payload_digest(observation)

        def operation(connection):
            current = connection.execute(
                "SELECT observation_high_water,command_id FROM execution_authority.openclaw_generation_bindings WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s AND generation=%s FOR UPDATE",
                (
                    observation.scope.namespace,
                    observation.scope.security_domain,
                    str(observation.runtime_instance_id),
                    observation.generation.value,
                ),
            ).fetchone()
            if current is None:
                raise ExecutionConflict("OPENCLAW_BINDING_NOT_FOUND")
            high_water = current["observation_high_water"]
            if observation.high_water <= high_water:
                existing = connection.execute(
                    "SELECT observation_digest FROM execution_authority.openclaw_binding_observations WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s AND generation=%s AND high_water=%s",
                    (
                        observation.scope.namespace,
                        observation.scope.security_domain,
                        str(observation.runtime_instance_id),
                        observation.generation.value,
                        observation.high_water,
                    ),
                ).fetchone()
                if observation.high_water == high_water and existing == {
                    "observation_digest": digest
                }:
                    return AppendDisposition.REPLAYED
                raise ExecutionConflict("OPENCLAW_OBSERVATION_HIGH_WATER_REGRESSION")
            if observation.high_water != high_water + 1:
                raise ExecutionConflict("OPENCLAW_OBSERVATION_HIGH_WATER_GAP")
            connection.execute(
                "INSERT INTO execution_authority.openclaw_binding_observations(namespace,security_domain,runtime_instance_id,generation,high_water,association_status,source_version,observation_digest,record,observed_at,freshness_deadline) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (
                    observation.scope.namespace,
                    observation.scope.security_domain,
                    str(observation.runtime_instance_id),
                    observation.generation.value,
                    observation.high_water,
                    observation.association_status.value,
                    observation.source_version,
                    digest,
                    json.dumps(record),
                    observation.observed_at,
                    observation.freshness_deadline,
                ),
            )
            connection.execute(
                "UPDATE execution_authority.openclaw_generation_bindings SET observation_high_water=%s,association_status=%s WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s AND generation=%s",
                (
                    observation.high_water,
                    observation.association_status.value,
                    observation.scope.namespace,
                    observation.scope.security_domain,
                    str(observation.runtime_instance_id),
                    observation.generation.value,
                ),
            )
            command_result = {
                AssociationStatus.MATCHED: CommandResult.OBSERVED,
                AssociationStatus.MISMATCHED: CommandResult.REJECTED,
                AssociationStatus.RECOVERY_REQUIRED: CommandResult.RECOVERY_REQUIRED,
                AssociationStatus.UNVERIFIED: CommandResult.UNKNOWN,
            }[observation.association_status]
            _append_openclaw_command_result(
                connection,
                observation.scope,
                CommandId(current["command_id"]),
                command_result,
                {
                    "kind": "OPENCLAW_BINDING_OBSERVATION",
                    "runtime_instance_id": str(observation.runtime_instance_id),
                    "generation": observation.generation.value,
                    "observation_high_water": observation.high_water,
                    "association_status": observation.association_status.value,
                    "reason_code": observation.reason_code,
                },
            )
            return AppendDisposition.APPENDED

        return self._transaction(operation)

    def read_openclaw_observations(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        generation: Generation,
    ) -> tuple[OpenClawBindingObservation, ...]:
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT record FROM execution_authority.openclaw_binding_observations WHERE namespace=%s AND security_domain=%s AND runtime_instance_id=%s AND generation=%s ORDER BY high_water",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(runtime_instance_id),
                    generation.value,
                ),
            ).fetchall()
        return tuple(_openclaw_observation_from_record(row["record"]) for row in rows)

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
