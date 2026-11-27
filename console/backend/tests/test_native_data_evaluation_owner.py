# ruff: noqa: F401,F811 -- Reuse original isolated owner fixtures explicitly.
"""Real Native execution and evaluation owners; model transport remains controlled."""

from types import SimpleNamespace

import pytest
from agent_console.delivery_evaluation import CHECKS
from agent_console.execution_domain import ScopeIdentity
from agent_console.owned_business_resource_adapter import derive_work
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
from agent_console.workbench_prepared_execution import PreparedExecutionOwner, candidate
from native_data_owner_support import configure_scope, prepare_source, semantics
from native_data_pipeline_support import compose
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import (
    cleanup_consumer_resources,
)
from test_owned_business_consumer_chain import (
    test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
)
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [{"prepare_source": prepare_source, "configure_scope": configure_scope}],
        indirect=True,
    ),
]


def test_original_owner_measures_native_delivery_and_replays_without_new_model(
    owned_created, tmp_path, request, monkeypatch
):
    import owned_business_planning_support as support

    e = owned_created
    original_activate = support.activate_created

    def activate(value):
        identity = value.created["revision"]["business_problem_id"]
        criteria = [
            {
                "problemId": identity,
                "criterionType": "DETERMINISTIC_BOOLEAN",
                "measurement": {"expected": True},
                "requiredEvidenceKinds": [
                    "NATIVE_EXECUTION_ARTIFACT",
                    "PUBLISHED_SYNTHETIC_SOURCE",
                ],
                "evaluatorType": "SYNTHETIC_DELIVERY",
                "evaluatorVersion": "1",
                "applicability": {
                    "check": check,
                    "sourceContentDigest": value.business_result["inputSource"][
                        "sourceContentDigest"
                    ],
                },
                "idempotencyKey": "native-delivery-criterion:" + check,
            }
            for check in CHECKS
        ]
        return original_activate(value, criterion_payloads=criteria)

    monkeypatch.setattr(support, "activate_created", activate)
    monkeypatch.setattr(support, "document_semantics", semantics)
    observed = []

    def inspect(work, native, receipt, ready):
        with native.pool.connection() as c:
            p = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                receipt["preparationDigest"],
            )
        live = compose(e, work, native, p, tmp_path=tmp_path, monkeypatch=monkeypatch)
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        for _ in range(4):
            assert live.worker.run_once().state == "SUCCEEDED"
        before_calls = len(live.calls)
        owner = PreparedExecutionOwner()

        def evaluate():
            with native.pool.connection() as c:
                context, authority = work.authority_factory(
                    c, SimpleNamespace(principal_id=e.context.principal_id)
                )
                return owner(
                    AuthorizedOwnerCall(
                        "EVALUATE_PREPARED_EXECUTION",
                        context,
                        c,
                        {"idempotencyKey": "native-exact-evaluation"},
                        {"digest": p.digest},
                        {},
                        (),
                        authority,
                        1,
                        1,
                    )
                )

        first = evaluate()
        assert evaluate() == first
        assert len(live.calls) == before_calls
        evaluation = first["evaluation"]
        assert (
            evaluation["evaluator"] == "prepared-native-synthetic-delivery-evidence.v1"
        )
        assert len(evaluation["results"]) == 6
        assert {r["check"] for r in evaluation["results"]} == set(CHECKS)
        assert all(r["result"] == "SATISFIED" for r in evaluation["results"]), (
            evaluation
        )
        assert first["businessResolution"] != "RESOLVED"
        from agent_console.authority_contracts import AuthorityError
        from agent_console.grant_administration_application import (
            GrantRevocationCommand,
        )

        with native.pool.connection() as c:
            grants = c.execute(
                "SELECT grant_id FROM authorization_admin.grants "
                "WHERE owner='EVALUATION' AND action='EVALUATE'"
            ).fetchall()
        assert len(grants) == 1
        automation = e.consumer_preparation_context[0]
        automation.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grants[0]["grant_id"],
                "TEST_WITHDRAWAL",
                "withdraw-native-evaluation",
                surrender=True,
            ),
        )
        with pytest.raises(AuthorityError):
            evaluate()  # Even the same already-committed key needs current rights.
        with native.pool.connection() as c:
            assert (
                c.execute("SELECT count(*) n FROM product_outcome.outcomes").fetchone()[
                    "n"
                ]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM success_criteria_evaluation.jobs"
                ).fetchone()["n"]
                == 1
            )
        observed.append(first["evaluation"]["evaluationId"])

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
    assert len(observed) == 1
