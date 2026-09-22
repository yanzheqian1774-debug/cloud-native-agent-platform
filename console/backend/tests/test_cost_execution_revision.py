"""Only the explicitly approved execution boundary and exact selections change."""

import json
from pathlib import Path

import pytest
from agent_console.cost_execution_revision import (
    DELIVERY_SYNTHETIC_ONLY,
    SYNTHETIC_ONLY,
    CostExecutionRevisionRequest,
    execution_successor,
)
from agent_console.plan_suggestion_domain import (
    ConfirmedPlanRevision,
    PlanningConflict,
    ProposalRevision,
)
from test_plan_suggestion_v2 import repository as repository


def test_case_is_explicit_and_legacy_request_digest_is_unchanged():
    from agent_console.resource_use_domain import canonical_digest

    plan, source, request = inputs()
    old_record = request.model_dump(mode="json", exclude={"case"})
    assert request.digest == canonical_digest(old_record)
    delivery = request.model_copy(update={"case": "delivery"})
    assert delivery.digest != request.digest
    successor, _ = execution_successor(plan, source, delivery)
    assert DELIVERY_SYNTHETIC_ONLY in successor.semantics.boundaries
    assert SYNTHETIC_ONLY not in successor.semantics.boundaries
    assert successor.semantics.tasks == plan.semantics.tasks
    assert successor.semantics.target == plan.semantics.target
    assert (
        execution_successor(plan, source, request)[0].semantics.boundaries[0]
        == SYNTHETIC_ONLY
    )


def inputs():
    root = Path(__file__).parents[3]
    snapshot = json.loads(
        (
            root / "docs/evidence/s5/v0.2/s5-v023-impl-324/baseline-readback.json"
        ).read_text()
    )
    plan = ConfirmedPlanRevision.model_validate(
        snapshot["planningOwnerPlans"][-1]["record"]
    )
    # Synthetic invocation identity: unit test does not claim original DB proposal.
    source = ProposalRevision(
        proposal_id=plan.plan_id,
        revision=2,
        predecessor_digest="f" * 64,
        invocation_id="fixture:original",
        semantics=plan.semantics,
    )
    plan = plan.model_copy(update={"source_proposal_digest": source.digest})
    ref = {"resource_id": "isolated-synthetic", "revision_id": "1", "digest": "a" * 64}
    request = CostExecutionRevisionRequest(
        plan_version=2,
        plan_digest=plan.digest,
        source_snapshot=ref,
        mapping_digest="b" * 64,
        selections={r.requirement_id: ref for r in plan.semantics.requirements},
    )
    return plan, source, request


def test_successor_preserves_six_tasks_criteria_cost_policy_and_original_records():
    plan, source, request = inputs()
    original = plan.model_dump_json()
    successor, changes = execution_successor(plan, source, request)
    assert successor.revision == 3
    assert successor.predecessor_digest == source.digest
    assert successor.semantics.tasks == plan.semantics.tasks
    assert successor.semantics.stages == plan.semantics.stages
    assert successor.semantics.target == plan.semantics.target
    assert successor.semantics.policy == plan.semantics.policy
    assert successor.semantics.business_rules[:-1] == plan.semantics.business_rules[:-1]
    assert {c["path"] for c in changes} == {
        "business_rules",
        "boundaries",
        "requirements",
    }
    assert plan.model_dump_json() == original
    assert execution_successor(plan, source, request)[0] == successor
    assert successor.invocation_id.startswith("execution-revision:")


@pytest.mark.parametrize("mutation", ["digest", "proposal", "resource", "boundary"])
def test_stale_source_missing_resource_or_different_boundary_fail_closed(mutation):
    plan, source, request = inputs()
    if mutation == "digest":
        request = request.model_copy(update={"plan_digest": "0" * 64})
    elif mutation == "proposal":
        source = source.model_copy(update={"revision": 1})
    elif mutation == "resource":
        request = request.model_copy(update={"selections": {}})
    else:
        semantics = plan.semantics.model_copy(update={"business_rules": ("changed",)})
        source = source.model_copy(update={"semantics": semantics})
        plan = plan.model_copy(
            update={"semantics": semantics, "source_proposal_digest": source.digest}
        )
        request = request.model_copy(update={"plan_digest": plan.digest})
    with pytest.raises(PlanningConflict):
        execution_successor(plan, source, request)


def test_revision_uses_normal_append_only_confirmation(repository):
    from agent_console.execution_domain import ScopeIdentity
    from test_plan_suggestion_v2 import confirm

    plan, source, request = inputs()
    scope = ScopeIdentity("controlled-324-successor", "isolated")
    first = source.model_copy(update={"revision": 1, "predecessor_digest": None})
    source = source.model_copy(update={"predecessor_digest": first.digest})
    for proposal in (first, source):
        with repository.transaction(
            scope, proposal.proposal_id, authorized=True
        ) as cur:
            repository.add_proposal(cur, scope, proposal)
        confirm(
            repository,
            scope,
            proposal,
            f"fixture-confirm-{proposal.revision}",
            expected=proposal.revision - 1,
        )
    with repository.transaction(scope, source.proposal_id, authorized=True) as cur:
        before = repository.read_plan(cur, scope, source.proposal_id, 2)
        plan = ConfirmedPlanRevision.model_validate(before["plan"])
        request = request.model_copy(update={"plan_digest": plan.digest})
        successor, _ = execution_successor(plan, source, request)
        repository.add_proposal(cur, scope, successor)
        # Preparing a successor alone does not approve it or mutate v2.
        assert repository.read_plan(cur, scope, source.proposal_id, 2) == before
        assert (
            cur.execute(
                "SELECT count(*) FROM execution_authority.workflow_runs"
            ).fetchone()["count"]
            == 0
        )
    result = confirm(repository, scope, successor, "fixture-confirm-3", expected=2)
    assert result["plan"]["version"] == 3
    assert result["plan"]["predecessor_digest"] == plan.digest
    assert result["approval"] != before["approval"]
    with repository.transaction(scope, source.proposal_id, authorized=True) as cur:
        assert repository.read_plan(cur, scope, source.proposal_id, 2) == before


@pytest.mark.parametrize("mixed", [False, True])
def test_delivery_executor_cannot_reuse_cost_only_approval(repository, mixed):
    from agent_console.execution_preparation import ExecutionPreparationError
    from agent_console.prepared_execution_lineage import validate_approved_preparation
    from agent_console.synthetic_delivery_skill import SyntheticDeliverySkillExecutor
    from prepared_execution_support import seed

    p = seed(repository)
    participants = list(p.participants)
    for index, participant in enumerate(participants):
        if not mixed or index == 0:
            participants[index] = participant.model_copy(
                update={
                    "executor_id": SyntheticDeliverySkillExecutor.revision.executor_id
                }
            )
    p = p.model_copy(update={"participants": tuple(participants)})
    reason = "CASE_MIXED" if mixed else "EXECUTION_SUCCESSOR_REQUIRED"
    with (
        repository.pool.connection() as connection,
        pytest.raises(ExecutionPreparationError, match=reason),
    ):
        validate_approved_preparation(connection, p)
