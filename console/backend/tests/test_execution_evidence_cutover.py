import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from agent_console.execution_domain import (
    CutoverState,
    ExecutionConflict,
    ImportCheckpoint,
    Writer,
)
from agent_console.execution_evidence_cutover import (
    CutoverError,
    EvidenceCutoverCoordinator,
)
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
MIGRATION = (
    Path(__file__).parents[1] / "migrations/0008_execution_runtime_authority.sql"
)


def checkpoint(**overrides):
    values = {
        "state": CutoverState.IMPORTING,
        "writer": Writer.NONE,
        "source_backup_identity": "sqlite-backup:sha256:a",
        "source_backup_digest": "a" * 64,
        "last_storage_sequence": 2,
        "last_record_id": "evidence-2",
        "target_high_water": 2,
        "importer_version": "v1",
        "verification_status": "PARITY_VERIFIED",
    }
    values.update(overrides)
    return ImportCheckpoint(**values)


class Authority:
    def __init__(self, value):
        self.value = value

    def load_checkpoint(self):
        return self.value

    def replace_checkpoint(self, value):
        self.value = value
        return value


def test_cutover_selects_exactly_one_postgres_writer() -> None:
    authority = Authority(checkpoint())
    coordinator = EvidenceCutoverCoordinator(authority)
    result = coordinator.activate_postgres(sqlite_quiesced=True, parity_verified=True)
    assert (result.state, result.writer) == (
        CutoverState.POSTGRES_ACTIVE,
        Writer.POSTGRES,
    )
    coordinator.assert_writer(Writer.POSTGRES)
    with pytest.raises(CutoverError, match="NON_AUTHORITATIVE_WRITER"):
        coordinator.assert_writer(Writer.SQLITE)


def test_cutover_never_dual_writes_or_silently_falls_back() -> None:
    authority = Authority(checkpoint(writer=Writer.SQLITE))
    with pytest.raises(CutoverError, match="CUTOVER_PRECONDITION_FAILED"):
        EvidenceCutoverCoordinator(authority).activate_postgres(
            sqlite_quiesced=True, parity_verified=True
        )
    assert authority.value.state is CutoverState.RECOVERY_REQUIRED
    assert authority.value.writer is Writer.NONE


def test_rollback_rehearsal_protects_post_cutover_facts() -> None:
    authority = Authority(
        replace(
            checkpoint(),
            state=CutoverState.POSTGRES_ACTIVE,
            writer=Writer.POSTGRES,
        )
    )
    coordinator = EvidenceCutoverCoordinator(authority)
    with pytest.raises(CutoverError, match="ROLLBACK_WOULD_DISCARD_FACTS"):
        coordinator.rollback_to_sqlite(
            all_writers_stopped=True,
            sqlite_backup_verified=True,
            post_cutover_postgres_facts=1,
        )
    authority.value = checkpoint(
        state=CutoverState.ROLLBACK_REQUIRED,
        writer=Writer.NONE,
    )
    result = coordinator.rollback_to_sqlite(
        all_writers_stopped=True,
        sqlite_backup_verified=True,
        post_cutover_postgres_facts=0,
    )
    assert (result.state, result.writer) == (CutoverState.SQLITE_ACTIVE, Writer.SQLITE)


@pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
def test_checkpoint_compare_and_set_allows_exactly_one_concurrent_transition() -> None:
    authority = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    authority.migrate()
    current = authority.load_checkpoint()
    candidate = replace(
        current,
        state=CutoverState.IMPORTING,
        writer=Writer.NONE,
        verification_status="IN_PROGRESS",
    )

    def transition(_):
        try:
            authority.replace_checkpoint(candidate)
        except ExecutionConflict:
            return "CONFLICT"
        return "UPDATED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(transition, range(2)))
    assert sorted(results) == ["CONFLICT", "UPDATED"]
    stored = authority.load_checkpoint()
    assert stored.checkpoint_version == current.checkpoint_version + 1
    authority.pool.close()
    restarted = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    assert restarted.load_checkpoint() == stored
    EvidenceCutoverCoordinator(restarted).assert_writer(Writer.NONE)
    restarted.pool.close()
