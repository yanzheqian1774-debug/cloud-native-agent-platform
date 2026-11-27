"""Real automatic writers then original approve; synthetic isolated ledger setup."""

import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as N

import pytest
import test_conversation_experience_admission as experience
import test_conversation_planning_admission as planning_support
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import ContextApproval
from agent_console.context_readmission_plan import ReadmissionPlan
from agent_console.conversation_experience_admission import (
    ConversationExperienceAdmission,
)
from agent_console.task_delegation import digest
from test_context_call_admission import env as env


@pytest.fixture
def setup():
    from dataclasses import replace
    from datetime import UTC, datetime

    from agent_console.authority_contracts import CredentialId, GrantSource
    from agent_console.browser_session_application import (
        BrowserSessionService,
        StaticGenerationAuthenticator,
    )
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )
    from agent_console.local_accounts import operate
    from test_local_accounts_postgres import PASSWORD
    from test_local_accounts_postgres import setup as base_setup

    fixture = base_setup.__wrapped__()
    repo, gen, sessions, _ = next(fixture)
    credential = replace(
        gen.credentials[1],
        credential_id=CredentialId("independent-admin-source"),
        principal_id="human:independent-admin",
    )
    account = replace(
        gen.local_accounts[1],
        credential_id=CredentialId("local-account:independentadmin"),
        username="independentadmin",
        principal_id="human:independent-admin",
        grant_source_id=credential.credential_id,
    )
    gen = replace(
        gen,
        generation=2,
        digest="c" * 64,
        credentials=(*gen.credentials, credential),
        local_accounts=(*gen.local_accounts, account),
    )
    repo.activate_generation(
        2,
        gen.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=datetime.now(UTC),
    )
    operate(
        repo,
        account,
        action="CREATE",
        command_id="create-independent",
        operator_id="operator:test",
        now=datetime.now(UTC),
        password=PASSWORD,
    )
    sessions = BrowserSessionService(
        repo,
        StaticGenerationAuthenticator(gen, source=GrantSource.BROWSER_BOOTSTRAP),
        sessions.policy,
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    try:
        yield (
            repo,
            gen,
            sessions,
            GenerationAuthorizationReader(gen, repo, repo, recovery_epoch=1),
        )
    finally:
        with suppress(StopIteration):
            next(fixture)


def real_configure(e, tmp_path):
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
    from test_context_call_admission import ROOT

    invocation = e.draft.begin(
        e.reviewer, key="experience", content="synthetic review"
    ).invocation
    e.admission.configuration = {
        **e.limits,
        "ledger_id": experience.LEDGER,
        "calls": 20,
        "cost_microusd": 1000000,
        "profile_revision_id": invocation.profile_revision_id,
    }
    doc = {
        "schemaVersion": "f3-conversation-experience.v1",
        "tenantId": "s5-323-demo",
        "securityDomain": "isolated-real-demo",
        "subjectId": e.reviewer.principal_id,
        "accountId": "local-account:reviewer324",
        "authorizationDigest": "a" * 64,
        "configuration": e.admission.configuration,
        "conversations": {"approved-conversation": "SYNTHETIC_DOCUMENT_REVIEW"},
        "externalWrites": False,
    }
    path = tmp_path / "experience.json"
    path.write_text(json.dumps(doc))
    path.chmod(0o600)
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=ROOT / "0024_draft_provider_budget.sql",
        profile=e.draft.profile,
        ledger_id=experience.LEDGER,
        call_cap=20,
        total_cost_cap_microusd=1000000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    try:
        budget.migrate_and_configure()
    finally:
        budget.close()
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    return (
        invocation,
        N(begin=lambda context, **kw: e.admission.prepare(context, invocation)),
        path,
        doc,
    )


@pytest.mark.parametrize("phase", ["understanding", "planning"])
def test_real_automatic_writer_then_original_approve(
    env, setup, tmp_path, monkeypatch, phase
):
    e = env
    if phase == "understanding":
        invocation, owner, _, _ = real_configure(e, tmp_path)
        # Existing writer must see exact ordinary actor, not the independent approver.
        experience.prepare(e, invocation, owner)
        service = e.admission
        identity = invocation.context_id
    else:
        monkeypatch.setattr(planning_support, "configure", real_configure)
        # configure retains the caller's actor; fixture original BIND uses business.
        planning_support.ordinary.__wrapped__(e, tmp_path)
        first = planning_support.planned(e)
        service = e.planning
        identity = first["admission"]["context_id"]
    with e.repo.connection_scope() as c:
        row = c.execute(
            "SELECT * FROM authorization_admin.context_call_requests "
            "WHERE context_id=%s",
            (identity,),
        ).fetchone()
        old = c.execute(
            "SELECT * FROM authorization_admin.context_call_decisions "
            "WHERE context_id=%s",
            (identity,),
        ).fetchone()
        assert "request_digest" not in old["record"]
        assert old["record"]["type"] == (
            "F3_CONVERSATION_EXPERIENCE"
            if phase == "understanding"
            else "F3_CONVERSATION_PLANNING"
        )
    command = ContextApproval(
        request_digest=row["digest"],
        expires_at=old["expires_at"],
        idempotency_key="auto-renewal",
    )
    from test_local_accounts_postgres import login

    _, admin = setup[2].authenticate_session(login(setup[2], "independentadmin").value)
    current = N(
        **{
            **vars(e),
            "business": e.reviewer,
            "reviewer": admin,
            "admission": service,
            "limits": service.configuration,
            "invocation": N(context_id=identity),
        }
    )
    plan = plan_for(current, old, command).model_copy(update={"generation": 2})
    import copy

    for change in [
        "type",
        "issuer",
        "policy",
        "payload",
        "request",
        "ordinal",
        "missing_record",
    ]:
        bad = copy.deepcopy(old)
        if change == "type":
            bad["record"]["type"] = "UNKNOWN_POLICY"
        elif change == "issuer":
            bad["issuer_id"] = "policy:other"
        elif change == "policy":
            bad["record"]["policy_digest"] = "f" * 64
        elif change == "payload":
            bad["payload_digest"] = "f" * 64
        elif change == "request":
            bad["record"]["request"]["account_id"] = "other"
        elif change == "ordinal":
            bad["ordinal"] = 2
        else:
            bad["record"] = {}

        # Simulate a corrupted read response; immutable persisted rows stay unchanged.
        class CorruptRead:
            def __init__(self, c, bad_record):
                self.c = c
                self.bad_record = bad_record

            def execute(self, sql, args=None):
                if "context_call_decisions" in sql and "admission_id=%s" in sql:
                    return N(fetchone=lambda: self.bad_record)
                return self.c.execute(sql, args)

        bad_plan = plan.model_copy(
            update={
                "entries": (
                    plan.entries[0].model_copy(
                        update={"prior_record_digest": digest(bad["record"])}
                    ),
                )
            }
        )
        with e.repo.connection_scope() as c:
            with pytest.raises(AuthorityError, match="PRIOR_INVALID"):
                bad_plan.require(
                    service,
                    CorruptRead(c, bad),
                    admin,
                    row,
                    command,
                    old,
                    None,
                    datetime.now(UTC),
                )
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.context_call_decisions "
                    "WHERE context_id=%s",
                    (identity,),
                ).fetchone()["n"]
                == 1
            )
    result = service.approve(admin, identity, command, readmission_plan=plan)
    assert (
        result["ordinal"] == 2
        and result["record"]["predecessor_id"] == old["admission_id"]
    )
    assert service.approve(admin, identity, command, readmission_plan=plan) == result
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT * FROM authorization_admin.context_call_decisions "
                "WHERE admission_id=%s",
                (old["admission_id"],),
            ).fetchone()
            == old
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
    service.revoke(admin, identity, result["admission_id"])
    with pytest.raises(AuthorityError, match="PRIOR_INVALID"):
        service.approve(admin, identity, command, readmission_plan=plan)


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
    deadline = datetime.now(UTC) + timedelta(hours=23)
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
