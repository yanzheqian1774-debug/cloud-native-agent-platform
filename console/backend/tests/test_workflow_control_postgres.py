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
    AtomicControlCommand,
    InterventionRequest,
    InterventionState,
    InterventionTarget,
    InterventionTransition,
    WorkflowControlConflict,
    WorkflowControlNotAuthorized,
    canonical_digest,
)
from agent_console.workflow_control_postgres import PostgresWorkflowControlRepository

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION_8 = MIGRATIONS / "0008_execution_runtime_authority.sql"
MIGRATION_9 = MIGRATIONS / "0009_workflow_control_persistence.sql"


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
