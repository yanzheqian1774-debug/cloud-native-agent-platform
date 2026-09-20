"""Planning receipt + existing budget owner, using only exclusive test PostgreSQL."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_domain import PlanningConflict
from agent_console.plan_suggestion_runtime import PlanningBudget
from agent_console.planning_measurement import measurement, settle
from test_draft_provider_budget_postgres import _invocation, _ledger
from test_plan_suggestion_v2 import repository as repository
from test_planning_runtime import formal as formal


@pytest.fixture
def owners(repository):
    with repository.pool.connection() as conn:
        conn.execute(
            (
                Path(__file__).parents[1] / "migrations/0023_draft_assistance.sql"
            ).read_text()
        )
    invocations = PostgresPlanningInvocations(repository)
    invocations.migrate()
    invocations.migrate()  # checksum-verified additive migration is repeatable
    owner = _ledger(
        os.environ["PLANNING323_TEST_DATABASE_URL"], uuid4().hex, cost_cap=1000
    )
    try:
        yield invocations, PlanningBudget(owner)
    finally:
        owner.close()


def receipt(owners, usage=None, status="completed"):
    invocations, budget = owners
    identity = _invocation(int(uuid4().int % 1000000000))
    scope = ScopeIdentity("tenant-a", "quality")
    record = {
        "target": {"invocation_id": identity.invocation_id, "problem": "synthetic-only"}
    }
    invocations.claim(scope, "test-actor", identity.invocation_id, "a" * 64, record)
    reservation = budget.owner.reserve(
        identity.invocation_id, identity, ProviderBudgetQuote(50, 100, 150)
    )
    response = {
        "id": "resp-provider-123",
        "model": "controlled-model",
        "status": status,
    }
    if usage is not None:
        response["usage"] = usage
    m = measurement(
        response,
        "req-provider-456",
        identity.invocation_id,
        17,
        NS(
            native_model_id="controlled-model",
            maximum_input_tokens=50,
            maximum_output_tokens=100,
        ),
    )
    value = {
        "invocation_id": identity.invocation_id,
        "measurement": m,
        "reservation_id": reservation,
        "pricing": budget.pricing(),
    }
    return scope, identity.invocation_id, value


@pytest.mark.parametrize("business", ["VALID_SUGGESTION", "INVALID"])
def test_durable_usage_concurrent_settlement_and_restart(owners, business):
    invocations, budget = owners
    scope, identity, value = receipt(
        owners,
        {
            "input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 30,
            "input_tokens_details": {"cached_tokens": 7},
            "output_tokens_details": {"reasoning_tokens": 2},
        },
    )

    def complete(_):
        invocations.save_receipt(scope, identity, value)
        return settle(budget, identity, value)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(complete, range(8)))
    assert all(
        r["estimate_microusd"] == 30 for r in results
    )  # no adding cached/reasoning
    invocations.finish(
        scope, identity, {"technical_status": "SUCCEEDED", "kind": business}
    )
    restarted = PostgresPlanningInvocations(invocations.planning)
    saved = restarted.receipt(scope, identity)
    assert saved == value
    assert saved["measurement"]["provider_request_id"] != identity
    assert (
        saved["measurement"]["provider_response_id"]
        != saved["measurement"]["provider_request_id"]
    )
    assert (
        saved["pricing"]["price_version_digest"]
        == budget.pricing()["price_version_digest"]
    )
    assert settle(budget, identity, saved) == results[0]
    with budget.owner._connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements "
                "WHERE ledger_id=%s",
                (budget.owner.ledger_id,),
            ).fetchone()["n"]
            == 1
        )
    with pytest.raises(PlanningConflict, match="PLANNING_RECEIPT_IMMUTABLE"):
        restarted.save_receipt(scope, identity, {**value, "measurement": {}})


@pytest.mark.parametrize(
    "usage,status",
    [
        (None, "completed"),
        ({"input_tokens": 20}, "completed"),
        ({"input_tokens": True, "output_tokens": 1}, "completed"),
        ({"input_tokens": 20, "output_tokens": 10, "total_tokens": 99}, "completed"),
        (
            {
                "input_tokens": 20,
                "output_tokens": 10,
                "input_tokens_details": {"cached_tokens": 21},
            },
            "completed",
        ),
        ({"input_tokens": 20, "output_tokens": 101}, "completed"),
        ({"input_tokens": 20, "output_tokens": 10}, "in_progress"),
    ],
)
def test_unknown_partial_and_inconsistent_usage_retain_reservation(
    owners, usage, status
):
    invocations, budget = owners
    scope, identity, value = receipt(owners, usage, status)
    invocations.save_receipt(scope, identity, value)
    assert settle(budget, identity, value) == {
        "status": "PENDING_RECONCILIATION",
        "reservation_retained": True,
    }
    assert budget.owner.read_settlement(value["reservation_id"])["reservation_retained"]
    assert (
        invocations.read(scope, identity, "test-actor")["result"]["technical_status"]
        == "OUTCOME_UNKNOWN"
    )


def test_receipt_transaction_failure_and_settlement_recovery(owners, monkeypatch):
    invocations, budget = owners
    scope, identity, value = receipt(owners, {"input_tokens": 20, "output_tokens": 10})
    # Insert then force rollback: no receipt and no settlement can be inferred.
    from psycopg.types.json import Jsonb

    with (
        pytest.raises(RuntimeError),
        invocations.planning.transaction(scope, identity, authorized=True) as cursor,
    ):
        cursor.execute(
            "INSERT INTO workflow_planning.provider_receipts VALUES (%s,%s,%s,%s)",
            (scope.namespace, scope.security_domain, identity, Jsonb(value)),
        )
        raise RuntimeError("controlled rollback")
    assert invocations.receipt(scope, identity) is None
    assert budget.owner.read_settlement(value["reservation_id"])["reservation_retained"]
    invocations.save_receipt(scope, identity, value)
    original = budget.owner.record_usage
    monkeypatch.setattr(
        budget.owner,
        "record_usage",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("controlled owner unavailable")
        ),
    )
    with pytest.raises(RuntimeError):
        settle(budget, identity, value)
    monkeypatch.setattr(budget.owner, "record_usage", original)
    recovered = PostgresPlanningInvocations(invocations.planning).receipt(
        scope, identity
    )
    assert settle(budget, identity, recovered)["estimate_microusd"] == 30
    assert (
        invocations.read(scope, identity, "test-actor")["result"]["technical_status"]
        == "OUTCOME_UNKNOWN"
    )
    assert "credential" not in json.dumps(recovered)


@pytest.mark.parametrize("mode", ["valid", "invalid", "late"])
def test_formal_service_persists_metering_before_business_finish(
    repository, formal, monkeypatch, mode, record_property
):
    from agent_console import plan_suggestion_bootstrap as boot
    from agent_console import plan_suggestion_runtime as runtime
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
    from test_planning_runtime import send

    with repository.pool.connection() as conn:
        conn.execute(
            (
                Path(__file__).parents[1] / "migrations/0023_draft_assistance.sql"
            ).read_text()
        )
    from agent_console.plan_model_use_postgres import PostgresPlanModelUseOwner

    monkeypatch.setattr(
        boot,
        "PostgresPlanModelUseOwner",
        lambda *_: PostgresPlanModelUseOwner(repository),
    )
    invocations = PostgresPlanningInvocations(repository)
    monkeypatch.setattr(boot, "PostgresPlanningInvocations", lambda *_: invocations)
    budgets = []

    def owner(_database, **kwargs):
        value = PostgresProviderCallBudget(
            os.environ["PLANNING323_TEST_DATABASE_URL"], **kwargs
        )
        budgets.append(value)
        return value

    monkeypatch.setattr(runtime, "create_provider_budget", owner)
    original_exchange = runtime.OpenAIResponsesDraftTransport.exchange

    def metered(self, **kwargs):
        status, body, _, latency = original_exchange(self, **kwargs)
        doc = json.loads(body)
        doc.update(
            id="resp-metered-323", usage={"input_tokens": 30, "output_tokens": 12}
        )
        return status, json.dumps(doc).encode(), "req-metered-323", latency

    monkeypatch.setattr(runtime.OpenAIResponsesDraftTransport, "exchange", metered)
    formal.document["budget"].update(totalCostCapMicrousd=1000000, ledgerId=uuid4().hex)
    formal.path.write_text(json.dumps(formal.document))
    formal.mode = mode
    client = formal.start()
    try:
        response = send(client)
        assert response.status_code == (409 if mode == "late" else 201)
        with repository.pool.connection() as conn:
            row = conn.execute(
                "SELECT invocation_id,record FROM workflow_planning.provider_receipts"
            ).fetchone()
        identity, saved = row["invocation_id"], row["record"]
        assert saved["measurement"]["provider_response_id"] == "resp-metered-323"
        assert saved["measurement"]["local_request_id"] == identity
        scope = ScopeIdentity("tenant-a", "quality")
        durable = PostgresPlanningInvocations(repository).read(
            scope, identity, "employee:17"
        )
        assert (
            durable["result"]["kind"]
            == {"valid": "VALID_SUGGESTION", "invalid": "INVALID", "late": None}[mode]
        )
        cost = budgets[0].read_settlement(saved["reservation_id"])
        assert cost["status"] == "ESTIMATE_SETTLED"
        assert cost["estimate_microusd"] == 156
        record_property("receipt", json.dumps(saved, sort_keys=True))
        record_property("settlement", json.dumps(cost, sort_keys=True))
        if mode != "late":
            with repository.pool.connection() as conn:
                evidence = conn.execute(
                    "SELECT record FROM model_evidence.records"
                ).fetchone()["record"]
            assert evidence["measurementState"] == "MEASURED"
            assert evidence["inputTokens"] == 30
            assert evidence["providerResponseId"] == "resp-metered-323"
        replay = send(client)
        assert replay.status_code == 201
        assert "cost" not in replay.json()["result"]
        assert "provider_receipt" not in replay.json()["result"]
        assert budgets[0].read_settlement(saved["reservation_id"]) == cost
        assert len(formal.calls) == 1
    finally:
        client.close()
        for budget in budgets:
            budget.close()


def test_settlement_transaction_failure_rolls_back_and_replays_once(
    owners, monkeypatch
):
    from contextlib import contextmanager

    invocations, budget = owners
    scope, identity, value = receipt(owners, {"input_tokens": 20, "output_tokens": 10})
    invocations.save_receipt(scope, identity, value)
    original = budget.owner._connection

    @contextmanager
    def failed_commit():
        with original() as connection:
            yield connection
            raise RuntimeError("controlled transaction rollback after INSERT")

    monkeypatch.setattr(budget.owner, "_connection", failed_commit)
    with pytest.raises(RuntimeError):
        settle(budget, identity, value)
    monkeypatch.setattr(budget.owner, "_connection", original)
    assert budget.owner.read_settlement(value["reservation_id"])["reservation_retained"]
    assert (
        settle(budget, identity, invocations.receipt(scope, identity))[
            "estimate_microusd"
        ]
        == 30
    )
