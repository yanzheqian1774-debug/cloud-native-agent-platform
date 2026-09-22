"""Exact D7 extension on original PG ledger; no supplier invocation."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.bounded_task_policy import ConfigurationRevision
from agent_console.draft_assistance import DraftAssistanceError, ProviderBudgetQuote
from psycopg.types.json import Jsonb
from test_bounded_task_authorization import signature, task_env  # noqa: F401
from test_context_call_admission import env, setup  # noqa: F401
from test_planning_call_admission import (  # noqa: F401
    claim,
    history,
    planning,
    pytestmark,
    sign,
)


def prepared(e, key):
    ref = e.task_spec.root
    request = SimpleNamespace(
        idempotency_key=key,
        target=SimpleNamespace(problem=ref),
        model_dump=lambda **kw: {"idempotency_key": key},
    )
    record = {
        "request": {"idempotency_key": key},
        "target": {
            "invocation_id": "inv-" + key,
            "suggestion_context_id": "ctx-" + key,
            "input_commitment": key,
            "problem": {"problem": ref.model_dump(mode="json")},
        },
    }
    return e.planning.prepare_record(e.business, request, record)


@pytest.fixture
def successor(planning, task_env):  # noqa: F811
    e = planning
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_objects VALUES "
            "('s5-323-demo','isolated-real-demo','BUSINESS_PROBLEM','test-root',%s,%s)",
            (e.invocation.context_id, e.invocation.invocation_id),
        )
    history(e)
    old = prepared(e, "old")
    sign(e, old)
    inv = claim(e, old)
    e.budget.reserve("old", inv, ProviderBudgetQuote(100, 500, 600))
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES "
            "('s5-323-demo','isolated-real-demo',%s,%s)",
            (inv.invocation_id, Jsonb({"technical_status": "OUTCOME_UNKNOWN"})),
        )
    e.planning.configuration = {
        **e.planning.configuration,
        "configuration_digest": "b" * 64,
    }
    actual = {
        **e.planning.configuration,
        "connect_seconds": 5,
        "read_seconds": 55,
        "total_seconds": 60,
    }
    e.planning.actual_configuration = actual
    e.tasks.actual_configuration = actual
    e.planning.bounded_tasks_enabled = True
    e.budget.delegation_configuration = e.planning.configuration
    e.budget.task_actual_configuration = actual
    cfg = ConfigurationRevision(
        revision_id="config-55",
        predecessor_digest="a" * 64,
        configuration_digest="b" * 64,
        ledger_id=e.budget.ledger_id,
        model_target="exact",
    )
    spec = e.task_spec.model_copy(
        update={"configuration": cfg, "recovery_invocation_id": inv.invocation_id}
    )
    row = e.tasks.prepare(e.business, spec)
    e.tasks.approve(e.reviewer, row["request_id"], signature(row))
    yield e


def test_exact_twenty_first_call_concurrency_no_reset_and_terminal_no_replay(successor):
    e = successor
    new = prepared(e, "new")
    assert new["admission"]["cumulative_call_cap"] == 21
    assert not new["admission"]["ready"]
    inv = claim(e, new)
    quote = ProviderBudgetQuote(100, 500, 600)
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        e.budget.reserve("new", inv, quote)
    sign(e, new)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _: e.budget.reserve("new", inv, quote), range(2)))
    assert values[0] == values[1]
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 21
        )
        assert (
            c.execute("SELECT call_cap FROM draft_provider_budget.policies").fetchone()[
                "call_cap"
            ]
            == 8
        )
        assert (
            c.execute(
                "SELECT cumulative_call_cap FROM "
                "authorization_admin.planning_call_allowances"
            ).fetchone()["cumulative_call_cap"]
            == 20
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )
    with pytest.raises(AuthorityError, match="SINGLE_ALLOWANCE_ALREADY_BOUND"):
        prepared(e, "another")
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES "
            "('s5-323-demo','isolated-real-demo',%s,%s)",
            (inv.invocation_id, Jsonb({"technical_status": "OUTCOME_UNKNOWN"})),
        )
    with (
        pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"),
        e.budget.dispatch_guard(inv, quote),
    ):
        pytest.fail("must not dispatch")


def test_configuration_drift_stops_both_reserve_and_dispatch(successor):
    e = successor
    new = prepared(e, "new")
    sign(e, new)
    inv = claim(e, new)
    e.budget.task_actual_configuration = {
        **e.budget.task_actual_configuration,
        "read_seconds": 30,
    }
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        e.budget.reserve("new", inv, ProviderBudgetQuote(100, 500, 600))
    with (
        pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"),
        e.budget.dispatch_guard(inv, ProviderBudgetQuote(100, 500, 600)),
    ):
        pytest.fail("must not dispatch")


def test_original_amount_cap_still_counts_unknowns(successor):
    e = successor
    new = prepared(e, "new")
    sign(e, new)
    inv = claim(e, new)
    # A quote exceeding original money cap must fail, even with one count available.
    e.budget.input_price = 100000000000
    quote = ProviderBudgetQuote(100, 500, 10000000 + 500)
    with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
        e.budget.reserve("new", inv, quote)
