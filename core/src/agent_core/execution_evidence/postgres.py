# ruff: noqa: E501
"""PostgreSQL adapter for immutable Execution Evidence continuity."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .domain import ExecutionEvidenceRecord, canonical_json
from .ports import (
    AppendDisposition,
    AppendResult,
    AuthorizedEvidenceScope,
    EvidenceDigestConflict,
    EvidenceRepositoryUnavailable,
    EvidenceSchemaIncompatible,
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class PostgresExecutionEvidenceRepository:
    """Bounded pooled adapter; callers must establish migration compatibility."""

    def __init__(
        self,
        database_url: str,
        *,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout: float = 5.0,
        clock: Callable[[], str] = _now,
    ) -> None:
        if not database_url or not 1 <= min_pool_size <= max_pool_size <= 16:
            raise EvidenceRepositoryUnavailable("EVIDENCE_STORAGE_UNAVAILABLE")
        if not 0 < timeout <= 30:
            raise EvidenceRepositoryUnavailable("EVIDENCE_STORAGE_UNAVAILABLE")
        self._clock = clock
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
            raise EvidenceRepositoryUnavailable("EVIDENCE_STORAGE_UNAVAILABLE") from exc

    def compatibility(self) -> None:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT version FROM execution_authority.schema_migrations "
                    "WHERE version=8"
                ).fetchone()
                newer = connection.execute(
                    "SELECT 1 FROM execution_authority.schema_migrations "
                    "WHERE version>8 LIMIT 1"
                ).fetchone()
                columns = connection.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='execution_authority' "
                    "AND table_name='execution_evidence'"
                ).fetchall()
                required = {
                    "storage_sequence",
                    "evidence_record_id",
                    "payload_digest",
                    "canonical_bytes",
                    "record",
                }
                if (
                    row is None
                    or newer
                    or not required <= {item["column_name"] for item in columns}
                ):
                    raise EvidenceSchemaIncompatible("EVIDENCE_SCHEMA_INCOMPATIBLE")
        except EvidenceSchemaIncompatible:
            raise
        except PsycopgError as exc:
            raise EvidenceSchemaIncompatible("EVIDENCE_SCHEMA_INCOMPATIBLE") from exc

    def append(self, record: ExecutionEvidenceRecord) -> AppendResult:
        return self._append(record, storage_sequence=None, recorded_at=None)

    def import_exact(self, record: ExecutionEvidenceRecord) -> AppendResult:
        if record.storage_sequence is None or record.recorded_at is None:
            raise EvidenceRepositoryUnavailable("EVIDENCE_IMPORT_METADATA_REQUIRED")
        return self._append(
            record,
            storage_sequence=record.storage_sequence,
            recorded_at=record.recorded_at,
        )

    def _append(
        self,
        record: ExecutionEvidenceRecord,
        *,
        storage_sequence: int | None,
        recorded_at: str | None,
    ) -> AppendResult:
        try:
            with self.pool.connection() as connection, connection.transaction():
                canonical = canonical_json(dict(record.canonical_payload)).encode()
                timestamp = recorded_at or self._clock()
                params = self._params(record, timestamp, canonical)
                if storage_sequence is None:
                    row = connection.execute(
                        """INSERT INTO execution_authority.execution_evidence
                        (evidence_record_id,schema_version,namespace,security_domain,
                        platform_execution_identity,workflow_identity,task_identity,
                        attempt_ordinal,event_ordinal,event_type,occurred_at,recorded_at,
                        payload_digest,canonical_bytes,record,supersedes_record_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                        ON CONFLICT (evidence_record_id) DO NOTHING
                        RETURNING storage_sequence,recorded_at""",
                        params,
                    ).fetchone()
                else:
                    row = connection.execute(
                        """INSERT INTO execution_authority.execution_evidence
                        (storage_sequence,evidence_record_id,schema_version,namespace,
                        security_domain,platform_execution_identity,workflow_identity,
                        task_identity,attempt_ordinal,event_ordinal,event_type,occurred_at,
                        recorded_at,payload_digest,canonical_bytes,record,supersedes_record_id)
                        OVERRIDING SYSTEM VALUE
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                        ON CONFLICT (evidence_record_id) DO NOTHING
                        RETURNING storage_sequence,recorded_at""",
                        (storage_sequence, *params),
                    ).fetchone()
                if row is None:
                    existing = connection.execute(
                        "SELECT storage_sequence,recorded_at,payload_digest,canonical_bytes "
                        "FROM execution_authority.execution_evidence "
                        "WHERE evidence_record_id=%s",
                        (record.evidence_record_id,),
                    ).fetchone()
                    if (
                        existing is None
                        or existing["payload_digest"] != record.payload_digest
                        or bytes(existing["canonical_bytes"]) != canonical
                        or (
                            storage_sequence is not None
                            and existing["storage_sequence"] != storage_sequence
                        )
                    ):
                        raise EvidenceDigestConflict("EVIDENCE_DIGEST_CONFLICT")
                    return AppendResult(
                        AppendDisposition.REPLAYED,
                        record.with_repository_metadata(
                            storage_sequence=existing["storage_sequence"],
                            recorded_at=existing["recorded_at"]
                            .isoformat()
                            .replace("+00:00", "Z"),
                        ),
                    )
                return AppendResult(
                    AppendDisposition.APPENDED,
                    record.with_repository_metadata(
                        storage_sequence=row["storage_sequence"],
                        recorded_at=row["recorded_at"]
                        .isoformat()
                        .replace("+00:00", "Z"),
                    ),
                )
        except EvidenceDigestConflict:
            raise
        except PsycopgError as exc:
            raise EvidenceRepositoryUnavailable("EVIDENCE_APPEND_UNAVAILABLE") from exc

    @staticmethod
    def _params(
        record: ExecutionEvidenceRecord, recorded_at: str, canonical: bytes
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
            canonical,
            json.dumps(dict(record.canonical_payload)),
            record.supersedes_record_id,
        )

    def high_water_mark(self, scope: AuthorizedEvidenceScope) -> int:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(storage_sequence),0) AS mark FROM "
                    "execution_authority.execution_evidence WHERE namespace=%s "
                    "AND security_domain=%s",
                    (scope.namespace, scope.security_domain),
                ).fetchone()
                return int(row["mark"])
        except PsycopgError as exc:
            raise EvidenceRepositoryUnavailable("EVIDENCE_READ_UNAVAILABLE") from exc

    def read_execution(
        self,
        scope: AuthorizedEvidenceScope,
        platform_execution_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        return self._read(
            scope,
            "platform_execution_identity=%s",
            (platform_execution_identity,),
            through_high_water_mark,
            "attempt_ordinal,event_ordinal,occurred_at,recorded_at,evidence_record_id",
        )

    def read_subject(
        self,
        scope: AuthorizedEvidenceScope,
        workflow_identity: str,
        task_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        return self._read(
            scope,
            "workflow_identity=%s AND task_identity=%s",
            (workflow_identity, task_identity),
            through_high_water_mark,
            "platform_execution_identity,attempt_ordinal,event_ordinal,occurred_at,recorded_at,evidence_record_id",
        )

    def _read(
        self,
        scope: AuthorizedEvidenceScope,
        predicate: str,
        values: tuple[object, ...],
        mark: int,
        order: str,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        try:
            with self.pool.connection() as connection:
                rows = connection.execute(
                    f"SELECT record,storage_sequence,recorded_at FROM execution_authority.execution_evidence "
                    f"WHERE namespace=%s AND security_domain=%s AND {predicate} "
                    f"AND storage_sequence<=%s ORDER BY {order}",
                    (scope.namespace, scope.security_domain, *values, mark),
                ).fetchall()
                return tuple(self._from_row(row) for row in rows)
        except (PsycopgError, ValueError, TypeError) as exc:
            raise EvidenceRepositoryUnavailable("EVIDENCE_READ_UNAVAILABLE") from exc

    @staticmethod
    def _from_row(row: dict[str, object]) -> ExecutionEvidenceRecord:
        value = ExecutionEvidenceRecord.from_allowlisted(row["record"])
        recorded = row["recorded_at"]
        return value.with_repository_metadata(
            storage_sequence=int(row["storage_sequence"]),
            recorded_at=recorded.isoformat().replace("+00:00", "Z"),
        )
