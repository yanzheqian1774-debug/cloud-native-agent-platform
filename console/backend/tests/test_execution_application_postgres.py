import os
import uuid
from pathlib import Path

import psycopg
import pytest
from agent_console.execution_application import (
    ApprovedPlanIdentity,
    ExecutionApplicationService,
    ExecutionCompletionService,
    ExecutionEvidenceRecord,
    PostgresExecutionCompletionWriter,
    RecordCompletionCommand,
    RetryExecutionCommand,
    StartExecutionCommand,
)
from agent_console.execution_postgres import (
    AppendDisposition,
    AssignmentId,
    DigitalEmployeeInstanceId,
    PostgresExecutionAuthorityRepository,
    ScopeIdentity,
)
from agent_console.planning import (
    CanonicalWorkflowRevision,
    IntentRevision,
    TaskRequirement,
)

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION = MIGRATIONS / "0008_execution_runtime_authority.sql"


def repository() -> PostgresExecutionAuthorityRepository:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )
    value = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    value.migrate()
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.evidence_cutover SET "
            "state='POSTGRES_ACTIVE',authoritative_writer='POSTGRES' "
            "WHERE singleton=true"
        )
    return value


def approved_plan(suffix: str) -> CanonicalWorkflowRevision:
    intent = IntentRevision(
        f"intent-{suffix}",
        f"intent-revision-{suffix}",
        1,
        None,
        "planning.v1",
        "policy.v1",
        f"question-{suffix}",
        "objective",
        (),
        ("done",),
        "a" * 64,
    )
    task = TaskRequirement(
        f"requirement-{suffix}",
        "collect",
        f"intent-revision-{suffix}",
        "COLLECT",
        "purpose",
        (),
        ("result",),
        (),
        (),
        ("done",),
        "LOW",
        "REQUIRED",
        (),
        0,
    )
    return CanonicalWorkflowRevision(
        f"plan-{suffix}",
        1,
        None,
        f"tenant-{suffix}",
        "domain",
        "b" * 64,
        f"approval-{suffix}",
        "policy.v1",
        intent,
        (task,),
        ("collect",),
        (),
        True,
    )


def start(value, suffix: str):
    plan = approved_plan(suffix)
    command = StartExecutionCommand(
        ScopeIdentity(plan.tenant_id, plan.security_domain),
        plan,
        ApprovedPlanIdentity(
            plan.canonical_workflow_revision_id,
            plan.approved_candidate_digest,
            plan.approval_id,
        ),
        AssignmentId(f"assignment-{suffix}"),
        DigitalEmployeeInstanceId(f"employee-{suffix}"),
        "collect",
        f"start-{suffix}",
    )
    return ExecutionApplicationService(value).start(command)


def evidence(identity, suffix: str, ordinal: int) -> ExecutionEvidenceRecord:
    return ExecutionEvidenceRecord.from_allowlisted(
        {
            "evidence_record_id": f"evidence-{suffix}-{ordinal}",
            "namespace": identity.scope.namespace,
            "security_domain": identity.scope.security_domain,
            "platform_execution_identity": str(identity.attempt.attempt_id),
            "workflow_identity": str(identity.workflow_run.workflow_run_id),
            "task_identity": str(identity.task_run.task_run_id),
            "attempt_ordinal": 1,
            "event_ordinal": ordinal,
            "event_type": "EXECUTION_OUTCOME",
            "occurred_at": f"2026-09-03T00:00:0{ordinal}+00:00",
            "runtime_classification": "NONE",
            "selected_instance_identity": "none",
            "capability_identity": None,
            "authorization_decision": "ALLOW",
            "reason_code": "EXECUTION_COMPLETED",
            "provider_correlation_id": None,
            "provider_call_count": 0,
            "outcome_classification": "SUCCEEDED",
            "outcome_reference": f"outcome-{suffix}",
            "references": [],
            "limitation_code": None,
            "supersedes_record_id": None,
            "schema_version": 1,
        }
    )


def completion(identity, suffix: str, facts=None) -> RecordCompletionCommand:
    records = facts or (evidence(identity, suffix, 1), evidence(identity, suffix, 2))
    return RecordCompletionCommand(
        identity.scope,
        identity.attempt.attempt_id,
        records,
        f"outcome-{suffix}",
        {
            "outcome_id": f"outcome-{suffix}",
            "workflow_run_id": str(identity.workflow_run.workflow_run_id),
            "task_run_id": str(identity.task_run.task_run_id),
            "attempt_id": str(identity.attempt.attempt_id),
            "approved_plan_revision_id": (
                identity.workflow_run.approved_plan_revision_id
            ),
            "evidence_ids": [item.evidence_record_id for item in records],
            "classification": "SUCCEEDED",
        },
    )


def test_postgres_replay_restart_retry_scope_and_order() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    started = start(value, suffix)
    assert start(value, suffix).disposition is AppendDisposition.REPLAYED
    restarted = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    service = ExecutionApplicationService(restarted)
    assert (
        service.read_attempt(
            started.identity.scope, started.identity.attempt.attempt_id
        )
        == started.identity
    )
    assert (
        service.read_attempt(
            ScopeIdentity("other", "domain"), started.identity.attempt.attempt_id
        )
        is None
    )
    retried = service.retry(
        RetryExecutionCommand(
            started.identity.scope, started.identity.attempt.attempt_id, "retry"
        )
    )
    assert (
        retried.identity.attempt.predecessor_attempt_id
        == started.identity.attempt.attempt_id
    )

    completion_service = ExecutionCompletionService(
        restarted, PostgresExecutionCompletionWriter(restarted)
    )
    command = completion(started.identity, suffix)
    assert completion_service.record(command).disposition is AppendDisposition.APPENDED
    assert completion_service.record(command).disposition is AppendDisposition.REPLAYED
    with restarted.pool.connection() as connection:
        rows = connection.execute(
            "SELECT evidence_record_id FROM execution_authority.execution_evidence "
            "WHERE namespace=%s AND security_domain=%s "
            "AND platform_execution_identity=%s "
            "ORDER BY storage_sequence",
            (
                started.identity.scope.namespace,
                started.identity.scope.security_domain,
                str(started.identity.attempt.attempt_id),
            ),
        ).fetchall()
    assert [row["evidence_record_id"] for row in rows] == [
        item.evidence_record_id for item in command.evidence
    ]
    value.pool.close()
    restarted.pool.close()


def test_completion_failure_rolls_back_evidence_and_outcome() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    started = start(value, suffix)
    service = ExecutionCompletionService(
        value, PostgresExecutionCompletionWriter(value)
    )
    command = completion(started.identity, suffix)
    assert service.record(command).disposition is AppendDisposition.APPENDED
    conflicting = completion(
        started.identity,
        suffix,
        (evidence(started.identity, f"{suffix}-new", 1),),
    )
    conflicting = RecordCompletionCommand(
        conflicting.scope,
        conflicting.attempt_id,
        conflicting.evidence,
        command.outcome_id,
        {**conflicting.outcome, "outcome_id": command.outcome_id},
    )
    with pytest.raises(Exception, match="OUTCOME_CONFLICT"):
        service.record(conflicting)
    with value.pool.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM execution_authority.execution_evidence "
            "WHERE evidence_record_id=%s",
            (conflicting.evidence[0].evidence_record_id,),
        ).fetchone()["count"]
    assert count == 0
    value.pool.close()
