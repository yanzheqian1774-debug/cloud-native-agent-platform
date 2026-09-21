"""Isolated PostgreSQL D324-5; no deployment decisions or provider traffic."""

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import (
    ContextApproval,
    ContextCallAdmission,
    guard,
)
from agent_console.draft_assistance import (
    AuthorizationState,
    DraftScope,
    ProviderBudgetQuote,
)
from agent_console.draft_assistance_postgres import PostgresDraftAssistanceRepository
from agent_console.grant_administration_application import GrantAdministrationService
from agent_console.task_delegation import TaskDelegationService
from test_draft_assistance import build
from test_local_accounts_postgres import login
from test_local_accounts_postgres import setup as setup

pytestmark = pytest.mark.skipif(
    not os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL"),
    reason="exclusive PostgreSQL required",
)

ROOT = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def env(setup):
    repo, generation, sessions, reader = setup
    grants = GrantAdministrationService(
        repo, reader, generation, continuation_owner=None, recovery_epoch=1
    )
    limits = {
        "ledger_id": "original",
        "configuration_digest": "a" * 64,
        "profile_revision_id": "profile",
        "profile_digest": "b" * 64,
        "model_target": "exact",
        "calls": 2,
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_microusd": 10000000,
    }
    delegation = TaskDelegationService(grants, {"understanding": limits})
    delegation.migrate()
    admission = ContextCallAdmission(delegation, limits)
    admission.migrate()
    # Immutable, expired historical fixture, never a deployed approval.
    from psycopg.types.json import Jsonb

    with repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.task_delegations VALUES "
            "('old','S5-V023-ARCH-323','s5-323-demo','isolated-real-demo',"
            "'human:demo323-requester','old-context','human:demo323-approver',1,1,"
            "now()-interval '2 days',now()-interval '1 day','old','old',%s)",
            (Jsonb({"understanding": limits}),),
        )
        c.execute(
            "INSERT INTO authorization_admin.task_delegation_control "
            "VALUES('old',false)"
        )
        c.execute(
            "INSERT INTO authorization_admin.task_delegation_ledgers VALUES "
            "('s5-323-demo','isolated-real-demo','original','old','understanding')"
        )

    url = repo.pool.conninfo
    draft_repo = PostgresDraftAssistanceRepository(
        url, migration_path=ROOT / "0023_draft_assistance.sql"
    )
    draft_repo.migrate()
    # Exact budget schema, isolated and empty; tests never touch original ledgers.
    with repo.connection_scope() as c:
        c.execute((ROOT / "0024_draft_provider_budget.sql").read_text())
    secret = login(sessions)
    _, business = sessions.authenticate_session(secret.value)
    reviewer_secret = login(sessions, "reviewer324")
    _, reviewer = sessions.authenticate_session(reviewer_secret.value)
    draft, *_ = build(
        authorization_state=AuthorizationState.PENDING, now=datetime.now(UTC)
    )
    draft.profile = replace(
        draft.profile, scope=DraftScope("s5-323-demo", "isolated-real-demo")
    )
    draft.repository = draft_repo
    invocation = draft.begin(
        business, key="new-context", content="synthetic supplier question"
    ).invocation
    try:
        yield SimpleNamespace(
            repo=repo,
            admission=admission,
            business=business,
            reviewer=reviewer,
            invocation=invocation,
            limits=limits,
            draft=draft,
        )
    finally:
        draft_repo.close()


def spec(e, key="decision"):
    row = e.admission.read(e.business, e.invocation.context_id)["request"]
    return ContextApproval(
        request_digest=row["digest"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        idempotency_key=key,
    )


def test_pending_independent_signature_idempotency_and_revoke(env):
    e = env
    e.admission.prepare(e.business, e.invocation)
    e.admission.prepare(e.business, e.invocation)
    assert not e.admission.ready(e.business, e.invocation)
    command = spec(e)
    with pytest.raises(AuthorityError):
        e.admission.approve(e.business, e.invocation.context_id, command)
    decision = e.admission.approve(e.reviewer, e.invocation.context_id, command)
    assert e.admission.approve(e.reviewer, e.invocation.context_id, command) == decision
    assert e.admission.ready(e.business, e.invocation)
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        e.admission.approve(
            e.reviewer,
            e.invocation.context_id,
            command.model_copy(update={"request_digest": "f" * 64}),
        )
    e.admission.revoke(e.reviewer, e.invocation.context_id, decision["admission_id"])
    assert not e.admission.ready(e.business, e.invocation)
    e.repo.verify_existing_schema()


def test_scope_account_config_and_immutable_history(env):
    e = env
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        e.admission.prepare(e.reviewer, e.invocation)
    e.admission.prepare(e.business, e.invocation)
    e.admission.approve(e.reviewer, e.invocation.context_id, spec(e))
    old = e.admission.configuration
    e.admission.configuration = {**old, "calls": 13}
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        e.admission.ready(e.business, e.invocation)
    e.admission.configuration = old
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE browser_identity.local_accounts SET status='DISABLED',"
            "revision=revision+1 WHERE username='demo324'"
        )
    with pytest.raises(AuthorityError, match="ACCOUNT_INACTIVE"):
        e.admission.ready(e.business, e.invocation)
    import psycopg

    with pytest.raises(psycopg.Error), e.repo.connection_scope() as c:
        c.execute("DELETE FROM authorization_admin.context_call_decisions")


