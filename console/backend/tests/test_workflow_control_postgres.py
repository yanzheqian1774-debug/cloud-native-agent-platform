# ruff: noqa: E501
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from agent_console.execution_postgres import (
    PostgresExecutionAuthorityRepository,
    ScopeIdentity,
)
from agent_console.workflow_control_domain import (
    ApprovalDecision,
    AtomicCommandType,
    AtomicControlCommand,
    InterventionDecision,
    InterventionRequest,
    InterventionReview,
    InterventionState,
    InterventionTarget,
    InterventionTransition,
    WorkflowControlConflict,
    WorkflowControlNotAuthorized,
    WorkflowControlOperation,
    canonical_digest,
)
from agent_console.workflow_control_postgres import PostgresWorkflowControlRepository

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION_8 = MIGRATIONS / "0008_execution_runtime_authority.sql"
MIGRATION_9 = MIGRATIONS / "0009_workflow_control_persistence.sql"
MIGRATION_10 = MIGRATIONS / "0010_workflow_control_uow_extension.sql"


def repository() -> PostgresWorkflowControlRepository:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )
        table_exists = connection.execute(
            "SELECT to_regclass('execution_authority.schema_migrations') AS name"
        ).fetchone()[0]
        has_0008 = (
            None
            if table_exists is None
            else connection.execute(
                "SELECT 1 FROM execution_authority.schema_migrations WHERE version=8"
            ).fetchone()
        )
    if has_0008 is None:
        old = PostgresExecutionAuthorityRepository(
            DATABASE_URL or "", migration_path=MIGRATION_8
        )
        old.migrate()
        old.pool.close()
    value = PostgresWorkflowControlRepository(
        DATABASE_URL or "", migration_path=MIGRATION_9
    )
    value.migrate()
    return value


def extended_repository() -> PostgresWorkflowControlRepository:
    old = repository()
    old.pool.close()
    value = PostgresWorkflowControlRepository(
        DATABASE_URL or "", migration_path=MIGRATION_10
    )
    value.migrate()
    return value


def seed_run(
    value: PostgresWorkflowControlRepository, suffix: str
) -> tuple[ScopeIdentity, str]:
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


def command(
    scope: ScopeIdentity, run_id: str, suffix: str, *, digest: str | None = None
) -> AtomicControlCommand:
    now = datetime.now(UTC)
    request = InterventionRequest(
        f"intervention-{suffix}",
        "PAUSE",
        "BUSINESS_REQUEST",
        "actor",
        "role:operator",
        1,
        InterventionTarget(workflow_run_id=run_id),
        {"category": "pause"},
        now,
    )
    transition = InterventionTransition(
        f"transition-{suffix}",
        request.intervention_id,
        2,
        InterventionState.REQUESTED,
        InterventionState.AUTHORIZED,
        "actor",
        "role:operator",
        "POLICY",
        now,
    )
    payload = digest or canonical_digest(
        {
            "scope": [scope.namespace, scope.security_domain],
            "run": run_id,
            "action": "PAUSE",
        }
    )
    return AtomicControlCommand(
        scope,
        "PAUSE",
        f"key-{suffix}",
        payload,
        request,
        transition,
        f"control-{suffix}",
        "PAUSE_REQUESTED",
        {"action": "PAUSE"},
        now + timedelta(days=30),
    )


