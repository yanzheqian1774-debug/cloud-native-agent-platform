"""D8 isolated PostgreSQL continuity; never calls any supplier."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.bounded_task_policy import (
    ConfigurationRevision,
    DevelopmentPlanningRevision,
    TaskAuthorizationRequest,
)
from agent_console.development_planning_recovery import RecoveryObservation, observe
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
from test_task_planning_successor import prepared, successor  # noqa: F401


@pytest.fixture
def development(successor):  # noqa: F811
    e = successor
    d7 = prepared(e, "d7")
    sign(e, d7)
    inv = claim(e, d7)
    e.budget.reserve("d7", inv, ProviderBudgetQuote(100, 500, 600))
    # Deliberately no terminal result or provider receipt, matching invocation21.
    observation = RecoveryObservation(
        root=e.task_spec.root,
        invocation_id=inv.invocation_id,
        evidence_digest="e" * 64,
        evidence_summary="Local claim and reservation; no durable terminal or receipt.",
        idempotency_key="observation21",
        provenance="LOCAL_ONLY",
        local_cleanup_confirmed=True,
    )
    row = observe(e.tasks, e.business, observation)
    e.observation, e.observation_spec, e.predecessor = row, observation, inv
    cfg = ConfigurationRevision(
        revision_id="config-55",
        predecessor_digest="a" * 64,
        configuration_digest="b" * 64,
        ledger_id=e.budget.ledger_id,
        model_target="exact",
    )
    spec = e.task_spec.model_copy(
        update={
            "idempotency_key": "development-task",
            "configuration": cfg,
            "recovery_invocation_id": inv.invocation_id,
            "development_revision": DevelopmentPlanningRevision(
                revision_id="dev100-usd50",
                recovery_observation_ids=(row["observation_id"],),
            ),
        }
    )
    e.dev_spec = TaskAuthorizationRequest.model_validate(spec.model_dump(mode="json"))
    task = e.tasks.prepare(e.business, e.dev_spec)
    e.tasks.approve(e.reviewer, task["request_id"], signature(task, "dev-sign"))
    e.dev_task = task
    yield e


def test_missing_terminal_followup_signed_exact_and_duplicate_safe(development):
    e = development
    new = prepared(e, "dev22")
    assert new["admission"]["cumulative_call_cap"] == 100
    assert new["admission"]["total_cost_cap_microusd"] == 50000000
    inv = claim(e, new)
    quote = ProviderBudgetQuote(100, 500, 600)
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        e.budget.reserve("dev22", inv, quote)
    sign(e, new)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(
            pool.map(lambda _: e.budget.reserve("dev22", inv, quote), range(2))
        )
    assert values[0] == values[1]
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 22
        )
        assert c.execute(
            "SELECT call_cap,total_cost_cap_microusd FROM "
            "draft_provider_budget.policies"
        ).fetchone() == {"call_cap": 8, "total_cost_cap_microusd": 10000000}
        assert (
            c.execute(
                "SELECT cumulative_call_cap FROM "
                "authorization_admin.task_planning_successors"
            ).fetchone()["cumulative_call_cap"]
            == 21
        )
        assert not c.execute(
            "SELECT 1 FROM workflow_planning.invocation_results WHERE invocation_id=%s",
            (e.predecessor.invocation_id,),
        ).fetchone()
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )
    assert prepared(e, "dev22")["invocation"]["target"] == new["invocation"]["target"]
    with pytest.raises(AuthorityError, match="FOLLOWUP_ALREADY_BOUND"):
        prepared(e, "another-auto-call")
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.invocation_results "
            "VALUES('s5-323-demo','isolated-real-demo',%s,%s)",
            (inv.invocation_id, Jsonb({"technical_status": "OUTCOME_UNKNOWN"})),
        )
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        e.budget.reserve("different-key", inv, quote)


def test_followup_keeps_planning_context_but_gets_independent_approval(development):
    e = development
    original_context = "ctx-d7"
    request = SimpleNamespace(
        idempotency_key="explicit-invalid-successor",
        predecessor_invocation_id="inv-d7",
        target=SimpleNamespace(problem=e.task_spec.root),
        model_dump=lambda **kw: {
            "idempotency_key": "explicit-invalid-successor",
            "predecessor_invocation_id": "inv-d7",
        },
    )
    record = {
        "request": request.model_dump(),
        "target": {
            "invocation_id": "inv-explicit-invalid-successor",
            "suggestion_context_id": original_context,
            "input_commitment": "explicit-invalid-successor",
            "problem": {"problem": e.task_spec.root.model_dump(mode="json")},
        },
    }
    new = e.planning.prepare_record(e.business, request, record)
    assert new["admission"]["context_id"] == "inv-explicit-invalid-successor"
    assert new["invocation"]["target"]["suggestion_context_id"] == original_context
    inv = claim(e, new)
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_REQUIRED"):
        e.budget.reserve(
            "explicit-invalid-successor", inv, ProviderBudgetQuote(100, 500, 600)
        )
    sign(e, new)
    value = e.budget.reserve(
        "explicit-invalid-successor", inv, ProviderBudgetQuote(100, 500, 600)
    )
    assert value == e.budget.reserve(
        "explicit-invalid-successor", inv, ProviderBudgetQuote(100, 500, 600)
    )
    again = e.planning.prepare_record(e.business, request, record)
    assert again["admission"]["context_id"] == new["admission"]["context_id"]
    with e.repo.connection_scope() as c:
        rows = c.execute(
            "SELECT context_id,record->>'source_context_id' source "
            "FROM authorization_admin.context_call_requests "
            "WHERE context_id IN (%s,%s) ORDER BY context_id",
            (original_context, "inv-explicit-invalid-successor"),
        ).fetchall()
    assert len(rows) == 2
    assert rows[1] == {
        "context_id": "inv-explicit-invalid-successor",
        "source": original_context,
    }


def add_history(e, count, cost):
    with e.repo.connection_scope() as c:
        for n in range(count):
            c.execute(
                "INSERT INTO draft_provider_budget.reservations VALUES"
                "('s5-323-demo','isolated-real-demo','planning-original',"
                "%s,%s,%s,100,500,%s,%s,now())",
                (f"extra-r-{n}", f"extra-op-{n}", f"extra-i-{n}", cost, "f" * 64),
            )


def test_development_amount_counts_all_unsettled_history(development):
    e = development
    add_history(e, 1, 19000000)
    new = prepared(e, "above10")
    sign(e, new)
    inv = claim(e, new)
    assert e.budget.reserve("above10", inv, ProviderBudgetQuote(100, 500, 600))
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT sum(worst_case_cost_microusd) n FROM "
                "draft_provider_budget.reservations"
            ).fetchone()["n"]
            > 10000000
        )


@pytest.mark.parametrize("calls,cost", [(1, 50000000), (79, 1)])
def test_development_fifty_dollar_and_hundred_call_limits(development, calls, cost):
    e = development
    new = prepared(e, "limited")
    sign(e, new)
    inv = claim(e, new)
    add_history(e, calls, cost)
    with pytest.raises(DraftAssistanceError, match="BUDGET_EXHAUSTED"):
        e.budget.reserve("limited", inv, ProviderBudgetQuote(100, 500, 600))


def test_observations_idempotent_scoped_and_never_adjudicate(development):
    e = development
    assert (
        observe(e.tasks, e.business, e.observation_spec)["observation_id"]
        == e.observation["observation_id"]
    )
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        observe(
            e.tasks,
            e.business,
            e.observation_spec.model_copy(update={"evidence_digest": "f" * 64}),
        )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        observe(e.tasks, e.reviewer, e.observation_spec)
    with pytest.raises(AuthorityError, match="TARGET_DENIED"):
        observe(
            e.tasks,
            e.business,
            e.observation_spec.model_copy(update={"invocation_id": "unrelated"}),
        )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM "
                "authorization_admin.planning_recovery_observations"
            ).fetchone()["n"]
            == 1
        )


def test_followup_observation_ledger_and_independent_signature(development):
    e = development
    for change, code in [
        ({"recovery_invocation_id": "inv-old"}, "OBSERVATION_REQUIRED"),
        (
            {
                "development_revision": e.dev_spec.development_revision.model_copy(
                    update={"recovery_observation_ids": ("absent",)}
                )
            },
            "OBSERVATION_REQUIRED",
        ),
    ]:
        with pytest.raises(AuthorityError, match=code):
            e.tasks.prepare(
                e.business,
                e.dev_spec.model_copy(update={**change, "idempotency_key": "invalid"}),
            )
    task = e.tasks.prepare(
        e.business, e.dev_spec.model_copy(update={"idempotency_key": "unsigned"})
    )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        e.tasks.approve(e.business, task["request_id"], signature(task, "self-sign"))


def test_old_task_serialization_does_not_acquire_development_revision():
    from agent_console.plan_suggestion_domain import ExactReference
    from pydantic import ValidationError

    ref = ExactReference(resource_id="r", revision_id="v", digest="a" * 64)
    spec = TaskAuthorizationRequest(
        purpose="SAME_CASE_DELIVERY",
        root=ref,
        source_snapshot=ref,
        determination_date="2026-11-03",
        idempotency_key="old",
        permissions=(
            {
                "owner": "BUSINESS_PROBLEM",
                "action": "READ",
                "exact_resource": "business-problem:r",
            },
        ),
    )
    assert "development_revision" not in spec.model_dump(mode="json")
    with pytest.raises(ValidationError):
        DevelopmentPlanningRevision(
            revision_id="bad",
            cumulative_call_cap=101,
            recovery_observation_ids=("obs",),
        )
    with pytest.raises(ValidationError):
        RecoveryObservation(
            root=ref,
            invocation_id="i",
            evidence_digest="a" * 64,
            evidence_summary="local",
            idempotency_key="k",
            provenance="SUPPLIER_VERIFIED",
        )


def test_development_expiry_revocation_and_configuration_drift(development):
    e = development
    new = prepared(e, "revocable")
    sign(e, new)
    inv = claim(e, new)
    quote = ProviderBudgetQuote(100, 500, 600)
    original = e.budget.task_actual_configuration
    e.budget.task_actual_configuration = {**original, "read_seconds": 30}
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        e.budget.reserve("revocable", inv, quote)
    e.budget.task_actual_configuration = original
    row = e.tasks.read(e.business, e.dev_task["request_id"])
    e.tasks.revoke(e.reviewer, e.dev_task["request_id"], row["decision"]["decision_id"])
    with pytest.raises(AuthorityError, match="TASK_AUTHORIZATION_REQUIRED"):
        e.budget.reserve("revocable", inv, quote)


def test_development_new_facts_are_immutable(development):
    import psycopg

    e = development
    prepared(e, "immutable")
    for table in ["planning_recovery_observations", "development_planning_followups"]:
        with (
            pytest.raises(psycopg.errors.RaiseException),
            e.repo.connection_scope() as c,
        ):
            c.execute(f"DELETE FROM authorization_admin.{table}")


def test_development_wrong_ledger_cannot_create_followup(development):
    e = development
    from agent_console.development_planning_recovery import validate_followup

    bad = e.dev_spec.model_copy(
        update={
            "configuration": e.dev_spec.configuration.model_copy(
                update={"ledger_id": "other-ledger"}
            )
        }
    )
    with (
        pytest.raises(AuthorityError, match="LEDGER_DENIED"),
        e.repo.connection_scope() as c,
    ):
        validate_followup(
            c, bad, ("s5-323-demo", "isolated-real-demo"), e.business.principal_id
        )


def test_new_schema_readiness_and_readonly_observation(development):
    from agent_console.development_planning_recovery import read_observation

    e = development
    e.repo.verify_existing_schema()
    row = read_observation(e.tasks, e.business, e.observation["observation_id"])
    assert row["record"]["local_cleanup_confirmed"] is True
    assert row["record"]["provenance"] == "LOCAL_ONLY"
    assert row["digest"] == e.observation["digest"]
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        read_observation(e.tasks, e.business, "absent")
