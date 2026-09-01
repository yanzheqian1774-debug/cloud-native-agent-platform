import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_core.execution_evidence import (
    AppendDisposition,
    AuthorizationDecision,
    AuthorizedEvidenceScope,
    EvidenceDigestConflict,
    EvidenceEventType,
    ExecutionEvidenceRecord,
    OutcomeClassification,
)
from agent_core.execution_evidence.postgres import PostgresExecutionEvidenceRepository

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATION = (
    Path(__file__).parents[2]
    / "console/backend/migrations/0008_execution_runtime_authority.sql"
)


def record(**overrides) -> ExecutionEvidenceRecord:
    values = {
        "evidence_record_id": f"evidence:{uuid.uuid4()}",
        "namespace": "execution-test",
        "security_domain": "quality",
        "platform_execution_identity": "execution-001",
        "workflow_identity": "workflow-001",
        "task_identity": "task-001",
        "attempt_ordinal": 1,
        "event_ordinal": 1,
        "event_type": EvidenceEventType.EXECUTION_OUTCOME,
        "occurred_at": "2026-09-01T08:00:00Z",
        "runtime_classification": "NATIVE",
        "selected_instance_identity": "agent-instance-001",
        "capability_identity": None,
        "authorization_decision": AuthorizationDecision.ALLOW,
        "reason_code": "EXECUTION_SUCCEEDED",
        "provider_correlation_id": None,
        "provider_call_count": 1,
        "outcome_classification": OutcomeClassification.SUCCEEDED,
    }
    values.update(overrides)
    return ExecutionEvidenceRecord(**values)


def repositories():
    authority = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    authority.migrate()
    evidence = PostgresExecutionEvidenceRepository(DATABASE_URL or "")
    evidence.compatibility()
    return authority, evidence


def test_postgres_evidence_replay_conflict_scope_and_high_water() -> None:
    authority, repository = repositories()
    value = record()
    first = repository.append(value)
    assert first.disposition is AppendDisposition.APPENDED
    assert repository.append(value).disposition is AppendDisposition.REPLAYED
    with pytest.raises(EvidenceDigestConflict):
        repository.append(replace(value, reason_code="EXECUTION_FAILED"))
    scope = AuthorizedEvidenceScope("execution-test", "quality")
    assert repository.high_water_mark(scope) >= first.record.storage_sequence
    assert (
        repository.read_execution(
            scope,
            "execution-001",
            through_high_water_mark=first.record.storage_sequence or 0,
        )[-1].payload_digest
        == value.payload_digest
    )
    assert (
        repository.read_execution(
            AuthorizedEvidenceScope("execution-test", "other"),
            "execution-001",
            through_high_water_mark=10**9,
        )
        == ()
    )
    repository.pool.close()
    authority.pool.close()


def test_postgres_evidence_restart_recovery() -> None:
    authority, repository = repositories()
    value = record()
    appended = repository.append(value).record
    repository.pool.close()
    restarted = PostgresExecutionEvidenceRepository(DATABASE_URL or "")
    rows = restarted.read_execution(
        AuthorizedEvidenceScope("execution-test", "quality"),
        "execution-001",
        through_high_water_mark=appended.storage_sequence or 0,
    )
    assert any(item.evidence_record_id == value.evidence_record_id for item in rows)
    restarted.pool.close()
    authority.pool.close()


def test_concurrent_exact_replay_is_single_append() -> None:
    authority, repository = repositories()
    value = record()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(lambda _: repository.append(value), range(8)))
    dispositions = [result.disposition for result in results]
    assert dispositions.count(AppendDisposition.APPENDED) == 1
    assert dispositions.count(AppendDisposition.REPLAYED) == 7
    assert len({result.record.storage_sequence for result in results}) == 1
    repository.pool.close()
    authority.pool.close()