def test_migration_0001_through_0009_empty_and_populated_0008() -> None:
    suffix = uuid.uuid4().hex
    database_name = f"impl221_{suffix}"
    admin = psycopg.connect(DATABASE_URL or "", autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = (DATABASE_URL or "").rsplit("/", 1)[0] + f"/{database_name}"
    with psycopg.connect(database_url) as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )
    old = PostgresExecutionAuthorityRepository(database_url, migration_path=MIGRATION_8)
    old.migrate()
    with old.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO execution_authority.digital_employee_instances(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) VALUES (%s,'domain',%s,'revision',1,'{}')",
            (f"legacy-{suffix}", f"employee-{suffix}"),
        )
        connection.execute(
            "INSERT INTO execution_authority.assignments(namespace,security_domain,assignment_id,digital_employee_instance_id,approved_input_digest,record) VALUES (%s,'domain',%s,%s,%s,'{}')",
            (
                f"legacy-{suffix}",
                f"assignment-{suffix}",
                f"employee-{suffix}",
                "a" * 64,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,assignment_id,approved_plan_revision_id,record) VALUES (%s,'domain',%s,%s,'legacy','{}')",
            (f"legacy-{suffix}", f"run-{suffix}", f"assignment-{suffix}"),
        )
    old.pool.close()
    value = PostgresWorkflowControlRepository(database_url, migration_path=MIGRATION_9)
    value.migrate()
    with value.pool.connection() as connection:
        row = connection.execute(
            "SELECT aggregate_version,control_state FROM execution_authority.workflow_runs WHERE namespace=%s",
            (f"legacy-{suffix}",),
        ).fetchone()
    assert row == {"aggregate_version": 1, "control_state": "LEGACY_UNBOUND"}
    value.pool.close()
    admin.execute(f'DROP DATABASE "{database_name}"')
    admin.close()


def test_atomic_uow_replay_mismatch_stale_scope_and_restart() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    original = command(scope, run_id, suffix)
    result = value.persist(original, authorized=True)
    assert result.target_version == 2
    assert value.persist(original, authorized=True).replayed is True
    with pytest.raises(WorkflowControlNotAuthorized):
        value.persist(
            command(scope, run_id, f"unauthorized-{suffix}"), authorized=False
        )
    different = AtomicControlCommand(
        **{**original.__dict__, "payload_digest": "f" * 64}
    )
    with pytest.raises(WorkflowControlConflict, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        value.persist(different, authorized=True)
    stale = command(scope, run_id, f"stale-{suffix}")
    with pytest.raises(WorkflowControlConflict, match="STALE_AGGREGATE_VERSION"):
        value.persist(stale, authorized=True)
    restarted = PostgresWorkflowControlRepository(
        DATABASE_URL or "", migration_path=MIGRATION_9
    )
    assert restarted.persist(original, authorized=True).replayed is True
    assert (
        restarted.read_transitions(scope, original.request.intervention_id)[0].to_state
        is InterventionState.REQUESTED
    )
    assert (
        restarted.read_transitions(
            ScopeIdentity("other", "domain"), original.request.intervention_id
        )
        == ()
    )
    value.pool.close()
    restarted.pool.close()


def test_partial_write_rolls_back_when_required_link_is_missing() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    original = command(scope, run_id, suffix)
    broken = AtomicControlCommand(**{**original.__dict__, "evidence_ids": ("missing",)})
    with pytest.raises(WorkflowControlConflict):
        value.persist(broken, authorized=True)
    with value.pool.connection() as connection:
        run = connection.execute(
            "SELECT aggregate_version,control_state FROM execution_authority.workflow_runs WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
            (scope.namespace, scope.security_domain, run_id),
        ).fetchone()
        interventions = connection.execute(
            "SELECT count(*) AS count FROM execution_authority.interventions WHERE namespace=%s AND security_domain=%s AND intervention_id=%s",
            (scope.namespace, scope.security_domain, original.request.intervention_id),
        ).fetchone()
        claims = connection.execute(
            "SELECT count(*) AS count FROM execution_authority.idempotency_claims WHERE namespace=%s AND security_domain=%s AND idempotency_key=%s",
            (scope.namespace, scope.security_domain, original.idempotency_key),
        ).fetchone()
    assert run == {"aggregate_version": 1, "control_state": "RUNNING"}
    assert interventions["count"] == claims["count"] == 0
    value.pool.close()


def test_invalid_target_transition_and_cross_tenant_target_roll_back() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    invalid = AtomicControlCommand(
        **{**command(scope, run_id, suffix).__dict__, "target_state": "PAUSED"}
    )
    with pytest.raises(
        WorkflowControlConflict, match="INVALID_TARGET_STATE_TRANSITION"
    ):
        value.persist(invalid, authorized=True)
    cross_scope = ScopeIdentity("other-tenant", scope.security_domain)
    cross_tenant = command(cross_scope, run_id, f"cross-{suffix}")
    with pytest.raises(WorkflowControlConflict, match="WORKFLOW_CONTROL_CONFLICT"):
        value.persist(cross_tenant, authorized=True)
    with value.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM execution_authority.idempotency_claims WHERE idempotency_key IN (%s,%s)",
                (invalid.idempotency_key, cross_tenant.idempotency_key),
            ).fetchone()["count"]
            == 0
        )
    value.pool.close()


