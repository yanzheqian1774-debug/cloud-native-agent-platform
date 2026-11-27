# ruff: noqa: F401,F811,E501 -- Original isolated full-owner fixtures.
"""Original BOUND Planning + actual Native journal/Attempt share one real ledger.

Native decisions/provider are controlled test ports. Budget provenance, owner
checks, PostgreSQL reservations and both limits are actual implementations.
"""

from types import SimpleNamespace as NS

import pytest
from agent_console import service_local_budget as local
from agent_console.bound_service_execution import BoundServiceExecutionBridge
from agent_console.draft_assistance import DraftAssistanceError, ProviderBudgetQuote
from agent_console.fixed_work_bound_policy import BoundServicePlanningPolicy
from agent_console.fixed_work_service_runtime import ServicePlanningRuntime
from agent_console.native_loop_journal import NativeLoopJournal
from agent_console.plan_suggestion_runtime import PlanningBudget
from test_native_service_readonly_postgres import automation, case, repository, services
from test_native_service_readonly_postgres import (
    test_service_native_original_tools_and_results as original_chain,
)
from test_service_local_budget import document, select


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_bound_planning_native_same_scope_actual_owner_provenance(
    automation, monkeypatch, tmp_path, request, repository
):
    holder = {}
    init = ServicePlanningRuntime.__init__
    authorize = BoundServiceExecutionBridge.authorize
    claim = NativeLoopJournal.claim

    def install(self, *args, **kwargs):
        init(self, *args, **kwargs)
        if not self.enabled:
            return
        p = self.registry._policy()
        if not isinstance(p, BoundServicePlanningPolicy):
            return
        o = self.service.budget.owner
        from agent_console.provider_budget_allowance import prepare as allowance
        from test_provider_budget_allowance import document as allowance_doc
        from test_provider_budget_extension import enable

        saved = allowance(o, allowance_doc(o, calls=100, cost=10_000_000))
        o.allowance_id = saved["allowanceId"]
        o.extension_test_base = saved
        enable(o)
        value = document(o)
        value.update(
            subjectId=p.subjectId,
            credentialId=p.credentialId,
            work=p.work.model_dump(mode="json"),
            sourceBindingDigest=p.sourceBindingDigest,
            servicePolicyDigest=p.digest,
            allowedEventIds=list(p.allowedEventIds),
            expiresAt=p.expiresAt.isoformat(),
        )
        select(o, tmp_path / "exact-local-policy.json", value)
        local.migrate(o)
        holder.update(owner=o, scope=o.service_local_budget.policy)

    def observe(self, c, context, command):
        result = authorize(self, c, context, command)
        holder.update(bridge=self, command=command)
        return result

    def reserve_native_inner(self, key, commitment):
        result = claim(self, key, commitment)
        if result is not None or not key.endswith(":MODEL"):
            return result
        o = holder["owner"]
        command = holder["command"]
        o.service_budget_native_bridge = holder["bridge"]
        inv = NS(
            scope=o.profile.scope,
            invocation_id=key,
            profile_revision_id=o.profile.profile_revision_id,
            service_budget_call=local.NativeBudgetCall(command, self.identity[2]),
        )
        quote = ProviderBudgetQuote(
            1,
            o.profile.maximum_output_tokens,
            o._cost(1, o.input_price)
            + o._cost(o.profile.maximum_output_tokens, o.output_price),
        )
        budget = PlanningBudget(o)
        if not holder.get("schema_marker_tested"):
            # Actual Native owner path, independent of CycleProcess.check. Both
            # tables stay present while its version marker is absent/corrupt.
            for mutation in ("missing", "checksum", "adapter"):
                with o._connection() as c:
                    marker = c.execute(
                        "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations WHERE version=80"
                    ).fetchone()
                    before = [
                        c.execute(
                            "SELECT count(*) n FROM draft_provider_budget." + table
                        ).fetchone()["n"]
                        for table in (
                            "reservations",
                            "service_scopes",
                            "service_reservations",
                        )
                    ]
                    if mutation == "missing":
                        c.execute(
                            "DELETE FROM draft_provider_budget.schema_migrations WHERE version=80"
                        )
                    else:
                        c.execute(
                            "UPDATE draft_provider_budget.schema_migrations SET "
                            + mutation
                            + "=%s WHERE version=80",
                            ("0" * 64 if mutation == "checksum" else "wrong-adapter",),
                        )
                try:
                    with pytest.raises(
                        DraftAssistanceError,
                        match="SERVICE_LOCAL_BUDGET_SCHEMA_REQUIRED",
                    ):
                        budget.reserve("native:" + key, inv, quote)
                    with (
                        pytest.raises(
                            DraftAssistanceError,
                            match="SERVICE_LOCAL_BUDGET_SCHEMA_REQUIRED",
                        ),
                        budget.dispatch_guard(inv, quote),
                    ):
                        pytest.fail("Native selected path skipped migration marker")
                    with o._connection() as c:
                        assert before == [
                            c.execute(
                                "SELECT count(*) n FROM draft_provider_budget." + table
                            ).fetchone()["n"]
                            for table in (
                                "reservations",
                                "service_scopes",
                                "service_reservations",
                            )
                        ]
                finally:
                    with o._connection() as c:
                        c.execute(
                            "INSERT INTO draft_provider_budget.schema_migrations VALUES(80,%s,%s) ON CONFLICT(version) DO UPDATE SET checksum=excluded.checksum,adapter=excluded.adapter",
                            (marker["checksum"], marker["adapter"]),
                        )
            holder["schema_marker_tested"] = True
        one = budget.reserve("native:" + key, inv, quote)
        assert budget.reserve("native:" + key, inv, quote) == one
        with budget.dispatch_guard(inv, quote):
            pass
        # Caller-provided wrong identity/skill/key cannot use this scope.
        bad = NS(**vars(inv))
        bad.service_budget_call = local.NativeBudgetCall(command, "missing-skill")
        with pytest.raises(DraftAssistanceError, match="NATIVE_ATTEMPT_MISMATCH"):
            budget.reserve("native:" + key, bad, quote)
        return result

    monkeypatch.setattr(ServicePlanningRuntime, "__init__", install)
    monkeypatch.setattr(BoundServiceExecutionBridge, "authorize", observe)
    monkeypatch.setattr(NativeLoopJournal, "claim", reserve_native_inner)
    original_chain(automation, monkeypatch, tmp_path, request)
    o = holder["owner"]
    with repository.pool.connection() as c:
        rows = c.execute(
            "SELECT provenance->>'kind' kind,count(*) n FROM draft_provider_budget.service_reservations WHERE ledger_id=%s GROUP BY 1",
            (o.ledger_id,),
        ).fetchall()
        counts = {r["kind"]: r["n"] for r in rows}
        assert counts["PLANNING"] == 1
        assert 1 <= counts["NATIVE"] <= 19
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.service_scopes WHERE ledger_id=%s",
                (o.ledger_id,),
            ).fetchone()["n"]
            == 1
        )


def test_original_existing_planning_pricing_case_on_disposable_db(
    repository, tmp_path, monkeypatch
):
    from psycopg.conninfo import conninfo_to_dict
    from test_fixed_work_existing_planning_postgres import (
        test_existing_runtime_checks_original_pricing_without_any_new_rows as original,
    )

    values = conninfo_to_dict(repository.pool.conninfo)
    assert values["host"] == "127.0.0.1"
    assert values["port"] != "64330"
    assert values["dbname"].startswith("planning323_")
    original(repository.pool.conninfo, tmp_path, monkeypatch)
