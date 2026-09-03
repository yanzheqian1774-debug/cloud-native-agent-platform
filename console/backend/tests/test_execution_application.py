from dataclasses import replace

import pytest
from agent_console.execution_application import (
    ApprovedPlanIdentity,
    ExecutionApplicationError,
    ExecutionApplicationService,
    ExecutionOutcomeService,
    RecordOutcomeCommand,
    RetryExecutionCommand,
    StartExecutionCommand,
    successor_workflow,
)
from agent_console.execution_postgres import (
    AppendDisposition,
    AssignmentId,
    DigitalEmployeeInstanceId,
    ScopeIdentity,
    WorkflowRunId,
)
from agent_console.planning import (
    CanonicalWorkflowRevision,
    IntentRevision,
    PlanningState,
    TaskRequirement,
)


class MemoryIdentities:
    def __init__(self) -> None:
        self.values = {}
        self.calls = 0

    def save(self, scope, aggregate):
        self.calls += 1
        self.values[(scope, aggregate.attempt.attempt_id)] = aggregate
        return aggregate

    def get_attempt(self, scope, attempt_id):
        return self.values.get((scope, attempt_id))


class MemoryOutcomes:
    def __init__(self) -> None:
        self.values = {}
        self.calls = 0

    def append_outcome(self, scope, outcome_id, workflow_run_id, record):
        self.calls += 1
        key = (scope, outcome_id)
        value = (workflow_run_id, record)
        if key in self.values:
            if self.values[key] != value:
                raise RuntimeError("OUTCOME_CONFLICT")
            return AppendDisposition.REPLAYED
        self.values[key] = value
        return AppendDisposition.APPENDED


def plan() -> CanonicalWorkflowRevision:
    intent = IntentRevision(
        "intent",
        "intent-revision",
        1,
        None,
        "planning.v1",
        "policy.v1",
        "question",
        "objective",
        (),
        ("done",),
        "a" * 64,
    )
    task = TaskRequirement(
        "requirement",
        "collect",
        "intent-revision",
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
        "plan-revision",
        1,
        None,
        "tenant",
        "domain",
        "b" * 64,
        "approval",
        "policy.v1",
        intent,
        (task,),
        ("collect",),
        (),
        True,
    )


def command(**changes) -> StartExecutionCommand:
    approved = plan()
    value = StartExecutionCommand(
        ScopeIdentity("tenant", "domain"),
        approved,
        ApprovedPlanIdentity("plan-revision", "b" * 64, "approval"),
        AssignmentId("assignment"),
        DigitalEmployeeInstanceId("employee"),
        "collect",
        "request-1",
    )
    return replace(value, **changes)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            {"plan": replace(plan(), lifecycle=PlanningState.APPROVED)},
            "PLAN_NOT_APPROVED",
        ),
        (
            {"approved_plan": ApprovedPlanIdentity("stale", "b" * 64, "approval")},
            "PLAN_REVISION_MISMATCH",
        ),
        (
            {
                "approved_plan": ApprovedPlanIdentity(
                    "plan-revision", "c" * 64, "approval"
                )
            },
            "PLAN_DIGEST_MISMATCH",
        ),
        (
            {"approved_plan": ApprovedPlanIdentity("plan-revision", "b" * 64, "wrong")},
            "PLAN_APPROVAL_MISMATCH",
        ),
        ({"scope": ScopeIdentity("other", "domain")}, "TENANT_SCOPE_MISMATCH"),
        ({"task_id": "missing"}, "PLAN_TASK_MISMATCH"),
    ],
)
def test_exact_approval_rejects_before_any_persistence(change, reason) -> None:
    identities = MemoryIdentities()
    with pytest.raises(ExecutionApplicationError, match=reason):
        ExecutionApplicationService(identities).start(command(**change))
    assert identities.calls == 0
    assert identities.values == {}


def test_start_replay_retry_restart_and_scope_isolation() -> None:
    identities = MemoryIdentities()
    service = ExecutionApplicationService(identities)
    first = service.start(command())
    replay = ExecutionApplicationService(identities).start(command())
    assert first.disposition is AppendDisposition.APPENDED
    assert replay.disposition is AppendDisposition.REPLAYED
    assert replay.identity == first.identity
    assert (
        service.read_attempt(
            ScopeIdentity("other", "domain"), first.identity.attempt.attempt_id
        )
        is None
    )

    retry = service.retry(
        RetryExecutionCommand(
            first.identity.scope, first.identity.attempt.attempt_id, "retry-1"
        )
    )
    retry_replay = service.retry(
        RetryExecutionCommand(
            first.identity.scope, first.identity.attempt.attempt_id, "retry-1"
        )
    )
    assert retry.identity.attempt.attempt_id != first.identity.attempt.attempt_id
    assert (
        retry.identity.attempt.predecessor_attempt_id
        == first.identity.attempt.attempt_id
    )
    assert retry_replay.disposition is AppendDisposition.REPLAYED


def test_outcome_is_scoped_identity_bound_and_idempotent() -> None:
    identities = MemoryIdentities()
    started = ExecutionApplicationService(identities).start(command())
    outcomes = MemoryOutcomes()
    service = ExecutionOutcomeService(identities, outcomes)
    record = {
        "outcome_id": "outcome-1",
        "workflow_run_id": str(started.identity.workflow_run.workflow_run_id),
        "task_run_id": str(started.identity.task_run.task_run_id),
        "attempt_id": str(started.identity.attempt.attempt_id),
        "approved_plan_revision_id": "plan-revision",
        "classification": "SUCCEEDED",
    }
    cmd = RecordOutcomeCommand(
        started.identity.scope, started.identity.attempt.attempt_id, "outcome-1", record
    )
    assert service.record(cmd).disposition is AppendDisposition.APPENDED
    assert service.record(cmd).disposition is AppendDisposition.REPLAYED
    with pytest.raises(ExecutionApplicationError, match="OUTCOME_IDENTITY_MISMATCH"):
        service.record(replace(cmd, record={**record, "attempt_id": "wrong"}))
    assert outcomes.calls == 2


def test_successor_identity_never_mutates_predecessor() -> None:
    previous = (
        ExecutionApplicationService(MemoryIdentities())
        .start(command())
        .identity.workflow_run
    )
    rerun = successor_workflow(previous, WorkflowRunId("rerun"))
    correction = successor_workflow(
        previous,
        WorkflowRunId("correction"),
        successor_plan_revision_id="plan-revision-2",
    )
    assert rerun.predecessor_workflow_run_id == previous.workflow_run_id
    assert correction.correction_of_workflow_run_id == previous.workflow_run_id
    assert correction.approved_plan_revision_id == "plan-revision-2"
