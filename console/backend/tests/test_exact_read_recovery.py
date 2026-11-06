# ruff: noqa: F401,F811,E501 -- Existing isolated PostgreSQL fixture graph.
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError, AuthorityScope, ExactGrant
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
    GrantRevocationCommand,
)
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_api import install_planning_invocations
from agent_console.plan_suggestion_domain import PlanningError
from agent_console.plan_suggestion_invocation import PlanningInvocationTarget
from agent_console.plan_suggestion_service import PlanningSuggestionService
from agent_console.read_access_recovery import read_targets, recover_request
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from fastapi.testclient import TestClient
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import manager
from test_workbench_bff import SessionStub


@pytest.fixture
def recovery(manager):
    a, _ = manager
    g = a.automation.grants
    extra = tuple(
        RequestabilityRule(o, action, prefix, purpose)
        for o, action, prefix, purpose in [
            ("PLAN", "READ", "plan:prepared:", "WORKBENCH_PLANNING"),
            ("RESOURCE_USE", "READ", "resource-use:", "PROVIDER_USAGE_REVIEW"),
            (
                "EVIDENCE",
                "READ_MEASUREMENT",
                "evidence-reference:",
                "PROVIDER_USAGE_REVIEW",
            ),
        ]
    )
    gen = replace(g.generation, requestability=g.generation.requestability + extra)
    g._generation_provider = lambda: gen
    g.authorization._generation_provider = lambda: gen
    with a.repository.pool.connection() as c:
        c.execute(
            (
                Path(__file__).parents[1] / "migrations/0023_draft_assistance.sql"
            ).read_text()
        )
    inv = PostgresPlanningInvocations(a.repository)
    inv.migrate()
    root = a.e.p.semantics.target.problem.resource_id
    for key, status, kind in [
        ("unknown", "OUTCOME_UNKNOWN", None),
        ("invalid", "SUCCEEDED", "INVALID"),
        ("missing", None, None),
        ("valid", "SUCCEEDED", "VALID_SUGGESTION"),
    ]:
        inv.claim(
            a.e.scope,
            a.subject.principal_id,
            key,
            "b" * 64,
            {
                "target": {
                    "invocation_id": key,
                    "problem": {"problem": {"resource_id": root}},
                },
                "private": "raw-business-body",
            },
        )
        if status:
            inv.finish(
                a.e.scope,
                key,
                {"technical_status": status, "kind": kind, "private": "raw-result"},
            )
    member = ExactGrant("PLAN", "READ", "plan:prepared:" + root)
    return NS(a=a, g=g, inv=inv, root=root, member=member)


def submit(r, key="read-request-original"):
    return r.g.submit_request(
        r.a.subject, GrantRequestCommand("WORKBENCH_PLANNING", (r.member,), key)
    )


def decide(r, request, approve=True):
    issuer = r.a.automation.authenticate(r.a.subject)
    return r.g.decide_request(
        issuer,
        GrantDecisionCommand(
            request_id=request.request_id,
            expected_version=request.aggregate_version,
            approve=approve,
            reason_category="CONTROLLED_REVIEW",
            basis_type="TICKET",
            basis_reference="controlled-read-only",
            not_before=None,
            expires_at=r.g.clock() + timedelta(minutes=3) if approve else None,
            idempotency_key="decision-" + request.request_id,
        ),
    )


def test_owned_metadata_requires_actual_durable_failed_result_and_never_discloses_body(
    recovery,
):
    r = recovery
    for key in ["unknown", "invalid"]:
        assert r.inv.read_access_metadata(
            r.a.e.scope, r.a.subject.principal_id, key
        ) == {"requestKey": key, "invocationId": key, "problemId": r.root}
    assert (
        r.inv.read(r.a.e.scope, "missing", r.a.subject.principal_id)["result"][
            "technical_status"
        ]
        == "OUTCOME_UNKNOWN"
    )
    for key in ["missing", "valid", "absent"]:
        with pytest.raises(PlanningError):
            r.inv.read_access_metadata(r.a.e.scope, r.a.subject.principal_id, key)
    with pytest.raises(PlanningError):
        r.inv.read_access_metadata(r.a.e.scope, "another-actor", "unknown")
    with pytest.raises(PlanningError):
        r.inv.read_access_metadata(
            type(r.a.e.scope)("foreign", "foreign"), r.a.subject.principal_id, "unknown"
        )