def seed_failed_attempt(
    value: PostgresWorkflowControlRepository, suffix: str
) -> tuple[ScopeIdentity, str, InterventionRequest]:
    scope, run_id = seed_run(value, suffix)
    task_id = f"task-{suffix}"
    attempt_id = f"attempt-{suffix}"
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO execution_authority.task_runs(namespace,security_domain,task_run_id,workflow_run_id,record,aggregate_version,control_state,workflow_node_id) VALUES (%s,%s,%s,%s,'{}',1,'FAILED','node')",
            (scope.namespace, scope.security_domain, task_id, run_id),
        )
        connection.execute(
            "INSERT INTO execution_authority.attempts(namespace,security_domain,attempt_id,task_run_id,aggregate_digest,record,aggregate_version,control_state,attempt_ordinal) VALUES (%s,%s,%s,%s,%s,'{}',1,'FAILED',1)",
            (scope.namespace, scope.security_domain, attempt_id, task_id, "d" * 64),
        )
    now = datetime.now(UTC)
    request = InterventionRequest(
        f"retry-intervention-{suffix}",
        "RETRY_ATTEMPT",
        "OPERATIONAL_RECOVERY",
        "actor",
        "role:operator",
        1,
        InterventionTarget(attempt_id=attempt_id),
        {"action": "retry", "attempt_id": attempt_id},
        now,
    )
    value.request_intervention(scope, request)
    return scope, attempt_id, request


def authorize_request(
    value: PostgresWorkflowControlRepository,
    scope: ScopeIdentity,
    request: InterventionRequest,
    suffix: str,
) -> None:
    now = datetime.now(UTC)
    review = InterventionReview(
        f"review-{suffix}", request.intervention_id, "reviewer", "role:reviewer", now
    )
    value.append_review(scope, review)
    value.append_decision(
        scope,
        InterventionDecision(
            f"decision-{suffix}",
            request.intervention_id,
            review.review_id,
            "AUTHORIZE",
            "decider",
            "role:decider",
            "POLICY",
            now,
        ),
    )


def retry_operation(
    scope: ScopeIdentity,
    attempt_id: str,
    request: InterventionRequest,
    suffix: str,
) -> WorkflowControlOperation:
    now = datetime.now(UTC)
    return WorkflowControlOperation(
        scope,
        AtomicCommandType.RETRY_ATTEMPT,
        "actor",
        f"retry-key-{suffix}",
        {"attempt_id": attempt_id, "successor_attempt_id": f"successor-{suffix}"},
        f"retry-command-{suffix}",
        now,
        now + timedelta(days=30),
        request.target,
        1,
        intervention_id=request.intervention_id,
        successor_id=f"successor-{suffix}",
        affected_attempt_id=attempt_id,
    )


