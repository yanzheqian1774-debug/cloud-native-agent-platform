# ruff: noqa: F401, F811, E501 -- Shared isolated owner fixtures and exact SQL.
"""Service model -> original Plan/readonly continuation -> queue, no real provider/worker."""

import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_model_binding_resolution as model_fixture
import test_planning_candidates_source_change as original_case
import test_resource_automation as resources
from agent_console import fixed_work_authoring_postgres as drafts
from agent_console.authority_configuration import RequestabilityRule, StaticGrant
from agent_console.authority_contracts import ExactGrant, GrantSource
from agent_console.draft_assistance import DraftScope, ProviderBudgetQuote
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.fixed_work_authoring import SaveDraft
from agent_console.fixed_work_cycle_approval import ServiceCyclePlanApproval
from agent_console.fixed_work_cycle_host import FixedWorkCycleHost
from agent_console.fixed_work_service_admission import migrate
from agent_console.fixed_work_service_continuation import ServiceCycleContinuation
from agent_console.fixed_work_service_policy import ServicePlanningPolicy
from agent_console.fixed_work_service_runtime import ServicePlanningRuntime
from agent_console.fixed_work_trigger_postgres import migrate as trigger_migrate
from agent_console.model_binding_resolution import ModelConsumptionScope
from agent_console.model_governance import ModelScope
from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
from agent_console.plan_suggestion_domain import ConfirmedPlanRevision, ExactReference
from agent_console.plan_suggestion_invocation import PlanningProfile
from agent_console.plan_suggestion_runtime import PlanningBudget
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.readonly_continuation import ReadonlyContinuation
from agent_console.readonly_continuation_policy import (
    ReadonlyContinuationPolicy,
    ReadonlyWork,
)
from agent_console.workbench_business_problem import OwnerPrincipal
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from psycopg.rows import dict_row
from test_draft_assistance import profile
from test_fixed_work_authoring import body
from test_plan_suggestion_v2 import repository
from test_prepared_resource_owners import services

M = Path(__file__).parents[1] / "migrations"
MODEL = ExactReference(
    resource_id="model:reviewer", revision_id="model-revision:7", digest="a" * 64
)


@pytest.fixture
def case(repository):
    generator = original_case.case.__wrapped__(repository)
    value = next(generator)
    value.principal.principal_id = "service:fixed-work-test"
    try:
        yield value
    finally:
        next(generator, None)


