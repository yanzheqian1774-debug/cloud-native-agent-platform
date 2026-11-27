# ruff: noqa: F401,F811,E501 -- Original owner fixtures and exact SQL.
"""Exact Service Plan/START -> real Native data tools, controlled decision port."""

from types import SimpleNamespace

import pytest
import test_fixed_work_cycle_host_postgres as cycle
import test_planning_candidates_source_change as original_case
from agent_console.delivery_evaluation import CHECKS
from agent_console.delivery_resource_bundle import source_document
from agent_console.native_data_adapters import capabilities
from agent_console.native_data_resource_bundle import resource_content
from agent_console.plan_suggestion_domain import FlexiblePlanSemantics
from agent_console.readonly_native_policy import (
    ReadonlyContinuationPolicyV2,
    ServiceNativeReadonlyWork,
)
from agent_console.resource_use_domain import canonical_digest
from test_fixed_chat_delivery_postgres import automation, repository, services

DESCRIPTOR = capabilities("synthetic-delivery-source.v1")[0]


@pytest.fixture
def case(repository, monkeypatch):
    import agent_console.sales_resource_bundle as bundle
    import prepared_execution_support as seed_support
    from test_planning_contracts import modern

    monkeypatch.setattr(original_case, "source_document", lambda *_: source_document())
    from agent_console.development_administrator import SCOPE
    from agent_console.execution_domain import ScopeIdentity

    # All fixture owners, resources, generation and commands are created in the
    # existing supported sandbox from the outset; runtime scope guard is intact.
    monkeypatch.setattr(
        original_case, "ScopeIdentity", lambda *_: ScopeIdentity(*SCOPE)
    )
    original_preparation = original_case.preparation
    base = original_preparation().model_copy(
        update={"namespace": SCOPE[0], "security_domain": SCOPE[1]}
    )
    target = base.semantics.target.model_copy(
        update={
            "criterion_revision_ids": tuple("criterion-native:" + c for c in CHECKS)
        }
    )
    monkeypatch.setattr(
        original_case,
        "preparation",
        lambda: base.model_copy(
            update={"semantics": base.semantics.model_copy(update={"target": target})}
        ),
    )
    original_criterion = original_case.SuccessCriterionRevision

    def criterion(*args):
        args = list(args)
        args[8] = "SYNTHETIC_DELIVERY"
        args[10] = {
            "check": args[2].split(":", 1)[1],
            "sourceContentDigest": canonical_digest(source_document()),
        }
        return original_criterion(*args)

    monkeypatch.setattr(original_case, "SuccessCriterionRevision", criterion)
    seed_preparation = seed_support.preparation

    def seeded_preparation():
        value = seed_preparation().model_copy(
            update={"namespace": SCOPE[0], "security_domain": SCOPE[1]}
        )
        return value.model_copy(
            update={
                "semantics": value.semantics.model_copy(
                    update={
                        "tasks": tuple(
                            t.model_copy(
                                update={
                                    "criterion_revision_ids": target.criterion_revision_ids
                                }
                            )
                            for t in value.semantics.tasks
                        )
                    }
                )
            }
        )

    monkeypatch.setattr(seed_support, "preparation", seeded_preparation)
    gen = cycle.case.__wrapped__(repository)
    e = next(gen)
    monkeypatch.setattr(
        bundle, "resource_content", lambda source: resource_content(source, DESCRIPTOR)
    )
    value = modern(DESCRIPTOR["operations"])
    value.update(
        target=e.p.semantics.target.model_dump(mode="json"),
        scenario="GENERAL_READ_ONLY",
    )
    value["requirements"][1]["kind"] = "KNOWLEDGE"
    value["business_rules"] = list(e.p.semantics.business_rules)
    value["boundaries"] = list(e.p.semantics.boundaries)
    for task in value["tasks"]:
        task["criterion_revision_ids"] = e.p.semantics.target.criterion_revision_ids
    e.p = e.p.model_copy(
        update={"semantics": FlexiblePlanSemantics.model_validate(value)}
    )
    try:
        yield e
    finally:
        next(gen, None)


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_service_native_original_tools_and_results(
    automation, monkeypatch, tmp_path, request
):
    import pending_pipeline_support
    from agent_console.bound_service_execution import BoundServiceExecutionBridge
    from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
    from test_fixed_chat_delivery_postgres import (
        test_bound_committed_event_is_read_in_original_chat_without_human_model_lease as original_chain,
    )

    a = automation
    original_prepare = a.automation.prepare_one

    def traced_prepare(*args, **kwargs):
        try:
            return original_prepare(*args, **kwargs)
        except Exception:
            print("EXACT_FIXTURE_RESOURCE", args[1:3], flush=True)
            raise

    monkeypatch.setattr(a.automation, "prepare_one", traced_prepare)
    original_continue = ServiceCycleContinuation.continue_once
    holder = {}

    def continued(owner, call, event):
        result = original_continue(owner, call, event)
        holder["bridge"] = BoundServiceExecutionBridge(owner.registry)
        return result

    monkeypatch.setattr(ServiceCycleContinuation, "continue_once", continued)

    def work(**kwargs):
        kwargs["case"] = "native_readonly"
        return ServiceNativeReadonlyWork(
            **kwargs,
            adapter=DESCRIPTOR,
            source=a.refs["knowledge"],
            skill=a.refs["skill"],
            employee=next(
                r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
            ),
            agent=a.refs["agent"],
            runtime=a.refs["runtime"],
        )

    monkeypatch.setattr(cycle, "ReadonlyWork", work)
    monkeypatch.setattr(
        cycle,
        "ReadonlyContinuationPolicy",
        lambda **kw: ReadonlyContinuationPolicyV2(
            schemaVersion="readonly-work-policy.v2", **kw
        ),
    )

    def drive(a, native, policy, _output, task_count, **kwargs):
        import time
        from datetime import UTC, datetime

        from agent_console import fixed_work_bound_source
        from agent_console.execution_preparation_postgres import PreparedExecutionStore
        from agent_console.prepared_execution_lineage import dispatch_grants
        from agent_console.prepared_native_composition import owner_authority_factory
        from agent_console.readonly_continuation_worker import ContinuationWork
        from native_data_pipeline_support import compose

        spans = {}

        def observe(obj, name, label):
            original = getattr(obj, name)

            def timed(*args, **kwargs):
                before = time.monotonic()
                try:
                    return original(*args, **kwargs)
                finally:
                    row = spans.setdefault(label, {"calls": 0, "seconds": 0.0})
                    row["calls"] += 1
                    row["seconds"] += time.monotonic() - before

            monkeypatch.setattr(obj, name, timed)

        bridge = holder["bridge"]
        observe(bridge.registry, "_check", "registry_current_check")
        observe(bridge.registry.authorization, "has_current_grants", "registry_grants")
        observe(fixed_work_bound_source, "require_bound_source", "bound_source")
        reader = a.automation.grants.authorization

        def authorize(c, command):
            bridge.authorize(c, a.subject, command)
            return all(
                reader.has_current_grants(
                    a.subject,
                    dispatch_grants(c, command),
                    now=datetime.now(UTC),
                    generation=1,
                    recovery_epoch=1,
                    connection=c,
                    configure_transaction=False,
                )
            )

        factory = owner_authority_factory(reader, a.gen, authorize)
        work = ContinuationWork(native, policy, factory, bound_service_execution=bridge)
        with native.pool.connection() as c:
            p, _ = PreparedExecutionStore(c).read(
                a.e.scope.namespace, a.e.scope.security_domain, kwargs["exact_run_id"]
            )
            command = native._dispatch_command(
                c.execute(
                    "SELECT payload FROM execution_authority.native_dispatch_commands WHERE namespace=%s AND security_domain=%s AND authorization_resource=%s ORDER BY queued_at,command_id LIMIT 1",
                    (
                        p.namespace,
                        p.security_domain,
                        "governed-execution:prepared:" + p.digest,
                    ),
                ).fetchone()["payload"]
            )
        assert command.timeout_seconds == 480
        assert len(work.dispatches()) == 1
        # Corrupt executor bytes cannot reuse the original exact START authority.
        from agent_console.authority_contracts import AuthorityError
        from agent_console.prepared_native_coordinator import PreparedNativeCoordinator

        bad = p.model_copy(
            update={
                "participants": (
                    p.participants[0].model_copy(update={"executor_digest": "0" * 64}),
                    *p.participants[1:],
                )
            }
        )
        with native.pool.connection() as c, c.transaction():
            _, authority = factory(c, command)
            before = c.execute(
                "SELECT count(*) AS n FROM execution_authority.native_dispatch_commands"
            ).fetchone()["n"]
            with pytest.raises(AuthorityError), c.transaction():
                PreparedNativeCoordinator(native)(
                    SimpleNamespace(
                        connection=c,
                        context=a.subject,
                        authority=authority,
                        policy_generation=1,
                        recovery_epoch=1,
                    ),
                    bad,
                )
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.native_dispatch_commands"
                ).fetchone()["n"]
                == before
            )
        e = SimpleNamespace(
            context=a.subject, service_bridge=bridge, factory_command=command
        )
        live = compose(e, work, native, p, tmp_path=tmp_path, monkeypatch=monkeypatch)
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        for _ in range(task_count):
            assert live.worker.run_once().state == "SUCCEEDED"
        assert live.worker.run_once().state == "IDLE"
        assert "build_report" in live.calls
        import json

        print(
            "SERVICE_NATIVE_SPANS",
            json.dumps(
                {
                    "spans": spans,
                    "controlledNativeDecisions": len(live.decisions),
                    "toolCalls": live.calls,
                    "runtime": live.runtime_results,
                    "note": "nested spans overlap; provider and Kubernetes controlled; no live model",
                },
                sort_keys=True,
            ),
        )
        assert work.evaluate_terminal() == {"evaluated": 1, "blocked": 0}
        assert work.evaluate_terminal() == {"evaluated": 0, "blocked": 0}
        with native.pool.connection() as c:
            _, progress = PreparedExecutionStore(c).read(
                p.namespace, p.security_domain, p.run_id
            )
            assert progress.state == "SUCCEEDED"
            rows = c.execute(
                "SELECT record FROM product_outcome.outcomes WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                (p.namespace, p.security_domain, p.run_id),
            ).fetchall()
            assert len(rows) == 1
            return {
                "artifacts": sum(len(t.output_artifact_ids) for t in progress.tasks),
                "outcome": rows[0]["record"],
            }

    monkeypatch.setattr(pending_pipeline_support, "drive", drive)
    original_chain(a, monkeypatch, tmp_path)
