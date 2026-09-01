import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from agent_core.execution_contract import (
    AgentInstanceId,
    AssignmentId,
    AssignmentIdentity,
    AttemptId,
    AttemptIdentity,
    CommandId,
    CommandResult,
    DigitalEmployeeInstanceId,
    ExecutionContractError,
    ExecutionIdentityAggregate,
    ExternalCorrelation,
    Generation,
    ObservationId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
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
    assert_monotonic_generation,
    assert_request_replay,
    canonical_bytes,
    canonical_digest,
    correct_workflow,
    current_observed_state,
    may_reissue_command,
    rerun_workflow,
    retry_attempt,
)

NOW = datetime(2026, 9, 1, 8, tzinfo=UTC)


def placement_request(**overrides) -> PlacementRequest:
    values = {
        "request_id": PlacementRequestId("placement-request-001"),
        "scope": ScopeIdentity("agent-workloads", "business-unit-a"),
        "workflow_run_id": WorkflowRunId("workflow-run-001"),
        "task_run_id": TaskRunId("task-run-001"),
        "attempt_id": AttemptId("attempt-001"),
        "agent_instance_id": AgentInstanceId("agent-instance-001"),
        "agent_revision_id": "agent-revision-001",
        "runtime_profile_revision_id": "runtime-profile-revision-001",
        "capability_requirements": ("MCP", "KNOWLEDGE"),
        "resource_requirements": ("CPU_1", "MEMORY_1_GIB"),
        "isolation_requirements": ("DEDICATED_NAMESPACE",),
        "state_requirements": ("STATELESS",),
        "requested_at": NOW,
    }
    values.update(overrides)
    return PlacementRequest(**values)


def observation(**overrides) -> RuntimeObservation:
    values = {
        "observation_id": ObservationId("observation-001"),
        "runtime_instance_id": RuntimeInstanceId("runtime-instance-001"),
        "observed_generation": Generation(1),
        "observed_state": RuntimeObservedStateKind.RUNNING,
        "health": RuntimeHealth.HEALTHY,
        "readiness": RuntimeReadiness.READY,
        "observed_at": NOW,
        "freshness_deadline": NOW + timedelta(minutes=5),
        "provider_correlation": ExternalCorrelation(
            "native", "invocation", "provider-handle-001"
        ),
        "kubernetes_correlation": ExternalCorrelation(
            "kubernetes", "pod-uid", "pod-uid-001"
        ),
        "limitation_codes": (),
    }
    values.update(overrides)
    return RuntimeObservation(**values)


def aggregate(**overrides) -> ExecutionIdentityAggregate:
    assignment = AssignmentIdentity(
        AssignmentId("assignment-001"),
        DigitalEmployeeInstanceId("digital-employee-instance-001"),
    )
    workflow = WorkflowRunIdentity(
        WorkflowRunId("workflow-run-001"),
        assignment.assignment_id,
        "approved-plan-revision-001",
    )
    task = TaskRunIdentity(TaskRunId("task-run-001"), workflow.workflow_run_id)
    attempt = AttemptIdentity(AttemptId("attempt-001"), task.task_run_id)
    values = {
        "scope": ScopeIdentity("agent-workloads", "business-unit-a"),
        "assignment": assignment,
        "workflow_run": workflow,
        "task_run": task,
        "attempt": attempt,
    }
    values.update(overrides)
    return ExecutionIdentityAggregate(**values)


def test_nominal_product_identities_are_not_interchangeable() -> None:
    value = AgentInstanceId("same-opaque-value")
    assert value != RuntimeInstanceId("same-opaque-value")
    with pytest.raises(ExecutionContractError, match="INVALID_AGENT_INSTANCE_ID"):
        placement_request(agent_instance_id=RuntimeInstanceId("runtime-001"))


@pytest.mark.parametrize("value", ["", "  ", "x" * 201])
def test_invalid_empty_and_oversized_identity_is_rejected(value: str) -> None:
    with pytest.raises(ExecutionContractError, match="INVALID_PRODUCT_ID"):
        AttemptId(value)


def test_identity_limit_is_utf8_bytes_not_characters() -> None:
    assert AttemptId("界" * 66).value
    with pytest.raises(ExecutionContractError, match="INVALID_PRODUCT_ID"):
        AttemptId("界" * 67)


def test_scope_is_normalized_and_byte_limited() -> None:
    scope = ScopeIdentity("  cafe\u0301  ", " domain-a ")
    assert scope == ScopeIdentity("café", "domain-a")
    with pytest.raises(ExecutionContractError, match="INVALID_SCOPE_IDENTITY"):
        ScopeIdentity("界" * 43, "domain-a")


def test_generation_is_positive_explicit_and_monotonic() -> None:
    assert Generation(1).successor() == Generation(2)
    for invalid in (0, -1, True, 1.5):
        with pytest.raises(ExecutionContractError, match="INVALID_GENERATION"):
            Generation(invalid)  # type: ignore[arg-type]
    assert_monotonic_generation(Generation(1), Generation(2))
    with pytest.raises(ExecutionContractError, match="GENERATION_MUST_INCREASE"):
        assert_monotonic_generation(Generation(2), Generation(2))


