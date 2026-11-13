# ruff: noqa: F401,F811 -- Shared disposable database fixture.
"""Two exact profiles use original immutable pricing/settlement on one ledger."""

from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    ObservationState,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.native_typed_answer import settlement_reader_for_services
from agent_console.provider_profile_pricing import prepare_revision
from test_draft_provider_budget_postgres import MIGRATION, _profile
from test_plan_suggestion_v2 import repository


def test_structured_and_retained_typed_read_their_actual_same_ledger_settlements(
    repository,
):
    common = dict(
        database_url=repository.pool.conninfo,
        migration_path=MIGRATION,
        ledger_id="retained-typed-structured",
        call_cap=3,
        total_cost_cap_microusd=100000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    old = PostgresProviderCallBudget(
        **common,
        profile=replace(
            _profile(), adapter_revision="v3-relation-adoption-source-answers"
        ),
    )
    old.migrate_and_configure()
    with old.pool.connection() as c:
        root = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
            (old.ledger_id,),
        ).fetchone()["record"]
    new = PostgresProviderCallBudget(
        **common,
        profile=replace(
            old.profile,
            adapter_revision="v4-structured-conversation",
            profile_revision_id="structured-v4",
            profile_digest="b" * 64,
        ),
        profile_pricing_root_digest=_digest(root),
    )
    try:
        with new.pool.connection() as c, c.transaction():
            prepare_revision(c, new)
        new.migrate_and_configure()
        invocations = []
        for ordinal, owner in enumerate((old, new)):
            inv = NS(
                scope=owner.profile.scope,
                profile_revision_id=owner.profile.profile_revision_id,
                invocation_id=f"exact-invocation-{ordinal}",
                snapshot=NS(
                    adapter_revision=owner.profile.adapter_revision,
                    profile_digest=owner.profile.profile_digest,
                ),
            )
            inv.budget_reservation_id = owner.reserve(
                f"reserve-{ordinal}", inv, ProviderBudgetQuote(50, 100, 150)
            )
            owner.record_usage(
                f"settle-{ordinal}",
                inv.budget_reservation_id,
                ProviderObservation(
                    f"observed-{ordinal}",
                    ObservationState.FAILED,
                    reason_code="PROVIDER_REFUSAL",
                    input_tokens=10,
                    output_tokens=10,
                ),
            )
            invocations.append(inv)
        read = settlement_reader_for_services(
            NS(profile=old.profile, budget=old), NS(profile=new.profile, budget=new)
        )
        with old.pool.connection() as c:
            before = c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            for inv in (*invocations, invocations[0]):
                settled = read(c, inv)
                assert settled["status"] == "ESTIMATE_SETTLED"
                assert settled["reservation_retained"] is False
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.settlements"
                ).fetchone()["n"]
                == before
                == 2
            )
            wrong = NS(
                **{
                    **vars(invocations[0]),
                    "budget_reservation_id": invocations[1].budget_reservation_id,
                }
            )
            with pytest.raises(
                DraftAssistanceError, match=r"RESERVATION_CONFLICT|PROFILE_MISMATCH"
            ):
                read(c, wrong)
    finally:
        new.close()
        old.close()