def test_original_key_get_pending_approval_expiry_and_grant_history(recovery):
    r = recovery
    meta = r.inv.read_access_metadata(r.a.e.scope, r.a.subject.principal_id, "unknown")
    assert [
        x["classification"] for x in read_targets(r.g, r.a.subject, meta)["groups"]
    ] == ["FIRST_READ", "FIRST_READ"]
    req = submit(r)
    status = recover_request(r.g, r.a.subject, "read-request-original")
    assert (
        status["state"] == status["accessState"] == "PENDING"
        and status["decision"] is None
    )
    assert status["requestedGrants"] == [
        {"owner": "PLAN", "action": "READ", "resource": r.member.exact_resource}
    ]
    decision = decide(r, req)
    approved = recover_request(r.g, r.a.subject, "read-request-original")
    assert (
        approved["accessState"] == "EFFECTIVE"
        and approved["decision"]["reasonCategory"] == "CONTROLLED_REVIEW"
    )
    groups = read_targets(r.g, r.a.subject, meta)["groups"]
    assert (
        groups[0]["classification"] == "RENEWAL"
        and groups[1]["classification"] == "FIRST_READ"
    )
    old_clock = r.g.clock
    r.g.clock = lambda: old_clock() + timedelta(minutes=5)
    assert (
        recover_request(r.g, r.a.subject, "read-request-original")["accessState"]
        == "EXPIRED"
    )
    assert decision.grants
    with pytest.raises(AuthorityError):
        recover_request(
            r.g,
            replace(r.a.subject, scope=AuthorityScope("foreign", "foreign")),
            "read-request-original",
        )
    with pytest.raises(AuthorityError):
        recover_request(
            r.g, replace(r.a.subject, principal_id="another"), "read-request-original"
        )


def test_rejection_and_revocation_are_not_renewed_by_get(recovery):
    r = recovery
    rejected = submit(r, "rejected-read-request")
    decide(r, rejected, False)
    assert (
        recover_request(r.g, r.a.subject, "rejected-read-request")["accessState"]
        == "REJECTED"
    )
    approved = submit(r)
    decision = decide(r, approved)
    r.g.revoke_grant(
        r.a.subject,
        GrantRevocationCommand(
            decision.grants[0], "USER_REQUESTED", "revoke-read-only", True
        ),
    )
    assert (
        recover_request(r.g, r.a.subject, "read-request-original")["accessState"]
        == "REVOKED"
    )
    meta = r.inv.read_access_metadata(r.a.e.scope, r.a.subject.principal_id, "unknown")
    target = read_targets(r.g, r.a.subject, meta)["groups"][0]
    assert target["currentRead"] == "REVOKED" and target["requestable"] is False


def test_cross_epoch_ambiguous_submit_key_is_not_latest_wins(recovery):
    r = recovery
    first = submit(r)
    second = submit(r, "another-exact-key")
    with r.a.authority.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.idempotency_claims(tenant_id,security_domain,actor_id,command_type,idempotency_key,payload_digest,result_kind,result_id,result_record) SELECT tenant_id,security_domain,actor_id,'SUBMIT_GRANT_REQUEST:RECOVERY_EPOCH:2','read-request-original',payload_digest,result_kind,result_id,result_record FROM authorization_admin.idempotency_claims WHERE result_id=%s",
            (second.request_id,),
        )
    assert first.request_id != second.request_id
    with pytest.raises(AuthorityError, match="READ_REQUEST_AMBIGUOUS"):
        recover_request(r.g, r.a.subject, "read-request-original")