def test_execution_relationships_are_scope_bound_and_consistent() -> None:
    value = aggregate()
    assert value.attempt.task_run_id == value.task_run.task_run_id
    with pytest.raises(ExecutionContractError, match="ATTEMPT_TASK_MISMATCH"):
        aggregate(
            attempt=AttemptIdentity(
                AttemptId("attempt-002"), TaskRunId("another-task-run")
            )
        )


def test_retry_rerun_and_correction_create_successor_identities() -> None:
    value = aggregate()
    retried = retry_attempt(value.attempt, AttemptId("attempt-002"))
    assert retried.task_run_id == value.task_run.task_run_id
    assert retried.predecessor_attempt_id == value.attempt.attempt_id
    rerun = rerun_workflow(value.workflow_run, WorkflowRunId("workflow-run-002"))
    assert rerun.predecessor_workflow_run_id == value.workflow_run.workflow_run_id
    corrected = correct_workflow(
        rerun, WorkflowRunId("workflow-run-003"), "approved-plan-revision-002"
    )
    assert corrected.correction_of_workflow_run_id == rerun.workflow_run_id
    with pytest.raises(ExecutionContractError, match="SUCCESSOR_PLAN"):
        correct_workflow(
            value.workflow_run,
            WorkflowRunId("workflow-run-004"),
            value.workflow_run.approved_plan_revision_id,
        )


def test_replacement_preserves_attempt_identity() -> None:
    desired = RuntimeDesiredState(
        RuntimeInstanceId("runtime-instance-001"),
        Generation(2),
        RuntimeDesiredStateKind.REPLACED,
        CommandId("command-001"),
        "policy-engine",
        NOW,
        NOW + timedelta(minutes=5),
        "FAILURE_REPLACEMENT",
    )
    assert desired.desired_state is RuntimeDesiredStateKind.REPLACED
    assert not hasattr(desired, "attempt_id")


def test_placement_placed_and_rejected_invariants() -> None:
    placed = PlacementDecision.create(
        placement_id=PlacementId("placement-001"),
        request_id=PlacementRequestId("placement-request-001"),
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=RuntimeInstanceId("runtime-instance-001"),
        policy_version="placement-policy-v1",
        compatibility_facts=("STATELESS_SUPPORTED",),
        limitation_codes=(),
        decided_at=NOW,
    )
    placed.verify_digest()
    rejected = PlacementDecision.create(
        placement_id=PlacementId("placement-002"),
        request_id=PlacementRequestId("placement-request-002"),
        decision=PlacementDecisionKind.REJECTED,
        runtime_instance_id=None,
        policy_version="placement-policy-v1",
        compatibility_facts=(),
        limitation_codes=("NO_COMPATIBLE_RUNTIME",),
        decided_at=NOW,
    )
    assert rejected.runtime_instance_id is None
    with pytest.raises(ExecutionContractError, match="PLACED_REQUIRES"):
        replace(rejected, decision=PlacementDecisionKind.PLACED)
    with pytest.raises(ExecutionContractError, match="REJECTED_PROHIBITS"):
        replace(placed, decision=PlacementDecisionKind.REJECTED)


def test_request_replay_is_idempotent_and_conflicting_reuse_fails() -> None:
    stored = placement_request()
    assert_request_replay(stored, placement_request())
    with pytest.raises(ExecutionContractError, match="PLACEMENT_REQUEST_CONFLICT"):
        assert_request_replay(
            stored,
            placement_request(resource_requirements=("CPU_2", "MEMORY_1_GIB")),
        )


def test_canonical_serialization_is_deterministic_versioned_and_sorted() -> None:
    first = placement_request(capability_requirements=("MCP", "KNOWLEDGE"))
    second = placement_request(capability_requirements=("KNOWLEDGE", "MCP"))
    assert first.canonical_bytes == second.canonical_bytes
    assert first.digest == second.digest == canonical_digest(first)
    assert first.digest == first.digest.lower()
    payload = json.loads(first.canonical_bytes)
    assert payload["contract_version"] == "v0.2.3-a0"
    assert payload["payload"]["capability_requirements"] == ["KNOWLEDGE", "MCP"]
    assert b"PlacementRequest(" not in first.canonical_bytes


