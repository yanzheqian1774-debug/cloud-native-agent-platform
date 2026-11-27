# ruff: noqa: F401,F811,E501 -- Disposable PG fixture and exact owner SQL.
"""Real ledger concurrency/accounting with a synthetic verified-provenance seam.

Original owner provenance is exercised separately by the full BOUND chain tests.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console import service_local_budget as local
from agent_console.draft_assistance import (
    DraftAssistanceError,
    ObservationState,
    ProviderBudgetQuote,
    ProviderObservation,
)
from test_draft_provider_budget_postgres import _invocation, _ledger
from test_plan_suggestion_v2 import repository


def document(o, **updates):
    return dict(
        schemaVersion="service-local-budget.v1",
        namespace=o.profile.scope.namespace,
        securityDomain=o.profile.scope.security_domain,
        ledgerId=o.ledger_id,
        subjectId="service:test",
        credentialId="credential:test",
        work=dict(resource_id="work:test", revision_id="revision:1", digest="a" * 64),
        sourceBindingDigest="b" * 64,
        servicePolicyDigest="c" * 64,
        allowedEventIds=["slot:1", "slot:2"],
        expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        callCap=20,
        totalCostCapMicrousd=1_000_000,
        authorizationEvidenceDigest="d" * 64,
        **updates,
    )


def select(o, path, value):
    import json

    path.write_text(json.dumps(value))
    path.chmod(0o600)
    local.configure(o, path)
    return o.service_local_budget.policy


@pytest.fixture
def accounting(repository, tmp_path, monkeypatch):
    o = _ledger(
        repository.pool.conninfo,
        "service-local-accounting",
        call_cap=200,
        cost_cap=20_000_000,
    )
    local.migrate(o)
    p = select(o, tmp_path / "scope.json", document(o))
    original = local.provenance

    def verified(c, o, inv, q):
        if not getattr(inv, "test_verified", False):
            return original(c, o, inv, q)
        p = o.service_local_budget.verify()
        return p, dict(
            kind=inv.test_kind,
            eventId="slot:1",
            scopeId=p.scope_id,
            invocationId=inv.invocation_id,
        )

    monkeypatch.setattr(local, "provenance", verified)
    try:
        yield NS(owner=o, policy=p, tmp=tmp_path)
    finally:
        o.close()


def identity(n, kind="PLANNING"):
    v = _invocation(n)
    v.test_verified = True
    v.test_kind = kind
    return v


def count(o):
    with o._connection() as c:
        return c.execute(
            "SELECT count(*) n FROM draft_provider_budget.service_reservations WHERE ledger_id=%s",
            (o.ledger_id,),
        ).fetchone()["n"]


Q = ProviderBudgetQuote(50, 100, 150)


def test_planning_native_share20_and_idempotence(accounting):
    o = accounting.owner
    for n in range(20):
        inv = identity(n, "NATIVE" if n % 2 else "PLANNING")
        r = o.reserve(str(n), inv, Q)
        assert o.reserve(str(n), inv, Q) == r
        with o.dispatch_guard(inv, Q):
            pass
    assert count(o) == 20
    with pytest.raises(DraftAssistanceError, match="SERVICE_LOCAL_BUDGET_EXHAUSTED"):
        o.reserve("21", identity(21), Q)


def test_unknown_holds_worst_cost_settlement_releases_cost_not_call(accounting):
    o = accounting.owner
    select(
        o,
        accounting.tmp / "small.json",
        accounting.policy.model_copy(update={"totalCostCapMicrousd": 200}).model_dump(
            mode="json"
        ),
    )
    r = o.reserve("1", identity(1), Q)
    o.record_usage(
        "unknown",
        r,
        ProviderObservation(
            "uncertain", ObservationState.UNKNOWN, reason_code="TRANSPORT_AMBIGUOUS"
        ),
    )
    with pytest.raises(DraftAssistanceError, match="SERVICE_LOCAL_BUDGET_EXHAUSTED"):
        o.reserve("2", identity(2, "NATIVE"), Q)
    assert count(o) == 1
    o.record_usage(
        "measured",
        r,
        ProviderObservation(
            "measured",
            ObservationState.FAILED,
            reason_code="PROVIDER_REFUSAL",
            input_tokens=10,
            output_tokens=10,
        ),
    )
    o.reserve("2", identity(2, "NATIVE"), Q)
    assert count(o) == 2


def test_concurrent_last_slot(accounting):
    o = accounting.owner
    for n in range(19):
        o.reserve(str(n), identity(n), Q)

    def attempt(n):
        try:
            o.reserve(str(n), identity(n, "NATIVE"), Q)
            return "accepted"
        except DraftAssistanceError as e:
            assert "SERVICE_LOCAL_BUDGET_EXHAUSTED" in str(e)
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [30, 31])) == ["accepted", "rejected"]
    assert count(o) == 20


def test_global_limit_preserved_and_human_history_unlabelled(accounting):
    o = accounting.owner
    selected = o.service_local_budget
    del o.service_local_budget
    for n in range(199):
        o.reserve(str(n), _invocation(n), Q)
    o.service_local_budget = selected
    o.reserve("local1", identity(500), Q)
    with pytest.raises(DraftAssistanceError, match=r"^PROVIDER_BUDGET_EXHAUSTED$"):
        o.reserve("local2", identity(501), Q)
    assert count(o) == 1


def test_scope_change_cannot_reset_counter_or_replay(accounting):
    o = accounting.owner
    o.reserve("first", identity(1), Q)
    changed = accounting.policy.model_copy(update={"callCap": 19})
    select(o, accounting.tmp / "changed.json", changed.model_dump(mode="json"))
    assert changed.scope_id == accounting.policy.scope_id
    for key, n in [("next", 2), ("first", 1)]:
        with pytest.raises(DraftAssistanceError, match="SCOPE_CONFLICT"):
            o.reserve(key, identity(n), Q)
    assert count(o) == 1


def test_missing_provenance_and_file_change_fail_closed(accounting):
    o = accounting.owner
    with pytest.raises(DraftAssistanceError, match="PLANNING_PROOF_REQUIRED"):
        o.reserve("fake", _invocation(1), Q)
    o.service_local_budget.path.write_text("{}")
    with pytest.raises(DraftAssistanceError, match="POLICY_CHANGED"):
        o.reserve("changed", identity(1), Q)
    assert count(o) == 0


def test_old_reservation_not_adopted_or_selection_dropped(accounting):
    o = accounting.owner
    selected = o.service_local_budget
    del o.service_local_budget
    o.reserve("old", _invocation(1), Q)
    o.service_local_budget = selected
    with pytest.raises(DraftAssistanceError, match="RESERVATION_PROOF_MISMATCH"):
        o.reserve("old", identity(1), Q)
    o.reserve("new", identity(2), Q)
    del o.service_local_budget
    with pytest.raises(DraftAssistanceError, match="SELECTION_REQUIRED"):
        o.reserve("new", _invocation(2), Q)
    assert count(o) == 1


def test_scope_attribution_immutable(accounting):
    import psycopg

    o = accounting.owner
    o.reserve("one", identity(1), Q)
    for table in ["service_scopes", "service_reservations"]:
        with pytest.raises(psycopg.Error), o._connection() as c:
            c.execute("DELETE FROM draft_provider_budget." + table)
    assert count(o) == 1


def test_service_starts_after_shared_baseline20_and_dollar1_exceeded(accounting):
    o = accounting.owner
    selected = o.service_local_budget
    del o.service_local_budget
    old_quote = ProviderBudgetQuote(20_000, 100, 20_100)
    for n in range(96):
        o.reserve(str(n), _invocation(n), old_quote)
    o.service_local_budget = selected
    o.reserve("service-first", identity(500), Q)
    assert count(o) == 1


def test_concurrent_last_cost_and_missing_schema(accounting):
    o = accounting.owner
    value = accounting.policy.model_copy(update={"totalCostCapMicrousd": 200})
    select(o, accounting.tmp / "cost-bound.json", value.model_dump(mode="json"))

    def attempt(n):
        try:
            o.reserve(str(n), identity(n, "NATIVE" if n % 2 else "PLANNING"), Q)
            return "accepted"
        except DraftAssistanceError as exc:
            assert "SERVICE_LOCAL_BUDGET_EXHAUSTED" in str(exc)
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [30, 31])) == ["accepted", "rejected"]
    assert count(o) == 1


@pytest.mark.parametrize("mutation", ["public", "symlink", "missing"])
def test_private_selection_rejects_unowned_shape(tmp_path, mutation):
    p = tmp_path / "scope.json"
    p.write_text("{}")
    p.chmod(0o644 if mutation == "public" else 0o600)
    if mutation == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(p)
        p = link
    elif mutation == "missing":
        p.unlink()
    with pytest.raises(DraftAssistanceError, match="PRIVATE_POLICY_REQUIRED"):
        local.Selection(p)


def test_private_selection_rejects_duplicate_policy_fields(tmp_path):
    p = tmp_path / "scope.json"
    p.write_text('{"callCap":20,"callCap":1}')
    p.chmod(0o600)
    with pytest.raises(DraftAssistanceError, match="DUPLICATE_POLICY_FIELD"):
        local.Selection(p)


@pytest.mark.parametrize("mutation", ["missing", "checksum", "adapter"])
@pytest.mark.parametrize("kind", ["PLANNING", "NATIVE"])
def test_selected_kernel_requires_0080_marker_without_cycle_preflight(
    repository, tmp_path, mutation, kind
):
    """Both real reserve/dispatch reject before provenance or writes; no CycleProcess."""
    o = _ledger(
        repository.pool.conninfo, "selected-marker", call_cap=200, cost_cap=20_000_000
    )
    try:
        local.migrate(o)
        select(o, tmp_path / "selected.json", document(o))
        inv = _invocation(1)
        if kind == "NATIVE":
            inv.service_budget_call = local.NativeBudgetCall(NS(), "skill:test")
        with o._connection() as c:
            assert c.execute(
                "SELECT to_regclass('draft_provider_budget.service_scopes') s,to_regclass('draft_provider_budget.service_reservations') r"
            ).fetchone() == dict(
                s="draft_provider_budget.service_scopes",
                r="draft_provider_budget.service_reservations",
            )
            if mutation == "missing":
                c.execute(
                    "DELETE FROM draft_provider_budget.schema_migrations WHERE version=80"
                )
            else:
                statement = (
                    "UPDATE draft_provider_budget.schema_migrations SET "
                    + mutation
                    + "=%s WHERE version=80"
                )
                c.execute(
                    statement,
                    ("0" * 64 if mutation == "checksum" else "wrong-adapter",),
                )
        with o._connection() as c:
            marker = c.execute(
                "SELECT * FROM draft_provider_budget.schema_migrations WHERE version=80"
            ).fetchone()
        for operation in ("reserve", "dispatch"):
            with pytest.raises(
                DraftAssistanceError, match="SERVICE_LOCAL_BUDGET_SCHEMA_REQUIRED"
            ):
                if operation == "reserve":
                    o.reserve("unavailable-marker", inv, Q)
                else:
                    with o.dispatch_guard(inv, Q):
                        pytest.fail(
                            "selected Native/Planning dispatched without exact schema marker"
                        )
        with o._connection() as c:
            assert (
                c.execute(
                    "SELECT * FROM draft_provider_budget.schema_migrations WHERE version=80"
                ).fetchone()
                == marker
            )
            for table in ("reservations", "service_scopes", "service_reservations"):
                assert (
                    c.execute(
                        "SELECT count(*) n FROM draft_provider_budget." + table
                    ).fetchone()["n"]
                    == 0
                )
    finally:
        o.close()
