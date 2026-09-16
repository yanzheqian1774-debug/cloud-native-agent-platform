from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftScope,
    ObservationState,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.model_binding_resolution import ExactModelBinding

DIGEST = "a" * 64
MIGRATION = Path(__file__).parents[1] / "migrations" / "0024_draft_provider_budget.sql"


@pytest.fixture(scope="module")
def database_url():
    value = os.environ.get("DRAFT_PROVIDER_BUDGET_TEST_DATABASE_URL")
    if not value:
        pytest.skip("DRAFT_PROVIDER_BUDGET_TEST_DATABASE_URL is not configured")
    return value


def _profile() -> DraftAssistanceProfileRevision:
    return DraftAssistanceProfileRevision(
        "draft-profile-real-1",
        DIGEST,
        DraftScope("tenant-a", "quality"),
        ExactModelBinding("model-1", "model-revision-1", DIGEST),
        "provider-1",
        "provider-revision-1",
        DIGEST,
        "endpoint-1",
        "endpoint-revision-1",
        DIGEST,
        "connection-profile-1",
        "connection-profile-revision-1",
        DIGEST,
        "openai-responses-draft",
        "v1",
        maximum_output_tokens=100,
    )


def _invocation(number: int):
    return SimpleNamespace(
        scope=DraftScope("tenant-a", "quality"),
        profile_revision_id="draft-profile-real-1",
        invocation_id=f"budget-invocation-{number}",
    )


def _ledger(database_url, ledger_id, *, call_cap=3, cost_cap=150):
    value = PostgresProviderCallBudget(
        database_url,
        migration_path=MIGRATION,
        profile=_profile(),
        ledger_id=ledger_id,
        call_cap=call_cap,
        total_cost_cap_microusd=cost_cap,
        input_price_microusd_per_million_tokens=1_000_000,
        output_price_microusd_per_million_tokens=1_000_000,
    )
    value.migrate_and_configure()
    return value


def test_missing_usage_retains_worst_case_reservation(database_url):
    ledger = _ledger(database_url, "budget-ledger-missing-usage-v2")
    try:
        first = ledger.reserve(
            "reserve-missing-1", _invocation(101), ProviderBudgetQuote(50, 100, 150)
        )
        ledger.record_usage(
            "usage-missing-1",
            first,
            ProviderObservation(
                "observation-missing",
                ObservationState.UNKNOWN,
                reason_code="TRANSPORT_AMBIGUOUS",
            ),
        )
        with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
            ledger.reserve(
                "reserve-missing-2",
                _invocation(102),
                ProviderBudgetQuote(30, 100, 130),
            )
    finally:
        ledger.close()


def test_authoritative_usage_settlement_releases_only_measured_difference(
    database_url,
):
    ledger = _ledger(database_url, "budget-ledger-settled-v2", cost_cap=200)
    try:
        first = ledger.reserve(
            "reserve-settled-1", _invocation(201), ProviderBudgetQuote(50, 100, 150)
        )
        ledger.record_usage(
            "usage-settled-1",
            first,
            ProviderObservation(
                "observation-settled",
                ObservationState.FAILED,
                reason_code="PROVIDER_REFUSAL",
                input_tokens=10,
                output_tokens=10,
            ),
        )
        second = ledger.reserve(
            "reserve-settled-2", _invocation(202), ProviderBudgetQuote(50, 100, 150)
        )
        assert first != second
    finally:
        ledger.close()


def test_concurrent_admission_cannot_oversell_call_cap(database_url):
    ledger = _ledger(
        database_url, "budget-ledger-concurrent-v2", call_cap=1, cost_cap=1_000
    )

    def reserve(number):
        try:
            return ledger.reserve(
                f"reserve-concurrent-{number}",
                _invocation(300 + number),
                ProviderBudgetQuote(10, 100, 110),
            )
        except DraftAssistanceError as exc:
            return exc.reason_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(reserve, (1, 2)))
        assert (
            sum(value.startswith("provider-budget-reservation:") for value in results)
            == 1
        )
        assert results.count("PROVIDER_BUDGET_EXHAUSTED") == 1
    finally:
        ledger.close()


def test_underquoted_request_fails_closed(database_url):
    ledger = _ledger(database_url, "budget-ledger-underquote-v1", cost_cap=1_000)
    try:
        with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_QUOTE_INVALID"):
            ledger.reserve(
                "reserve-underquoted",
                _invocation(401),
                ProviderBudgetQuote(50, 100, 149),
            )
    finally:
        ledger.close()


def test_concurrent_admission_cannot_oversell_cost_cap(database_url):
    ledger = _ledger(
        database_url, "budget-ledger-concurrent-cost-v1", call_cap=2, cost_cap=150
    )

    def reserve(number):
        try:
            return ledger.reserve(
                f"reserve-concurrent-cost-{number}",
                _invocation(500 + number),
                ProviderBudgetQuote(10, 100, 110),
            )
        except DraftAssistanceError as exc:
            return exc.reason_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(reserve, (1, 2)))
        assert (
            sum(value.startswith("provider-budget-reservation:") for value in results)
            == 1
        )
        assert results.count("PROVIDER_BUDGET_EXHAUSTED") == 1
    finally:
        ledger.close()
