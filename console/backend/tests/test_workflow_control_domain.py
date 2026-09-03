from datetime import UTC, datetime

import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.workflow_control_domain import (
    AtomicCommandType,
    InterventionDecision,
    InterventionReview,
    InterventionState,
    InterventionTarget,
    InterventionTransition,
    WorkflowControlConflict,
    WorkflowControlOperation,
    canonical_digest,
)
from agent_console.workflow_control_postgres import PostgresWorkflowControlRepository


def test_intervention_target_requires_exactly_one_primary_target() -> None:
    with pytest.raises(ValueError, match="EXACTLY_ONE"):
        InterventionTarget()
    with pytest.raises(ValueError, match="EXACTLY_ONE"):
        InterventionTarget(workflow_run_id="run", attempt_id="attempt")
    assert InterventionTarget(task_run_id="task").values() == (None, "task", None)


def test_transition_vocabulary_rejects_duplicate_and_invalid_edges() -> None:
    now = datetime.now(UTC)
    invalid = InterventionTransition(
        "transition",
        "intervention",
        2,
        InterventionState.REQUESTED,
        InterventionState.OBSERVED,
        "actor",
        "role:operator",
        "POLICY",
        now,
    )
    with pytest.raises(
        WorkflowControlConflict, match="INVALID_INTERVENTION_TRANSITION"
    ):
        PostgresWorkflowControlRepository._validate_transition(invalid)


def test_repository_has_no_runtime_effect_entrypoint() -> None:
    prohibited = {
        "start_runtime",
        "stop_runtime",
        "call_provider",
        "call_kubernetes",
        "apply_runtime_effect",
    }
    assert prohibited.isdisjoint(vars(PostgresWorkflowControlRepository))


def test_atomic_command_vocabulary_is_closed_and_payload_digest_is_canonical() -> None:
    assert {item.value for item in AtomicCommandType} == {
        "APPROVE_AND_CONTINUE",
        "REJECT_PLAN",
        "APPLY_INTERVENTION_DECISION",
        "RETRY_ATTEMPT",
        "CREATE_SUCCESSOR_RUN",
        "REPLACE_RUNTIME",
        "CANCEL_CONTROLLED_EXECUTION",
    }
    now = datetime.now(UTC)
    operation = WorkflowControlOperation(
        ScopeIdentity("tenant", "domain"),
        AtomicCommandType.RETRY_ATTEMPT,
        "actor",
        "key",
        {"b": 2, "a": 1},
        "command",
        now,
        now,
        InterventionTarget(attempt_id="attempt"),
        1,
    )
    assert operation.payload_digest == canonical_digest({"a": 1, "b": 2})


def test_review_and_decision_are_distinct_immutable_facts() -> None:
    now = datetime.now(UTC)
    review = InterventionReview("review", "request", "reviewer", "role", now)
    decision = InterventionDecision(
        "decision",
        "request",
        review.review_id,
        "AUTHORIZE",
        "decider",
        "role",
        "POLICY",
        now,
    )
    assert review.digest != decision.digest
    with pytest.raises(ValueError, match="INVALID_INTERVENTION_DECISION"):
        InterventionDecision(
            "bad",
            "request",
            review.review_id,
            "APPROVED",
            "decider",
            "role",
            "POLICY",
            now,
        )
