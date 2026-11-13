# ruff: noqa: F401, F811, E501 -- Shared isolated owner fixtures and exact SQL.
"""Service model -> original Plan/readonly continuation -> queue, no real provider/worker."""

import json
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
            ExactGrant("PLAN", "READ", "plan:v2:service-fixed-plan"),
            ExactGrant("PLAN", "APPROVE", "plan:v2:service-fixed-plan"),
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
def test_service_model_to_existing_readonly_owner_atomic_receipt(
    automation, monkeypatch
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
                allowedEventIds=["work-slot:1"],
                eventWindows={
                    "work-slot:1": (
                        now - timedelta(minutes=1),
                        now + timedelta(minutes=30),
                    )
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
        runtime = ServicePlanningRuntime(
            service, a.adapter.authorization, lambda: policy, enabled=True
        )
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
        result = runtime.begin(a.subject, "work-slot:1")
        assert result["result"]["kind"] == "VALID_SUGGESTION", result["result"]
        assert provider.calls == 1
        principal = OwnerPrincipal(
            a.subject.principal_id, a.e.scope.namespace, a.e.scope.security_domain
        )
        proposed = result["result"]["proposal"]
        confirmed = service.application.confirm(
            principal,
            proposed["proposal_id"],
            proposed["revision"],
            result["result"]["proposal_digest"],
            expected_plan_version=0,
            key="independent-test-confirm",
        )
        a.e.p = a.e.p.model_copy(
            update={
                "plan_id": proposed["proposal_id"],
                "plan_version": confirmed["plan"]["version"],
                "plan_digest": confirmed["digest"],
                "semantics": ConfirmedPlanRevision.model_validate(
                    confirmed["plan"]
                ).semantics,
            }
        )
        assert a.run(key="new-service-model-resources")["state"] == "READY"
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
        continuation = ServiceCycleContinuation(
            runtime.registry, readonly, enabled=True
        )

        def act():
            with a.repository.pool.connection() as c, c.transaction():
                authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
                call = AuthorizedOwnerCall(
                    "CONTINUE_FIXED_WORK_SERVICE",
                    a.subject,
                    c,
                    {"version": a.e.p.plan_version},
                    {"proposal_id": a.e.p.plan_id},
                    {},
                    (),
                    authority,
                    1,
                    1,
                )
                return continuation.continue_once(call, "work-slot:1")

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
        from agent_console.workbench_fixed_work_trigger import FixedWorkTriggerOwner

        original_receipt = FixedWorkTriggerOwner.receipt

        def fail_after_start(_):
            raise RuntimeError("isolated-after-enqueue")

        monkeypatch.setattr(
            FixedWorkTriggerOwner, "receipt", staticmethod(fail_after_start)
        )
        with pytest.raises(RuntimeError, match="isolated-after-enqueue"):
            act()
        assert footprint() == before
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
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == 1
            )
        assert provider.calls == 1
    finally:
        native.pool.close()
        budget.pool.close()
