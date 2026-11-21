# ruff: noqa: F811 -- Imported isolated real-owner fixtures.
"""SERVICE_ONLY current grants/0070 admission plus original cumulative ledger."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import DraftAssistanceError, ProviderBudgetQuote
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.provider_budget_allowance import prepare as prepare_allowance
from test_fixed_work_service_admission_postgres import fixture  # noqa: F401
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_provider_budget_allowance import document
from test_provider_budget_extension import enable


def test_exact_service_after_100_uses_200_but_event_unknown_and_revocation_remain(
    fixture,
):
    f = fixture
    budget = f.budget
    saved = prepare_allowance(budget, document(budget, calls=100, cost=10_000_000))
    budget.allowance_id = saved["allowanceId"]
    budget.extension_test_base = saved
    quote = ProviderBudgetQuote(50, f.p.maximum_output_tokens, 0)
    for n in range(100):
        old = SimpleNamespace(
            scope=f.p.scope,
            profile_revision_id=f.p.profile_revision_id,
            invocation_id=f"old-other-context:{n}",
        )
        budget.reserve(f"old:{n}", old, quote)
    f.current[0] = f.current[0].model_copy(
        update={"maximumOutputTokens": f.p.maximum_output_tokens}
    )
    prepared = f.registry.prepare(f.context, "slot:1", f.req, f.record)
    invocation = SimpleNamespace(
        scope=f.p.scope,
        profile_revision_id=f.p.profile_revision_id,
        invocation_id="call:1",
    )
    owner = PostgresPlanningInvocations(f.repository)
    owner.claim(
        f.p.scope,
        f.context.principal_id,
        f.req.idempotency_key,
        "controlled-input",
        prepared["invocation"],
    )
    with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
        budget.reserve("service:101", invocation, quote)
    enable(budget)  # No Human context eligibility; current SERVICE_ONLY owner guards.
    reservation = budget.reserve("service:101", invocation, quote)
    assert budget.reserve("service:101", invocation, quote) == reservation
    with budget.dispatch_guard(invocation, quote):
        pass
    with pytest.raises(AuthorityError, match="QUOTE_LIMIT"):
        budget.reserve(
            "bad-tokens",
            invocation,
            ProviderBudgetQuote(101, f.p.maximum_output_tokens, 0),
        )
    from agent_console.fixed_work_service_admission import event_key

    next_request = f.req.model_copy(
        update={"idempotency_key": event_key(f.policy.work, "slot:2")}
    )
    next_record = {
        **f.record,
        "target": {**f.record["target"], "invocation_id": "call:2"},
    }
    with pytest.raises(AuthorityError):
        f.registry.prepare(f.context, "slot:2", next_request, next_record)
    with pytest.raises(AuthorityError):
        f.registry.prepare(f.context, "not-approved-event", f.req, f.record)
    f.authority.activate_generation(
        2,
        "b" * 64,
        1,
        operator_id="test-only",
        revoked_credentials=("service-credential",),
        now=f.now,
    )
    with pytest.raises(AuthorityError), budget.dispatch_guard(invocation, quote):
        pytest.fail("revoked service dispatched")
    with budget._connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations "
                "WHERE ledger_id=%s",
                (budget.ledger_id,),
            ).fetchone()["n"]
            == 101
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 1
        )
