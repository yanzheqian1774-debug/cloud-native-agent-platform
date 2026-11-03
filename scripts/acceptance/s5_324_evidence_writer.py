"""Initialize a new empty 324 evidence source and use the existing cutover protocol.

This is not an import of claimed historical 323 evidence. It is permitted only
when the original execution domain has no Run, Attempt, Outcome or Evidence and
its untouched initial checkpoint has no source identity. Retain the empty source
and verified import checkpoint; never reset a nonempty or active owner.
"""

import argparse
import json
import os
from pathlib import Path

from agent_console.execution_domain import CutoverState, Writer
from agent_console.execution_evidence_cutover import EvidenceCutoverCoordinator
from agent_console.execution_evidence_import import SQLiteEvidenceImporter
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_core.execution_evidence import SQLiteExecutionEvidenceRepository
from agent_core.execution_evidence.postgres import PostgresExecutionEvidenceRepository

ROOT = Path(__file__).resolve().parents[2]


def initialize(authority, target, source):
    current = authority.load_checkpoint()
    importer = SQLiteEvidenceImporter(source, authority, target)
    if current.state is CutoverState.POSTGRES_ACTIVE:
        identity, digest = importer.source_identity()
        if current.writer is not Writer.POSTGRES or (
            current.source_backup_identity,
            current.source_backup_digest,
        ) != (identity, digest):
            raise ValueError("EVIDENCE_SOURCE_CONFLICT")
        return current
    if current.state not in {
        CutoverState.SQLITE_ACTIVE,
        CutoverState.IMPORTING,
        CutoverState.RECOVERY_REQUIRED,
    }:
        raise ValueError("EVIDENCE_INITIALIZATION_STATE_INVALID")
    with authority.pool.connection() as c:
        for table in (
            "workflow_runs",
            "task_runs",
            "attempts",
            "outcomes",
            "execution_evidence",
        ):
            if c.execute(
                f"SELECT count(*) AS n FROM execution_authority.{table}"
            ).fetchone()["n"]:
                raise ValueError("NONEMPTY_EVIDENCE_OWNER_REQUIRES_EXISTING_SOURCE")
    if current.state is CutoverState.SQLITE_ACTIVE and (
        current.source_backup_identity
        or current.last_storage_sequence
        or current.target_high_water
    ):
        raise ValueError("EXISTING_EVIDENCE_SOURCE_REQUIRED")
    if not source.exists():
        if current.state is not CutoverState.SQLITE_ACTIVE:
            raise ValueError("RECOVERY_SOURCE_MISSING")
        SQLiteExecutionEvidenceRepository(source)
    import sqlite3

    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as c:
        if c.execute("SELECT count(*) FROM execution_evidence").fetchone()[0]:
            raise ValueError("INITIAL_SOURCE_NOT_EMPTY")
    verified = importer.import_all(writer_quiesced=True)
    if verified.verification_status != "PARITY_VERIFIED" or verified.target_high_water:
        raise ValueError("INITIAL_EVIDENCE_PARITY_FAILED")
    return EvidenceCutoverCoordinator(authority).activate_postgres(
        sqlite_quiesced=True, parity_verified=True
    )


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    if os.environ.get("AGENT_EXECUTION_EVIDENCE_DB"):
        raise ValueError("SQLITE_WRITER_CONFIGURATION_PRESENT")
    r = json.loads(args.runtime.read_text())
    authority = PostgresExecutionAuthorityRepository(
        r["databaseUrl"],
        migration_path=ROOT
        / "console/backend/migrations/0008_execution_runtime_authority.sql",
    )
    target = PostgresExecutionEvidenceRepository(r["databaseUrl"])
    try:
        authority.compatibility()
        value = initialize(authority, target, args.source)
        receipt = {
            "state": value.state.value,
            "writer": value.writer.value,
            "sourceProvenance": (
                "NEW_324_EMPTY_INITIAL_SOURCE_NOT_HISTORICAL_323_BACKUP"
            ),
            "sourceDigest": value.source_backup_digest,
            "highWater": value.target_high_water,
            "verification": value.verification_status,
        }
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt))
    finally:
        target.pool.close()
        authority.pool.close()


if __name__ == "__main__":
    main()