@pytest.fixture
def automation(repository, case, services, tmp_path, request, monkeypatch):
    original = resources.StaticAuthorityGeneration

    def generation(*args, **kwargs):
        value = original(*args, **kwargs)
        root = case.p.semantics.target.problem.resource_id
        extra = (
            ExactGrant("TEAM", "READ", "team:fixed-team:r"),
            ExactGrant("PLAN", "PREPARE", "plan:prepare:" + root),
            ExactGrant("PLAN", "READ", "plan:prepared:" + root),
            ExactGrant(
                "MODEL_GOVERNANCE",
                "INVOKE_MODEL",
                f"model:invocation:plan-suggestion:{MODEL.resource_id}:{MODEL.revision_id}:{MODEL.digest}",
            ),
        )
        return replace(
            value,
            requestability=(
                *value.requestability,
                *(
                    RequestabilityRule(
                        "PLAN", action, "plan:v2:" + name, "RESOURCE_PREPARATION"
                    )
                    for name in ("service-fixed-plan", "service-fixed-plan-2")
                    for action in ("READ", "PREPARE", "APPROVE")
                ),
                *(
                    RequestabilityRule(
                        g.owner, g.action, g.exact_resource, "FIXED_WORK_MODEL_TEST"
                    )
                    for g in extra
                ),
            ),
            credentials=(
                replace(
                    value.credentials[0],
                    grants=value.credentials[0].grants
                    + tuple(StaticGrant(g, GrantSource.SERVICE_ONLY) for g in extra),
                ),
                *value.credentials[1:],
            ),
        )

    monkeypatch.setattr(resources, "StaticAuthorityGeneration", generation)
    generator = resources.automation.__wrapped__(
        repository, case, services, tmp_path, request
    )
    value = next(generator)
    try:
        yield value
    finally:
        next(generator, None)


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
@pytest.mark.parametrize("previous", ["UNKNOWN", "CANCELLED", "SUCCEEDED"])
def test_host_restarts_saved_event_through_existing_owners(
    automation, monkeypatch, previous, bound_setup=None, bound_rejected=False
):
    a = automation
    assert a.run()["state"] == "READY"
    from agent_console.cost_execution_revision import (
        EXECUTION_ONLY,
        PLANNING_ONLY,
        READ_ONLY_PLANNING,
        SALES_SYNTHETIC_ONLY,
        SYNTHETIC_ONLY,
    )

    # A normal model may state planning intent only. The original readonly owner,
    # not this adapter or fixture provider, creates execution scope later.
    sem = a.e.p.semantics.model_copy(
        update={
            "business_rules": (
                *tuple(
                    x for x in a.e.p.semantics.business_rules if x != EXECUTION_ONLY
                ),
                PLANNING_ONLY,
            ),
            "boundaries": (
                *tuple(
                    x
                    for x in a.e.p.semantics.boundaries
                    if x
                    not in (SYNTHETIC_ONLY, SALES_SYNTHETIC_ONLY, READ_ONLY_PLANNING)
                ),
                READ_ONLY_PLANNING,
            ),
        }
    )
    now = datetime.now(UTC)
    with a.repository.pool.connection() as c, c.transaction():
        drafts.migrate(c)
        saved, _ = drafts.save(
            c,
            (a.e.scope.namespace, a.e.scope.security_domain),
            "human:author",
            SaveDraft.model_validate(body()),
            dict(teamId="fixed-team", revisionId="r", digest="a" * 64),
            "b" * 64,
            "test-authoring",
            now,
        )
        migrate(c)
        trigger_migrate(c)
        c.execute((M / "0023_draft_assistance.sql").read_text())
    p = replace(
        profile(),
        scope=DraftScope(a.e.scope.namespace, a.e.scope.security_domain),
        binding=model_fixture.BINDING,
    )
    budget = PostgresProviderCallBudget(
        a.repository.pool.conninfo,
        migration_path=M / "0024_draft_provider_budget.sql",
        profile=p,
        ledger_id="original-test-ledger",
        call_cap=2,
        total_cost_cap_microusd=1000,
        input_price_microusd_per_million_tokens=0,
        output_price_microusd_per_million_tokens=0,
    )
    native = PostgresExecutionAuthorityRepository(
        a.repository.pool.conninfo,
        migration_path=M / "0008_execution_runtime_authority.sql",
    )
    try:
        budget.migrate_and_configure()
        policy = ServicePlanningPolicy.model_validate(
            dict(
                schemaVersion="fixed-work-service-planning.v1",
                policyId="test-service",
                enabled=True,
                tenantId=a.e.scope.namespace,
                securityDomain=a.e.scope.security_domain,
                subjectId=a.subject.principal_id,
                credentialId=a.subject.session_id_or_service_credential_id,
                work=dict(
                    resource_id="work:1",
                    revision_id="revision:1",
                    digest=saved["digest"],
                ),
                target=sem.target,
                resourceSnapshot=a.e.p.source_snapshot,
                planningPolicy=sem.policy,
                allowedEventIds=["work-slot:1", "work-slot:2"],
                eventWindows={
                    "work-slot:2": (
                        now - timedelta(minutes=1),
                        now + timedelta(minutes=30),
                    ),
                    "work-slot:1": (
                        now - timedelta(minutes=1),
                        now + timedelta(minutes=30),
                    ),
                },
                profileRevisionId=p.profile_revision_id,
                profileDigest=p.profile_digest,
                model=MODEL,
                ledgerId=budget.ledger_id,
                maximumInputTokens=65536,
                maximumOutputTokens=p.maximum_output_tokens,
                expiresAt=now + timedelta(hours=1),
            )
        )

        class Provider:
            synthetic = True
            calls = 0

            def suggest(self, *args):
                self.calls += 1
                return dict(
                    text=json.dumps(
                        dict(
                            kind="VALID_SUGGESTION",
                            semantics=sem.model_dump(mode="json"),
                        )
                    ),
                    measurement={
                        "settleable": True,
                        "usage": {"input_tokens": 10, "output_tokens": 10},
                    },
                )

        provider = Provider()
        scoped = ModelConsumptionScope(a.e.scope.namespace, a.e.scope.security_domain)
        resolver = model_fixture.RecordingResolver(
            [],
            model_fixture.resolution(
                scope=scoped,
                eligibility=model_fixture.eligibility(
                    scope=ModelScope(scoped.namespace, scoped.security_domain)
                ),
            ),
        )
        identities = iter(("service-fixed-invocation", "service-fixed-plan"))
        deps = PlanningInvocationDependencies(
            PlanningProfile(
                profile_revision_id=p.profile_revision_id,
                profile_digest=p.profile_digest,
                model=MODEL,
                adapter_id="controlled",
                adapter_revision="1",
                maximum_output_tokens=p.maximum_output_tokens,
                maximum_input_bytes=65536,
            ),
            resolver,
            PlanningBudget(budget),
            ProviderBudgetQuote(65536, p.maximum_output_tokens, 0),
            provider,
            b"isolated-only-service-test-commitment",
            lambda *args: a.e.p.source_snapshot,
            identity_factory=lambda: next(identities),
        )
        service = deps.bind(a.e.app, a.adapter.authorization)(a.subject)
        from agent_console.grant_administration_application import (
            GrantAdministrationService,
            GrantDecisionCommand,
            GrantRequestCommand,
        )
        from test_authority_foundation_postgres import KnownTestTargets

        grants_owner = GrantAdministrationService(
            a.authority,
            a.adapter.authorization,
            a.gen,
            continuation_owner=None,
            target_validator=KnownTestTargets(),
            recovery_epoch=1,
        )
        issuer = a.automation.authenticate(a.subject)
        members = tuple(
            x.grant
            for x in a.gen.credentials[0].grants
            if x.grant.owner in {"PLAN", "MODEL_GOVERNANCE"}
            and x.grant.exact_resource != "plan:v2:" + a.e.p.plan_id
        )
        request = grants_owner.submit_request(
            a.subject,
            GrantRequestCommand(
                "FIXED_WORK_MODEL_TEST", members, "independent-service-model-request"
            ),
        )
        grants_owner.decide_request(
            issuer,
            GrantDecisionCommand(
                request.request_id,
                True,
                "ASSIGNED_DUTY",
                "TICKET",
                "isolated-model-scope",
                None,
                policy.expiresAt,
                "independent-service-model-decision",
            ),
        )
        native.migrate_native_dispatch(M / "0022_native_execution_dispatch.sql")
        from agent_console.prepared_result_review import migrate as review_migrate

        with a.repository.pool.connection() as c:
            review_migrate(c)
        readonly_policy = ReadonlyContinuationPolicy(
            policyId="test-service-readonly",
            policyVersion="1",
            enabled=True,
            works=(
                ReadonlyWork(
                    namespace=a.e.scope.namespace,
                    securityDomain=a.e.scope.security_domain,
                    subject=a.subject.principal_id,
                    problem=sem.target.problem,
                    sourceContentDigests=a.policy.workScopes[0].sourceContentDigests,
                    case="sales",
                    nativeAgentName="test-fixed-native",
                    expiresAt=policy.expiresAt,
                ),
            ),
        )
        readonly = ReadonlyContinuation(
            a.automation, readonly_policy, PreparedNativeCoordinator(native)
        )
        loop = None
        if bound_setup is not None:
            loop = bound_setup(a, service, readonly, policy, saved, now)
            runtime = loop.host.runtime
        else:
            runtime = ServicePlanningRuntime(
                service, a.adapter.authorization, lambda: policy, enabled=True
            )
        continuation = ServiceCycleContinuation(
            runtime.registry, readonly, enabled=True
        )

        @contextmanager
        def call_scope(context):
            with a.repository.pool.connection() as c, c.transaction():
                authority = AuthorizedOwnerAuthority(a.adapter, context, c, 1, ())
                yield AuthorizedOwnerCall(
                    "CONTINUE_FIXED_WORK_SERVICE",
                    context,
                    c,
                    {},
                    {},
                    {},
                    (),
                    authority,
                    1,
                    1,
                )

        def act(event="work-slot:1"):
            if loop is not None:
                assert event == "work-slot:1"
                return loop.step()[0]["receipt"]
            if event == "work-slot:2":
                next_ids = iter(("service-fixed-invocation-2", "service-fixed-plan-2"))
                service.identity_factory = lambda: next(next_ids)
            # New host object represents a process restart: no in-memory stage.
            host = FixedWorkCycleHost(
                runtime,
                continuation,
                call_scope,
                enabled=True,
                plan_approval=ServiceCyclePlanApproval(
                    runtime.registry, budget, a.automation, enabled=True
                ),
            )
            return host.step(a.subject, event)["receipt"]

        tables = (
            "execution_authority.workflow_runs",
            "execution_authority.prepared_candidates",
            "execution_authority.prepared_resource_commands",
            "fixed_work_triggers.receipts",
            "authorization_admin.grant_decisions",
            "workflow_planning.plans",
        )

        def footprint():
            with a.repository.pool.connection() as c:
                return tuple(
                    c.execute("SELECT count(*) n FROM " + table).fetchone()["n"]
                    for table in tables
                )

        before = footprint()
        if bound_rejected:
            from agent_console.authority_contracts import AuthorityError

            for _ in range(2):
                with pytest.raises(
                    AuthorityError, match="BOUND_EXECUTION_SOURCE_CHANGED"
                ):
                    act()
                after = footprint()
                assert after[0] == before[0]  # no committed Run
                assert after[1:4] == before[1:4]  # no preparation/START/trigger receipt
                assert provider.calls == 1  # durable saved planning result reused
                with a.repository.pool.connection() as c:
                    assert (
                        c.execute(
                            "SELECT count(*) n FROM draft_provider_budget.reservations"
                        ).fetchone()["n"]
                        == 1
                    )
                    assert (
                        c.execute(
                            "SELECT count(*) n FROM draft_provider_budget.settlements"
                        ).fetchone()["n"]
                        == 1
                    )
                    assert (
                        c.execute(
                            "SELECT count(*) n FROM execution_authority.native_dispatch_commands"
                        ).fetchone()["n"]
                        == 0
                    )
            # No Native worker/Kubernetes port is started in this isolated case.
            return

        from agent_console.workbench_fixed_work_trigger import FixedWorkTriggerOwner

        original_receipt = FixedWorkTriggerOwner.receipt

        def fail_after_start(_):
            raise RuntimeError("isolated-after-enqueue")

        monkeypatch.setattr(
            FixedWorkTriggerOwner, "receipt", staticmethod(fail_after_start)
        )
        with pytest.raises(RuntimeError, match="isolated-after-enqueue"):
            act()
        after = footprint()
        assert after[0] == before[0]  # no Run from rolled-back START
        assert after[2:4] == before[2:4]  # no command or event receipt
        assert provider.calls == 1
        monkeypatch.setattr(
            FixedWorkTriggerOwner, "receipt", staticmethod(original_receipt)
        )
        receipt = act()
        assert act() == receipt
        assert receipt["status"] == "START_COMMITTED"
        with a.repository.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_triggers.receipts"
                ).fetchone()["n"]
                == 1
            )
            assert c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"] == 1 + getattr(a, "expected_existing_runs", 0)
        assert provider.calls == 1
        if loop is not None:
            from agent_console.fixed_work_bound_composition import inspect_bound_cycle

            assert inspect_bound_cycle(loop)["executionStartedByObservation"] is False
            assert loop.step()[0]["receipt"] == receipt
            assert provider.calls == 1
            if previous == "SUCCEEDED":
                from agent_console.execution_preparation_postgres import (
                    PreparedExecutionStore,
                )
                from pending_pipeline_support import drive

                with a.repository.pool.connection() as c:
                    definitions = c.execute(
                        "SELECT count(*) n FROM digital_employee_definition.definitions"
                    ).fetchone()["n"]
                proof = drive(
                    a,
                    native,
                    readonly_policy,
                    Path("."),
                    len(sem.tasks),
                    expected_definitions=definitions,
                    exact_run_id=receipt["runId"],
                    expected_runs=1 + getattr(a, "expected_existing_runs", 0),
                )
                with native.pool.connection() as c:
                    prepared, progress = PreparedExecutionStore(c).read(
                        a.e.scope.namespace, a.e.scope.security_domain, receipt["runId"]
                    )
                    assert progress.state == "SUCCEEDED"
                    assert prepared.digest == receipt["preparationDigest"]
                    artifacts = c.execute(
                        "SELECT artifact_id,task_id FROM execution_authority.run_artifacts "
                        "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                        (
                            a.e.scope.namespace,
                            a.e.scope.security_domain,
                            receipt["runId"],
                        ),
                    ).fetchall()
                    assert len(artifacts) == len(sem.tasks)
                    assert {r["task_id"] for r in artifacts} == {
                        t.task_id for t in sem.tasks
                    }
                assert proof["artifacts"] == len(sem.tasks)
                assert proof["outcome"]
                assert loop.step()[0]["receipt"] == receipt
                assert provider.calls == 1
            return  # Exact v2 composition; no simulated natural second day.
        from agent_console.authority_contracts import AuthorityError

        with pytest.raises(AuthorityError, match="PREVIOUS_RUN_UNRESOLVED"):
            act("work-slot:2")
        assert provider.calls == 1
        from agent_console.execution_postgres import (
            NativeTerminalKind,
            NativeTerminalObservation,
        )
        from agent_console.execution_preparation_postgres import PreparedExecutionStore
        from agent_console.prepared_execution_cancellation import request_cancel

        if previous == "SUCCEEDED":
            from pending_pipeline_support import drive

            with a.repository.pool.connection() as c:
                definitions = c.execute(
                    "SELECT count(*) n FROM digital_employee_definition.definitions"
                ).fetchone()["n"]
            observations = []
            for ordinal in (1, 2):
                current = receipt if ordinal == 1 else act("work-slot:2")
                if ordinal == 2:
                    assert current["runId"] != receipt["runId"]
                    assert current["preparationDigest"] != receipt["preparationDigest"]
                proof = drive(
                    a,
                    native,
                    readonly_policy,
                    Path("."),
                    len(sem.tasks),
                    expected_definitions=definitions,
                    exact_run_id=current["runId"],
                    expected_runs=ordinal,
                )
                with native.pool.connection() as c:
                    prepared, progress = PreparedExecutionStore(c).read(
                        a.e.scope.namespace, a.e.scope.security_domain, current["runId"]
                    )
                    assert progress.state == "SUCCEEDED"
                    assert prepared.digest == current["preparationDigest"]
                    artifacts = c.execute(
                        "SELECT artifact_id,task_id FROM execution_authority.run_artifacts "
                        "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                        (
                            a.e.scope.namespace,
                            a.e.scope.security_domain,
                            current["runId"],
                        ),
                    ).fetchall()
                    assert len(artifacts) == len(sem.tasks)
                    assert {r["task_id"] for r in artifacts} == {
                        t.task_id for t in sem.tasks
                    }
                observations.append((current, proof, artifacts))
                assert act("work-slot:" + str(ordinal)) == current
                assert provider.calls == ordinal
            assert observations[0][1]["outcome"] != observations[1][1]["outcome"]
            assert act() == receipt and act("work-slot:2") == observations[1][0]
            assert provider.calls == 2
            return

        claim = native.claim_next("isolated-cycle-observer")
        assert claim is not None
        if previous == "UNKNOWN":
            native.permit_effect(claim, "isolated-task", lambda *_: True)
            native.record_uncertain(
                claim,
                NativeTerminalObservation(
                    claim.command.command_id,
                    NativeTerminalKind.UNKNOWN,
                    "isolated-task",
                    None,
                    None,
                    "isolated-observation-unavailable",
                    datetime.now(UTC),
                ),
            )
            with pytest.raises(AuthorityError, match="PREVIOUS_RUN_UNRESOLVED"):
                act("work-slot:2")
            assert provider.calls == 1
        else:

            class ExactCancelAuthority:
                def require(self, principal, owner, action, resource):
                    assert principal.principal_id == a.subject.principal_id
                    assert (owner, action, resource) == (
                        "EXECUTION",
                        "CANCEL",
                        "governed-execution:prepared:" + receipt["preparationDigest"],
                    )

            with native.pool.connection() as c, c.transaction():
                p0, _ = PreparedExecutionStore(c).read(
                    a.e.scope.namespace, a.e.scope.security_domain, receipt["runId"]
                )
                request_cancel(
                    c,
                    OwnerPrincipal(
                        a.subject.principal_id,
                        a.e.scope.namespace,
                        a.e.scope.security_domain,
                    ),
                    ExactCancelAuthority(),
                    p0,
                    "isolated-cycle-cancel",
                )
            # Original Native owner appends effect-not-permitted stop receipt;
            # no direct SQL state edits or fabricated successful artifacts.
            assert native.stop_prepared_before_effect(claim)
            while (claim := native.claim_next("isolated-cycle-observer")) is not None:
                assert native.stop_prepared_before_effect(claim)
            with native.pool.connection() as c:
                _, progress = PreparedExecutionStore(c).read(
                    a.e.scope.namespace, a.e.scope.security_domain, receipt["runId"]
                )
                assert progress.state == "CANCELLED"
            second = act("work-slot:2")
            assert second["runId"] != receipt["runId"]
            assert act("work-slot:2") == second
            assert provider.calls == 2

            # Complete the second engineering cycle through the same original
            # cancellation owner; never fabricate successful task/artifact facts.
            class SecondCancelAuthority:
                def require(self, principal, owner, action, resource):
                    assert principal.principal_id == a.subject.principal_id
                    assert (owner, action, resource) == (
                        "EXECUTION",
                        "CANCEL",
                        "governed-execution:prepared:" + second["preparationDigest"],
                    )

            with native.pool.connection() as c, c.transaction():
                p1, _ = PreparedExecutionStore(c).read(
                    a.e.scope.namespace, a.e.scope.security_domain, second["runId"]
                )
                request_cancel(
                    c,
                    OwnerPrincipal(
                        a.subject.principal_id,
                        a.e.scope.namespace,
                        a.e.scope.security_domain,
                    ),
                    SecondCancelAuthority(),
                    p1,
                    "isolated-second-cycle-cancel",
                )
            while (claim := native.claim_next("isolated-cycle-observer")) is not None:
                assert native.stop_prepared_before_effect(claim)
            with native.pool.connection() as c:
                for run_id in (receipt["runId"], second["runId"]):
                    _, progress = PreparedExecutionStore(c).read(
                        a.e.scope.namespace, a.e.scope.security_domain, run_id
                    )
                    assert progress.state == "CANCELLED"
            assert act() == receipt and act("work-slot:2") == second
            assert provider.calls == 2
    finally:
        native.pool.close()
        budget.pool.close()