def test_0010_retry_successor_replay_restart_and_immutable_predecessor() -> None:
    value = extended_repository()
    suffix = uuid.uuid4().hex
    scope, attempt_id, request = seed_failed_attempt(value, suffix)
    authorize_request(value, scope, request, suffix)
    operation = retry_operation(scope, attempt_id, request, suffix)
    result = value.persist_operation(operation, authorized=True)
    assert result.successor_attempt_id == f"successor-{suffix}"
    assert value.persist_operation(operation, authorized=True).replayed is True
    assert value.read_successor_attempts(scope, attempt_id) == (f"successor-{suffix}",)
    with value.pool.connection() as connection:
        predecessor = connection.execute(
            "SELECT control_state,aggregate_version FROM execution_authority.attempts WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
            (scope.namespace, scope.security_domain, attempt_id),
        ).fetchone()
        successor = connection.execute(
            "SELECT predecessor_attempt_id,attempt_ordinal,control_state FROM execution_authority.attempts WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
            (scope.namespace, scope.security_domain, f"successor-{suffix}"),
        ).fetchone()
    assert predecessor == {"control_state": "FAILED", "aggregate_version": 1}
    assert successor == {
        "predecessor_attempt_id": attempt_id,
        "attempt_ordinal": 2,
        "control_state": "PENDING",
    }
    value.pool.close()
    restarted = PostgresWorkflowControlRepository(
        DATABASE_URL or "", migration_path=MIGRATION_10
    )
    restarted.compatibility()
    assert restarted.persist_operation(operation, authorized=True).replayed is True
    restarted.pool.close()


def test_0010_retry_negative_controls_roll_back_everything() -> None:
    value = extended_repository()
    suffix = uuid.uuid4().hex
    scope, attempt_id, request = seed_failed_attempt(value, suffix)
    authorize_request(value, scope, request, suffix)
    operation = retry_operation(scope, attempt_id, request, suffix)
    broken = WorkflowControlOperation(
        **{**operation.__dict__, "evidence_ids": ("missing-evidence",)}
    )
    with pytest.raises(WorkflowControlConflict):
        value.persist_operation(broken, authorized=True)
    with value.pool.connection() as connection:
        counts = connection.execute(
            "SELECT (SELECT count(*) FROM execution_authority.attempts WHERE namespace=%s AND attempt_id=%s) AS successors,(SELECT count(*) FROM execution_authority.control_commands WHERE namespace=%s AND control_command_id=%s) AS commands,(SELECT count(*) FROM execution_authority.idempotency_claims WHERE namespace=%s AND idempotency_key=%s) AS claims",
            (
                scope.namespace,
                operation.successor_id,
                scope.namespace,
                operation.control_command_id,
                scope.namespace,
                operation.idempotency_key,
            ),
        ).fetchone()
    assert counts == {"successors": 0, "commands": 0, "claims": 0}
    value.persist_operation(operation, authorized=True)
    mismatch = WorkflowControlOperation(
        **{**operation.__dict__, "payload": {"different": True}}
    )
    with pytest.raises(WorkflowControlConflict, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        value.persist_operation(mismatch, authorized=True)
    value.pool.close()


def test_0010_successor_run_and_cancel_preserve_terminal_predecessor() -> None:
    value = extended_repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.workflow_runs SET control_state='FAILED' WHERE namespace=%s AND workflow_run_id=%s",
            (scope.namespace, run_id),
        )
    now = datetime.now(UTC)
    request = InterventionRequest(
        f"rerun-intervention-{suffix}",
        "RERUN_APPROVED_PLAN",
        "OPERATIONAL_RECOVERY",
        "actor",
        "role:operator",
        1,
        InterventionTarget(workflow_run_id=run_id),
        {"action": "rerun"},
        now,
    )
    value.request_intervention(scope, request)
    authorize_request(value, scope, request, suffix)
    operation = WorkflowControlOperation(
        scope,
        AtomicCommandType.CREATE_SUCCESSOR_RUN,
        "actor",
        f"rerun-key-{suffix}",
        {"predecessor": run_id},
        f"rerun-command-{suffix}",
        now,
        now + timedelta(days=30),
        request.target,
        1,
        intervention_id=request.intervention_id,
        successor_id=f"successor-run-{suffix}",
    )
    result = value.persist_operation(operation, authorized=True)
    assert result.successor_workflow_run_id == f"successor-run-{suffix}"
    assert value.read_successor_runs(scope, run_id) == (f"successor-run-{suffix}",)
    with value.pool.connection() as connection:
        predecessor = connection.execute(
            "SELECT control_state,aggregate_version FROM execution_authority.workflow_runs WHERE namespace=%s AND workflow_run_id=%s",
            (scope.namespace, run_id),
        ).fetchone()
    assert predecessor == {"control_state": "FAILED", "aggregate_version": 1}
    value.pool.close()


