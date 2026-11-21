"""Actual original approval transaction; disposable accounts database only."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_readmission_plan import ReadmissionPlan
from agent_console.task_delegation import digest
from test_context_call_admission import env as env
from test_context_call_admission import spec
from test_local_accounts_postgres import setup as setup

pytestmark = pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="isolated PostgreSQL required",
)


def plan_for(e, old, command):
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
    from agent_console.provider_budget_allowance import prepare
    from test_context_call_admission import ROOT

    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=ROOT / "0024_draft_provider_budget.sql",
        profile=e.draft.profile,
        ledger_id=e.limits["ledger_id"],
        call_cap=e.limits["calls"],
        total_cost_cap_microusd=e.limits["cost_microusd"],
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    deadline = datetime.now(UTC) + timedelta(hours=2)
    try:
        budget.migrate_and_configure()
        with e.repo.connection_scope() as c:
            root = c.execute(
                "SELECT record FROM draft_provider_budget.policies"
            ).fetchone()["record"]
        prepare(
            budget,
            dict(
                schemaVersion="provider-budget-allowance.v1",
                allowanceId="original-bound",
                ledgerId=e.limits["ledger_id"],
                namespace=e.business.scope.tenant_id,
                securityDomain=e.business.scope.security_domain,
                rootPolicyDigest=digest(root),
                authorizationDigest="d" * 64,
                callCap=100,
                totalCostCapMicrousd=10000000,
                notBefore=datetime.now(UTC) - timedelta(seconds=1),
                expiresAt=deadline,
                externalWrites=False,
            ),
        )
    finally:
        budget.close()
    row = e.admission.read(e.business, e.invocation.context_id)["request"]
    return ReadmissionPlan.model_validate(
        dict(
            schema_version="context-readmission.v1",
            issuer_id=e.reviewer.principal_id,
            generation=1,
            recovery_epoch=1,
            authorization_evidence_digest="c" * 64,
            global_expires_at=deadline,
            entries=[
                dict(
                    context_id=row["context_id"],
                    subject_id=row["subject_id"],
                    tenant_id=row["tenant_id"],
                    security_domain=row["security_domain"],
                    request_digest=row["digest"],
                    configuration=e.limits,
                    allowance_id="original-bound",
                    allowance_authorization_digest="d" * 64,
                    prior_admission_id=old["admission_id"],
                    prior_record_digest=digest(old["record"]),
                    idempotency_key=command.idempotency_key,
                    expires_at=command.expires_at,
                    lease_mode="KEEP_EXPIRY",
                )
            ],
        )
    )


def test_explicit_renewal_keeps_original_request_budget_and_rechecks_revoke(env):
    e = env
    e.admission.prepare(e.business, e.invocation)
    initial = spec(e)
    old = e.admission.approve(e.reviewer, e.invocation.context_id, initial)
    command = initial.model_copy(update={"idempotency_key": "renewal"})
    plan = plan_for(e, old, command)
    # A renewal must not run the old planning first-approval allowance hook.
    e.admission.before_approve = lambda *a: pytest.fail("renewal created allowance")
    original = e.admission.read(e.business, e.invocation.context_id)["request"]
    result = e.admission.approve(
        e.reviewer, e.invocation.context_id, command, readmission_plan=plan
    )
    assert result["ordinal"] == 2
    assert result["record"]["predecessor_id"] == old["admission_id"]
    assert result["expires_at"] == old["expires_at"]
    assert result["record"]["request"] == old["record"]["request"]
    assert e.admission.read(e.business, e.invocation.context_id)["request"] == original
    assert (
        e.admission.approve(
            e.reviewer, e.invocation.context_id, command, readmission_plan=plan
        )
        == result
    )
    e.admission.revoke(e.reviewer, e.invocation.context_id, result["admission_id"])
    with pytest.raises(AuthorityError, match="PRIOR_INVALID"):
        e.admission.approve(
            e.reviewer, e.invocation.context_id, command, readmission_plan=plan
        )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.context_call_decisions"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


def test_original_context_can_receive_current_generation_decision(env, setup):
    from dataclasses import replace

    from agent_console.authority_contracts import GrantSource
    from agent_console.browser_session_application import (
        BrowserSessionService,
        StaticGenerationAuthenticator,
    )
    from agent_console.context_call_admission import ContextCallAdmission
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
        GrantAdministrationService,
    )
    from agent_console.task_delegation import TaskDelegationService
    from test_local_accounts_postgres import login

    e = env
    repo, generation, sessions, _ = setup
    e.admission.prepare(e.business, e.invocation)
    initial = spec(e)
    old = e.admission.approve(e.reviewer, e.invocation.context_id, initial)
    command = initial.model_copy(update={"idempotency_key": "generation-successor"})
    plan = plan_for(e, old, command).model_copy(update={"generation": 2})
    successor = replace(
        generation, generation=2, policy_version="changed", digest="b" * 64
    )
    repo.activate_generation(
        2,
        successor.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=datetime.now(UTC),
    )
    new_sessions = BrowserSessionService(
        repo,
        StaticGenerationAuthenticator(successor, source=GrantSource.BROWSER_BOOTSTRAP),
        sessions.policy,
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    _, reviewer = new_sessions.authenticate_session(
        login(new_sessions, "reviewer324").value
    )
    _, business = new_sessions.authenticate_session(login(new_sessions).value)
    reader = GenerationAuthorizationReader(successor, repo, repo, recovery_epoch=1)
    grants = GrantAdministrationService(
        repo, reader, successor, continuation_owner=None, recovery_epoch=1
    )
    owner = ContextCallAdmission(
        TaskDelegationService(grants, {"understanding": e.limits}), e.limits
    )
    assert owner.read(business, e.invocation.context_id)["status"] == "NOT_ADMITTED"
    renewed = owner.approve(
        reviewer, e.invocation.context_id, command, readmission_plan=plan
    )
    assert renewed["generation"] == 2
    assert renewed["record"]["predecessor_id"] == old["admission_id"]
    assert owner.read(business, e.invocation.context_id)["status"] == "ACTIVE"
    with repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_assistance.invocations"
            ).fetchone()["n"]
            == 1
        )


def test_expired_original_decision_requires_explicit_bounded_lease(env):
    import time

    e = env
    e.admission.prepare(e.business, e.invocation)
    initial = spec(e).model_copy(
        update={"expires_at": datetime.now(UTC) + timedelta(seconds=2)}
    )
    old = e.admission.approve(e.reviewer, e.invocation.context_id, initial)
    command = spec(e, "expired-renewal")
    plan = plan_for(e, old, command)
    time.sleep(max(0, (old["expires_at"] - datetime.now(UTC)).total_seconds()) + 0.02)
    with pytest.raises(AuthorityError, match="LEASE_INVALID"):
        e.admission.approve(
            e.reviewer, e.invocation.context_id, command, readmission_plan=plan
        )
    plan = plan.model_copy(
        update={
            "entries": (
                plan.entries[0].model_copy(update={"lease_mode": "EXPIRED_LEASE"}),
            )
        }
    )
    result = e.admission.approve(
        e.reviewer, e.invocation.context_id, command, readmission_plan=plan
    )
    assert result["ordinal"] == 2
    assert result["expires_at"] == command.expires_at
    assert result["record"]["request"] == old["record"]["request"]
    assert result["record"]["readmission"]["leaseMode"] == "EXPIRED_LEASE"
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


@pytest.fixture
def planning(env):
    from test_planning_call_admission import planning as fixture

    yield from fixture.__wrapped__(env)


def test_actual_planning_owner_renewal_does_not_create_or_raise_allowance(planning):
    from types import SimpleNamespace

    from agent_console.context_call_admission import ContextApproval
    from test_planning_call_admission import prepare, sign

    e = planning
    prepared = prepare(e)
    old = sign(e, prepared)
    identity = prepared["admission"]["context_id"]
    row = e.planning.read(e.business, identity)["request"]
    command = ContextApproval(
        request_digest=row["digest"],
        expires_at=old["expires_at"],
        idempotency_key="planning-renewal",
    )
    current = SimpleNamespace(
        **{
            **vars(e),
            "admission": e.planning,
            "limits": e.planning.configuration,
            "invocation": SimpleNamespace(context_id=identity),
            "draft": SimpleNamespace(profile=e.budget.profile),
        }
    )
    plan = plan_for(current, old, command)
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT * FROM authorization_admin.planning_call_allowances"
        ).fetchall()
    renewed = e.planning.approve(e.reviewer, identity, command, readmission_plan=plan)
    assert renewed["record"]["predecessor_id"] == old["admission_id"]
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT * FROM authorization_admin.planning_call_allowances"
            ).fetchall()
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
