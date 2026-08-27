import sqlite3
from dataclasses import replace

import pytest
from agent_core.execution_evidence import (
    AppendDisposition,
    AuthorizationDecision,
    AuthorizedEvidenceScope,
    EvidenceDigestConflict,
    EvidenceEventType,
    EvidenceRepositoryUnavailable,
    EvidenceSchemaIncompatible,
    ExecutionEvidenceRecord,
    OutcomeClassification,
    SQLiteExecutionEvidenceRepository,
)


def record(**overrides) -> ExecutionEvidenceRecord:
    values = {
        "evidence_record_id": "evidence.native.pei-001.1.1",
        "namespace": "agent-workloads",
        "security_domain": "business-unit-a",
        "platform_execution_identity": "pei-001",
        "workflow_identity": "workflow-uid-001",
        "task_identity": "task-uid-001",
        "attempt_ordinal": 1,
        "event_ordinal": 1,
        "event_type": EvidenceEventType.EXECUTION_OUTCOME,
        "occurred_at": "2026-08-27T08:00:00Z",
        "runtime_classification": "NATIVE",
        "selected_instance_identity": "instance-001",
        "capability_identity": "customer-lookup",
        "authorization_decision": AuthorizationDecision.ALLOW,
        "reason_code": "TASK_RUNTIME_SUCCEEDED",
        "provider_correlation_id": "provider-request-001",
        "provider_call_count": 1,
        "outcome_classification": OutcomeClassification.SUCCEEDED,
        "outcome_reference": "outcome-001",
        "evidence_references": ("evidence-ref-001",),
        "citation_references": ("citation-ref-001",),
        "schema_version": 1,
    }
    values.update(overrides)
    return ExecutionEvidenceRecord(**values)


def scope(domain="business-unit-a") -> AuthorizedEvidenceScope:
    return AuthorizedEvidenceScope("agent-workloads", domain)


def test_empty_database_bootstrap_append_and_restart_durability(tmp_path) -> None:
    path = tmp_path / "evidence.sqlite"
    repository = SQLiteExecutionEvidenceRepository(path)
    appended = repository.append(record())
    assert appended.disposition is AppendDisposition.APPENDED
    assert appended.record.storage_sequence == 1

    restarted = SQLiteExecutionEvidenceRepository(path)
    assert restarted.high_water_mark(scope()) == 1
    assert restarted.read_execution(scope(), "pei-001", through_high_water_mark=1) == (
        appended.record,
    )


def test_replay_ignores_different_repository_append_time(tmp_path) -> None:
    times = iter(("2026-08-27T09:00:00Z", "2026-08-28T09:00:00Z"))
    repository = SQLiteExecutionEvidenceRepository(
        tmp_path / "evidence.sqlite", clock=lambda: next(times)
    )
    first = repository.append(record())
    replay = repository.append(record())
    assert replay.disposition is AppendDisposition.REPLAYED
    assert replay.record.recorded_at == first.record.recorded_at
    assert repository.high_water_mark(scope()) == 1


def test_digest_conflict_fails_closed_without_second_row(tmp_path) -> None:
    repository = SQLiteExecutionEvidenceRepository(tmp_path / "evidence.sqlite")
    repository.append(record())
    with pytest.raises(EvidenceDigestConflict, match="EVIDENCE_DIGEST_CONFLICT"):
        repository.append(replace(record(), reason_code="NATIVE_EXECUTION_FAILED"))
    assert repository.high_water_mark(scope()) == 1


def test_namespace_and_security_domain_are_isolated(tmp_path) -> None:
    repository = SQLiteExecutionEvidenceRepository(tmp_path / "evidence.sqlite")
    repository.append(record())
    assert (
        repository.read_execution(
            scope("business-unit-b"), "pei-001", through_high_water_mark=100
        )
        == ()
    )
    assert (
        repository.read_execution(
            AuthorizedEvidenceScope("another-namespace", "business-unit-a"),
            "pei-001",
            through_high_water_mark=100,
        )
        == ()
    )


def test_fixed_high_water_mark_excludes_concurrent_later_append(tmp_path) -> None:
    repository = SQLiteExecutionEvidenceRepository(tmp_path / "evidence.sqlite")
    repository.append(record())
    mark = repository.high_water_mark(scope())
    repository.append(
        replace(
            record(),
            evidence_record_id="evidence.native.pei-001.1.2",
            event_ordinal=2,
        )
    )
    rows = repository.read_execution(scope(), "pei-001", through_high_water_mark=mark)
    assert tuple(item.event_ordinal for item in rows) == (1,)


def test_newer_partial_and_unknown_schema_fail_closed(tmp_path) -> None:
    path = tmp_path / "evidence.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE evidence_schema (singleton INTEGER PRIMARY KEY, "
        "schema_version INTEGER, adapter TEXT)"
    )
    connection.execute("INSERT INTO evidence_schema VALUES (1, 2, 'future')")
    connection.commit()
    connection.close()
    with pytest.raises(EvidenceSchemaIncompatible):
        SQLiteExecutionEvidenceRepository(path)


def test_corrupt_database_and_open_failure_are_bounded(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(EvidenceRepositoryUnavailable) as exc_info:
        SQLiteExecutionEvidenceRepository(corrupt)
    assert str(corrupt) not in str(exc_info.value)

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(EvidenceRepositoryUnavailable) as exc_info:
        SQLiteExecutionEvidenceRepository(directory)
    assert str(directory) not in str(exc_info.value)


def test_locked_append_is_bounded_and_rolls_back(tmp_path) -> None:
    path = tmp_path / "evidence.sqlite"
    repository = SQLiteExecutionEvidenceRepository(path, busy_timeout_ms=1)
    lock = sqlite3.connect(path, isolation_level=None)
    lock.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(
            EvidenceRepositoryUnavailable, match="EVIDENCE_APPEND_UNAVAILABLE"
        ):
            repository.append(record())
    finally:
        lock.execute("ROLLBACK")
        lock.close()
    assert repository.high_water_mark(scope()) == 0
