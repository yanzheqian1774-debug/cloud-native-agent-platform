import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from agent_console.execution_domain import (
    CommandResultFact,
    ExecutionConflict,
    ExecutionPersistenceError,
    ExecutionSchemaIncompatible,
    VersionedAggregate,
)
from agent_console.execution_postgres import (
    ADAPTER,
    AgentInstanceId,
    AssignmentId,
    AssignmentIdentity,
    AttemptId,
    AttemptIdentity,
    CommandId,
    CommandResult,
    DigitalEmployeeInstanceId,
    ExecutionIdentityAggregate,
    Generation,
    InterventionId,
    ObservationId,
    OutcomeId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    PostgresExecutionAuthorityRepository,
    PostgresRuntimeDesiredStateRepository,
    PostgresRuntimeObservationRepository,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeHealth,
    RuntimeInstanceId,
    RuntimeObservation,
    RuntimeObservedStateKind,
    RuntimeReadiness,
    ScopeIdentity,
    TaskRunId,
    TaskRunIdentity,
    WorkflowRunId,
    WorkflowRunIdentity,
)

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"
MIGRATION = MIGRATIONS / "0008_execution_runtime_authority.sql"


def apply_chain() -> None:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )


def test_clean_migration_0001_through_0008_and_checksum() -> None:
    apply_chain()
    repository = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    repository.compatibility()
    assert len(repository.migration_checksum) == 64
    with repository.pool.connection() as connection:
        row = connection.execute(
            "SELECT checksum,adapter FROM execution_authority.schema_migrations "
            "WHERE version=8"
        ).fetchone()
        columns = {
            item["column_name"]
            for item in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='execution_authority' AND "
                "table_name IN ('attempts','execution_evidence','evidence_cutover')"
            ).fetchall()
        }
        foreign_keys = connection.execute(
            "SELECT COUNT(*) AS count FROM information_schema.table_constraints "
            "WHERE constraint_schema='execution_authority' AND "
            "constraint_type='FOREIGN KEY' AND "
            "table_name IN ('workflow_runs','interventions','outcomes')"
        ).fetchone()["count"]
    assert row == {"checksum": repository.migration_checksum, "adapter": ADAPTER}
    assert {"aggregate_digest", "import_set_identity", "checkpoint_version"} <= columns
    assert foreign_keys >= 6
    repository.pool.close()


def test_newer_and_partial_schema_fail_closed() -> None:
    repository = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO execution_authority.schema_migrations"
            "(version,checksum,adapter) VALUES (9,%s,%s) "
            "ON CONFLICT DO NOTHING",
            ("f" * 64, ADAPTER),
        )
    with pytest.raises(ExecutionSchemaIncompatible):
        repository.compatibility()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "DELETE FROM execution_authority.schema_migrations WHERE version=9"
        )
        connection.execute(
            "DELETE FROM execution_authority.schema_migrations WHERE version=8"
        )
    with pytest.raises(ExecutionSchemaIncompatible):
        repository.compatibility()
    repository.migrate()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.schema_migrations SET checksum=%s "
            "WHERE version=8",
            ("0" * 64,),
        )
    with pytest.raises(ExecutionSchemaIncompatible):
        repository.compatibility()
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.schema_migrations SET checksum=%s "
            "WHERE version=8",
            (repository.migration_checksum,),
        )
    repository.pool.close()


def identities(suffix: str) -> ExecutionIdentityAggregate:
    scope = ScopeIdentity(f"scope-{suffix}", "quality")
    assignment = AssignmentIdentity(
        AssignmentId(f"assignment-{suffix}"),
        DigitalEmployeeInstanceId(f"employee-{suffix}"),
    )
    workflow = WorkflowRunIdentity(
        WorkflowRunId(f"workflow-{suffix}"),
        assignment.assignment_id,
        f"plan-{suffix}",
    )
    task = TaskRunIdentity(TaskRunId(f"task-{suffix}"), workflow.workflow_run_id)
    attempt = AttemptIdentity(AttemptId(f"attempt-{suffix}"), task.task_run_id)
    return ExecutionIdentityAggregate(scope, assignment, workflow, task, attempt)


def repository() -> PostgresExecutionAuthorityRepository:
    value = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    value.migrate()
    return value


def seed_runtime_agent(
    value: PostgresExecutionAuthorityRepository,
    scope: ScopeIdentity,
    suffix: str,
) -> tuple[RuntimeInstanceId, AgentInstanceId]:
    runtime_id = RuntimeInstanceId(f"runtime-{suffix}")
    agent_id = AgentInstanceId(f"agent-{suffix}")
    value.create_aggregate(
        "runtime_instance",
        VersionedAggregate(
            scope,
            str(runtime_id),
            1,
            {"current_generation": 1},
        ),
    )
    value.create_aggregate(
        "agent_instance",
        VersionedAggregate(
            scope,
            str(agent_id),
            1,
            {
                "agent_revision_id": f"agent-revision-{suffix}",
                "runtime_instance_id": str(runtime_id),
            },
        ),
    )
    return runtime_id, agent_id


