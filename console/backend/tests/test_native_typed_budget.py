# ruff: noqa: F811 -- Imported pytest fixture.
"""Actual disposable budget owner, no provider/model or answer writes."""

from types import SimpleNamespace as NS

import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    ObservationState,
    ProviderBudgetQuote,
    ProviderObservation,
)
from test_draft_provider_budget_postgres import _invocation, _ledger
from test_plan_suggestion_v2 import repository  # noqa: F401


def test_exact_settlement_ignores_terminal_snapshot_and_rejects_wrong_binding(
    repository,
):
    owner = _ledger(repository.pool.conninfo, "typed-budget-exact", cost_cap=200)
    try:
        invocation = _invocation(941)
        reservation = owner.reserve(
            "typed-reserve", invocation, ProviderBudgetQuote(50, 100, 150)
        )
        invocation.budget_reservation_id = reservation
        invocation.snapshot = NS(profile_digest=owner.profile.profile_digest)
        invocation.settlement_status = "ESTIMATE_SETTLED"
        with owner.pool.connection() as c:
            assert owner.read_invocation_settlement(c, invocation) == {
                "status": "PENDING_RECONCILIATION",
                "reservation_retained": True,
            }
            wrong = NS(**{**vars(invocation), "invocation_id": "other-invocation"})
            with pytest.raises(DraftAssistanceError, match="RESERVATION_CONFLICT"):
                owner.read_invocation_settlement(c, wrong)
            wrong = NS(**{**vars(invocation), "snapshot": NS(profile_digest="b" * 64)})
            with pytest.raises(DraftAssistanceError, match="PROFILE_MISMATCH"):
                owner.read_invocation_settlement(c, wrong)
        other = _ledger(repository.pool.conninfo, "typed-budget-other", cost_cap=200)
        try:
            with (
                owner.pool.connection() as c,
                pytest.raises(DraftAssistanceError, match="RESERVATION_CONFLICT"),
            ):
                other.read_invocation_settlement(c, invocation)
        finally:
            other.close()
        owner.record_usage(
            "typed-settle",
            reservation,
            ProviderObservation(
                "typed-observation",
                ObservationState.FAILED,
                reason_code="PROVIDER_REFUSAL",
                input_tokens=10,
                output_tokens=10,
            ),
        )
        with owner.pool.connection() as c:
            before = c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            actual = owner.read_invocation_settlement(c, invocation)
            assert actual["status"] == "ESTIMATE_SETTLED"
            assert actual["reservation_retained"] is False
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM draft_provider_budget.settlements"
                ).fetchone()["n"]
                == before
            )
    finally:
        owner.close()
