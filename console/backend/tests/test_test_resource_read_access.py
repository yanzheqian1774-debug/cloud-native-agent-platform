# ruff: noqa: F401,F811 -- Reuse isolated PostgreSQL fixture graph.
from dataclasses import replace
from datetime import timedelta

import pytest
from agent_console.authority_contracts import AuthenticationSource, AuthorityError
from agent_console.test_resource_read_access import prepare
from agent_console.test_resource_read_policy import TestReadPolicy
from agent_console.workbench_prepared_resources import reference
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


@pytest.fixture
def read_policy(automation):
    a = automation
    g = a.automation.grants
    context = replace(
        a.subject, authentication_source=AuthenticationSource.BROWSER_SESSION
    )
    ref = a.refs["knowledge"]
    policy = TestReadPolicy(
        schemaVersion="test-resource-read-policy.v1",
        policyId="test",
        policyVersion="1",
        enabled=True,
        tenant=context.scope.tenant_id,
        securityDomain=context.scope.security_domain,
        subjects=(context.principal_id,),
        issuer=a.policy.issuer,
        credentialPath=a.policy.credentialPath,
        expiresAt=g.clock() + timedelta(hours=1),
        grantTTLSeconds=120,
        targets=[
            dict(
                owner="KNOWLEDGE",
                action="READ_RESOURCE",
                resource=reference("knowledge", ref.resource_id, ref.revision_id),
                digest=ref.digest,
                purpose="RESOURCE_PREPARATION",
            )
        ],
    )

    def run(key="original", candidate=None):
        with a.repository.pool.connection() as c, c.transaction():
            return prepare(candidate or policy, g, context, c, key)

    return a, g, context, policy, run


def test_real_grant_receipt_recovery_and_expiry_does_not_repeat_decision(read_policy):
    a, g, _context, _policy, run = read_policy
    first = run()
    assert first["items"][0]["state"] == "APPROVED"
    assert run() == first
    old_clock = g.clock
    g.clock = lambda: old_clock() + timedelta(minutes=3)
    assert run()["items"][0]["state"] == "EXPIRED"
    renewed = run("explicit-new-key")
    assert renewed["items"][0]["state"] == "APPROVED"
    assert renewed["items"][0]["requestId"] != first["items"][0]["requestId"]
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == 2
        )


def test_snapshot_mismatch_writes_no_grant(read_policy):
    a, _g, _context, policy, run = read_policy
    target = policy.targets[0].model_copy(update={"digest": "f" * 64})
    with pytest.raises(AuthorityError, match="SNAPSHOT_CHANGED"):
        run(candidate=policy.model_copy(update={"targets": (target,)}))
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == 0
        )


def test_explicit_revocation_blocks_original_and_new_key(read_policy):
    from agent_console.grant_administration_application import GrantRevocationCommand

    a, g, context, _policy, run = read_policy
    first = run()
    with a.repository.pool.connection() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE request_id=%s",
            (first["items"][0]["requestId"],),
        ).fetchone()["grant_id"]
    g.revoke_grant(
        context, GrantRevocationCommand(grant, "USER_REQUESTED", "surrender", True)
    )
    assert run()["items"][0]["state"] == "REVOKED"
    assert run("new-key")["items"][0]["state"] == "REVOKED"
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == 1
        )


def test_prior_rejection_is_not_overridden(read_policy):
    from agent_console.grant_administration_application import (
        GrantDecisionCommand,
        GrantRequestCommand,
    )

    a, g, context, policy, run = read_policy
    target = policy.targets[0]
    issuer, _ = policy.authenticate(g, context)
    request = g.submit_request(
        context, GrantRequestCommand(target.purpose, (target.grant,), "denied-read")
    )
    g.decide_request(
        issuer,
        GrantDecisionCommand(
            request.request_id,
            False,
            "CONTROLLED_REVIEW",
            "POLICY",
            "test-denial",
            None,
            None,
            "deny-read",
            expected_version=1,
        ),
    )
    assert run()["items"][0]["state"] == "DENIED"
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM authorization_admin.grants").fetchone()[
                "n"
            ]
            == 0
        )


def test_unregistered_purpose_stops_before_request(read_policy):
    a, _g, _context, policy, run = read_policy
    target = policy.targets[0].model_copy(update={"purpose": "UNREGISTERED_READ"})
    with pytest.raises(AuthorityError):
        run(candidate=policy.model_copy(update={"targets": (target,)}))
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == 0
        )


def test_http_protects_identity_csrf_and_key_only_payload(read_policy):
    from contextlib import nullcontext

    from agent_console.authority_configuration import StaticGrant
    from agent_console.authority_contracts import ExactGrant, GrantSource
    from agent_console.browser_session_application import (
        BrowserSessionPolicy,
        BrowserSessionService,
        StaticGenerationAuthenticator,
    )
    from agent_console.test_resource_read_access import operations
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient

    a, g, context, policy, _run = read_policy
    credential = replace(
        g.generation.credentials[0],
        authentication_source=GrantSource.BROWSER_BOOTSTRAP,
        grants=(
            StaticGrant(
                ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
                GrantSource.BROWSER_BOOTSTRAP,
            ),
        ),
    )
    generation = replace(
        g.generation, credentials=(credential, *g.generation.credentials[1:])
    )
    g._generation_provider = lambda: generation
    g.authorization._generation_provider = lambda: generation
    a.adapter.controller.protected_request = lambda: nullcontext(generation)
    session = BrowserSessionService(
        a.authority,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=1),
            timedelta(minutes=30),
            timedelta(hours=1),
            timedelta(minutes=5),
        ),
        csrf_signing_key=b"isolated-test-key-not-production-credential",
        recovery_epoch=1,
    )
    secret = session.create_session(session.issue_login_nonce(), "unit-subject-secret")
    browser, real_context = session.authenticate_session(secret.value)
    assert real_context.principal_id == context.principal_id
    csrf = session.issue_csrf(browser)
    app = create_workbench_bff(
        session,
        a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        grant_administration=g,
        operations=operations(policy, g),
    )
    path = "/api/workbench/v1/test-resource-access/prepare"
    headers = {"origin": "https://workbench.example", "x-csrf-token": csrf}
    with TestClient(app, base_url="https://workbench.example") as client:
        assert (
            client.post(
                path, json={"idempotencyKey": "http"}, headers=headers
            ).status_code
            == 401
        )
        client.cookies.set("__Host-workbench_session", secret.value)
        assert (
            client.post(
                path,
                json={"idempotencyKey": "http"},
                headers={"origin": headers["origin"]},
            ).status_code
            == 403
        )
        assert (
            client.post(
                path,
                json={"idempotencyKey": "http", "subject": "human:other"},
                headers=headers,
            ).status_code
            == 422
        )
        availability = client.get("/api/workbench/v1/test-resource-access/status")
        assert availability.status_code == 200, availability.text
        assert availability.json()["result"]["policyDigest"] == policy.digest
        assert "credentialPath" not in availability.text
        with a.repository.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_requests"
                ).fetchone()["n"]
                == 0
            )
        response = client.post(path, json={"idempotencyKey": "http"}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["result"]["items"][0]["state"] == "APPROVED"
        assert (
            client.post(path, json={"idempotencyKey": "http"}, headers=headers).json()[
                "result"
            ]
            == response.json()["result"]
        )
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == 1
        )
