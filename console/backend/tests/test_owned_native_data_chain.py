# ruff: noqa: F401,F811 -- Explicit original isolated owner fixtures.
"""Real conversation/planning owners; publication/provider controlled."""

import pytest
from agent_console.owned_business_resource_adapter import derive_work, readonly_work
from agent_console.plan_suggestion_domain import ExactReference
from native_data_owner_support import configure_scope, prepare_source, semantics
from owned_business_planning_support import (
    activate_created,
    governed_planning_service,
    planning_application,
)
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode=None,
                prepare_source=prepare_source,
                configure_scope=configure_scope,
            )
        ],
        indirect=True,
    ),
]


def test_exact_delivery_owned_admission_and_original_planning(owned_created):
    e = activate_created(owned_created)
    _, _, current = planning_application(e)
    with e.repo.connection_scope() as c:
        work = derive_work(
            e.business_owner,
            c,
            e.context,
            ExactReference.model_validate(current["target"]["problem"]),
        )
        assert readonly_work(work).case == "native_readonly"
        assert (
            readonly_work(work).adapter.sourceSchema == "synthetic-delivery-source.v1"
        )
    with governed_planning_service(e, semantics(e, current["target"])) as (
        service,
        principal,
        request,
        provider,
    ):
        result = service.begin(principal, request)
        assert result["result"]["technical_status"] == "SUCCEEDED", result
        assert result["result"]["kind"] == "VALID_SUGGESTION", result
        assert service.begin(principal, request)["result"] == result["result"]
        assert provider.calls == 1
    assert len(e.calls) == e.business_model_call_count


def test_exact_delivery_original_preparation_start_and_native_results(
    owned_created, tmp_path, request, monkeypatch
):
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.workbench_prepared_execution import candidate
    from native_data_pipeline_support import compose
    from test_owned_business_consumer_chain import (
        test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
    )

    e = owned_created
    from agent_console import automatic_skill_testing

    original_verify = automatic_skill_testing.verify_skill

    def diagnostic_verify(*args, **kwargs):
        try:
            return original_verify(*args, **kwargs)
        except Exception:
            import traceback

            traceback.print_exc()
            raise

    monkeypatch.setattr(automatic_skill_testing, "verify_skill", diagnostic_verify)
    seen = []
    monkeypatch.setattr("owned_business_planning_support.document_semantics", semantics)

    def inspect(work, native, receipt, ready):
        with native.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                receipt["preparationDigest"],
            )
        from dataclasses import replace

        from agent_console.authority_contracts import AuthorityError
        from agent_console.native_data_adapters import ADAPTERS
        from agent_console.native_data_skill import NativeDataSkillExecutor
        from agent_console.owned_business_resource_adapter import require_preparation

        with native.pool.connection() as c:
            owned = derive_work(
                e.business_owner, c, e.context, p.semantics.target.problem
            )
            require_preparation(owned, p)
            with pytest.raises(AuthorityError):
                require_preparation(
                    owned,
                    p.model_copy(
                        update={
                            "source_snapshot": p.source_snapshot.model_copy(
                                update={"digest": "a" * 64}
                            )
                        }
                    ),
                )
            other = NativeDataSkillExecutor(ADAPTERS[0]).revision
            changed = p.participants[0].model_copy(
                update={
                    "executor_id": other.executor_id,
                    "executor_revision": other.executor_revision,
                    "executor_digest": other.configuration_digest,
                }
            )
            with pytest.raises(AuthorityError, match="NATIVE_ADAPTER_MISMATCH"):
                require_preparation(
                    owned,
                    p.model_copy(
                        update={"participants": (changed, *p.participants[1:])}
                    ),
                )
            with pytest.raises(AuthorityError):
                e.business_owner.work(
                    c,
                    replace(e.context, principal_id="human:other"),
                    p.semantics.target.problem,
                )
        live = compose(e, work, native, p, tmp_path=tmp_path, monkeypatch=monkeypatch)
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        for _ in range(4):
            result = live.worker.run_once()
            assert result.state == "SUCCEEDED", result
        assert "inspect_rows" in live.calls
        assert "build_report" in live.calls
        assert len(live.calls) >= 4
        assert live.worker.run_once().state == "IDLE"
        from types import SimpleNamespace

        from agent_console.workbench_business_problem import OwnerPrincipal
        from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
        from agent_console.workbench_prepared_execution import PreparedExecutionOwner

        with native.pool.connection() as c:
            context, authority = work.authority_factory(
                c, SimpleNamespace(principal_id=e.context.principal_id)
            )
            authority.require(
                OwnerPrincipal(context.principal_id, p.namespace, p.security_domain),
                "EXECUTION",
                "READ",
                "governed-execution:prepared:" + p.digest,
            )
            read = PreparedExecutionOwner()(
                AuthorizedOwnerCall(
                    "READ_PREPARED_EXECUTION",
                    context,
                    c,
                    {},
                    {"digest": p.digest},
                    {},
                    (),
                    authority,
                    1,
                    1,
                )
            )
            assert read["workflowRunId"] == p.run_id
            assert read["progress"]["state"] == "SUCCEEDED"
            assert len(read["artifacts"]) == 4
            assert read["technicalSuccessNotBusinessSuccess"] is True
            assert all(a["contentAccess"] == "AUTHORIZED" for a in read["artifacts"])
            assert any("build_report" in a["content"] for a in read["artifacts"])
            import json

            reports = [
                json.loads(a["content"])
                for a in read["artifacts"]
                if json.loads(a["content"]).get("operation") == "RENDER_REPORT"
            ]
            assert len(reports) == 1
            result = reports[0]
            assert result["nativeReportVerification"][
                "sourceSnapshot"
            ] == p.source_snapshot.model_dump(mode="json")
            assert (
                result["nativeReportVerification"]["reportDigest"]
                == result["nativeReport"]["reportDigest"]
            )
            assert result["nativeReportVerification"]["businessAcceptance"] is False
        seen.append(p.digest)

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
    assert len(seen) == 1
