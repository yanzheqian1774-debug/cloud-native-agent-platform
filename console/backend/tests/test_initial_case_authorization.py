"""D9 exact initial case, independent signature and shared original budget on PG."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.bounded_task_policy import (
    ConfigurationRevision,
    InitialCaseRevision,
    TaskAuthorizationRequest,
)
from agent_console.draft_assistance import ProviderBudgetQuote
from psycopg.types.json import Jsonb
from test_bounded_task_authorization import signature, task_env  # noqa: F401
from test_context_call_admission import env, setup  # noqa: F401
from test_planning_call_admission import claim, planning, pytestmark, sign  # noqa: F401


@pytest.fixture
def sales(planning, task_env):  # noqa: F811
    e = planning
    actual = {
        **e.planning.configuration,
        "connect_seconds": 5,
        "read_seconds": 55,
        "total_seconds": 60,
    }
    e.planning.actual_configuration = actual
    e.tasks.actual_configuration = actual
    e.planning.bounded_tasks_enabled = True
    e.budget.task_actual_configuration = actual
    e.tasks.root_bindings[
        (
            "SALES_DIAGNOSTIC",
            "s5-323-demo",
            "isolated-real-demo",
            e.task_spec.root.resource_id,
        )
    ] = e.task_spec.root.model_dump(mode="json")
    cfg = ConfigurationRevision(
        revision_id="same-ledger",
        predecessor_digest="a" * 64,
        configuration_digest=actual["configuration_digest"],
        ledger_id=e.budget.ledger_id,
        model_target="exact",
    )
    e.sales_spec = TaskAuthorizationRequest(
        **{
            **e.task_spec.model_dump(mode="json"),
            "purpose": "SALES_DIAGNOSTIC",
            "idempotency_key": "sales-task",
            "configuration": cfg,
            "initial_case_revision": InitialCaseRevision(
                revision_id="sales-first", criteria_set=e.task_spec.root
            ),
        }
    )
    task = e.tasks.prepare(e.business, e.sales_spec)
    e.tasks.approve(e.reviewer, task["request_id"], signature(task, "sales-sign"))
    e.sales_task = task
    return e


def prepare(e, key="sales"):
    ref = e.task_spec.root
    request = SimpleNamespace(
        idempotency_key=key,
        target=SimpleNamespace(problem=ref, criteria=ref),
        model_dump=lambda **kw: {"idempotency_key": key},
    )
    record = {
        "target": {
            "invocation_id": "inv-" + key,
            "suggestion_context_id": "ctx-" + key,
            "input_commitment": key,
            "problem": {
                "problem": ref.model_dump(mode="json"),
                "criteria": ref.model_dump(mode="json"),
            },
        }
    }
    return e.planning.prepare_record(e.business, request, record)


def test_single_exact_initial_call_with_separate_context_signature_and_original_policy(
    sales,
):
    e = sales
    new = prepare(e)
    assert new["admission"]["cumulative_call_cap"] == 100
    assert new["admission"]["total_cost_cap_microusd"] == 50000000
    inv = claim(e, new)
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        e.budget.reserve("sales", inv, ProviderBudgetQuote(100, 500, 600))
    sign(e, new)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reservations = list(
            pool.map(
                lambda _: e.budget.reserve(
                    "sales", inv, ProviderBudgetQuote(100, 500, 600)
                ),
                range(2),
            )
        )
    assert reservations[0] == reservations[1]
    assert prepare(e)["admission"]["context_id"] == new["admission"]["context_id"]
    with pytest.raises(AuthorityError, match="SINGLE_CALL_ALREADY_BOUND"):
        prepare(e, "different")
    with e.repo.connection_scope() as c:
        assert c.execute(
            "SELECT call_cap,total_cost_cap_microusd "
            "FROM draft_provider_budget.policies"
        ).fetchone() == {"call_cap": 8, "total_cost_cap_microusd": 10000000}
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 1
        )
        with pytest.raises(Exception, match="immutable"):
            c.execute("DELETE FROM authorization_admin.initial_case_planning_calls")


def test_new_unknown_requires_recovery_and_never_borrows_supplier_evidence(sales):
    e = sales
    new = prepare(e)
    inv = claim(e, new)
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.invocation_results "
            "VALUES('s5-323-demo','isolated-real-demo',%s,%s)",
            (inv.invocation_id, Jsonb({"technical_status": "OUTCOME_UNKNOWN"})),
        )
    spec = e.sales_spec.model_copy(update={"idempotency_key": "try-again"})
    with pytest.raises(AuthorityError, match="RECOVERY_REQUIRED"):
        e.tasks.prepare(e.business, spec)


def test_unconfigured_root_and_self_approval_rejected(sales):
    e = sales
    e.tasks.root_bindings.clear()
    with pytest.raises(AuthorityError, match="ROOT_DENIED"):
        e.tasks.prepare(e.business, e.sales_spec)
    with pytest.raises(AuthorityError):
        e.tasks.approve(
            e.business, e.sales_task["request_id"], signature(e.sales_task, "self")
        )


@pytest.mark.parametrize("calls,cost", [(100, 1), (1, 50000000)])
def test_sales_shares_supplier_history_and_cannot_reset_budget(sales, calls, cost):
    from agent_console.draft_assistance import DraftAssistanceError

    e = sales
    new = prepare(e)
    sign(e, new)
    inv = claim(e, new)
    with e.repo.connection_scope() as c:
        for n in range(calls):
            c.execute(
                "INSERT INTO draft_provider_budget.reservations VALUES"
                "('s5-323-demo','isolated-real-demo','planning-original',"
                "%s,%s,%s,100,500,%s,%s,now())",
                (
                    f"supplier-r-{n}",
                    f"supplier-op-{n}",
                    f"supplier-i-{n}",
                    cost,
                    "f" * 64,
                ),
            )
    with pytest.raises(DraftAssistanceError, match="BUDGET_EXHAUSTED"):
        e.budget.reserve("sales", inv, ProviderBudgetQuote(100, 500, 600))


@pytest.fixture
def sales_unknown(sales, request):
    from agent_console.development_planning_recovery import RecoveryObservation, observe
    from agent_console.task_delegation import digest
    from test_context_call_admission import ROOT

    e = sales
    variant = getattr(request.node, "callspec", SimpleNamespace(params={})).params.get(
        "change", "valid"
    )
    first = prepare(e)
    sign(e, first)
    invocation = claim(e, first)
    if variant != "unreserved":
        e.budget.reserve("first-sales", invocation, ProviderBudgetQuote(100, 500, 600))
    receipt = {
        "deadline": {"reaped": variant != "unreaped", "reason": "TRANSPORT_FAILURE"},
        "measurement": {},
    }
    with e.repo.connection_scope() as c:
        c.execute((ROOT / "0027_planning_provider_receipt.sql").read_text())
        reserved = c.execute(
            "SELECT reservation_id FROM draft_provider_budget.reservations "
            "WHERE invocation_id=%s",
            (invocation.invocation_id,),
        ).fetchone()
        receipt.update(
            invocation_id=invocation.invocation_id,
            target_digest=digest(first["invocation"]["target"]),
            reservation_id=reserved["reservation_id"] if reserved else "absent",
        )
        if variant == "wrong-invocation-metadata":
            receipt["invocation_id"] = "another-invocation"
        elif variant == "wrong-target-digest":
            receipt["target_digest"] = "f" * 64
        elif variant == "verified-usage":
            receipt["measurement"] = {"settleable": True}
        if variant != "missing-receipt":
            c.execute(
                "INSERT INTO workflow_planning.provider_receipts VALUES(%s,%s,%s,%s)",
                (
                    "s5-323-demo",
                    "isolated-real-demo",
                    invocation.invocation_id,
                    Jsonb(receipt),
                ),
            )
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES(%s,%s,%s,%s)",
            (
                "s5-323-demo",
                "isolated-real-demo",
                invocation.invocation_id,
                Jsonb({"technical_status": "OUTCOME_UNKNOWN"}),
            ),
        )
    # Prove configured sales-root admission, without an old supplier-root binding.
    e.tasks.root_bindings.pop(
        ("SAME_CASE_DELIVERY", "s5-323-demo", "isolated-real-demo")
    )
    observation = observe(
        e.tasks,
        e.business,
        RecoveryObservation(
            root=e.sales_spec.root,
            invocation_id=invocation.invocation_id,
            evidence_digest=digest(receipt),
            evidence_summary=(
                "Local worker reaped; supplier result unknown; reservation retained."
            ),
            idempotency_key="sales-unknown-observation",
            provenance="LOCAL_ONLY",
            local_cleanup_confirmed=True,
        ),
    )
    revision = e.sales_spec.initial_case_revision.model_copy(
        update={"recovery_observation_ids": (observation["observation_id"],)}
    )
    e.recovery_spec = TaskAuthorizationRequest.model_validate(
        e.sales_spec.model_copy(
            update={
                "idempotency_key": "sales-fresh-followup",
                "initial_case_revision": revision,
            }
        ).model_dump(mode="json")
    )
    e.unknown_invocation = invocation
    e.local_observation = observation
    return e


def test_sales_evidence_recovery_requires_new_signature_and_retains_unknown(
    sales_unknown,
):
    e = sales_unknown
    task = e.tasks.prepare(e.business, e.recovery_spec)
    e.tasks.approve(
        e.reviewer, task["request_id"], signature(task, "sales-recovery-sign")
    )
    second = prepare(e, "fresh-sales")
    sign(e, second)
    invocation = claim(e, second)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(
            pool.map(
                lambda _: e.budget.reserve(
                    "fresh-sales", invocation, ProviderBudgetQuote(100, 500, 600)
                ),
                range(2),
            )
        )
    assert rows[0] == rows[1]
    assert invocation.invocation_id != e.unknown_invocation.invocation_id
    with e.repo.connection_scope() as c:
        assert c.execute(
            "SELECT record FROM workflow_planning.invocation_results "
            "WHERE invocation_id=%s",
            (e.unknown_invocation.invocation_id,),
        ).fetchone()["record"] == {"technical_status": "OUTCOME_UNKNOWN"}
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize(
    "change",
    [
        "wrong-receipt-commitment",
        "missing-receipt",
        "unreaped",
        "unreserved",
        "duplicate-observation",
        "wrong-invocation-metadata",
        "wrong-target-digest",
        "verified-usage",
    ],
)
def test_sales_recovery_rejects_incomplete_or_wrong_evidence(sales_unknown, change):
    from agent_console.development_planning_recovery import RecoveryObservation, observe

    e = sales_unknown
    spec = e.recovery_spec
    if change == "duplicate-observation":
        revision = spec.initial_case_revision.model_copy(
            update={
                "recovery_observation_ids": (e.local_observation["observation_id"],) * 2
            }
        )
        spec = spec.model_copy(update={"initial_case_revision": revision})
    elif change == "wrong-receipt-commitment":
        row = observe(
            e.tasks,
            e.business,
            RecoveryObservation(
                root=e.sales_spec.root,
                invocation_id=e.unknown_invocation.invocation_id,
                evidence_digest="f" * 64,
                evidence_summary="Mismatched receipt commitment must fail closed.",
                idempotency_key="wrong-sales-observation",
                provenance="LOCAL_ONLY",
                local_cleanup_confirmed=True,
            ),
        )
        revision = spec.initial_case_revision.model_copy(
            update={"recovery_observation_ids": (row["observation_id"],)}
        )
        spec = spec.model_copy(update={"initial_case_revision": revision})
    with pytest.raises(AuthorityError, match="INITIAL_CASE_RECOVERY"):
        e.tasks.prepare(e.business, spec)


def test_default_initial_revision_keeps_its_original_serialization():
    revision = InitialCaseRevision(
        revision_id="unchanged",
        criteria_set={"resource_id": "root", "revision_id": "v1", "digest": "a" * 64},
    )
    assert "recovery_observation_ids" not in revision.model_dump(mode="json")