def test_track_b_placement_fixture_round_trip_is_stable() -> None:
    expected = (
        b'{"contract_version":"v0.2.3-a0","payload":{"agent_instance_id":'
        b'"agent-instance-001","agent_revision_id":"agent-revision-001",'
        b'"attempt_id":"attempt-001","capability_requirements":["KNOWLEDGE",'
        b'"MCP"],"isolation_requirements":["DEDICATED_NAMESPACE"],'
        b'"request_id":"placement-request-001","requested_at":'
        b'"2026-09-01T08:00:00Z","resource_requirements":["CPU_1",'
        b'"MEMORY_1_GIB"],"runtime_profile_revision_id":'
        b'"runtime-profile-revision-001","scope":{"namespace":'
        b'"agent-workloads","security_domain":"business-unit-a"},'
        b'"state_requirements":["STATELESS"],"task_run_id":"task-run-001",'
        b'"workflow_run_id":"workflow-run-001"}}'
    )
    value = placement_request()
    assert value.canonical_bytes == expected
    assert (
        value.digest
        == "0449066a6cba3eca8d2f79890f248f2c9c7688cbd76d1cb8222a6748f4a35d8c"
    )
    rebuilt = PlacementRequest.from_mapping(json.loads(expected)["payload"])
    assert rebuilt == value


def test_unknown_fields_and_invalid_enums_fail_closed() -> None:
    payload = json.loads(placement_request().canonical_bytes)["payload"]
    payload["raw_command"] = "do anything"
    with pytest.raises(ExecutionContractError, match="UNKNOWN_OR_MISSING"):
        PlacementRequest.from_mapping(payload)
    desired_payload = {
        "runtime_instance_id": "runtime-instance-001",
        "desired_generation": 1,
        "desired_state": "ARBITRARY_EXEC",
        "command_id": "command-001",
        "requested_by": "policy-engine",
        "requested_at": "2026-09-01T08:00:00Z",
        "deadline": "2026-09-01T08:05:00Z",
        "reason_classification": "AUTHORIZED_START",
    }
    with pytest.raises(ExecutionContractError, match="INVALID_CONTRACT_VALUE"):
        RuntimeDesiredState.from_mapping(desired_payload)


def test_desired_and_observed_runtime_state_validation() -> None:
    with pytest.raises(ExecutionContractError, match="DEADLINE_MUST_FOLLOW"):
        RuntimeDesiredState(
            RuntimeInstanceId("runtime-instance-001"),
            Generation(1),
            RuntimeDesiredStateKind.RUNNING,
            CommandId("command-001"),
            "policy-engine",
            NOW,
            NOW,
            "AUTHORIZED_START",
        )
    with pytest.raises(ExecutionContractError, match="FRESHNESS_DEADLINE"):
        observation(freshness_deadline=NOW)


def test_missing_is_unknown_and_expired_is_stale() -> None:
    assert current_observed_state(None, at=NOW) is RuntimeObservedStateKind.UNKNOWN
    value = observation()
    assert current_observed_state(value, at=NOW) is RuntimeObservedStateKind.RUNNING
    assert (
        current_observed_state(value, at=NOW + timedelta(minutes=6))
        is RuntimeObservedStateKind.STALE
    )


def test_running_and_ready_do_not_express_business_success() -> None:
    value = observation()
    assert value.observed_state is RuntimeObservedStateKind.RUNNING
    assert value.readiness is RuntimeReadiness.READY
    assert not hasattr(value, "outcome")
    assert not hasattr(value, "attempt_succeeded")


def test_provider_and_kubernetes_handles_are_correlations_not_product_ids() -> None:
    value = observation()
    assert isinstance(value.provider_correlation, ExternalCorrelation)
    assert isinstance(value.runtime_instance_id, RuntimeInstanceId)
    with pytest.raises(ExecutionContractError, match="INVALID_RUNTIME_INSTANCE_ID"):
        replace(value, runtime_instance_id=value.kubernetes_correlation)


@pytest.mark.parametrize(
    "forbidden", ["secret", "yaml", "pod", "command", "environment", "raw_payload"]
)
def test_forbidden_effect_fields_are_not_in_contract(forbidden: str) -> None:
    contract_fields = {
        name.casefold()
        for contract in (PlacementRequest, RuntimeDesiredState, RuntimeObservation)
        for name in contract.__dataclass_fields__
    }
    assert forbidden not in contract_fields


def test_ambiguous_command_effects_prohibit_blind_reissue() -> None:
    for result in (
        CommandResult.UNKNOWN,
        CommandResult.STALE,
        CommandResult.RECOVERY_REQUIRED,
        CommandResult.APPLIED,
        CommandResult.OBSERVED,
    ):
        assert not may_reissue_command(result)
    assert may_reissue_command(CommandResult.REQUESTED)
    assert may_reissue_command(CommandResult.REJECTED)


def test_decision_digest_is_immutable_and_verified_on_round_trip() -> None:
    decision = PlacementDecision.create(
        placement_id=PlacementId("placement-001"),
        request_id=PlacementRequestId("placement-request-001"),
        decision=PlacementDecisionKind.REJECTED,
        runtime_instance_id=None,
        policy_version="placement-policy-v1",
        compatibility_facts=(),
        limitation_codes=("NO_COMPATIBLE_RUNTIME",),
        decided_at=NOW,
    )
    payload = json.loads(canonical_bytes(decision))["payload"]
    assert PlacementDecision.from_mapping(payload) == decision
    payload["policy_version"] = "changed-policy"
    with pytest.raises(ExecutionContractError, match="DIGEST_MISMATCH"):
        PlacementDecision.from_mapping(payload)