def test_identity_generic_aggregates_ports_conflicts_and_scope() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    aggregate = identities(suffix)
    assert value.save(aggregate.scope, aggregate) == aggregate
    assert value.save(aggregate.scope, aggregate) == aggregate
    assert value.get_attempt(aggregate.scope, aggregate.attempt.attempt_id) == aggregate
    other_scope = ScopeIdentity("other-scope", "quality")
    assert value.get_attempt(other_scope, aggregate.attempt.attempt_id) is None
    changed = replace(
        aggregate,
        workflow_run=replace(
            aggregate.workflow_run, approved_plan_revision_id="conflicting-plan"
        ),
    )
    with pytest.raises(ExecutionConflict, match="EXECUTION_IDENTITY_CONFLICT"):
        value.save(aggregate.scope, changed)
    with pytest.raises(ExecutionConflict, match="EXECUTION_IDENTITY_SCOPE_MISMATCH"):
        value.save(other_scope, aggregate)

    digital = VersionedAggregate(
        aggregate.scope,
        f"generic-employee-{suffix}",
        1,
        {"definition_revision_id": f"definition-{suffix}"},
    )
    assert value.create_aggregate("digital_employee_instance", digital) == digital
    assert (
        value.get_aggregate(
            "digital_employee_instance", aggregate.scope, digital.aggregate_id
        )
        == digital
    )
    assert (
        value.get_aggregate(
            "digital_employee_instance", other_scope, digital.aggregate_id
        )
        is None
    )
    replacement = replace(
        digital,
        aggregate_version=2,
        record={"definition_revision_id": f"definition-{suffix}-2"},
    )
    assert (
        value.replace_aggregate(
            "digital_employee_instance", replacement, expected_version=1
        )
        == replacement
    )
    with pytest.raises(ExecutionConflict, match="STALE_EXECUTION_AGGREGATE"):
        value.replace_aggregate(
            "digital_employee_instance", replacement, expected_version=1
        )
    with pytest.raises(
        ExecutionPersistenceError, match="EXECUTION_AGGREGATE_FIELD_INVALID"
    ):
        value.create_aggregate(
            "runtime_instance",
            VersionedAggregate(aggregate.scope, f"bad-{suffix}", 1, {}),
        )
    value.pool.close()


