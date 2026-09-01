"""Verified, resumable SQLite-to-PostgreSQL Evidence importer."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from agent_core.execution_evidence.domain import ExecutionEvidenceRecord
from agent_core.execution_evidence.postgres import PostgresExecutionEvidenceRepository

from .execution_domain import (
    CutoverState,
    ExecutionPersistenceError,
    ImportCheckpoint,
    Writer,
)
from .execution_postgres import PostgresExecutionAuthorityRepository

IMPORTER_VERSION = "sqlite-postgres-evidence-v1"


class EvidenceImportError(ExecutionPersistenceError):
    reason_code = "EVIDENCE_IMPORT_ERROR"


class SQLiteEvidenceImporter:
    def __init__(
        self,
        source: Path,
        authority: PostgresExecutionAuthorityRepository,
        target: PostgresExecutionEvidenceRepository,
    ) -> None:
        self.source = source
        self.authority = authority
        self.target = target

    def source_identity(self) -> tuple[str, str]:
        if not self.source.is_file():
            raise EvidenceImportError("SOURCE_BACKUP_REQUIRED")
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        identity = f"sqlite-backup:sha256:{digest}"
        return identity, digest

    def import_all(self, *, writer_quiesced: bool) -> ImportCheckpoint:
        if not writer_quiesced:
            raise EvidenceImportError("SQLITE_WRITER_NOT_QUIESCED")
        identity, digest = self.source_identity()
        checkpoint = self.authority.load_checkpoint()
        if checkpoint.state not in {CutoverState.SQLITE_ACTIVE, CutoverState.IMPORTING}:
            raise EvidenceImportError("IMPORT_STATE_INVALID")
        if checkpoint.state is CutoverState.IMPORTING and (
            checkpoint.source_backup_identity != identity
            or checkpoint.source_backup_digest != digest
        ):
            raise EvidenceImportError("IMPORT_SOURCE_CHANGED")
        checkpoint = replace(
            checkpoint,
            state=CutoverState.IMPORTING,
            writer=Writer.NONE,
            source_backup_identity=identity,
            source_backup_digest=digest,
            importer_version=IMPORTER_VERSION,
            verification_status="IN_PROGRESS",
        )
        self.authority.replace_checkpoint(checkpoint)
        try:
            rows = self._rows(checkpoint.last_storage_sequence)
            for row in rows:
                record = ExecutionEvidenceRecord.from_allowlisted(
                    json.loads(row["canonical_bytes"])
                ).with_repository_metadata(
                    storage_sequence=row["storage_sequence"],
                    recorded_at=row["recorded_at"],
                )
                if record.payload_digest != row["payload_digest"]:
                    raise EvidenceImportError("SOURCE_DIGEST_MISMATCH")
                imported = self.target.import_exact(record).record
                if imported.payload_digest != record.payload_digest:
                    raise EvidenceImportError("TARGET_PARITY_MISMATCH")
                checkpoint = replace(
                    checkpoint,
                    last_storage_sequence=row["storage_sequence"],
                    last_record_id=row["evidence_record_id"],
                    target_high_water=max(
                        checkpoint.target_high_water, row["storage_sequence"]
                    ),
                )
                self.authority.replace_checkpoint(checkpoint)
            source_count, source_high = self._count_and_high_water()
            target_count, target_high = self._target_count_and_high_water()
            if (source_count, source_high) != (target_count, target_high):
                raise EvidenceImportError("IMPORT_PARITY_MISMATCH")
            checkpoint = replace(
                checkpoint,
                target_high_water=target_high,
                verification_status="PARITY_VERIFIED",
            )
            return self.authority.replace_checkpoint(checkpoint)
        except Exception as exc:
            recovery = replace(
                checkpoint,
                state=CutoverState.RECOVERY_REQUIRED,
                writer=Writer.NONE,
                verification_status="RECOVERY_REQUIRED",
            )
            self.authority.replace_checkpoint(recovery)
            if isinstance(exc, EvidenceImportError):
                raise
            raise EvidenceImportError("IMPORT_RECOVERY_REQUIRED") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.source}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def _rows(self, after: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM execution_evidence WHERE storage_sequence>? "
                "ORDER BY storage_sequence,evidence_record_id",
                (after,),
            ).fetchall()
        result = []
        for row in rows:
            canonical = {
                "schema_version": row["schema_version"],
                "evidence_record_id": row["evidence_record_id"],
                "namespace": row["namespace"],
                "security_domain": row["security_domain"],
                "platform_execution_identity": row["platform_execution_identity"],
                "workflow_identity": row["workflow_identity"],
                "task_identity": row["task_identity"],
                "attempt_ordinal": row["attempt_ordinal"],
                "event_ordinal": row["event_ordinal"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
                "runtime_classification": row["runtime_classification"],
                "selected_instance_identity": row["selected_instance_identity"],
                "capability_identity": row["capability_identity"],
                "authorization_decision": row["authorization_decision"],
                "reason_code": row["reason_code"],
                "provider_correlation_id": row["provider_correlation_id"],
                "provider_call_count": row["provider_call_count"],
                "outcome_classification": row["outcome_classification"],
                "outcome_reference": row["outcome_reference"],
                "references": json.loads(row["reference_authorizations"]),
                "limitation_code": row["limitation_code"],
                "supersedes_record_id": row["supersedes_record_id"],
            }
            item = dict(row)
            item["canonical_bytes"] = json.dumps(
                canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            result.append(item)
        return result

    def _count_and_high_water(self) -> tuple[int, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count,COALESCE(MAX(storage_sequence),0) AS high "
                "FROM execution_evidence"
            ).fetchone()
            return row["count"], row["high"]

    def _target_count_and_high_water(self) -> tuple[int, int]:
        with self.target.pool.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count,COALESCE(MAX(storage_sequence),0) AS high "
                "FROM execution_authority.execution_evidence"
            ).fetchone()
            return row["count"], row["high"]
