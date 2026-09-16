from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftResultKind,
    DraftScope,
    ObservationState,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.kimi_responses_draft_adapter import ADAPTER_ID, ADAPTER_REVISION
from agent_console.model_binding_resolution import ExactModelBinding

DIGEST = "a" * 64
MIGRATION = Path(__file__).parents[1] / "migrations" / "0024_draft_provider_budget.sql"
QUOTE_LABEL = "TEST_ONLY_SYNTHETIC_USD_QUOTE / NOT_KIMI_PRICE"


@pytest.fixture(scope="module")
def database_url():
    value = os.environ.get("DRAFT_PROVIDER_BUDGET_TEST_DATABASE_URL")
    if not value:
        pytest.skip("DRAFT_PROVIDER_BUDGET_TEST_DATABASE_URL is not configured")
    return value


def _profile() -> DraftAssistanceProfileRevision:
    return DraftAssistanceProfileRevision(
        "draft-profile-revision:s5-320:budget-test",
        DIGEST,
        DraftScope("tenant-a", "quality"),
        ExactModelBinding("model-kimi", "model-revision-kimi-1", DIGEST),
        "provider-kimi",
        "provider-revision-kimi-1",
        DIGEST,
        "endpoint-kimi",
        "endpoint-revision-kimi-1",
        DIGEST,
        "connection-kimi",
        "connection-revision-kimi-1",
        DIGEST,
        ADAPTER_ID,
        ADAPTER_REVISION,
        maximum_output_tokens=4096,
    )


def _invocation(number: int):
    return SimpleNamespace(
        scope=DraftScope("tenant-a", "quality"),
        profile_revision_id="draft-profile-revision:s5-320:budget-test",
        invocation_id=f"s5-320-budget-invocation-{number}-{uuid.uuid4().hex}",
    )


def _ledger(database_url: str, ledger_id: str) -> PostgresProviderCallBudget:
    ledger = PostgresProviderCallBudget(
        database_url,
        migration_path=MIGRATION,
        profile=_profile(),
        ledger_id=ledger_id,
        call_cap=2,
        total_cost_cap_microusd=10_000_000,
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=2_000_000,
    )
    ledger.migrate_and_configure()
    return ledger


def test_kimi_test_only_reservation_survives_restart_without_dispatch(database_url):
    assert QUOTE_LABEL == "TEST_ONLY_SYNTHETIC_USD_QUOTE / NOT_KIMI_PRICE"
    ledger_id = f"s5-v023-impl-320-restart-{uuid.uuid4().hex}"
    quote = ProviderBudgetQuote(1000, 4096, 9192)
    first = _ledger(database_url, ledger_id)
    try:
        reservation = first.reserve("reserve-before-dispatch", _invocation(1), quote)
        assert reservation.startswith("provider-budget-reservation:")
        # Deliberately stop before credential resolution/transport. The durable
        # reservation is conservative and is not released or converted to a call.
    finally:
        first.close()

    restarted = _ledger(database_url, ledger_id)
    try:
        restarted.reserve("reserve-after-restart", _invocation(2), quote)
        with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
            restarted.reserve("reserve-over-cap", _invocation(3), quote)
    finally:
        restarted.close()


@pytest.mark.parametrize(
    "usage", [(None, None), (1, None), (None, 1), (1001, 1), (1, 4097)]
)
def test_valid_output_with_incomplete_or_out_of_bound_usage_retains_reservation(
    database_url, usage
):
    ledger_id = f"s5-v023-impl-320-usage-{uuid.uuid4().hex}"
    ledger = _ledger(database_url, ledger_id)
    try:
        quote = ProviderBudgetQuote(1000, 4096, 9192)
        reservation = ledger.reserve("reserve-usage", _invocation(1), quote)
        observation = ProviderObservation(
            "usage-observation",
            ObservationState.SUCCEEDED,
            result_kind=DraftResultKind.NEEDS_CLARIFICATION,
            clarification_question="请补充完成标准。",
            input_tokens=usage[0],
            output_tokens=usage[1],
        )
        ledger.record_usage("record-usage", reservation, observation)
        assert observation.state is ObservationState.SUCCEEDED
        with psycopg.connect(database_url) as connection:
            assert (
                connection.execute(
                    "SELECT count(*) FROM draft_provider_budget.settlements "
                    "WHERE ledger_id=%s",
                    (ledger_id,),
                ).fetchone()[0]
                == 0
            )
            assert (
                connection.execute(
                    "SELECT worst_case_cost_microusd "
                    "FROM draft_provider_budget.reservations WHERE ledger_id=%s",
                    (ledger_id,),
                ).fetchone()[0]
                == quote.worst_case_cost_microusd
            )
    finally:
        ledger.close()
