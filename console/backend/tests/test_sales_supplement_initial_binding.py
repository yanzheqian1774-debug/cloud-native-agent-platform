# ruff: noqa: F401,F811 -- Reuse isolated PostgreSQL fixtures; never actual acceptance.
"""Exercise BFF, criterion owner and post-owner initial-case wrapper together."""

from types import SimpleNamespace

from agent_console.initial_case_creation import InitialCaseCreation, bind_created_object
from agent_console.sales_gross_profit_evaluation import CHECKS, criterion_candidate
from agent_console.sales_gross_profit_integration import SOURCE_DIGEST
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_business_problem import business_problem_operations
from fastapi.testclient import TestClient
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_sales_supplement_owners import (
    ExactFixtureAuthority,
    ExactFixtureBffAuthorizer,
    snapshot,
)
from test_workbench_bff import SessionStub


def fixture_client(a, *, enabled, acl):
    problem_id = a.e.p.semantics.target.problem.resource_id
    binding = InitialCaseCreation(
        tenant_id=a.subject.scope.tenant_id,
        security_domain=a.subject.scope.security_domain,
        subject_id=a.subject.principal_id,
        root_id=problem_id,
        title="isolated original sales",
        description_digest="a" * 64,
        source_content_digest=SOURCE_DIGEST,
    )
    application = SimpleNamespace(
        uow=SimpleNamespace(problems=a.e.app.problems, control=object()),
        workflows=object(),
        employees=object(),
        instances=object(),
    )
    sessions = SessionStub(a.subject.principal_id)
    sessions.context = a.subject
    bff = create_workbench_bff(
        sessions,
        ExactFixtureBffAuthorizer(a, acl),
        WorkbenchBffPolicy("review.test", "https://review.test"),
        operations=business_problem_operations(
            application,
            task_binding=bind_created_object(
                lambda *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("Exact root must not fall back to legacy adoption")
                ),
                (binding,),
                sales_supplement_enabled=enabled,
            ),
        ),
    )
    client = TestClient(bff, base_url="https://review.test")
    client.cookies.set("__Host-workbench_session", sessions.secret)
    return client


def claim(a, key):
    with a.repository.pool.connection() as c:
        return c.execute(
            "SELECT payload_digest,result_id,result_record FROM "
            "business_problem_authority.idempotency_claims WHERE namespace=%s "
            "AND security_domain=%s AND actor_id=%s AND command_type=%s "
            "AND idempotency_key=%s",
            (
                a.subject.scope.tenant_id,
                a.subject.scope.security_domain,
                a.subject.principal_id,
                "CREATE_CRITERION_REVISION",
                key,
            ),
        ).fetchall()


def body(check, problem_id):
    spec = criterion_candidate(check)
    return {
        "problemId": problem_id,
        "criterionType": spec["criterion_type"],
        "measurement": spec["measurement"],
        "requiredEvidenceKinds": spec["required_evidence_kinds"],
        "evaluatorType": spec["evaluator_type"],
        "evaluatorVersion": spec["evaluator_version"],
        "applicability": spec["applicability"],
        "idempotencyKey": "isolated-original-seven:" + check,
    }


def test_original_case_seven_criteria_closed_rollback_enabled_current_acl_and_recovery(
    automation,
):
    a = automation
    problem_id = a.e.p.semantics.target.problem.resource_id
    acl = ExactFixtureAuthority(
        a.subject.principal_id,
        [
            ("SUCCESS_CRITERION", "CREATE", "success-criterion:collection"),
            ("SUCCESS_CRITERION", "READ", "success-criterion:collection"),
            ("BUSINESS_PROBLEM", "READ", "business-problem:" + problem_id),
        ],
    )
    headers = {"Origin": "https://review.test", "X-CSRF-Token": "csrf-token"}
    before = snapshot(a)
    with fixture_client(a, enabled=False, acl=acl) as client:
        for check in CHECKS:
            payload = body(check, problem_id)
            response = client.post(
                "/api/workbench/v1/success-criteria", json=payload, headers=headers
            )
            assert response.status_code == 404, response.text
            assert response.json()["reasonCode"] == "INITIAL_CASE_CRITERION_DENIED"
            assert claim(a, payload["idempotencyKey"]) == []
    assert snapshot(a) == before

    saved = []
    with fixture_client(a, enabled=True, acl=acl) as client:
        for check in CHECKS:
            payload = body(check, problem_id)
            response = client.post(
                "/api/workbench/v1/success-criteria", json=payload, headers=headers
            )
            assert response.status_code == 201, response.text
            revision = response.json()["result"]["revision"]
            assert all(
                revision[key] == value
                for key, value in criterion_candidate(check).items()
            )
            records = claim(a, payload["idempotencyKey"])
            assert len(records) == 1
            assert records[0]["result_id"] == revision["revision_id"]
            assert records[0]["result_record"] == {
                "revision_id": revision["revision_id"]
            }
            saved.append(revision)
        permission = ("BUSINESS_PROBLEM", "READ", "business-problem:" + problem_id)
        acl.allowed.remove(permission)
        denied = body("totals", problem_id)
        denied["idempotencyKey"] = "isolated-no-current-problem-read"
        assert (
            client.post(
                "/api/workbench/v1/success-criteria", json=denied, headers=headers
            ).status_code
            == 404
        )
        assert claim(a, denied["idempotencyKey"]) == []
        acl.allowed.add(permission)
        malformed = body("reconciliations", problem_id)
        malformed["measurement"] = {"expected": False}
        malformed["idempotencyKey"] = "isolated-mutated-measurement"
        response = client.post(
            "/api/workbench/v1/success-criteria", json=malformed, headers=headers
        )
        assert response.status_code == 404
        assert response.json()["reasonCode"] == "INITIAL_CASE_CRITERION_DENIED"
        assert claim(a, malformed["idempotencyKey"]) == []
    assert len({r["revision_id"] for r in saved}) == 7
    assert snapshot(a) == before  # No model, Plan, Run or grant writes.
    with fixture_client(a, enabled=False, acl=acl) as client:
        for revision in saved:
            permission = (
                "SUCCESS_CRITERION",
                "READ",
                "success-criterion:revision:" + revision["revision_id"],
            )
            acl.allowed.add(permission)
            response = client.get(
                "/api/workbench/v1/success-criteria/revisions/"
                + revision["revision_id"]
            )
            assert response.status_code == 200, response.text
            assert response.json()["result"]["revision"] == revision
