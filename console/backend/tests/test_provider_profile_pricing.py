"""Real isolated PostgreSQL mixed-profile accounting, no provider calls."""

from dataclasses import replace
from types import SimpleNamespace as NS
from uuid import uuid4

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
from agent_console.provider_profile_pricing import prepare_revision
from psycopg import errors
from test_draft_provider_budget_postgres import MIGRATION, _profile
from test_plan_suggestion_v2 import repository as repository  # isolated DB fixture


@pytest.fixture
def ledgers(repository):
    import os

    ledger = "gpt-price-test:" + str(uuid4())
    args = dict(
        database_url=os.environ["PLANNING323_TEST_DATABASE_URL"],
        migration_path=MIGRATION,
        ledger_id=ledger,
        call_cap=3,
        total_cost_cap_microusd=100000,
    )
    old = PostgresProviderCallBudget(
        **args,
        profile=_profile(),
        input_price_microusd_per_million_tokens=8000000,
        output_price_microusd_per_million_tokens=20000000,
    )
    old.migrate_and_configure()
    with old._connection() as c:
        root = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
            (ledger,),
        ).fetchone()["record"]
    new = PostgresProviderCallBudget(
        **args,
        profile=replace(
            old.profile,
            profile_revision_id="gpt-profile:" + str(uuid4()),
            profile_digest="b" * 64,
        ),
        input_price_microusd_per_million_tokens=2000000,
        output_price_microusd_per_million_tokens=10000000,
        profile_pricing_root_digest=_digest(root),
    )
    try:
        yield old, new, root
    finally:
        new.close()
        old.close()


def inv(owner, identity):
    return NS(
        scope=owner.profile.scope,
        profile_revision_id=owner.profile.profile_revision_id,
        invocation_id=identity,
    )


def usage():
    return ProviderObservation(
        "usage:" + str(uuid4()),
        ObservationState.UNKNOWN,
        reason_code="USAGE_ONLY",
        input_tokens=10,
        output_tokens=5,
    )


def prepare(new):
    with new._connection() as c:
        prepare_revision(c, new)
    new.migrate_and_configure()


def test_same_ledger_preserves_old_unknown_and_prices_new_reservation(ledgers):
    old, new, root = ledgers
    old_id = old.reserve(
        "old-unknown", inv(old, "old-unknown"), ProviderBudgetQuote(50, 100, 2400)
    )
    with pytest.raises(DraftAssistanceError):
        new.migrate_and_configure()
    prepare(new)
    new_id = new.reserve(
        "gpt-new", inv(new, "gpt-new"), ProviderBudgetQuote(50, 100, 1100)
    )
    new.record_usage("new-usage", new_id, usage())
    assert new.read_settlement(new_id)["estimate_microusd"] == 70
    assert old.read_settlement(old_id)["reservation_retained"]
    with old._connection() as c:
        assert (
            c.execute(
                "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
                (old.ledger_id,),
            ).fetchone()["record"]
            == root
        )
        total = c.execute(
            "SELECT count(*) calls,sum(coalesce(s.actual_cost_microusd,"
            "r.worst_case_cost_microusd)) cost FROM "
            "draft_provider_budget.reservations r "
            "LEFT JOIN draft_provider_budget.settlements s "
            "USING(namespace,security_domain,"
            "ledger_id,reservation_id) WHERE r.ledger_id=%s",
            (old.ledger_id,),
        ).fetchone()
        assert total == {"calls": 2, "cost": 2470}
    with pytest.raises(DraftAssistanceError, match="RESERVATION_PROFILE_MISMATCH"):
        new.record_usage("bad-usage", old_id, usage())
    with pytest.raises(DraftAssistanceError, match="RESERVATION_PROFILE_MISMATCH"):
        old.record_usage("bad-usage", new_id, usage())
    old.reserve("old-2", inv(old, "old-2"), ProviderBudgetQuote(50, 100, 2400))
    with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
        new.reserve("gpt-4", inv(new, "gpt-4"), ProviderBudgetQuote(50, 100, 1100))


def test_price_binding_is_immutable_and_old_binary_settlement_is_fenced(ledgers):
    old, new, _ = ledgers
    prepare(new)
    identity = new.reserve("new", inv(new, "new"), ProviderBudgetQuote(50, 100, 1100))
    with (
        pytest.raises(errors.RaiseException, match="PRICE_MISMATCH"),
        old._connection() as c,
    ):
        c.execute(
            "INSERT INTO draft_provider_budget.settlements"
            "(namespace,security_domain,ledger_id,reservation_id,operation_id,"
            "observation_id,input_tokens,output_tokens,actual_cost_microusd,"
            "payload_digest) "
            "VALUES(%s,%s,%s,%s,'legacy','legacy',10,5,180,%s)",
            (
                old.profile.scope.namespace,
                old.profile.scope.security_domain,
                old.ledger_id,
                identity,
                "c" * 64,
            ),
        )
    assert new.read_settlement(identity)["reservation_retained"]
    with (
        pytest.raises(errors.RaiseException, match="IMMUTABLE"),
        new._connection() as c,
    ):
        c.execute(
            "DELETE FROM draft_provider_budget.reservation_pricing WHERE ledger_id=%s",
            (new.ledger_id,),
        )


def test_wrong_root_or_enlarged_root_caps_cannot_prepare(ledgers):
    _, new, _ = ledgers
    root_digest = new.profile_pricing_root_digest
    new.profile_pricing_root_digest = "f" * 64
    with pytest.raises(DraftAssistanceError, match="PROFILE_CONFLICT"):
        prepare(new)
    new.profile_pricing_root_digest = root_digest
    new.call_cap = 100
    with pytest.raises(DraftAssistanceError, match="PROFILE_CONFLICT"):
        prepare(new)


def test_old_and_new_profiles_share_atomic_call_cap(ledgers):
    from concurrent.futures import ThreadPoolExecutor

    old, new, _ = ledgers
    prepare(new)
    old.reserve("first", inv(old, "first"), ProviderBudgetQuote(50, 100, 2400))
    old.reserve("second", inv(old, "second"), ProviderBudgetQuote(50, 100, 2400))

    def reserve(owner):
        name = owner.profile.profile_revision_id
        quote = ProviderBudgetQuote(50, 100, 2400 if owner is old else 1100)
        try:
            owner.reserve(name, inv(owner, name), quote)
            return "OK"
        except DraftAssistanceError as exc:
            return exc.reason_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, (old, new))) == [
            "OK",
            "PROVIDER_BUDGET_EXHAUSTED",
        ]


def test_missing_original_ledger_is_not_created_by_revision_startup(ledgers):
    _, new, _ = ledgers
    new.ledger_id = "absent:" + str(uuid4())
    with pytest.raises(DraftAssistanceError):
        new.migrate_and_configure()
    with new._connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.policies "
                "WHERE ledger_id=%s",
                (new.ledger_id,),
            ).fetchone()["n"]
            == 0
        )


def test_historical_receipt_uses_its_price_and_never_settles_unknown(ledgers):
    from agent_console.plan_suggestion_domain import PlanningConflict
    from agent_console.plan_suggestion_runtime import PlanningBudget

    old, new, _ = ledgers
    settled_id = old.reserve(
        "old-settled", inv(old, "old-settled"), ProviderBudgetQuote(50, 100, 2400)
    )
    old.record_usage("old-usage", settled_id, usage())
    unknown_id = old.reserve(
        "old-unknown", inv(old, "old-unknown"), ProviderBudgetQuote(50, 100, 2400)
    )
    prepare(new)
    budget = PlanningBudget(new)
    receipt = {"reservation_id": settled_id, "pricing": old.pricing()}
    assert (
        budget.historical_settlement("old-settled", receipt, scope=old.profile.scope)[
            "estimate_microusd"
        ]
        == 180
    )
    assert budget.historical_settlement(
        "old-unknown",
        {**receipt, "reservation_id": unknown_id},
        scope=old.profile.scope,
    )["reservation_retained"]
    assert old.read_settlement(unknown_id)["reservation_retained"]
    with pytest.raises(PlanningConflict, match="PRICE_VERSION_CONFLICT"):
        budget.historical_settlement(
            "different-invocation", receipt, scope=old.profile.scope
        )
    with pytest.raises(PlanningConflict, match="PRICE_VERSION_CONFLICT"):
        budget.historical_settlement(
            "old-settled",
            {**receipt, "pricing": new.pricing()},
            scope=old.profile.scope,
        )


def test_historical_usage_still_requires_both_disclosure_grants(ledgers):
    from agent_console.authority_contracts import AuthorityError
    from agent_console.plan_suggestion_runtime import PlanningBudget
    from agent_console.plan_suggestion_service import PlanningSuggestionService

    old, new, _ = ledgers
    rid = old.reserve("old", inv(old, "old"), ProviderBudgetQuote(50, 100, 2400))
    old.record_usage("old-usage", rid, usage())
    prepare(new)
    receipt = {
        "reservation_id": rid,
        "pricing": old.pricing(),
        "measurement": {"fixture": True},
    }
    calls = []
    service = PlanningSuggestionService.__new__(PlanningSuggestionService)
    service.application = NS(
        scope=lambda _: old.profile.scope,
        authority=NS(require=lambda *args: calls.append(args)),
    )
    service.invocations = NS(receipt=lambda *_: receipt)
    service.budget = PlanningBudget(new)
    result = service.read_usage(NS(principal_id="reader"), "old")
    assert len(calls) == 2
    assert result["pricing"] == old.pricing()
    assert result["settlement"]["estimate_microusd"] == 180

    def denied(*_):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    service.application.authority.require = denied
    service.invocations.receipt = lambda *_: pytest.fail("Unauthorized lookup")
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        service.read_usage(NS(principal_id="reader"), "old")


def test_historical_read_accepts_readonly_transaction_and_rejects_foreign_scope(
    ledgers, monkeypatch
):
    from contextlib import contextmanager

    from agent_console.plan_suggestion_domain import PlanningConflict
    from agent_console.plan_suggestion_runtime import PlanningBudget

    old, new, _ = ledgers
    rid = old.reserve("old", inv(old, "old"), ProviderBudgetQuote(50, 100, 2400))
    prepare(new)
    connection = new._connection

    @contextmanager
    def readonly():
        with connection() as c:
            c.execute("SET TRANSACTION READ ONLY")
            yield c

    monkeypatch.setattr(new, "_connection", readonly)
    budget = PlanningBudget(new)
    receipt = {"reservation_id": rid, "pricing": old.pricing()}
    assert budget.historical_settlement("old", receipt, scope=old.profile.scope)[
        "reservation_retained"
    ]
    with pytest.raises(PlanningConflict, match="PRICE_VERSION_CONFLICT"):
        budget.historical_settlement(
            "old", receipt, scope=NS(namespace="foreign", security_domain="quality")
        )
