"""Controlled PostgreSQL delegation acceptance. Never external provider traffic."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError, GrantSource
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.draft_assistance_authorization import request_grant
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.grant_administration_application import GrantRequestCommand
from agent_console.task_delegation import Limits, TaskApproval, TaskDelegationService
from test_draft_assistance import build, context
from test_plan_suggestion_v2 import repository as repository
from test_provider_usage_grant_flow import ROOT
from test_provider_usage_grant_flow import assembled as assembled


@pytest.fixture
def env(assembled, request):
    _, _, draft, _ = assembled
    grants = draft.authorization.grants
    sessions = grants.authorization.dynamic
    # Explicit controlled static policy; same owner/requestability code as production.
    generation = grants.generation
    rules = tuple(
        RequestabilityRule(o, a, p, purpose)
        for purpose, o, a, p in [
            (
                "PROBLEM_DRAFT_ASSISTANCE",
                "DRAFT_ASSISTANCE",
                "REQUEST_DRAFT_ASSISTANCE",
                "draft-assistance:",
            ),
            (
                "PROBLEM_DRAFT_MODEL_INVOKE",
                "MODEL_GOVERNANCE",
                "INVOKE_MODEL",
                "model:",
            ),
            ("PROVIDER_USAGE_REVIEW", "RESOURCE_USE", "READ", "resource-use:"),
            (
                "PROVIDER_USAGE_REVIEW",
                "EVIDENCE",
                "READ_MEASUREMENT",
                "evidence-reference:",
            ),
        ]
    )
    # Replace the generation provider only within this isolated fixture. Real
    # deployment uses immutable activated generations and never this fixture.
    generation = replace(generation, requestability=generation.requestability + rules)
    grants._generation_provider = lambda: generation
    grants.authorization._generation_provider = lambda: generation
    synthetic, _auth, *_ = build(now=datetime.now(UTC))
    synthetic.repository = draft.repository
    synthetic.resource_use = draft.resource_use
    synthetic.evidence = draft.evidence
    synthetic.identity_factory = lambda prefix: (
        prefix + ":" + __import__("uuid").uuid4().hex
    )
    first = synthetic.begin(
        context("human:reader"),
        key="delegation-root",
        content="controlled synthetic procurement",
    )
    second = synthetic.begin(
        context("human:reader"),
        key="delegation-other-root",
        content="other synthetic task",
    )
    budgets = {}
    bounds = {}
    for kind in ("understanding", "planning"):
        b = PostgresProviderCallBudget(
            os.environ["PLANNING323_TEST_DATABASE_URL"],
            migration_path=ROOT / "0024_draft_provider_budget.sql",
            profile=synthetic.profile,
            ledger_id="delegation-" + kind,
            call_cap=2,
            total_cost_cap_microusd=getattr(request, "param", {}).get("cost", 10000000),
            input_price_microusd_per_million_tokens=1000000,
            output_price_microusd_per_million_tokens=1000000,
        )
        b.migrate_and_configure()
        request.addfinalizer(b.close)
        suffix = "model-1:model-revision-1:" + "a" * 64
        bounds[kind] = Limits(
            ledger_id=b.ledger_id,
            configuration_digest="b" * 64,
            profile_revision_id=synthetic.profile.profile_revision_id,
            profile_digest=synthetic.profile.profile_digest,
            model_target=(
                "model:invocation:plan-suggestion:" if kind == "planning" else ""
            )
            + suffix,
            calls=2,
            input_tokens=65536,
            output_tokens=synthetic.profile.maximum_output_tokens,
            cost_microusd=b.total_cost_cap_microusd,
        ).model_dump()
        b.delegation_configuration = bounds[kind]
        budgets[kind] = b
    service = TaskDelegationService(grants, bounds)
    service.migrate()
    # Authenticated real sessions are obtained through the same foundation service.
    from agent_console.browser_session_application import (
        BrowserSessionPolicy,
        BrowserSessionService,
        StaticGenerationAuthenticator,
    )

    session_service = BrowserSessionService(
        sessions,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=2),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"c" * 32,
        recovery_epoch=1,
    )
    contexts = {}
    for name in ("reader", "approver", "other"):
        secret = session_service.create_session(
            session_service.issue_login_nonce(), name + "-controlled"
        )
        _, contexts[name] = session_service.authenticate_session(secret.value)
    spec = TaskApproval(
        task_id="S5-V023-ARCH-323",
        subject_id="human:reader",
        root_context_id=first.invocation.context_id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        understanding=Limits(**bounds["understanding"]),
        planning=Limits(**bounds["planning"]),
        allow_usage_read=True,
        allow_measurement_read=True,
        idempotency_key="approve-task",
    )
    yield NS(
        service=service,
        grants=grants,
        sessions=session_service,
        contexts=contexts,
        spec=spec,
        first=first.invocation,
        second=second.invocation,
        synthetic=synthetic,
        budgets=budgets,
    )


def submit(e, invocation=None):
    target = request_grant(invocation or e.first)
    return e.grants.submit_request(
        e.contexts["reader"],
        GrantRequestCommand(
            purpose="PROBLEM_DRAFT_ASSISTANCE",
            requested_grants=(target,),
            idempotency_key="request-" + (invocation or e.first).invocation_id,
        ),
    )


def test_independent_approval_exact_grant_replay_revocation(env):
    e = env
    s = e.service
    with pytest.raises(AuthorityError, match="SELF_APPROVAL"):
        s.approve(e.contexts["reader"], e.spec)
    d = s.approve(e.contexts["approver"], e.spec)
    assert s.approve(e.contexts["approver"], e.spec) == d
    r = submit(e)
    decision = s.authorize(e.contexts["reader"], d, r.request_id)
    assert s.authorize(e.contexts["reader"], d, r.request_id) == decision
    assert (
        e.grants.authorization.authorize_current(
            e.contexts["reader"], request_grant(e.first), now=datetime.now(UTC)
        )
        is not None
    )
    s.revoke(e.contexts["approver"], d)
    assert (
        e.grants.authorization.authorize_current(
            e.contexts["reader"], request_grant(e.first), now=datetime.now(UTC)
        )
        is None
    )
    with pytest.raises(AuthorityError, match="INACTIVE"):
        s.authorize(e.contexts["reader"], d, r.request_id)


def test_other_task_and_subject_denied(env):
    e = env
    d = e.service.approve(e.contexts["approver"], e.spec)
    r = submit(e, e.second)
    with pytest.raises(AuthorityError, match="TARGET_DENIED"):
        e.service.authorize(e.contexts["reader"], d, r.request_id)
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        e.service.authorize(e.contexts["other"], d, r.request_id)


def test_configuration_and_expiry_denied(env):
    e = env
    bad = e.spec.model_copy(
        update={"understanding": e.spec.understanding.model_copy(update={"calls": 12})}
    )
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        e.service.approve(e.contexts["approver"], bad)
    with pytest.raises(AuthorityError, match="WINDOW_INVALID"):
        e.service.approve(
            e.contexts["approver"],
            e.spec.model_copy(
                update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
            ),
        )


def test_parallel_exact_grant_is_one_audited_decision(env):
    e = env
    d = e.service.approve(e.contexts["approver"], e.spec)
    r = submit(e)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: e.service.authorize(e.contexts["reader"], d, r.request_id),
                range(4),
            )
        )
    assert len(set(results)) == 1
    with e.service.repository.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM "
                "authorization_admin.task_delegation_decisions"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.audit_events WHERE "
                "event_type='TASK_DELEGATION_EXACT_GRANTED'"
            ).fetchone()["n"]
            == 1
        )


def test_budget_token_task_and_unknown_reservations(env):
    e = env
    e.service.approve(e.contexts["approver"], e.spec)
    b = e.budgets["understanding"]
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    with pytest.raises(AuthorityError, match="TARGET_DENIED"):
        b.reserve("wrong-task", e.second, quote)
    with pytest.raises(AuthorityError, match="TOKEN_LIMIT"):
        b.reserve(
            "bad-token",
            e.first,
            replace(
                quote,
                input_token_upper_bound=65537,
                worst_case_cost_microusd=65537 + quote.output_token_ceiling,
            ),
        )
    first = b.reserve("first", e.first, quote)
    assert b.reserve("first", e.first, quote) == first
    successor = e.synthetic.begin(
        context("human:reader"),
        key="successor",
        content="controlled correction",
        parent_context_id=e.first.context_id,
        parent_turn_id=e.first.turn_id,
        expected_parent_version=e.first.turn_version,
        predecessor_invocation_id=e.first.invocation_id,
    ).invocation
    with pytest.raises(AuthorityError, match="PENDING_RESERVATION"):
        b.reserve("next", successor, quote)


def test_http_independent_approval_csrf_and_exact_authorize(env):
    from agent_console.task_delegation_api import install_task_delegation_routes
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient
    from test_workbench_creator_continuation_postgres import login

    e = env
    app = create_workbench_bff(
        e.sessions,
        None,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        grant_administration=e.grants,
        route_installers=(install_task_delegation_routes(e.service),),
    )
    path = "/api/workbench/v1/authorization/task-delegations"
    with (
        TestClient(app, base_url="https://console.example") as caller,
        TestClient(app, base_url="https://console.example") as admin,
    ):
        csrf = login(caller, "reader-controlled")
        acsrf = login(admin, "approver-controlled")
        h = {"origin": "https://console.example", "x-csrf-token": csrf}
        ah = {"origin": "https://console.example", "x-csrf-token": acsrf}
        body = e.spec.model_dump(mode="json")
        assert (
            admin.post(
                path, json=body, headers={"origin": "https://console.example"}
            ).status_code
            == 403
        )
        denied = caller.post(path, json=body, headers=h)
        assert denied.status_code != 200
        assert denied.json()["reasonCode"] == "GRANT_SELF_APPROVAL_PROHIBITED"
        result = admin.post(path, json=body, headers=ah)
        assert result.status_code == 200, result.text
        identity = result.json()["delegation_id"]
        request = submit(e)
        response = caller.post(
            path + "/" + identity + "/grant-requests/" + request.request_id, headers=h
        )
        assert response.status_code == 200, response.text
        assert caller.get(path + "/" + identity).json()["issuer_id"] == "human:approver"
        assert (
            admin.post(path + "/" + identity + "/revoke", headers=ah).status_code == 200
        )
        assert (
            caller.post(
                path + "/" + identity + "/grant-requests/" + request.request_id,
                headers=h,
            ).json()["reasonCode"]
            == "TASK_DELEGATION_INACTIVE"
        )


@pytest.mark.parametrize("usage,measurement", [(True, False), (False, True)])
def test_fee_permissions_stay_separate(env, usage, measurement):
    from agent_console.authority_contracts import ExactGrant
    from agent_console.provider_usage import grants

    e = env
    # Synthetic owner observation supplies a real stored measurement target.
    e.synthetic._replace(e.first, measurement={"settleable": False, "usage": None})
    spec = e.spec.model_copy(
        update={"allow_usage_read": usage, "allow_measurement_read": measurement}
    )
    d = e.service.approve(e.contexts["approver"], spec)
    for allowed, member in zip(
        (usage, measurement),
        grants("understanding", e.first.invocation_id),
        strict=True,
    ):
        grant = ExactGrant(*member)
        r = e.grants.submit_request(
            e.contexts["reader"],
            GrantRequestCommand(
                purpose="PROVIDER_USAGE_REVIEW",
                requested_grants=(grant,),
                idempotency_key="usage-" + member[0],
            ),
        )
        if allowed:
            e.service.authorize(e.contexts["reader"], d, r.request_id)
        else:
            with pytest.raises(AuthorityError, match="TARGET_DENIED"):
                e.service.authorize(e.contexts["reader"], d, r.request_id)
        decision = e.grants.authorization.authorize_current(
            e.contexts["reader"], grant, now=datetime.now(UTC)
        )
        assert (decision is not None) == allowed


def successor(e, parent, key):
    return e.synthetic.begin(
        context("human:reader"),
        key=key,
        content="controlled correction " + key,
        parent_context_id=parent.context_id,
        parent_turn_id=parent.turn_id,
        expected_parent_version=parent.turn_version,
        predecessor_invocation_id=parent.invocation_id,
    ).invocation


def test_parallel_budget_reservation_serial_limit_and_call_cap(env):
    from agent_console.draft_assistance import (
        DraftAssistanceError,
        ObservationState,
        ProviderObservation,
    )

    e = env
    e.service.approve(e.contexts["approver"], e.spec)
    b = e.budgets["understanding"]
    second = successor(e, e.first, "parallel-2")
    third = successor(e, second, "parallel-3")
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )

    def reserve(inv):
        try:
            return (inv, b.reserve(inv.invocation_id, inv, quote))
        except AuthorityError as exc:
            return (inv, exc.reason_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [e.first, second]))
    assert sum(r == "TASK_DELEGATION_PENDING_RESERVATION" for _, r in results) == 1
    won, reservation = next(
        (i, r) for i, r in results if r.startswith("provider-budget-reservation:")
    )
    b.record_usage(
        "measured-1",
        reservation,
        ProviderObservation(
            "obs-1",
            ObservationState.FAILED,
            reason_code="PROVIDER_REFUSAL",
            input_tokens=10,
            output_tokens=10,
        ),
    )
    remaining = second if won == e.first else e.first
    next_reservation = b.reserve(remaining.invocation_id, remaining, quote)
    b.record_usage(
        "measured-2",
        next_reservation,
        ProviderObservation(
            "obs-2",
            ObservationState.FAILED,
            reason_code="PROVIDER_REFUSAL",
            input_tokens=10,
            output_tokens=10,
        ),
    )
    with pytest.raises(DraftAssistanceError, match="BUDGET_EXHAUSTED"):
        b.reserve("third", third, quote)


def test_revoked_dispatch_guard_never_enters_provider(env):
    e = env
    d = e.service.approve(e.contexts["approver"], e.spec)
    b = e.budgets["understanding"]
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    reservation = b.reserve("before-revoke", e.first, quote)
    e.service.revoke(e.contexts["approver"], d)
    with (
        pytest.raises(AuthorityError, match="INACTIVE"),
        b.dispatch_guard(e.first, quote),
    ):
        pytest.fail("revoked delegation entered provider boundary")
    with b._connection() as c:
        assert (
            c.execute(
                "SELECT reservation_id FROM draft_provider_budget.reservations"
            ).fetchone()["reservation_id"]
            == reservation
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )


def test_expired_task_blocks_existing_grant_and_dispatch(env):
    import time

    e = env
    expires = datetime.now(UTC) + timedelta(seconds=0.5)
    d = e.service.approve(
        e.contexts["approver"], e.spec.model_copy(update={"expires_at": expires})
    )
    r = submit(e)
    e.service.authorize(e.contexts["reader"], d, r.request_id)
    # Intentional boundary test: advance past the approved absolute expiry,
    # not a retry or timing workaround for a failing operation.
    while datetime.now(UTC) < expires:
        time.sleep(min(0.01, (expires - datetime.now(UTC)).total_seconds()))
    assert (
        e.grants.authorization.authorize_current(
            e.contexts["reader"], request_grant(e.first), now=datetime.now(UTC)
        )
        is None
    )
    with pytest.raises(AuthorityError, match="INACTIVE"):
        e.service.authorize(e.contexts["reader"], d, r.request_id)


def create_task_problem(e, key="problem"):
    from dataclasses import asdict

    from agent_console.business_problem_domain import BusinessProblemRevision
    from agent_console.business_problem_postgres import (
        PostgresBusinessProblemRepository,
    )
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.task_delegation import record_created_object

    problem = PostgresBusinessProblemRepository(
        os.environ["PLANNING323_TEST_DATABASE_URL"],
        migration_path=ROOT / "0013_business_problem_authority.sql",
    )
    try:
        revision = BusinessProblemRevision(
            ScopeIdentity("tenant-a", "quality"),
            key,
            key + ":1",
            1,
            None,
            "Synthetic procurement",
            "Only planning, no order access",
            "human:reader",
            "human:reader",
            datetime.now(UTC),
        )
        with e.service.repository.connection_scope() as c:
            saved = problem.create_problem(
                revision,
                idempotency_key=key,
                payload_digest="c" * 64,
                authorized=True,
                connection=c,
            )
            record_created_object(
                c, e.contexts["reader"], "BUSINESS_PROBLEM", {"revision": asdict(saved)}
            )
        e.synthetic.link_problem(
            context("human:reader"),
            e.first.invocation_id,
            problem_id=saved.business_problem_id,
            problem_revision_id=saved.revision_id,
            problem_digest=saved.digest,
        )
        return saved
    finally:
        problem.pool.close()


def test_owner_binding_and_cross_purpose_serial_budget(env):
    from agent_console.authority_contracts import ExactGrant
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
    from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
    from agent_console.task_delegation import target_in_task

    e = env
    d = e.service.approve(e.contexts["approver"], e.spec)
    problem = create_task_problem(e)
    with e.service.repository.connection_scope() as c:
        row = c.execute(
            "SELECT * FROM authorization_admin.task_delegations WHERE delegation_id=%s",
            (d,),
        ).fetchone()
        assert target_in_task(
            c,
            row,
            ExactGrant(
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:" + problem.business_problem_id,
            ),
        )
        assert not target_in_task(
            c, row, ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:foreign")
        )
    invocations = PostgresPlanningInvocations(
        PostgresPlanningRepository(e.service.repository.pool)
    )
    invocations.claim(
        ScopeIdentity("tenant-a", "quality"),
        "human:reader",
        "plan-test",
        "d" * 64,
        {
            "target": {
                "invocation_id": "plan-task-1",
                "problem": {"problem": {"resource_id": problem.business_problem_id}},
            }
        },
    )
    b = e.budgets["planning"]
    identity = NS(
        scope=e.first.scope,
        invocation_id="plan-task-1",
        profile_revision_id=b.profile.profile_revision_id,
    )
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    reservation = b.reserve("plan-first", identity, quote)
    assert reservation
    with pytest.raises(AuthorityError, match="PENDING_RESERVATION"):
        e.budgets["understanding"].reserve("understanding-next", e.first, quote)


def test_owner_cannot_adopt_preexisting_or_other_subject_resource(env):
    from agent_console.task_delegation import record_created_object

    e = env
    e.service.approve(e.contexts["approver"], e.spec)
    for created_by, created in [
        ("human:other", datetime.now(UTC)),
        ("human:reader", datetime.now(UTC) - timedelta(days=1)),
    ]:
        with (
            e.service.repository.connection_scope() as c,
            pytest.raises(AuthorityError, match="TARGET_DENIED"),
        ):
            record_created_object(
                c,
                e.contexts["reader"],
                "BUSINESS_PROBLEM",
                {
                    "revision": {
                        "created_by": created_by,
                        "created_at": created,
                        "business_problem_id": "not-adoptable",
                    }
                },
            )


def test_unknown_blocks_even_if_usage_was_settled(env):
    from agent_console.draft_assistance import (
        DraftInvocationState,
        ObservationState,
        ProviderObservation,
    )

    e = env
    e.service.approve(e.contexts["approver"], e.spec)
    b = e.budgets["understanding"]
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    reservation = b.reserve("first", e.first, quote)
    b.record_usage(
        "known-usage-unknown-result",
        reservation,
        ProviderObservation(
            "unknown", ObservationState.UNKNOWN, input_tokens=10, output_tokens=10
        ),
    )
    e.synthetic._replace(e.first, state=DraftInvocationState.OUTCOME_UNKNOWN)
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        b.reserve("no-retry", e.first, quote)


def test_extension_restart_checksum_and_immutable_approval(env):
    import psycopg

    e = env
    d = e.service.approve(e.contexts["approver"], e.spec)
    e.service.repository.verify_existing_schema()
    e.service.repository.migrate()
    e.service.migrate()
    with (
        e.service.repository.connection_scope() as c,
        pytest.raises(psycopg.Error, match="TASK_DELEGATION_IMMUTABLE"),
    ):
        c.execute(
            "UPDATE authorization_admin.task_delegations "
            "SET expires_at=expires_at+interval '1 day' WHERE delegation_id=%s",
            (d,),
        )
    changed = e.spec.model_copy(update={"allow_usage_read": False})
    with pytest.raises(AuthorityError, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        e.service.approve(e.contexts["approver"], changed)
    with pytest.raises(AuthorityError, match="ALREADY_BOUND"):
        e.service.approve(
            e.contexts["approver"],
            e.spec.model_copy(
                update={"task_id": "another-task", "idempotency_key": "another-task"}
            ),
        )


def test_extension_version_guard_rejects_missing_file_and_tampering(env, tmp_path):
    from agent_console.authority_postgres import PostgresAuthorityRepository

    repository = env.service.repository
    migration = tmp_path / repository.migration_path.name
    migration.write_bytes(repository.migration_path.read_bytes())
    old_layout = PostgresAuthorityRepository(
        os.environ["PLANNING323_TEST_DATABASE_URL"], migration_path=migration
    )
    try:
        for check in (old_layout.verify_existing_schema, old_layout.migrate):
            with pytest.raises(AuthorityError, match="AUTHORITY_SCHEMA_INCOMPATIBLE"):
                check()
    finally:
        old_layout.close()
    with repository.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.schema_migrations "
            "SET checksum='invalid' WHERE version=28"
        )
    for check in (repository.verify_existing_schema, repository.migrate):
        with pytest.raises(AuthorityError, match="AUTHORITY_SCHEMA_INCOMPATIBLE"):
            check()


def test_configuration_change_denies_existing_task(env):
    e = env
    d = e.service.approve(e.contexts["approver"], e.spec)
    r = submit(e)
    e.service.configurations = {
        **e.service.configurations,
        "understanding": {
            **e.service.configurations["understanding"],
            "configuration_digest": "f" * 64,
        },
    }
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        e.service.authorize(e.contexts["reader"], d, r.request_id)


def test_full_workbench_registers_delegation_and_budget_guards(env, tmp_path):
    from agent_console.business_problem_postgres import (
        PostgresBusinessProblemRepository,
    )
    from agent_console.kimi_responses_draft_adapter import KimiResponsesDraftTransport
    from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
    from agent_console.plan_suggestion_runtime import (
        PlanningBudget,
        PlanningResponsesProvider,
    )
    from agent_console.workbench_bootstrap import build_workbench_composition
    from fastapi.testclient import TestClient
    from test_kimi_responses_draft_adapter import _configuration
    from test_workbench_creator_continuation_postgres import login

    e = env
    configuration = _configuration(
        NS(server_port=1), tmp_path / "test.crt", tmp_path / "synthetic.credential"
    )
    configuration = replace(
        configuration, maximum_output_tokens=e.synthetic.profile.maximum_output_tokens
    )
    e.synthetic.transport = KimiResponsesDraftTransport(configuration)
    e.synthetic.budget = e.budgets["understanding"]
    provider = PlanningResponsesProvider(configuration, e.synthetic.profile, None)
    deps = PlanningInvocationDependencies(
        None,
        None,
        PlanningBudget(e.budgets["planning"]),
        None,
        provider,
        b"k" * 32,
        None,
    )
    url = os.environ["PLANNING323_TEST_DATABASE_URL"]
    problem = PostgresBusinessProblemRepository(
        url, migration_path=ROOT / "0013_business_problem_authority.sql"
    )
    composition = build_workbench_composition(
        runtime_configuration_path=tmp_path / "runtime.json",
        allowed_host="console.example",
        allowed_origin="https://console.example",
        owner_database_url=url,
        agent_database_url=url,
        business_problems=NS(problems=problem),
        agent_definitions=NS(),
        employee_definitions=NS(),
        digital_employees=NS(),
        draft_assistance=e.synthetic,
        planning_v2_enabled=True,
        planning_invocations=deps,
    )
    try:
        with TestClient(
            composition.application, base_url="https://console.example"
        ) as admin:
            login(admin, "approver-controlled")
            result = admin.get(
                "/api/workbench/v1/authorization/task-delegations/configuration"
            )
            assert result.status_code == 200, result.text
            bounds = result.json()["configurations"]
            assert (
                bounds["understanding"]["ledger_id"]
                == e.budgets["understanding"].ledger_id
            )
            assert e.budgets["planning"].delegation_configuration == bounds["planning"]
            assert len(bounds["planning"]["configuration_digest"]) == 64
            assert "credential" not in result.text
    finally:
        composition.close()
        problem.pool.close()


@pytest.mark.parametrize("env", [{"cost": 1200}], indirect=True)
def test_original_money_cap_is_not_reset(env):
    from agent_console.draft_assistance import (
        DraftAssistanceError,
        ObservationState,
        ProviderObservation,
    )

    e = env
    e.service.approve(e.contexts["approver"], e.spec)
    b = e.budgets["understanding"]
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    reservation = b.reserve("first-money", e.first, quote)
    b.record_usage(
        "billable",
        reservation,
        ProviderObservation(
            "billable",
            ObservationState.FAILED,
            reason_code="PROVIDER_REFUSAL",
            input_tokens=100,
            output_tokens=1000,
        ),
    )
    next_inv = successor(e, e.first, "money-successor")
    with pytest.raises(DraftAssistanceError, match="BUDGET_EXHAUSTED"):
        b.reserve("second-money", next_inv, quote)


def test_missing_target_and_cross_scope_approval_are_rejected(env):
    from agent_console.authority_contracts import ExactGrant

    e = env
    with pytest.raises(AuthorityError, match="SUBJECT_INVALID"):
        e.service.approve(e.contexts["other"], e.spec)
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        e.grants.submit_request(
            e.contexts["reader"],
            GrantRequestCommand(
                purpose="PROBLEM_DRAFT_ASSISTANCE",
                requested_grants=(
                    ExactGrant(
                        "DRAFT_ASSISTANCE",
                        "REQUEST_DRAFT_ASSISTANCE",
                        "draft-assistance:context:missing",
                    ),
                ),
                idempotency_key="fake-target",
            ),
        )


def test_same_case_cannot_adopt_second_problem(env):
    e = env
    e.service.approve(e.contexts["approver"], e.spec)
    create_task_problem(e, "first-task-problem")
    with pytest.raises(AuthorityError, match="PROBLEM_ALREADY_BOUND"):
        create_task_problem(e, "second-task-problem")


@pytest.mark.parametrize("phase", ["before", "after"])
def test_understanding_guard_denial_is_not_a_false_unknown(phase):
    from contextlib import contextmanager

    from agent_console.draft_assistance import (
        DraftAssistanceError,
        DraftInvocationState,
    )

    service, _, _, transport, _, _ = build(now=datetime.now(UTC))
    calls = []

    @contextmanager
    def guard(*args):
        if phase == "before":
            raise AuthorityError("TASK_DELEGATION_INACTIVE")
        yield

    def dispatch(**kwargs):
        calls.append("entered")
        raise AuthorityError("TEST_AFTER_PROVIDER_ENTRY")

    service.budget.dispatch_guard = guard
    transport.dispatch = dispatch
    reason = "DISPATCH_ADMISSION_DENIED" if phase == "before" else "TRANSPORT_AMBIGUOUS"
    with pytest.raises(DraftAssistanceError, match=reason):
        service.begin(context(), key="guard-boundary", content="synthetic problem")
    current = service.repository.get_by_key(
        service.profile.scope, "human:alice", "guard-boundary"
    )
    assert current.state == (
        DraftInvocationState.FAILED_PRE_DISPATCH
        if phase == "before"
        else DraftInvocationState.OUTCOME_UNKNOWN
    )
    assert len(calls) == (0 if phase == "before" else 1)
