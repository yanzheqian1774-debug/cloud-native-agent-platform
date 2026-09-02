import json
import os
import sqlite3
from pathlib import Path

import pytest
from agent_console.execution_domain import CutoverState, ImportCheckpoint, Writer
from agent_console.execution_evidence_import import (
    EvidenceImportError,
    ExecutionEvidenceRecord,
    PostgresExecutionEvidenceRepository,
    SQLiteEvidenceImporter,
)
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
MIGRATION = (
    Path(__file__).parents[1] / "migrations/0008_execution_runtime_authority.sql"
)


class Authority:
    def __init__(self):
        self.value = ImportCheckpoint(
            CutoverState.SQLITE_ACTIVE,
            Writer.SQLITE,
            None,
            None,
            0,
            None,
            0,
            "v1",
            "NOT_STARTED",
        )

    def load_checkpoint(self):
        return self.value

    def replace_checkpoint(self, value):
        self.value = value
        return value


class Target:
    pass


def test_import_requires_verified_backup_and_quiesced_writer(tmp_path: Path) -> None:
    source = tmp_path / "evidence.sqlite"
    source.write_bytes(b"verified-backup")
    importer = SQLiteEvidenceImporter(source, Authority(), Target())
    identity, digest = importer.source_identity()
    assert identity == f"sqlite-backup:sha256:{digest}"
    assert len(digest) == 64
    with pytest.raises(EvidenceImportError, match="SQLITE_WRITER_NOT_QUIESCED"):
        importer.import_all(writer_quiesced=False)


def test_resume_rejects_changed_source_backup(tmp_path: Path) -> None:
    source = tmp_path / "evidence.sqlite"
    source.write_bytes(b"current")
    authority = Authority()
    authority.value = ImportCheckpoint(
        CutoverState.IMPORTING,
        Writer.NONE,
        "sqlite-backup:sha256:old",
        "0" * 64,
        1,
        "evidence-1",
        1,
        "v1",
        "IN_PROGRESS",
    )
    importer = SQLiteEvidenceImporter(source, authority, Target())
    with pytest.raises(EvidenceImportError, match="IMPORT_SOURCE_CHANGED"):
        importer.import_all(writer_quiesced=True)


def test_missing_source_backup_fails_closed(tmp_path: Path) -> None:
    importer = SQLiteEvidenceImporter(
        tmp_path / "missing.sqlite", Authority(), Target()
    )
    with pytest.raises(EvidenceImportError, match="SOURCE_BACKUP_REQUIRED"):
        importer.source_identity()


@pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
def test_real_import_is_exact_resumable_and_identity_preserving(tmp_path: Path) -> None:
    source_path = tmp_path / "evidence.sqlite"
    original = ExecutionEvidenceRecord.from_allowlisted(
        {
            "schema_version": 1,
            "evidence_record_id": "evidence:import-exact-001",
            "namespace": "import-test",
            "security_domain": "quality",
            "platform_execution_identity": "execution-import-001",
            "workflow_identity": "workflow-import-001",
            "task_identity": "task-import-001",
            "attempt_ordinal": 1,
            "event_ordinal": 1,
            "event_type": "EXECUTION_OUTCOME",
            "occurred_at": "2026-09-01T08:00:00Z",
            "runtime_classification": "NATIVE",
            "selected_instance_identity": "agent-import-001",
            "capability_identity": None,
            "authorization_decision": "ALLOW",
            "reason_code": "EXECUTION_SUCCEEDED",
            "provider_correlation_id": None,
            "provider_call_count": 1,
            "outcome_classification": "SUCCEEDED",
            "outcome_reference": None,
            "references": [],
            "limitation_code": None,
            "supersedes_record_id": None,
        }
    )
    recorded_at = "2026-09-01T08:01:00Z"
    second_payload = dict(original.canonical_payload)
    second_payload["evidence_record_id"] = "evidence:import-exact-002"
    second_payload["event_ordinal"] = 2
    second = ExecutionEvidenceRecord.from_allowlisted(second_payload)

    def row_values(record, timestamp):
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
            timestamp,
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
            json.dumps(record.canonical_payload["references"]),
            record.limitation_code,
            record.supersedes_record_id,
        )

    with sqlite3.connect(source_path) as connection:
        connection.execute(
            "CREATE TABLE execution_evidence (storage_sequence INTEGER PRIMARY KEY,"
            "evidence_record_id TEXT,schema_version INTEGER,namespace TEXT,"
            "security_domain TEXT,platform_execution_identity TEXT,"
            "workflow_identity TEXT,task_identity TEXT,attempt_ordinal INTEGER,"
            "event_ordinal INTEGER,event_type TEXT,occurred_at TEXT,recorded_at TEXT,"
            "payload_digest TEXT,runtime_classification TEXT,"
            "selected_instance_identity TEXT,capability_identity TEXT,"
            "authorization_decision TEXT,reason_code TEXT,"
            "provider_correlation_id TEXT,provider_call_count INTEGER,"
            "outcome_classification TEXT,outcome_reference TEXT,"
            "reference_authorizations TEXT,limitation_code TEXT,"
            "supersedes_record_id TEXT)"
        )
        connection.execute(
            "INSERT INTO execution_evidence VALUES "
            "(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row_values(original, recorded_at),
        )
        connection.execute(
            "INSERT INTO execution_evidence VALUES "
            "(2,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row_values(second, "2026-09-01T08:02:00Z"),
        )
    authority = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    authority.migrate()
    target = PostgresExecutionEvidenceRepository(DATABASE_URL or "")
    with authority.pool.connection() as connection, connection.transaction():
        connection.execute("TRUNCATE execution_authority.execution_evidence")
        connection.execute(
            "SELECT setval("
            "'execution_authority.execution_evidence_storage_sequence_seq',100,true)"
        )
        connection.execute(
            "UPDATE execution_authority.evidence_cutover SET "
            "state='SQLITE_ACTIVE',authoritative_writer='SQLITE',"
            "source_backup_identity=NULL,source_backup_digest=NULL,"
            "last_storage_sequence=0,last_record_id=NULL,target_high_water=0,"
            "importer_version='v1',verification_status='NOT_STARTED'"
        )
    unrelated_payload = dict(original.canonical_payload)
    unrelated_payload["evidence_record_id"] = "evidence:unrelated-live"
    unrelated_payload["platform_execution_identity"] = "execution-unrelated"
    target.append(ExecutionEvidenceRecord.from_allowlisted(unrelated_payload))

    class InterruptedTarget:
        pool = target.pool

        def __init__(self):
            self.calls = 0

        def import_exact(self, record, *, import_set_identity):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("simulated process interruption")
            return target.import_exact(record, import_set_identity=import_set_identity)

    interrupted = SQLiteEvidenceImporter(source_path, authority, InterruptedTarget())
    with pytest.raises(EvidenceImportError, match="IMPORT_RECOVERY_REQUIRED"):
        interrupted.import_all(writer_quiesced=True)
    recovery = authority.load_checkpoint()
    assert recovery.state is CutoverState.RECOVERY_REQUIRED
    assert recovery.last_storage_sequence == 1

    importer = SQLiteEvidenceImporter(source_path, authority, target)
    resumed = importer.import_all(writer_quiesced=True)
    repeated = importer.import_all(writer_quiesced=True)
    assert (
        resumed.verification_status == repeated.verification_status == "PARITY_VERIFIED"
    )
    assert resumed.last_storage_sequence == repeated.last_storage_sequence == 2
    with target.pool.connection() as connection:
        imported = connection.execute(
            "SELECT evidence_record_id,payload_digest,storage_sequence,recorded_at "
            "FROM execution_authority.execution_evidence "
            "WHERE import_set_identity=%s ORDER BY storage_sequence",
            (resumed.source_backup_identity,),
        ).fetchall()
    assert [row["evidence_record_id"] for row in imported] == [
        original.evidence_record_id,
        second.evidence_record_id,
    ]
    assert [row["payload_digest"] for row in imported] == [
        original.payload_digest,
        second.payload_digest,
    ]
    assert [row["storage_sequence"] for row in imported] == [1, 2]
    assert imported[0]["recorded_at"].isoformat().replace("+00:00", "Z") == recorded_at
    target.pool.close()
    authority.pool.close()