def test_all_typed_surfaces_replay_scope_restart_and_relationships() -> None:
    value = repository()
    suffix = uuid.uuid4().hex
    aggregate = identities(suffix)
    value.save(aggregate.scope, aggregate)
    runtime_id, agent_id = seed_runtime_agent(value, aggregate.scope, suffix)
    now = datetime.now(UTC)
    request = PlacementRequest(
        PlacementRequestId(f"request-{suffix}"),
        aggregate.scope,
        aggregate.workflow_run.workflow_run_id,
        aggregate.task_run.task_run_id,
        aggregate.attempt.attempt_id,
        agent_id,
        f"agent-revision-{suffix}",
        f"runtime-profile-{suffix}",
        (),
        (),
        (),
        (),
        now,
    )
    decision = PlacementDecision.create(
        placement_id=PlacementId(f"placement-{suffix}"),
        request_id=request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=runtime_id,
        policy_version="v1",
        compatibility_facts=(),
        limitation_codes=(),
        decided_at=now,
    )
    assert value.decide(aggregate.scope, request, decision).decision == decision
    assert value.decide(aggregate.scope, request, decision).decision == decision

    command = RuntimeDesiredState(
        runtime_id,
        Generation(1),
        RuntimeDesiredStateKind.RUNNING,
        CommandId(f"command-{suffix}"),
        "test",
        now,
        now + timedelta(minutes=5),
        "START",
    )
    desired = PostgresRuntimeDesiredStateRepository(value)
    assert desired.append(aggregate.scope, command).value == "APPENDED"
    assert desired.append(aggregate.scope, command).value == "REPLAYED"
    assert desired.get(aggregate.scope, command.command_id) == command
    assert desired.read_runtime(aggregate.scope, runtime_id) == (command,)
    conflicting_command = replace(command, reason_classification="CONFLICT")
    with pytest.raises(ExecutionConflict, match="COMMAND_CONFLICT"):
        desired.append(aggregate.scope, conflicting_command)

    observation = RuntimeObservation(
        ObservationId(f"observation-{suffix}"),
        runtime_id,
        Generation(1),
        RuntimeObservedStateKind.RUNNING,
        RuntimeHealth.HEALTHY,
        RuntimeReadiness.READY,
        now,
        now + timedelta(minutes=5),
        None,
        None,
        (),
    )
    observed = PostgresRuntimeObservationRepository(value)
    assert observed.append(aggregate.scope, observation).value == "APPENDED"
    assert observed.append(aggregate.scope, observation).value == "REPLAYED"
    assert observed.get(aggregate.scope, observation.observation_id) == observation
    assert observed.read_runtime(aggregate.scope, runtime_id) == (observation,)
    with pytest.raises(ExecutionConflict, match="OBSERVATION_CONFLICT"):
        observed.append(
            aggregate.scope, replace(observation, health=RuntimeHealth.DEGRADED)
        )

    fact = CommandResultFact(
        command.command_id, 1, CommandResult.APPLIED, {"status": "applied"}
    )
    assert value.append_command_result(aggregate.scope, fact).value == "APPENDED"
    assert value.append_command_result(aggregate.scope, fact).value == "REPLAYED"
    assert value.read_command_results(aggregate.scope, command.command_id) == (fact,)
    with pytest.raises(ExecutionConflict, match="COMMAND_RESULT_CONFLICT"):
        value.append_command_result(
            aggregate.scope, replace(fact, record={"status": "different"})
        )

    outcome_id = OutcomeId(f"outcome-{suffix}")
    intervention_id = InterventionId(f"intervention-{suffix}")
    outcome_record = {"result": "success"}
    assert (
        value.append_outcome(
            aggregate.scope,
            str(outcome_id),
            str(aggregate.workflow_run.workflow_run_id),
            outcome_record,
        ).value
        == "APPENDED"
    )
    assert (
        value.append_outcome(
            aggregate.scope,
            str(outcome_id),
            str(aggregate.workflow_run.workflow_run_id),
            outcome_record,
        ).value
        == "REPLAYED"
    )
    with pytest.raises(ExecutionConflict, match="OUTCOME_CONFLICT"):
        value.append_outcome(
            aggregate.scope,
            str(outcome_id),
            str(aggregate.workflow_run.workflow_run_id),
            {"result": "changed"},
        )
    intervention_record = {"reason": "review"}
    intervention_args = {
        "runtime_instance_id": str(runtime_id),
        "assignment_id": str(aggregate.assignment.assignment_id),
    }
    assert (
        value.append_intervention(
            aggregate.scope,
            str(intervention_id),
            intervention_record,
            **intervention_args,
        ).value
        == "APPENDED"
    )
    assert (
        value.append_intervention(
            aggregate.scope,
            str(intervention_id),
            intervention_record,
            **intervention_args,
        ).value
        == "REPLAYED"
    )
    with pytest.raises(ExecutionConflict, match="INTERVENTION_CONFLICT"):
        value.append_intervention(
            aggregate.scope,
            str(intervention_id),
            {"reason": "changed"},
            **intervention_args,
        )
    assert value.read_workflow(
        aggregate.scope, aggregate.workflow_run.workflow_run_id
    ) == (outcome_id,)
    assert value.read_runtime(aggregate.scope, runtime_id) == (intervention_id,)
    assert value.read_assignment(
        aggregate.scope, aggregate.assignment.assignment_id
    ) == (intervention_id,)
    assert value.attempts_for_runtime_agent(aggregate.scope, runtime_id, agent_id) == (
        aggregate.attempt.attempt_id,
    )

    other = ScopeIdentity("undisclosed", "quality")
    assert desired.read_runtime(other, runtime_id) == ()
    assert observed.read_runtime(other, runtime_id) == ()
    assert value.get(other, decision.placement_id) is None
    assert value.get_attempt(other, aggregate.attempt.attempt_id) is None
    assert value.read_command_results(other, command.command_id) == ()
    assert value.read_workflow(other, aggregate.workflow_run.workflow_run_id) == ()
    assert value.read_runtime(other, runtime_id) == ()
    assert value.read_assignment(other, aggregate.assignment.assignment_id) == ()
    assert value.attempts_for_runtime_agent(other, runtime_id, agent_id) == ()

    value.pool.close()
    restarted = repository()
    assert (
        restarted.get_attempt(aggregate.scope, aggregate.attempt.attempt_id)
        == aggregate
    )
    assert restarted.get(aggregate.scope, decision.placement_id) == decision
    assert (
        PostgresRuntimeDesiredStateRepository(restarted).get(
            aggregate.scope, command.command_id
        )
        == command
    )
    assert (
        PostgresRuntimeObservationRepository(restarted).get(
            aggregate.scope, observation.observation_id
        )
        == observation
    )
    assert restarted.read_command_results(aggregate.scope, command.command_id) == (
        fact,
    )
    assert restarted.read_workflow(
        aggregate.scope, aggregate.workflow_run.workflow_run_id
    ) == (outcome_id,)
    assert restarted.read_runtime(aggregate.scope, runtime_id) == (intervention_id,)
    restarted.pool.close()
