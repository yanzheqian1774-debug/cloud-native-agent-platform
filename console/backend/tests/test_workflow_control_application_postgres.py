# ruff: noqa: E501
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.workflow_control_application import (
    TrustedPrincipal,
    WorkflowControlApplicationService,
    minimum_disclosure_evidence,
)
from agent_console.workflow_control_domain import (
    AtomicCommandType,
    InterventionRequest,
    InterventionTarget,
    WorkflowControlConflict,
    WorkflowControlOperation,
)
from agent_console.workflow_control_postgres import PostgresWorkflowControlRepository

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"


def repository() -> PostgresWorkflowControlRepository:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )
        exists = connection.execute(
            "SELECT to_regclass('execution_authority.schema_migrations')"
        ).fetchone()[0]
    if exists is None:
        old = PostgresExecutionAuthorityRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
        )
        old.migrate()
        old.pool.close()
    for version in (9, 10):
        value = PostgresWorkflowControlRepository(
            DATABASE_URL or "",
            migration_path=next(MIGRATIONS.glob(f"{version:04d}_*.sql")),
        )
        value.migrate()
        value.pool.close()
    value = PostgresWorkflowControlRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0011_workflow_control_plan_evidence_outcome.sql",
    )
    value.migrate()
    return value


def seed_run(value: PostgresWorkflowControlRepository, suffix: str):
    scope = ScopeIdentity(f"tenant-{suffix}", "domain")
    run_id = f"run-{suffix}"
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO workflow_definition.definitions(namespace,security_domain,workflow_definition_id,aggregate_version,record) VALUES (%s,%s,%s,1,'{}')",
            (scope.namespace, scope.security_domain, f"workflow-{suffix}"),
        )
        connection.execute(
            "INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,aggregate_version,plan_digest,canonical_bytes,created_at,updated_at) VALUES (%s,%s,%s,1,%s,'revision',%s,'APPROVED',1,%s,%s,now(),now())",
            (
                scope.namespace,
                scope.security_domain,
                f"plan-{suffix}",
                f"workflow-{suffix}",
                "b" * 64,
                "c" * 64,
                b"{}",
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.digital_employee_instances(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) VALUES (%s,%s,%s,'revision',1,'{}')",
            (scope.namespace, scope.security_domain, f"employee-{suffix}"),
        )
        connection.execute(
            "INSERT INTO execution_authority.assignments(namespace,security_domain,assignment_id,digital_employee_instance_id,approved_input_digest,record) VALUES (%s,%s,%s,%s,%s,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                f"assignment-{suffix}",
                f"employee-{suffix}",
                "a" * 64,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,assignment_id,approved_plan_revision_id,record,aggregate_version,control_state,plan_id,plan_version,approved_plan_digest) VALUES (%s,%s,%s,%s,'revision','{}',1,'RUNNING',%s,1,%s)",
            (
                scope.namespace,
                scope.security_domain,
                run_id,
                f"assignment-{suffix}",
                f"plan-{suffix}",
                "c" * 64,
            ),
        )
    return scope, run_id


def request_operation(scope: ScopeIdentity, run_id: str, suffix: str):
    now = datetime.now(UTC)
    target = InterventionTarget(workflow_run_id=run_id)
    request = InterventionRequest(
        f"intervention-{suffix}",
        "PAUSE",
        "BUSINESS_REQUEST",
        "actor",
        "role:operator",
        1,
        target,
        {"category": "pause"},
        now,
    )
    evidence = minimum_disclosure_evidence(
        evidence_id=f"evidence-{suffix}",
        workflow_id=run_id,
        task_id=f"task-context-{suffix}",
        execution_id=run_id,
        attempt_ordinal=1,
        event_ordinal=1,
        event_type="INTERVENTION_REQUESTED",
        category="WORKFLOW_CONTROL",
        reason_code="PAUSE_REQUESTED",
        occurred_at=now,
    )
    return WorkflowControlOperation(
        scope,
        AtomicCommandType.REQUEST_INTERVENTION,
        "actor",
        f"key-{suffix}",
        {"action": "PAUSE", "target": run_id},
        f"command-{suffix}",
        now,
        now + timedelta(days=30),
        target,
        1,
        intervention_id=request.intervention_id,
        request=request,
        evidence_records=(evidence,),
    )


def test_postgres_request_replay_restart_scope_and_conflict() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    operation = request_operation(scope, run_id, suffix)
    principal = TrustedPrincipal(
        "actor", scope, frozenset({AtomicCommandType.REQUEST_INTERVENTION})
    )
    service = WorkflowControlApplicationService(value)
    first = service.execute(principal, operation)
    assert first.evidence_ids == (f"evidence-{suffix}",)
    assert service.execute(principal, operation).durable.replayed is True
    with pytest.raises(WorkflowControlConflict, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        service.execute(
            principal,
            WorkflowControlOperation(
                **{**operation.__dict__, "payload": {"action": "different"}}
            ),
        )
    value.pool.close()

    restarted = PostgresWorkflowControlRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0011_workflow_control_plan_evidence_outcome.sql",
    )
    assert (
        WorkflowControlApplicationService(restarted)
        .execute(principal, operation)
        .durable.replayed
        is True
    )
    assert (
        restarted.read_linked_evidence(
            ScopeIdentity("other", "domain"), operation.intervention_id or ""
        )
        == ()
    )
    restarted.pool.close()
