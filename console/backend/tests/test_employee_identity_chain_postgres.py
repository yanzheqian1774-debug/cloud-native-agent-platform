"""Normal backend identity chain and rejection invariants on real PostgreSQL."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.execution_application import (
    ExecutionApplicationError,
    ExecutionApplicationService,
    RetryExecutionCommand,
)
from agent_console.execution_domain import ExecutionConflict, VersionedAggregate
from agent_console.execution_postgres import (
    AgentInstanceId,
    AppendDisposition,
    AssignmentId,
    DigitalEmployeeInstanceId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    PostgresExecutionAuthorityRepository,
    RuntimeInstanceId,
    ScopeIdentity,
)
from employee_identity_support import authorize, fail_attempt, start_chain
from test_execution_application_postgres import approved_plan

DATABASE_URL = os.environ.get("EMPLOYEE_IDENTITY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real dedicated PostgreSQL required"
)
MIGRATION = (
    Path(__file__).parents[1] / "migrations/0008_execution_runtime_authority.sql"
)


@pytest.fixture
def chain():
    repo = PostgresExecutionAuthorityRepository(DATABASE_URL, migration_path=MIGRATION)
    try:
        yield repo, start_chain(repo, DATABASE_URL, approved_plan(uuid.uuid4().hex))
    finally:
        repo.pool.close()


def counts(repo, scope):
    with repo.pool.connection() as conn:
        return tuple(
            conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE namespace=%s AND "
                f"security_domain=%s",
                (scope.namespace, scope.security_domain),
            ).fetchone()["n"]
            for table in (
                "execution_authority.workflow_runs",
                "execution_authority.task_runs",
                "execution_authority.attempts",
                "digital_employee_definition.execution_bindings",
                "execution_authority.placement_requests",
                "execution_authority.placement_decisions",
            )
        )


def test_normal_start_retry_replay_restart_and_successor_binding(chain):
    repo, (revision, instance, assignment, command, started) = chain
    assert (
        len(
            {
                revision.definition_id,
                revision.members[0].resource_id,
                command.approved_plan.plan_id,
            }
        )
        == 3
    )
    assert (
        len(
            {
                revision.digest,
                revision.members[0].digest,
                command.approved_plan.plan_digest,
            }
        )
        == 3
    )
    service = ExecutionApplicationService(repo, authorize(command.scope))
    assert service.start(command).disposition is AppendDisposition.REPLAYED
    before = counts(repo, command.scope)
    retry = RetryExecutionCommand(
        command.scope, started.identity.attempt.attempt_id, "retry"
    )
    with pytest.raises(ExecutionConflict, match="RETRY_REQUIRES_FAILED_ATTEMPT"):
        service.retry(retry)
    assert counts(repo, command.scope) == before
    fail_attempt(repo, started.identity)
    successor = service.retry(retry)
    assert successor.identity.assignment == started.identity.assignment
    assert successor.identity.workflow_run == started.identity.workflow_run
    assert (
        successor.identity.attempt.predecessor_attempt_id
        == started.identity.attempt.attempt_id
    )
    assert service.retry(retry).disposition is AppendDisposition.REPLAYED
    with pytest.raises(ExecutionConflict, match="ATTEMPT_SUCCESSOR_CONFLICT"):
        service.retry(replace(retry, replay_identity="another"))
    with repo.pool.connection() as conn:
        bindings = conn.execute(
            "SELECT "
            "definition_id,revision_id,digest,plan_digest,approval_id FROM "
            "digital_employee_definition.execution_bindings WHERE "
            "namespace=%s",
            (command.scope.namespace,),
        ).fetchall()
        assert len(bindings) == 2 and bindings[0] == bindings[1]
    restarted = PostgresExecutionAuthorityRepository(
        DATABASE_URL, migration_path=MIGRATION
    )
    try:
        assert (
            restarted.get_attempt(command.scope, successor.identity.attempt.attempt_id)
            == successor.identity
        )
        assert (
            PostgresDigitalEmployeeRepository(restarted).get_instance(
                command.scope, instance.instance_id
            )
            == instance
        )
        assert PostgresDigitalEmployeeRepository(restarted).assignments_for_instance(
            command.scope, instance.instance_id
        ) == (assignment,)
    finally:
        restarted.pool.close()


@pytest.mark.parametrize(
    "change",
    ["approval", "plan", "version", "digest", "assignment", "instance", "content"],
)
def test_exact_plan_mismatches_have_zero_writes(chain, change):
    repo, (_, _, _, command, _) = chain
    service = ExecutionApplicationService(repo, authorize(command.scope))
    if change == "approval":
        bad = replace(
            command, approved_plan=replace(command.approved_plan, approval_id="absent")
        )
    elif change in {"plan", "version", "digest"}:
        field, value = {
            "plan": ("plan_id", "absent"),
            "version": ("plan_version", 99),
            "digest": ("plan_digest", "0" * 64),
        }[change]
        bad = replace(
            command, approved_plan=replace(command.approved_plan, **{field: value})
        )
    elif change == "content":
        bad = replace(command, plan=replace(command.plan, policy_version="forged"))
    else:
        bad = replace(
            command,
            **{
                (
                    "assignment_id"
                    if change == "assignment"
                    else "digital_employee_instance_id"
                ): (
                    AssignmentId("absent")
                    if change == "assignment"
                    else DigitalEmployeeInstanceId("absent")
                )
            },
        )
    before = counts(repo, command.scope)
    with pytest.raises((ExecutionConflict, ExecutionApplicationError)):
        service.start(bad)
    assert counts(repo, command.scope) == before


def test_denied_start_and_retry_do_not_lookup_or_write(chain):
    _repo, (_, _, _, command, started) = chain

    class Never:
        def __getattr__(self, name):
            pytest.fail("denied request reached persistence")

    for scope in (command.scope, ScopeIdentity("foreign", "domain")):
        service = ExecutionApplicationService(Never(), authorize(scope, ()))
        with pytest.raises(ExecutionApplicationError, match="EXECUTION_NOT_FOUND"):
            service.start(command)
        with pytest.raises(ExecutionApplicationError, match="EXECUTION_NOT_FOUND"):
            service.retry(
                RetryExecutionCommand(
                    command.scope, started.identity.attempt.attempt_id, "denied"
                )
            )


def placement(repo, revision, identity):
    suffix = uuid.uuid4().hex
    agent, runtime = (
        AgentInstanceId(f"agent-{suffix}"),
        RuntimeInstanceId(f"runtime-{suffix}"),
    )
    member = revision.members[0]
    repo.create_aggregate(
        "runtime_instance",
        VersionedAggregate(identity.scope, str(runtime), 1, {"current_generation": 1}),
    )
    record = {
        "agent_definition_id": member.resource_id,
        "agent_revision_id": member.revision_id,
        "agent_digest": member.digest,
        "runtime_instance_id": str(runtime),
    }
    repo.create_aggregate(
        "agent_instance", VersionedAggregate(identity.scope, str(agent), 1, record)
    )
    now = datetime.now(UTC)
    request = PlacementRequest(
        PlacementRequestId(f"request-{suffix}"),
        identity.scope,
        identity.workflow_run.workflow_run_id,
        identity.task_run.task_run_id,
        identity.attempt.attempt_id,
        agent,
        member.revision_id,
        "runtime-profile",
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
        runtime_instance_id=runtime,
        policy_version="policy",
        compatibility_facts=(),
        limitation_codes=(),
        decided_at=now,
    )
    return request, decision, record


@pytest.mark.parametrize(
    "field", ["agent_definition_id", "agent_revision_id", "agent_digest"]
)
def test_placement_exact_primary_agent_and_rollback(chain, field):
    repo, (revision, _, _, command, started) = chain
    request, decision, record = placement(repo, revision, started.identity)
    repo.replace_aggregate(
        "agent_instance",
        VersionedAggregate(
            command.scope, str(request.agent_instance_id), 2, {**record, field: "wrong"}
        ),
        expected_version=1,
    )
    before = counts(repo, command.scope)
    with pytest.raises(ExecutionConflict, match="PLACEMENT_PRIMARY_AGENT_MISMATCH"):
        repo.decide(command.scope, request, decision, require_employee_lineage=True)
    assert counts(repo, command.scope) == before
    repo.replace_aggregate(
        "agent_instance",
        VersionedAggregate(command.scope, str(request.agent_instance_id), 3, record),
        expected_version=2,
    )
    assert (
        repo.decide(
            command.scope, request, decision, require_employee_lineage=True
        ).disposition
        is AppendDisposition.APPENDED
    )
    assert (
        repo.decide(
            command.scope, request, decision, require_employee_lineage=True
        ).disposition
        is AppendDisposition.REPLAYED
    )
    assert repo.get(command.scope, decision.placement_id) == decision


def test_retry_race_has_one_successor(chain):
    repo, (_, _, _, command, started) = chain
    fail_attempt(repo, started.identity)
    service = ExecutionApplicationService(repo, authorize(command.scope))

    def retry(key):
        try:
            return service.retry(
                RetryExecutionCommand(
                    command.scope, started.identity.attempt.attempt_id, key
                )
            ).disposition.value
        except ExecutionConflict as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(retry, ("race-a", "race-b"))) == [
            "APPENDED",
            "ATTEMPT_SUCCESSOR_CONFLICT",
        ]
    assert counts(repo, command.scope)[:4] == (1, 1, 2, 2)


def test_late_failure_rolls_back_entire_start(chain, monkeypatch):
    from agent_console import execution_lineage

    repo, (_, _, _, command, _) = chain

    def fail(*args):
        raise ExecutionConflict("INJECTED_LATE_FAILURE")

    monkeypatch.setattr(execution_lineage, "append_lineage", fail)
    before = counts(repo, command.scope)
    with pytest.raises(ExecutionConflict, match="INJECTED_LATE_FAILURE"):
        ExecutionApplicationService(repo, authorize(command.scope)).start(
            replace(command, replay_identity="new-run")
        )
    assert counts(repo, command.scope) == before


def test_workflow_control_retry_preserves_canonical_identity(chain):
    from agent_console.workflow_control_domain import (
        InterventionRequest,
        InterventionTarget,
    )
    from agent_console.workflow_control_postgres import (
        PostgresWorkflowControlRepository,
    )
    from test_workflow_control_postgres import authorize_request, retry_operation

    repo, (_, _, _, command, started) = chain
    identity = started.identity
    fail_attempt(repo, identity)
    control = PostgresWorkflowControlRepository(
        DATABASE_URL,
        migration_path=MIGRATION.with_name("0010_workflow_control_uow_extension.sql"),
    )
    suffix = uuid.uuid4().hex
    attempt_id = str(identity.attempt.attempt_id)
    request = InterventionRequest(
        f"intervention-{suffix}",
        "RETRY_ATTEMPT",
        "OPERATIONAL_RECOVERY",
        "actor",
        "role:operator",
        1,
        InterventionTarget(attempt_id=attempt_id),
        {"action": "retry"},
        datetime.now(UTC),
    )
    try:
        control.request_intervention(command.scope, request)
        authorize_request(control, command.scope, request, suffix)
        operation = retry_operation(command.scope, attempt_id, request, suffix)
        result = control.persist_operation(operation, authorized=True)
        assert control.persist_operation(operation, authorized=True).replayed
        successor = repo.get_attempt(command.scope, result.successor_attempt_id)
        assert successor.assignment == identity.assignment
        assert successor.workflow_run == identity.workflow_run
        assert successor.attempt.predecessor_attempt_id == identity.attempt.attempt_id
        with repo.pool.connection() as conn:
            rows = conn.execute(
                "SELECT "
                "definition_id,revision_id,digest,plan_digest,approval_id FROM "
                "digital_employee_definition.execution_bindings WHERE "
                "namespace=%s",
                (command.scope.namespace,),
            ).fetchall()
            assert len(rows) == 2 and rows[0] == rows[1]
    finally:
        control.pool.close()


def test_real_workflow_runtime_members_and_legacy_compatibility(chain):
    from agent_console.digital_employee_definition import (
        EmployeeDefinitionService,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from employee_identity_support import publish_workflow
    from test_digital_employee_definition_postgres import Authorized

    repo, (revision, instance, _, command, started) = chain
    scope = command.scope
    workflow, runtime = publish_workflow(DATABASE_URL, scope)
    successor = replace(
        revision,
        revision_id="employee-successor",
        predecessor_revision_id=revision.revision_id,
        members=(*revision.members, workflow, runtime),
    )
    store = PostgresEmployeeDefinitionRepository(repo)
    service = EmployeeDefinitionService(store, Authorized(scope))
    current = service.create(
        successor, expected_version=4, command_id="successor-create"
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        current = service.decide(
            scope,
            successor.definition_id,
            successor.revision_id,
            successor.digest,
            action,
            expected_version=current["aggregateVersion"],
            command_id=f"successor-{action}",
        )
    fail_attempt(repo, started.identity)
    result = ExecutionApplicationService(repo, authorize(scope)).retry(
        RetryExecutionCommand(
            scope, started.identity.attempt.attempt_id, "after-successor"
        )
    )
    with repo.pool.connection() as conn:
        row = conn.execute(
            "SELECT revision_id,digest FROM "
            "digital_employee_definition.execution_bindings WHERE "
            "namespace=%s AND attempt_id=%s",
            (scope.namespace, str(result.identity.attempt.attempt_id)),
        ).fetchone()
        assert row == {"revision_id": revision.revision_id, "digest": revision.digest}
        original = conn.execute(
            "SELECT record FROM "
            "execution_authority.digital_employee_instances WHERE "
            "namespace=%s AND digital_employee_instance_id=%s",
            (scope.namespace, str(instance.instance_id)),
        ).fetchone()["record"]
    legacy_id = f"legacy-{uuid.uuid4().hex}"
    legacy = {
        k: v
        for k, v in original.items()
        if k
        not in {
            "definition_authority",
            "primary_agent_id",
            "primary_agent_revision_id",
            "primary_agent_digest",
        }
    }
    legacy["digital_employee_instance_id"] = legacy_id
    repo.create_aggregate(
        "digital_employee_instance", VersionedAggregate(scope, legacy_id, 1, legacy)
    )
    read = PostgresDigitalEmployeeRepository(repo).get_instance(
        scope, DigitalEmployeeInstanceId(legacy_id)
    )
    assert read.definition.authority_kind == "LEGACY_UNVERIFIED"
    before = repo.get_aggregate("digital_employee_instance", scope, legacy_id)
    with pytest.raises(ExecutionConflict, match="EXACT_EMPLOYEE_LINEAGE_REQUIRED"):
        ExecutionApplicationService(repo, authorize(scope)).start(
            replace(
                command,
                digital_employee_instance_id=DigitalEmployeeInstanceId(legacy_id),
                replay_identity="legacy",
            )
        )
    assert repo.get_aggregate("digital_employee_instance", scope, legacy_id) == before


def test_replay_checks_typed_run_columns(chain):
    repo, (_, _, _, command, started) = chain
    before = counts(repo, command.scope)
    with repo.pool.connection() as conn:
        conn.execute(
            "UPDATE execution_authority.workflow_runs SET approved_plan_digest=%s "
            "WHERE namespace=%s AND workflow_run_id=%s",
            (
                "0" * 64,
                command.scope.namespace,
                str(started.identity.workflow_run.workflow_run_id),
            ),
        )
    with pytest.raises(ExecutionConflict, match="EXECUTION_IDENTITY_CONFLICT"):
        ExecutionApplicationService(repo, authorize(command.scope)).start(command)
    assert counts(repo, command.scope) == before
