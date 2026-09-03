from datetime import UTC, datetime

import pytest
from agent_console.workflow_control_domain import (
    InterventionState,
    InterventionTarget,
    InterventionTransition,
    WorkflowControlConflict,
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
