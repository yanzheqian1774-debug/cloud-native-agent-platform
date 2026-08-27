"""Bounded single-node SQLite execution evidence repository."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .domain import (
    AuthorizationDecision,
    EvidenceEventType,
    ExecutionEvidenceRecord,
    OutcomeClassification,
)
from .ports import (
    AppendDisposition,
    AppendResult,
    AuthorizedEvidenceScope,
    EvidenceDigestConflict,
    EvidenceRepositoryUnavailable,
    EvidenceSchemaIncompatible,
)

SCHEMA_VERSION = 1
_EXPECTED_COLUMNS = (
    "storage_sequence",
    "evidence_record_id",
    "schema_version",
    "namespace",
    "security_domain",
    "platform_execution_identity",
    "workflow_identity",
    "task_identity",
    "attempt_ordinal",
    "event_ordinal",
    "event_type",
    "occurred_at",
    "recorded_at",
    "payload_digest",
    "runtime_classification",
    "selected_instance_identity",
    "capability_identity",
    "authorization_decision",
    "reason_code",
    "provider_correlation_id",
    "provider_call_count",
    "outcome_classification",
    "outcome_reference",
    "evidence_references",
    "citation_references",
    "limitation_code",
    "supersedes_record_id",
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SQLiteExecutionEvidenceRepository:
    """Local restart-durable adapter; not multi-node or production certified."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        busy_timeout_ms: int = 500,
        clock: Callable[[], str] = _now,
    ) -> None:
        path = Path(database_path)
        if not str(path).strip() or path.name in {"", "."}:
            raise EvidenceRepositoryUnavailable("EVIDENCE_DATABASE_LOCATION_REQUIRED")
        if not isinstance(busy_timeout_ms, int) or not 1 <= busy_timeout_ms <= 5_000:
            raise EvidenceRepositoryUnavailable("EVIDENCE_BUSY_TIMEOUT_INVALID")
        self._path = path
        self._busy_timeout_ms = busy_timeout_ms
        self._clock = clock
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self._path,
                timeout=self._busy_timeout_ms / 1_000,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except (OSError, sqlite3.Error) as exc:
            raise EvidenceRepositoryUnavailable(
                "EVIDENCE_DATABASE_OPEN_FAILED"
            ) from exc

    def _bootstrap(self) -> None:
        connection = self._connect()
        try:
            objects = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','index') "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            if not objects:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE evidence_schema ("
                    "singleton INTEGER PRIMARY KEY CHECK (singleton=1), "
                    "schema_version INTEGER NOT NULL, adapter TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO evidence_schema VALUES (1, 1, 'sqlite-single-node-v1')"
                )
                connection.execute(
                    """CREATE TABLE execution_evidence (
                    storage_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    evidence_record_id TEXT NOT NULL UNIQUE,
                    schema_version INTEGER NOT NULL CHECK (schema_version=1),
                    namespace TEXT NOT NULL, security_domain TEXT NOT NULL,
                    platform_execution_identity TEXT NOT NULL,
                    workflow_identity TEXT NOT NULL, task_identity TEXT NOT NULL,
                    attempt_ordinal INTEGER NOT NULL, event_ordinal INTEGER NOT NULL,
                    event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, payload_digest TEXT NOT NULL,
                    runtime_classification TEXT NOT NULL,
                    selected_instance_identity TEXT NOT NULL,
                    capability_identity TEXT, authorization_decision TEXT NOT NULL,
                    reason_code TEXT NOT NULL, provider_correlation_id TEXT,
                    provider_call_count INTEGER NOT NULL,
                    outcome_classification TEXT NOT NULL, outcome_reference TEXT,
                    evidence_references TEXT NOT NULL,
                    citation_references TEXT NOT NULL,
                    limitation_code TEXT, supersedes_record_id TEXT)"""
                )
                connection.execute(
                    "CREATE INDEX evidence_execution_idx ON execution_evidence("
                    "namespace, security_domain, platform_execution_identity, "
                    "storage_sequence)"
                )
                connection.execute(
                    "CREATE INDEX evidence_task_idx ON execution_evidence("
                    "namespace, security_domain, task_identity, storage_sequence)"
                )
                connection.execute(
                    "CREATE INDEX evidence_workflow_idx ON execution_evidence("
                    "namespace, security_domain, workflow_identity, storage_sequence)"
                )
                connection.execute(
                    "CREATE INDEX evidence_event_idx ON execution_evidence("
                    "platform_execution_identity, attempt_ordinal, event_ordinal)"
                )
                connection.execute(
                    "CREATE INDEX evidence_supersedes_idx ON "
                    "execution_evidence(supersedes_record_id)"
                )
                connection.execute("COMMIT")
            self._verify_schema(connection)
        except EvidenceSchemaIncompatible:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise EvidenceRepositoryUnavailable(
                "EVIDENCE_SCHEMA_BOOTSTRAP_FAILED"
            ) from exc
        finally:
            connection.close()

    def _verify_schema(self, connection: sqlite3.Connection) -> None:
        try:
            row = connection.execute(
                "SELECT schema_version, adapter FROM evidence_schema WHERE singleton=1"
            ).fetchone()
            columns = tuple(
                item[1]
                for item in connection.execute("PRAGMA table_info(execution_evidence)")
            )
        except sqlite3.DatabaseError as exc:
            raise EvidenceSchemaIncompatible("EVIDENCE_SCHEMA_INCOMPATIBLE") from exc
        if (
            row is None
            or tuple(row) != (SCHEMA_VERSION, "sqlite-single-node-v1")
            or columns != _EXPECTED_COLUMNS
        ):
            raise EvidenceSchemaIncompatible("EVIDENCE_SCHEMA_INCOMPATIBLE")

    def append(self, record: ExecutionEvidenceRecord) -> AppendResult:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT storage_sequence, recorded_at, payload_digest "
                "FROM execution_evidence WHERE evidence_record_id=?",
                (record.evidence_record_id,),
            ).fetchone()
            if existing is not None:
                if existing["payload_digest"] != record.payload_digest:
                    connection.execute("ROLLBACK")
                    raise EvidenceDigestConflict("EVIDENCE_DIGEST_CONFLICT")
                connection.execute("COMMIT")
                return AppendResult(
                    AppendDisposition.REPLAYED,
                    record.with_repository_metadata(
                        storage_sequence=existing["storage_sequence"],
                        recorded_at=existing["recorded_at"],
                    ),
                )
            recorded_at = self._clock()
            values = self._to_values(record, recorded_at)
            columns = ",".join(_EXPECTED_COLUMNS[1:])
            placeholders = ",".join("?" for _ in _EXPECTED_COLUMNS[1:])
            cursor = connection.execute(
                f"INSERT INTO execution_evidence ({columns}) VALUES ({placeholders})",
                values,
            )
            sequence = int(cursor.lastrowid)
            connection.execute("COMMIT")
            return AppendResult(
                AppendDisposition.APPENDED,
                record.with_repository_metadata(
                    storage_sequence=sequence, recorded_at=recorded_at
                ),
            )
        except EvidenceDigestConflict:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise EvidenceRepositoryUnavailable("EVIDENCE_APPEND_UNAVAILABLE") from exc
        finally:
            connection.close()

    def high_water_mark(self, scope: AuthorizedEvidenceScope) -> int:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT COALESCE(MAX(storage_sequence),0) "
                "FROM execution_evidence WHERE namespace=? AND security_domain=?",
                (scope.namespace, scope.security_domain),
            ).fetchone()
            return int(row[0])
        except sqlite3.DatabaseError as exc:
            raise EvidenceRepositoryUnavailable("EVIDENCE_READ_UNAVAILABLE") from exc
        finally:
            connection.close()

    def read_execution(
        self,
        scope: AuthorizedEvidenceScope,
        platform_execution_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM execution_evidence WHERE namespace=? "
                "AND security_domain=? AND platform_execution_identity=? "
                "AND storage_sequence<=? ORDER BY attempt_ordinal,event_ordinal,"
                "occurred_at,recorded_at,evidence_record_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    platform_execution_identity,
                    through_high_water_mark,
                ),
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)
        except sqlite3.DatabaseError as exc:
            raise EvidenceRepositoryUnavailable("EVIDENCE_READ_UNAVAILABLE") from exc
        finally:
            connection.close()

    def read_task(
        self,
        scope: AuthorizedEvidenceScope,
        task_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM execution_evidence WHERE namespace=? "
                "AND security_domain=? AND task_identity=? AND storage_sequence<=? "
                "ORDER BY platform_execution_identity,attempt_ordinal,event_ordinal,"
                "occurred_at,recorded_at,evidence_record_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    task_identity,
                    through_high_water_mark,
                ),
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)
        except sqlite3.DatabaseError as exc:
            raise EvidenceRepositoryUnavailable("EVIDENCE_READ_UNAVAILABLE") from exc
        finally:
            connection.close()

    @staticmethod
    def _to_values(
        record: ExecutionEvidenceRecord, recorded_at: str
    ) -> tuple[object, ...]:
        return (
            record.evidence_record_id,
            record.schema_version,
            record.namespace,
            record.security_domain,
            record.platform_execution_identity,
            record.workflow_identity,
            record.task_identity,
            record.attempt_ordinal,
            record.event_ordinal,
            record.event_type.value,
            record.occurred_at,
            recorded_at,
            record.payload_digest,
            record.runtime_classification,
            record.selected_instance_identity,
            record.capability_identity,
            record.authorization_decision.value,
            record.reason_code,
            record.provider_correlation_id,
            record.provider_call_count,
            record.outcome_classification.value,
            record.outcome_reference,
            json.dumps(record.evidence_references, separators=(",", ":")),
            json.dumps(record.citation_references, separators=(",", ":")),
            record.limitation_code,
            record.supersedes_record_id,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ExecutionEvidenceRecord:
        return ExecutionEvidenceRecord(
            evidence_record_id=row["evidence_record_id"],
            namespace=row["namespace"],
            security_domain=row["security_domain"],
            platform_execution_identity=row["platform_execution_identity"],
            workflow_identity=row["workflow_identity"],
            task_identity=row["task_identity"],
            attempt_ordinal=row["attempt_ordinal"],
            event_ordinal=row["event_ordinal"],
            event_type=EvidenceEventType(row["event_type"]),
            occurred_at=row["occurred_at"],
            runtime_classification=row["runtime_classification"],
            selected_instance_identity=row["selected_instance_identity"],
            capability_identity=row["capability_identity"],
            authorization_decision=AuthorizationDecision(row["authorization_decision"]),
            reason_code=row["reason_code"],
            provider_correlation_id=row["provider_correlation_id"],
            provider_call_count=row["provider_call_count"],
            outcome_classification=OutcomeClassification(row["outcome_classification"]),
            outcome_reference=row["outcome_reference"],
            evidence_references=tuple(json.loads(row["evidence_references"])),
            citation_references=tuple(json.loads(row["citation_references"])),
            limitation_code=row["limitation_code"],
            supersedes_record_id=row["supersedes_record_id"],
            schema_version=row["schema_version"],
            storage_sequence=row["storage_sequence"],
            recorded_at=row["recorded_at"],
        )
