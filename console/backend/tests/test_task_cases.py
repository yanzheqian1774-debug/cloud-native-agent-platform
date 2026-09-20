"""Explicit case enrollment cannot change the subject or discard liabilities."""

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.task_cases import CaseEnrollment, enroll
from agent_console.task_development import revise
from test_task_delegation import assembled as assembled
from test_task_delegation import create_task_problem, submit
from test_task_delegation import env as env
from test_task_delegation import repository as repository
from test_task_development import planning, setup


def spec(e):
    return CaseEnrollment(
        context_id=e.second.context_id,
        case_label="Synthetic monthly model cost",
        description_digest="b" * 64,
        unknown_invocation_ids=["old-unknown"],
        idempotency_key="case-cost",
    )


def test_case_requires_independent_exact_enrollment_and_retains_old_facts(env):
    e = env
    d, revision = setup(e)
    planning(e, d)
    revise(e.service, e.contexts["approver"], d, revision)
    request = submit(e, e.second)
    with pytest.raises(AuthorityError):
        e.service.authorize(e.contexts["reader"], d, request.request_id)
    with pytest.raises(AuthorityError, match="SELF_APPROVAL"):
        enroll(e.service, e.contexts["reader"], d, spec(e))
    saved = enroll(e.service, e.contexts["approver"], d, spec(e))
    assert saved == enroll(e.service, e.contexts["approver"], d, spec(e))
    assert saved["record"]["facts"][0]["remote_processing_and_cost"] == "UNKNOWN"
    e.service.authorize(e.contexts["reader"], d, request.request_id)
    with pytest.raises(AuthorityError, match="CONFLICT"):
        enroll(
            e.service,
            e.contexts["approver"],
            d,
            spec(e).model_copy(update={"case_label": "changed"}),
        )
    # Normal restart must retain migration 30 and must not recreate the old
    # global one-Problem index from migration 28.
    e.service.migrate()
    e.service.repository.verify_existing_schema()
    with e.service.repository.connection_scope() as c:
        assert (
            c.execute(
                "SELECT to_regclass("
                "'authorization_admin.task_delegation_one_problem') AS name"
            ).fetchone()["name"]
            is None
        )
        assert (
            c.execute(
                "SELECT record FROM workflow_planning.invocation_results "
                "WHERE invocation_id='old-unknown'"
            ).fetchone()["record"]["technical_status"]
            == "OUTCOME_UNKNOWN"
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 1
        )


def test_case_rejects_unreaped_worker(env):
    e = env
    d, revision = setup(e)
    planning(e, d, reaped=False)
    revise(e.service, e.contexts["approver"], d, revision)
    with pytest.raises(AuthorityError, match="WORKER_NOT_REAPED"):
        enroll(e.service, e.contexts["approver"], d, spec(e))


def test_case_problem_exact_binding_and_cross_case_budget(env):
    from types import SimpleNamespace

    from agent_console.draft_assistance import ProviderBudgetQuote
    from agent_console.task_delegation import active, task_problem_ids

    e = env
    d, revision = setup(e)
    planning(e, d)
    revise(e.service, e.contexts["approver"], d, revision)
    enroll(e.service, e.contexts["approver"], d, spec(e))
    from test_draft_assistance import context

    ready = e.synthetic.begin(
        context("human:reader"),
        key="cost-answer",
        content="Synthetic project monthly model cost; no bills provided; plan only.",
        parent_context_id=e.second.context_id,
        parent_turn_id=e.second.turn_id,
        expected_parent_version=e.second.turn_version,
        predecessor_invocation_id=e.second.invocation_id,
    ).invocation
    problem = create_task_problem(e, "cost-problem", draft=ready)
    with e.service.repository.connection_scope() as c:
        row, _ = active(c, d)
        assert task_problem_ids(c, row) == {"problem", problem.business_problem_id}
    with pytest.raises(AuthorityError, match=r"TARGET_DENIED|ALREADY_BOUND"):
        create_task_problem(e, "third-problem", draft=ready)
    budget = e.budgets["understanding"]
    quote = ProviderBudgetQuote(
        100,
        budget.profile.maximum_output_tokens,
        100 + budget.profile.maximum_output_tokens,
    )
    identity = SimpleNamespace(
        scope=e.second.scope,
        invocation_id=e.second.invocation_id,
        profile_revision_id=budget.profile.profile_revision_id,
    )
    reservation = budget.reserve("cost-understanding", identity, quote)
    assert reservation
    # The original unresolved reservation remains outstanding; enrollment is
    # an exact exception, not settlement or a new ledger.
    with e.service.repository.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )
