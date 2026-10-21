"""D324-6 isolated PostgreSQL: immutable history, exact one-call allowance."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import ContextApproval
from agent_console.draft_assistance import DraftAssistanceError, ProviderBudgetQuote
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.planning_call_admission import PlanningCallAdmission
from psycopg.types.json import Jsonb
from test_context_call_admission import ROOT, env, pytestmark, setup  # noqa: F401


@pytest.fixture
def planning(env):  # noqa: F811
    e = env
    e.admission.prepare(e.business, e.invocation)
    limits = {**e.limits, "ledger_id": "planning-original", "calls": 8}
    service = PlanningCallAdmission(e.admission.delegation, limits)
    service.migrate()
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_objects VALUES "
            "('s5-323-demo','isolated-real-demo','BUSINESS_PROBLEM','new-problem',%s,%s)",
            (e.invocation.context_id, e.invocation.invocation_id),
        )
        c.execute(
            "INSERT INTO authorization_admin.task_delegation_ledgers VALUES "
            "('s5-323-demo','isolated-real-demo','planning-original','old','planning')"
        )
        c.execute((ROOT / "0025_plan_suggestion.sql").read_text())
        # Use actual owner DDL; contextual/model tables exist in this fixture.
        c.execute((ROOT / "0026_plan_suggestion_invocation.sql").read_text())
    profile = replace(e.draft.profile, maximum_output_tokens=500)
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=ROOT / "0024_draft_provider_budget.sql",
        profile=profile,
        ledger_id="planning-original",
        call_cap=8,
        total_cost_cap_microusd=10000000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    budget.delegation_configuration = limits
    budget.migrate_and_configure()
    e.planning, e.budget = service, budget
    try:
        yield e
    finally:
        budget.close()


def prepare(e, key="one"):
    request = SimpleNamespace(
        idempotency_key=key,
        target=SimpleNamespace(problem=SimpleNamespace(resource_id="new-problem")),
    )
    record = {
        "request": {"idempotency_key": key},
        "target": {
            "invocation_id": "invocation-" + key,
            "suggestion_context_id": "planning-" + key,
            "input_commitment": key,
            "problem": {"problem": {"resource_id": "new-problem"}},
        },
    }
    return e.planning.prepare_record(e.business, request, record)


def sign(e, prepared):
    identity = prepared["admission"]["context_id"]
    row = e.planning.read(e.business, identity)["request"]
    return e.planning.approve(
        e.reviewer,
        identity,
        ContextApproval(
            request_digest=row["digest"],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            idempotency_key=identity,
        ),
    )


def claim(e, prepared):
    record = prepared["invocation"]
    inv = record["target"]["invocation_id"]
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.invocations VALUES "
            "('s5-323-demo','isolated-real-demo',%s,'human:demo323-requester',%s,%s,%s)",
            (inv, inv, "fixture", Jsonb(record)),
        )
    return SimpleNamespace(
        scope=e.budget.profile.scope,
        invocation_id=inv,
        profile_revision_id=e.budget.profile.profile_revision_id,
    )


def history(e, cost=1000):
    with e.repo.connection_scope() as c:
        for n in range(19):
            c.execute(
                "INSERT INTO draft_provider_budget.reservations VALUES "
                "('s5-323-demo','isolated-real-demo','planning-original',%s,%s,%s,100,500,%s,%s,now())",
                (f"old-r-{n}", f"old-op-{n}", f"old-i-{n}", cost, "f" * 64),
            )


def test_exact_preparation_independent_signature_and_single_binding(planning):
    e = planning
    first = prepare(e)
    assert not first["admission"]["ready"]
    assert prepare(e) == first
    assert e.planning.recover(e.business, "one") == first
    row = e.planning.read(e.business, "planning-one")["request"]
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        e.planning.approve(
            e.business,
            "planning-one",
            ContextApproval(
                request_digest=row["digest"],
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                idempotency_key="self",
            ),
        )
    sign(e, first)
    assert prepare(e)["admission"]["ready"]
    with pytest.raises(AuthorityError, match="SINGLE_ALLOWANCE_ALREADY_BOUND"):
        sign(e, prepare(e, "second"))
    e.repo.verify_existing_schema()


def test_all_19_history_rows_count_and_concurrent_replay_consumes_once(planning):
    from concurrent.futures import ThreadPoolExecutor

    e = planning
    history(e)
    prepared = prepare(e)
    sign(e, prepared)
    inv = claim(e, prepared)
    quote = ProviderBudgetQuote(100, 500, 600)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: e.budget.reserve("one", inv, quote), range(2))
        )
    assert results[0] == results[1]
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 20
        )
        assert (
            c.execute("SELECT call_cap FROM draft_provider_budget.policies").fetchone()[
                "call_cap"
            ]
            == 8
        )
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES "
            "('s5-323-demo','isolated-real-demo',%s,%s)",
            (inv.invocation_id, Jsonb({"technical_status": "OUTCOME_UNKNOWN"})),
        )
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        e.budget.reserve("again", inv, quote)


def test_money_cap_still_counts_unknown_reservations(planning):
    e = planning
    history(e, 526300)
    prepared = prepare(e)
    sign(e, prepared)
    inv = claim(e, prepared)
    with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
        e.budget.reserve("one", inv, ProviderBudgetQuote(100, 500, 600))


def test_changed_target_revocation_and_history_immutable(planning):
    from psycopg import errors

    e = planning
    prepared = prepare(e)
    decision = sign(e, prepared)
    inv = claim(e, prepared)
    e.planning.revoke(e.reviewer, "planning-one", decision["admission_id"])
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        e.budget.reserve("one", inv, ProviderBudgetQuote(100, 500, 600))
    assert not prepare(e)["admission"]["ready"]
    with pytest.raises(errors.RaiseException), e.repo.connection_scope() as c:
        c.execute("DELETE FROM authorization_admin.planning_call_allowances")
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.planning_call_allowances"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


def test_twentieth_historical_call_prevents_new_reservation(planning):
    e = planning
    history(e)
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_provider_budget.reservations VALUES "
            "('s5-323-demo','isolated-real-demo','planning-original',"
            "'twentieth','old-op20','old-i20',100,500,1000,repeat('f',64),now())"
        )
    prepared = prepare(e)
    sign(e, prepared)
    inv = claim(e, prepared)
    with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
        e.budget.reserve("one", inv, ProviderBudgetQuote(100, 500, 600))


def test_source_context_unknown_blocks_planning_successor(planning):
    from agent_console.draft_assistance import DraftInvocationState

    e = planning
    prepared = prepare(e)
    sign(e, prepared)
    inv = claim(e, prepared)
    e.draft._replace(e.invocation, state=DraftInvocationState.OUTCOME_UNKNOWN)
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        e.budget.reserve("one", inv, ProviderBudgetQuote(100, 500, 600))


def test_historical_signature_does_not_imply_current_exact_grants(planning):
    from agent_console.planning_call_admission import BoundPlanningAdmission

    e = planning
    sign(e, prepare(e))
    value = BoundPlanningAdmission(e.planning, e.business).recover("one")
    assert not value["admission"]["ready"]
    assert value["admission"]["reasonCode"] == "CONTEXT_ADMISSION_GRANTS_REQUIRED"
