# ruff: noqa: F811 -- Imported isolated owner fixtures.
"""Formal original experience admission, current revocation and cumulative reserve."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import guard, request_row
from agent_console.conversation_experience_admission import LEDGER
from agent_console.draft_assistance import DraftAssistanceError, ProviderBudgetQuote
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.provider_budget_allowance import experience_limits
from test_context_call_admission import env  # noqa: F401
from test_conversation_experience_admission import configure_successor, prepare
from test_local_accounts_postgres import setup  # noqa: F401
from test_provider_budget_extension import enable


def test_old_formal_context_reserves_101_without_rewrite_and_revoke_still_blocks(
    env,
    tmp_path,
):
    e = env
    invocation, wrapper, path, allowance = configure_successor(e, tmp_path)
    prepare(e, invocation, wrapper)
    frozen_policy = path.read_bytes()
    profile = replace(e.draft.profile, maximum_output_tokens=500)
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=profile,
        ledger_id=LEDGER,
        call_cap=20,
        total_cost_cap_microusd=1_000_000,
        input_price_microusd_per_million_tokens=0,
        output_price_microusd_per_million_tokens=0,
        allowance_id=allowance["allowanceId"],
    )
    budget.delegation_configuration = e.admission.configuration
    budget.extension_test_base = allowance
    quote = ProviderBudgetQuote(10, 500, 0)
    try:
        with e.repo.connection_scope() as c:
            original = request_row(c, invocation.context_id)
            assert experience_limits(c, original, budget) == (100, 10_000_000)
            assert guard(c, budget, invocation, quote)
        # Existing history on this ledger, outside this conversation. Real budget owner.
        for n in range(100):
            old = SimpleNamespace(
                scope=profile.scope,
                profile_revision_id=profile.profile_revision_id,
                invocation_id=f"old-history:{n}",
            )
            budget.reserve(f"history:{n}", old, quote)
        with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
            budget.reserve("old-context:101", invocation, quote)
        enable(
            budget,
            [
                {
                    "subjectId": original["subject_id"],
                    "authorizationDigest": original["record"]["authorization_digest"],
                    "configurationDigest": _digest(original["record"]["configuration"]),
                }
            ],
        )
        actual = budget.reserve("old-context:101", invocation, quote)
        assert budget.reserve("old-context:101", invocation, quote) == actual
        with e.repo.connection_scope() as c:
            assert request_row(c, invocation.context_id) == original
            assert experience_limits(c, original, budget) == (200, 20_000_000)
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations "
                    "WHERE ledger_id=%s",
                    (LEDGER,),
                ).fetchone()["n"]
                == 101
            )
            decision = c.execute(
                "SELECT admission_id FROM authorization_admin.context_call_decisions "
                "WHERE context_id=%s ORDER BY created_at DESC LIMIT 1",
                (invocation.context_id,),
            ).fetchone()
            c.execute(
                "INSERT INTO authorization_admin.context_call_revocations"
                "(admission_id,actor_id) VALUES(%s,%s)",
                (decision["admission_id"], "operator:test"),
            )
        assert path.read_bytes() == frozen_policy
        with (
            pytest.raises(AuthorityError, match="ADMISSION_REQUIRED"),
            budget.dispatch_guard(invocation, quote),
        ):
            pytest.fail("revoked original context dispatched")
    finally:
        budget.close()


def test_formal_planning_context_keeps_original_scope_and_uses_same_extension(
    env, tmp_path, monkeypatch
):
    import test_conversation_planning_admission as fixture
    from agent_console.conversation_planning_admission import limits

    e = env
    captured = {}

    def configuration(*args, **kwargs):
        result = configure_successor(*args, **kwargs)
        captured["allowance"] = result[3]
        return result

    monkeypatch.setattr(fixture, "configure", configuration)
    fixture.ordinary.__wrapped__(e, tmp_path)
    prepared = fixture.planned(e)
    owner = SimpleNamespace(
        _connection=e.repo.connection_scope,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=e.draft.profile,
        ledger_id=LEDGER,
        allowance_id=captured["allowance"]["allowanceId"],
        extension_test_base=captured["allowance"],
    )
    with e.repo.connection_scope() as c:
        row = request_row(c, prepared["admission"]["context_id"])
        assert limits(c, row, owner) == (100, 10_000_000)
    enable(
        owner,
        [
            {
                "subjectId": row["subject_id"],
                "authorizationDigest": row["record"]["authorization_digest"],
                "configurationDigest": _digest(row["record"]["configuration"]),
            }
        ],
    )
    with e.repo.connection_scope() as c:
        assert limits(c, row, owner) == (200, 20_000_000)
        assert request_row(c, row["context_id"]) == row
        source = request_row(c, row["record"]["source_context_id"])
        # This fixture uses the SAME approved configuration for source and plan.
        assert source["record"]["configuration"] == row["record"]["configuration"]
        assert experience_limits(c, source, owner) == (200, 20_000_000)
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) SELECT admission_id,'operator:test' "
            "FROM authorization_admin.context_call_decisions WHERE context_id=%s",
            (source["context_id"],),
        )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="ADMISSION_REQUIRED"),
    ):
        limits(c, row, owner)