def test_guard_pins_exact_new_context_and_blocks_unknown(env):
    e = env
    e.admission.prepare(e.business, e.invocation)
    e.admission.approve(e.reviewer, e.invocation.context_id, spec(e))
    budget = SimpleNamespace(ledger_id="original", delegation_configuration=e.limits)
    quote = ProviderBudgetQuote(100, 500, 1000)
    with e.repo.connection_scope() as c:
        assert guard(c, budget, e.invocation, quote)
        assert not guard(
            c, budget, replace(e.invocation, context_id="unregistered"), quote
        )
    from agent_console.draft_assistance import DraftInvocationState

    e.draft._replace(e.invocation, state=DraftInvocationState.OUTCOME_UNKNOWN)
    with (
        pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"),
        e.repo.connection_scope() as c,
    ):
        guard(c, budget, e.invocation, quote)


def test_shared_ledger_atomic_history_caps_and_dispatch_grant_check(env):
    from concurrent.futures import ThreadPoolExecutor

    from agent_console.draft_assistance import DraftAssistanceError
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
    from agent_console.task_delegation import guard_budget

    e = env
    e.admission.configuration = {**e.limits, "calls": 2}
    profile = replace(e.draft.profile, maximum_output_tokens=500)
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=ROOT / "0024_draft_provider_budget.sql",
        profile=profile,
        ledger_id="original",
        call_cap=2,
        total_cost_cap_microusd=10000000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    budget.delegation_configuration = e.admission.configuration
    budget.migrate_and_configure()
    quote = ProviderBudgetQuote(100, 500, 600)
    try:
        # Retained un-settled historical reservation occupies the original ledger.
        old_id = "old-reservation"
        with e.repo.connection_scope() as c:
            c.execute(
                "INSERT INTO draft_provider_budget.reservations "
                "VALUES('s5-323-demo','isolated-real-demo','original',%s,"
                "'old-operation','old-unknown',100,500,600,%s,now())",
                (old_id, "f" * 64),
            )
        second = e.draft.begin(
            e.business, key="second-context", content="synthetic second"
        ).invocation
        for inv in (e.invocation, second):
            e.admission.prepare(e.business, inv)
            row = e.admission.read(e.business, inv.context_id)["request"]
            e.admission.approve(
                e.reviewer,
                inv.context_id,
                ContextApproval(
                    request_digest=row["digest"],
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    idempotency_key=inv.invocation_id,
                ),
            )
        with e.repo.connection_scope() as c:
            assert guard_budget(c, budget, e.invocation, quote) is False
        with (
            pytest.raises(AuthorityError, match="GRANTS_REQUIRED"),
            e.repo.connection_scope() as c,
        ):
            e.admission.require_dispatch_grants(c, e.business, e.invocation)

        def reserve(inv):
            try:
                return budget.reserve(inv.invocation_id, inv, quote)
            except DraftAssistanceError as exc:
                return exc.reason_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, (e.invocation, second)))
        assert results.count("PROVIDER_BUDGET_EXHAUSTED") == 1
        winner = (e.invocation, second)[
            0 if results[0] != "PROVIDER_BUDGET_EXHAUSTED" else 1
        ]
        assert reserve(winner) in results  # Replay does not consume another slot.
        with e.repo.connection_scope() as c:
            rows = c.execute(
                "SELECT reservation_id,worst_case_cost_microusd "
                "FROM draft_provider_budget.reservations"
            ).fetchall()
            assert len(rows) == 2
            assert sum(r["worst_case_cost_microusd"] for r in rows) == 1200
            assert old_id in {r["reservation_id"] for r in rows}
    finally:
        budget.close()


def test_original_guard_stays_expired_and_new_admission_cannot_adopt_old(env):
    from agent_console.task_delegation import guard_budget

    e = env
    old = replace(e.invocation, context_id="old-context")
    assert e.admission.prepare(e.business, old) is False
    budget = SimpleNamespace(ledger_id="original", delegation_configuration=e.limits)
    with (
        pytest.raises(AuthorityError, match="TASK_DELEGATION_INACTIVE"),
        e.repo.connection_scope() as c,
    ):
        guard_budget(c, budget, old, ProviderBudgetQuote(100, 500, 600))
    e.admission.prepare(e.business, e.invocation)
    command = spec(e)
    with pytest.raises(AuthorityError, match="CONTEXT_ADMISSION_INVALID"):
        e.admission.approve(
            e.reviewer,
            e.invocation.context_id,
            command.model_copy(
                update={"expires_at": datetime.now(UTC) + timedelta(hours=9)}
            ),
        )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.context_call_decisions"
            ).fetchone()["n"]
            == 0
        )
        assert c.execute(
            "SELECT expires_at<clock_timestamp() AS expired "
            "FROM authorization_admin.task_delegations"
        ).fetchone()["expired"]