def test_bff_metadata_and_original_key_get_do_not_call_planning_read_or_dispatch(
    recovery,
):
    r = recovery
    s = SessionStub()
    s.context = r.a.subject
    app = create_workbench_bff(
        s,
        r.a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        grant_administration=r.g,
        route_installers=(
            install_planning_invocations(
                lambda _: NS(
                    invocations=r.inv,
                    application=NS(
                        scope=lambda p: type(r.a.e.scope)(
                            p.tenant_id, p.security_domain
                        )
                    ),
                )
            ),
        ),
    )
    with TestClient(app, base_url="https://workbench.example") as c:
        c.cookies.set("__Host-workbench_session", s.secret)
        response = c.get(
            "/api/workbench/v1/authorization/planning-read-targets/unknown"
        )
        assert response.status_code == 200, response.text
        assert (
            "raw-business-body" not in response.text
            and "raw-result" not in response.text
        )
        assert (
            c.get(
                "/api/workbench/v1/authorization/planning-read-targets/missing"
            ).status_code
            == 404
        )
        req = submit(r)
        for _ in range(2):
            response = c.get(
                "/api/workbench/v1/authorization/grant-request-keys/read-request-original"
            )
            assert response.status_code == 200, response.text
            assert response.json()["result"]["requestId"] == req.request_id
        with r.a.authority.connection_scope() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_requests WHERE purpose='WORKBENCH_PLANNING'"
                ).fetchone()["n"]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM authorization_admin.grants WHERE exact_resource=%s",
                    (r.member.exact_resource,),
                ).fetchone()["n"]
                == 0
            )
        s.context = replace(r.a.subject, principal_id="another")
        assert (
            c.get(
                "/api/workbench/v1/authorization/planning-read-targets/unknown"
            ).status_code
            == 404
        )
        assert (
            c.get(
                "/api/workbench/v1/authorization/grant-request-keys/read-request-original"
            ).status_code
            == 404
        )


def test_no_settlement_read_retains_plan_authority_and_never_calls_receipt_or_budget(
    recovery,
):
    r = recovery
    target = PlanningInvocationTarget(
        namespace=r.a.e.scope.namespace,
        security_domain=r.a.e.scope.security_domain,
        invocation_id="read-no-settle",
        suggestion_context_id="ctx-read",
        request_revision=1,
        problem=r.a.e.p.semantics.target,
        source_proposal=None,
        variant="FIRST_PROPOSAL",
        resource_snapshot=None,
        input_commitment="a" * 64,
        policy_version="read-test",
    )
    observed = []

    def forbidden(*args, **kwargs):
        raise AssertionError("READ must not enter receipt or budget reconciliation")

    app = NS(
        scope=lambda p: r.a.e.scope,
        authority=NS(require=lambda *args: observed.append(args)),
        repository=r.a.repository,
        validate_target=lambda *args, **kwargs: observed.append("target-validated"),
    )
    service = NS(
        application=app,
        invocations=NS(
            read=lambda *args: {
                "invocation": {"target": target.model_dump(mode="json")},
                "result": {"technical_status": "OUTCOME_UNKNOWN"},
            },
            receipt=forbidden,
        ),
        model_use_owner=NS(status=lambda *args: "PRESERVED"),
        budget=NS(pricing=forbidden),
    )
    result = PlanningSuggestionService.read(
        service, r.a.e.principal, "read-no-settle", settle_receipt=False
    )
    assert (
        result["result"]["technical_status"] == "OUTCOME_UNKNOWN"
        and "target-validated" in observed
    )
    assert observed[0][1:] == ("PLAN", "READ", "plan:prepared:" + r.root)
    app.authority = NS(
        require=lambda *args: (_ for _ in ()).throw(AuthorityError("DENIED"))
    )
    with pytest.raises(AuthorityError, match="DENIED"):
        PlanningSuggestionService.read(
            service, r.a.e.principal, "read-no-settle", settle_receipt=False
        )