def test_0010_decision_application_is_guarded_and_atomic() -> None:
    value = extended_repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    now = datetime.now(UTC)
    request = InterventionRequest(
        f"apply-intervention-{suffix}",
        "PAUSE",
        "BUSINESS_REQUEST",
        "actor",
        "role:operator",
        1,
        InterventionTarget(workflow_run_id=run_id),
        {"action": "pause"},
        now,
    )
    value.request_intervention(scope, request)
    authorize_request(value, scope, request, suffix)
    operation = WorkflowControlOperation(
        scope,
        AtomicCommandType.APPLY_INTERVENTION_DECISION,
        "actor",
        f"apply-key-{suffix}",
        {"target_state": "PAUSE_REQUESTED"},
        f"apply-command-{suffix}",
        now,
        now + timedelta(days=30),
        request.target,
        1,
        intervention_id=request.intervention_id,
    )
    result = value.persist_operation(operation, authorized=True)
    assert result.target_version == 2
    assert [
        item.to_state.value
        for item in value.read_transitions(scope, request.intervention_id)
    ] == [
        "REQUESTED",
        "AUTHORIZED",
        "APPLICATION_PENDING",
        "APPLIED",
    ]
    terminal = WorkflowControlOperation(
        **{
            **operation.__dict__,
            "idempotency_key": f"again-{suffix}",
            "target_expected_version": 2,
        }
    )
    with pytest.raises(WorkflowControlConflict, match="APPROVED_DECISION_REQUIRED"):
        value.persist_operation(terminal, authorized=True)
    value.pool.close()


def test_0010_exact_plan_approval_and_continuation_roll_back_together() -> None:
    value = extended_repository()
    suffix = uuid.uuid4().hex
    scope, run_id = seed_run(value, suffix)
    now = datetime.now(UTC)
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.plans SET status='PENDING_APPROVAL' WHERE namespace=%s AND plan_id=%s",
            (scope.namespace, f"plan-{suffix}"),
        )
        connection.execute(
            "UPDATE execution_authority.workflow_runs SET control_state='PAUSED' WHERE namespace=%s AND workflow_run_id=%s",
            (scope.namespace, run_id),
        )
    request = InterventionRequest(
        f"approval-intervention-{suffix}",
        "APPROVE_AND_CONTINUE",
        "HUMAN_APPROVAL",
        "actor",
        "role:approver",
        1,
        InterventionTarget(workflow_run_id=run_id),
        {"action": "approve"},
        now,
    )
    value.request_intervention(scope, request)
    authorize_request(value, scope, request, suffix)
    approval = ApprovalDecision(
        f"approval-{suffix}",
        f"plan-{suffix}",
        1,
        "c" * 64,
        1,
        "APPROVE",
        "actor",
        "role:approver",
        "BUSINESS_APPROVAL",
        "e" * 64,
        now,
    )
    operation = WorkflowControlOperation(
        scope,
        AtomicCommandType.APPROVE_AND_CONTINUE,
        "actor",
        f"approval-key-{suffix}",
        {"plan_id": f"plan-{suffix}", "plan_version": 1, "plan_digest": "c" * 64},
        f"approval-command-{suffix}",
        now,
        now + timedelta(days=30),
        request.target,
        1,
        intervention_id=request.intervention_id,
        plan_id=f"plan-{suffix}",
        plan_version=1,
        plan_digest="c" * 64,
        approval=approval,
        evidence_ids=("missing",),
    )
    with pytest.raises(WorkflowControlConflict):
        value.persist_operation(operation, authorized=True)
    with value.pool.connection() as connection:
        state = connection.execute(
            "SELECT p.status,r.control_state,(SELECT count(*) FROM execution_authority.plan_approval_decisions WHERE namespace=%s AND plan_id=%s) AS decisions FROM execution_authority.plans p JOIN execution_authority.workflow_runs r ON r.namespace=p.namespace AND r.security_domain=p.security_domain AND r.plan_id=p.plan_id AND r.plan_version=p.plan_version WHERE p.namespace=%s AND p.plan_id=%s",
            (scope.namespace, f"plan-{suffix}", scope.namespace, f"plan-{suffix}"),
        ).fetchone()
    assert state == {
        "status": "PENDING_APPROVAL",
        "control_state": "PAUSED",
        "decisions": 0,
    }
    valid = WorkflowControlOperation(**{**operation.__dict__, "evidence_ids": ()})
    result = value.persist_operation(valid, authorized=True)
    assert result.approval_decision_id == approval.approval_decision_id
    assert result.target_version == 2
    value.pool.close()


