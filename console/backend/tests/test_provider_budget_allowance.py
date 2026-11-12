"""Cumulative successors reuse real ledger locks and retain UNKNOWN reservations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from agent_console.draft_assistance import DraftAssistanceError, ProviderBudgetQuote
from agent_console.draft_provider_budget_postgres import _digest
from agent_console.provider_budget_allowance import prepare, require
from test_draft_provider_budget_postgres import (
    _invocation,
    _ledger,
    database_url,  # noqa: F401
)

QUOTE = ProviderBudgetQuote(50, 100, 150)


def document(owner, *, calls=3, cost=500, expired=False):
    with owner._connection() as c:
        root = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
            (owner.ledger_id,),
        ).fetchone()["record"]
    now = datetime.now(UTC)
    return {
        "schemaVersion": "provider-budget-allowance.v1",
        "allowanceId": "allowance:test",
        "ledgerId": owner.ledger_id,
        "namespace": owner.profile.scope.namespace,
        "securityDomain": owner.profile.scope.security_domain,
        "rootPolicyDigest": _digest(root),
        "authorizationDigest": "b" * 64,
        "callCap": calls,
        "totalCostCapMicrousd": cost,
        "notBefore": (now - timedelta(hours=1)).isoformat(),
        "expiresAt": (now + timedelta(seconds=-1 if expired else 3600)).isoformat(),
        "externalWrites": False,
    }


def test_old_unknown_counts_and_concurrent_new_calls_share_original_lock(database_url):  # noqa: F811
    owner = _ledger(database_url, "successor-" + uuid4().hex, call_cap=1, cost_cap=150)
    try:
        old = owner.reserve("old", _invocation(1), QUOTE)
        saved = prepare(owner, document(owner))
        owner.allowance_id = saved["allowanceId"]
        with ThreadPoolExecutor(max_workers=3) as pool:

            def reserve(n):
                try:
                    return owner.reserve(str(n), _invocation(n), QUOTE)
                except DraftAssistanceError as e:
                    return str(e)

            results = list(pool.map(reserve, [2, 3, 4]))
        assert sum("EXHAUSTED" in result for result in results) == 1
        with owner._connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations "
                    "WHERE ledger_id=%s",
                    (owner.ledger_id,),
                ).fetchone()["n"]
                == 3
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.settlements "
                    "WHERE ledger_id=%s",
                    (owner.ledger_id,),
                ).fetchone()["n"]
                == 0
            )
            assert (
                c.execute(
                    "SELECT call_cap FROM draft_provider_budget.policies "
                    "WHERE ledger_id=%s",
                    (owner.ledger_id,),
                ).fetchone()["call_cap"]
                == 1
            )
        assert owner.reserve("old", _invocation(1), QUOTE) == old
    finally:
        owner.close()


def test_money_cap_retains_previous_unsettled_cost(database_url):  # noqa: F811
    owner = _ledger(database_url, "cost-" + uuid4().hex, call_cap=1, cost_cap=150)
    try:
        owner.reserve("old", _invocation(1), QUOTE)
        prepare(owner, document(owner, calls=10, cost=250))
        owner.allowance_id = "allowance:test"
        with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
            owner.reserve("new", _invocation(2), QUOTE)
    finally:
        owner.close()


def test_expired_allowance_blocks_reserve_and_dispatch_without_replay(database_url):  # noqa: F811
    owner = _ledger(database_url, "expiry-" + uuid4().hex)
    try:
        owner.reserve("old", _invocation(1), QUOTE)
        prepare(owner, document(owner, expired=True))
        owner.allowance_id = "allowance:test"
        with pytest.raises(DraftAssistanceError, match="ALLOWANCE_EXPIRED"):
            owner.reserve("new", _invocation(2), QUOTE)
        with (
            pytest.raises(DraftAssistanceError, match="ALLOWANCE_EXPIRED"),
            owner.dispatch_guard(_invocation(1), QUOTE),
        ):
            pytest.fail("Must not dispatch")
    finally:
        owner.close()


def test_immutable_idempotent_allowance_survives_reopen(database_url):  # noqa: F811
    identity = "restart-" + uuid4().hex
    owner = _ledger(database_url, identity)
    saved = prepare(owner, document(owner))
    assert prepare(owner, saved) == saved
    with pytest.raises(DraftAssistanceError, match="CONFLICT"):
        prepare(owner, {**saved, "callCap": 4})
    with (
        pytest.raises(psycopg.errors.RaiseException, match="IMMUTABLE"),
        owner._connection() as c,
    ):
        c.execute(
            "DELETE FROM draft_provider_budget.allowances WHERE ledger_id=%s",
            (identity,),
        )
    owner.close()
    reopened = _ledger(database_url, identity)
    try:
        reopened.allowance_id = saved["allowanceId"]
        with reopened._connection() as c:
            assert require(c, reopened).model_dump(mode="json") == saved
    finally:
        reopened.close()


def test_scope_conflict_and_missing_allowance_fail_closed(database_url):  # noqa: F811
    owner = _ledger(database_url, "scope-" + uuid4().hex)
    try:
        with pytest.raises(DraftAssistanceError, match="SCOPE_MISMATCH"):
            prepare(owner, {**document(owner), "ledgerId": "another-ledger"})
        owner.allowance_id = "missing"
        with pytest.raises(DraftAssistanceError, match="NOT_PREPARED"):
            owner.reserve("new", _invocation(1), QUOTE)
    finally:
        owner.close()


def test_allowance_does_not_override_narrower_context_limits(database_url, monkeypatch):  # noqa: F811
    owner = _ledger(database_url, "narrow-" + uuid4().hex, call_cap=1, cost_cap=150)
    try:
        owner.reserve("old", _invocation(1), QUOTE)
        prepare(owner, document(owner, calls=10, cost=1000))
        owner.allowance_id = "allowance:test"
        monkeypatch.setattr(
            "agent_console.planning_call_admission.effective_cap", lambda *args: 1
        )
        with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
            owner.reserve("new", _invocation(2), QUOTE)
        monkeypatch.setattr(
            "agent_console.planning_call_admission.effective_cap", lambda *args: 10
        )
        monkeypatch.setattr(
            "agent_console.planning_call_admission.effective_cost_cap",
            lambda *args: 200,
        )
        with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
            owner.reserve("new", _invocation(2), QUOTE)
    finally:
        owner.close()


def test_conversation_allowance_binding_and_expiry(database_url):  # noqa: F811
    from agent_console.authority_contracts import AuthorityError
    from agent_console.provider_budget_allowance import experience_limits

    owner = _ledger(
        database_url, "context-" + uuid4().hex, call_cap=20, cost_cap=1_000_000
    )
    try:
        saved = prepare(owner, document(owner, calls=100, cost=10_000_000))
        owner.allowance_id = saved["allowanceId"]
        row = {
            "tenant_id": owner.profile.scope.namespace,
            "security_domain": owner.profile.scope.security_domain,
            "record": {
                "budget_allowance_id": saved["allowanceId"],
                "authorization_digest": saved["authorizationDigest"],
                "configuration": {
                    "ledger_id": owner.ledger_id,
                    "calls": 40,
                    "cost_microusd": 2_000_000,
                },
            },
        }
        with owner._connection() as c:
            assert experience_limits(c, row, owner) == (40, 2_000_000)
            row["record"]["authorization_digest"] = "c" * 64
            with pytest.raises(AuthorityError, match="ALLOWANCE_MISMATCH"):
                experience_limits(c, row, owner)
            row["record"]["authorization_digest"] = saved["authorizationDigest"]
            row["record"]["budget_allowance_id"] = "another-allowance"
            with pytest.raises(AuthorityError, match="ALLOWANCE_MISMATCH"):
                experience_limits(c, row, owner)
            row["record"]["budget_allowance_id"] = saved["allowanceId"]
            row["record"]["configuration"]["calls"] = 101
            with pytest.raises(AuthorityError, match="ALLOWANCE_MISMATCH"):
                experience_limits(c, row, owner)
        expired = document(owner, calls=100, cost=10_000_000, expired=True)
        expired["allowanceId"] = "allowance:expired-context"
        prepare(owner, expired)
        owner.allowance_id = expired["allowanceId"]
        row["record"]["budget_allowance_id"] = owner.allowance_id
        row["record"]["configuration"]["calls"] = 40
        with (
            owner._connection() as c,
            pytest.raises(AuthorityError, match="ALLOWANCE_EXPIRED"),
        ):
            experience_limits(c, row, owner)
    finally:
        owner.close()