def test_0010_runtime_replacement_requires_scoped_placement_and_command_linkage() -> (
    None
):
    value = extended_repository()
    suffix = uuid.uuid4().hex
    scope, attempt_id, _ = seed_failed_attempt(value, suffix)
    now = datetime.now(UTC)
    runtime_id = f"runtime-{suffix}"
    agent_id = f"agent-{suffix}"
    placement_request_id = f"placement-request-{suffix}"
    placement_id = f"placement-{suffix}"
    runtime_command_id = f"runtime-command-{suffix}"
    with value.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO execution_authority.runtime_instances(namespace,security_domain,runtime_instance_id,current_generation,aggregate_version,record) VALUES (%s,%s,%s,1,1,'{}')",
            (scope.namespace, scope.security_domain, runtime_id),
        )
        connection.execute(
            "INSERT INTO execution_authority.agent_instances(namespace,security_domain,agent_instance_id,agent_revision_id,runtime_instance_id,aggregate_version,record) VALUES (%s,%s,%s,'revision',%s,1,'{}')",
            (scope.namespace, scope.security_domain, agent_id, runtime_id),
        )
        connection.execute(
            "INSERT INTO execution_authority.placement_requests(namespace,security_domain,request_id,request_digest,canonical_bytes,attempt_id,agent_instance_id,requested_at) VALUES (%s,%s,%s,%s,'{}',%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                placement_request_id,
                "a" * 64,
                attempt_id,
                agent_id,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.placement_decisions(namespace,security_domain,placement_id,request_id,decision,runtime_instance_id,digest,canonical_record,decided_at) VALUES (%s,%s,%s,%s,'PLACED',%s,%s,'{}',%s)",
            (
                scope.namespace,
                scope.security_domain,
                placement_id,
                placement_request_id,
                runtime_id,
                "b" * 64,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.desired_commands(namespace,security_domain,command_id,runtime_instance_id,generation,command_digest,record,requested_at) VALUES (%s,%s,%s,%s,1,%s,'{}',%s)",
            (
                scope.namespace,
                scope.security_domain,
                runtime_command_id,
                runtime_id,
                "d" * 64,
                now,
            ),
        )
    request = InterventionRequest(
        f"replace-intervention-{suffix}",
        "REQUEST_RUNTIME_REPLACEMENT",
        "RUNTIME_HEALTH",
        "actor",
        "role:operator",
        1,
        InterventionTarget(attempt_id=attempt_id),
        {"action": "replace"},
        now,
    )
    value.request_intervention(scope, request)
    authorize_request(value, scope, request, suffix)
    operation = WorkflowControlOperation(
        scope,
        AtomicCommandType.REPLACE_RUNTIME,
        "actor",
        f"replace-key-{suffix}",
        {"attempt_id": attempt_id, "placement_id": placement_id},
        f"replace-command-{suffix}",
        now,
        now + timedelta(days=30),
        request.target,
        1,
        intervention_id=request.intervention_id,
        placement_id=placement_id,
        runtime_command_id=runtime_command_id,
        affected_attempt_id=attempt_id,
    )
    assert (
        value.persist_operation(operation, authorized=True).runtime_command_id
        == runtime_command_id
    )
    foreign = WorkflowControlOperation(
        **{
            **operation.__dict__,
            "idempotency_key": f"foreign-{suffix}",
            "placement_id": "missing",
        }
    )
    with pytest.raises(WorkflowControlConflict, match="INELIGIBLE_PLACEMENT"):
        value.persist_operation(foreign, authorized=True)
    value.pool.close()
