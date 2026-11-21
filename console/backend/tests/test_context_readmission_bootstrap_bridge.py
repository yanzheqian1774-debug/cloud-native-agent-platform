"""Seven actual admission owners through the real workbench composition.

Reuse the original task-delegation PG fixture, never a registry/owner substitute.
Profiles/policies are controlled test inputs; no provider dispatch or reservation.
"""

# ruff: noqa: F401,F811 -- transitive original random-database fixtures
import copy
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_experience_admission import (
    LEDGER,
    ConversationExperienceAdmission,
)
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.kimi_responses_draft_adapter import KimiResponsesDraftTransport
from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
from agent_console.plan_suggestion_runtime import (
    PlanningBudget,
    PlanningResponsesProvider,
)
from agent_console.planning_call_admission import PlanningCallAdmission
from agent_console.provider_budget_allowance import prepare as prepare_allowance
from agent_console.task_delegation import configured_limits, digest
from agent_console.workbench_bootstrap import build_workbench_composition
from psycopg.types.json import Jsonb
from test_kimi_responses_draft_adapter import _configuration
from test_plan_suggestion_v2 import repository
from test_prepared_resource_owners import services as resource_services
from test_provider_budget_allowance import document as allowance_document
from test_provider_budget_extension import enable as enable_extension
from test_provider_usage_grant_flow import ROOT, assembled
from test_task_delegation import env


def private(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return str(path)


def counters(repository):
    with repository.connection_scope() as c:
        return tuple(
            c.execute(f"SELECT count(*) n FROM {name}").fetchone()["n"]
            for name in (
                "draft_assistance.invocations",
                "draft_provider_budget.reservations",
                "draft_provider_budget.settlements",
                "draft_provider_budget.allowances",
            )
        )


@pytest.mark.parametrize("plan_enabled", [False, True])
def test_real_bootstrap_registers_all_seven_exact_owners(
    env, resource_services, tmp_path, monkeypatch, plan_enabled, request
):
    from agent_console import context_call_admission_api

    e = env
    url = os.environ["PLANNING323_TEST_DATABASE_URL"]
    # Clear optional ambient deployment policies: this test composes only its
    # explicit controlled private policies and the original real PG foundation.
    for name in tuple(os.environ):
        if name.startswith(("F3_", "OWNED_BUSINESS_", "CONTEXT_CALL_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("CONTEXT_CALL_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("F3_CONVERSATION_PLANNING_ENABLED", "true")
    config = replace(
        _configuration(NS(server_port=1), tmp_path / "test.crt", tmp_path / "key"),
        maximum_output_tokens=e.synthetic.profile.maximum_output_tokens,
    )
    root = copy.copy(e.synthetic)
    root.profile = replace(
        root.profile,
        adapter_revision="v3-execution",
        output_schema_version="conversation-understanding-output.v3-execution",
    )
    root.transport = KimiResponsesDraftTransport(config)
    root.transport.dispatch = lambda **kw: pytest.fail("unexpected provider dispatch")
    root.transport.prepare = lambda **kw: pytest.fail("unexpected provider prepare")
    budget = PostgresProviderCallBudget(
        url,
        migration_path=ROOT / "0024_draft_provider_budget.sql",
        profile=root.profile,
        ledger_id=LEDGER,
        call_cap=20,
        total_cost_cap_microusd=1000000,
        input_price_microusd_per_million_tokens=1000000,
        output_price_microusd_per_million_tokens=1000000,
    )
    request.addfinalizer(budget.close)
    budget.migrate_and_configure()
    allowance = prepare_allowance(
        budget, allowance_document(budget, calls=100, cost=10000000)
    )
    budget.allowance_id = allowance["allowanceId"]
    root.budget = budget
    budget.extension_test_base = allowance
    extension = enable_extension(budget)
    from agent_console.provider_budget_extension import configure_from_environment
    from agent_console.provider_budget_extension import require as require_extension

    selection_path = private(tmp_path / "extension.json", budget.budget_extension)
    monkeypatch.setenv("PROVIDER_BUDGET_EXTENSION_POLICY", selection_path)
    configure_from_environment(budget)
    with budget._connection() as c:
        assert require_extension(c, budget).extensionId == extension["extensionId"]
    from agent_console.mcp_tool_test_postgres import migrate as migrate_tools

    migrate_tools(e.service.repository)
    expires = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    management = dict(
        schemaVersion="resource-management-policy.v1",
        enabled=True,
        policyId="bridge-management",
        policyVersion="1",
        issuer="service:bridge",
        credentialPath=str(tmp_path / "unused.credential"),
        workScopes=[
            dict(
                namespace="s5-323-demo",
                securityDomain="isolated-real-demo",
                subject="human:demo323-approver",
                kinds=["skill", "mcp"],
                expiresAt=expires,
            )
        ],
    )
    monkeypatch.setenv(
        "RESOURCE_MANAGEMENT_POLICY", private(tmp_path / "management.json", management)
    )
    ref = dict(resource_id="bridge-mcp", revision_id="bridge-revision", digest="a" * 64)
    tool = dict(
        schemaVersion="mcp-published-tool-test.v1",
        enabled=True,
        policyId="bridge-tool",
        policyVersion="1",
        issuer="service:bridge",
        credentialPath=str(tmp_path / "unused.credential"),
        bindings=[
            dict(
                namespace="s5-323-demo",
                securityDomain="isolated-real-demo",
                subject="human:demo323-approver",
                mcp=ref,
                source={**ref, "resource_id": "bridge-source"},
                sourceContentDigest="b" * 64,
                endpoint="http://127.0.0.1:1/no-dispatch",
                selectionId="bridge-selection",
                snapshotId="bridge-snapshot",
                snapshotDigest="c" * 64,
                toolName="bridge.read",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                arguments={},
                sideEffect="READ",
                expiresAt=expires,
            )
        ],
    )
    monkeypatch.setenv(
        "MCP_PUBLISHED_TOOL_TEST_POLICY", private(tmp_path / "tool.json", tool)
    )
    monkeypatch.setenv("PREPARED_DELIVERY_ACCEPTANCE_ENABLED", "true")
    root_limits = configured_limits(root.profile, config, budget)
    base = dict(
        schemaVersion="f3-conversation-experience.v2",
        tenantId="s5-323-demo",
        securityDomain="isolated-real-demo",
        subjectId="human:demo323-approver",
        accountId="local-account:reviewer324",
        authorizationDigest=allowance["authorizationDigest"],
        configuration=root_limits,
        conversations={"controlled": "SYNTHETIC_DOCUMENT_REVIEW"},
        externalWrites=False,
        allowanceId=allowance["allowanceId"],
    )
    experience_path = tmp_path / "experience.json"
    private(experience_path, base)
    previous = ConversationExperienceAdmission(experience_path, root_limits)
    private(
        experience_path,
        {
            **base,
            "schemaVersion": "f3-conversation-experience.v3",
            "predecessorSchemaVersion": base["schemaVersion"],
            "predecessorPolicyDigest": previous.policy_digest,
            "ownedConversationUnderstanding": True,
        },
    )
    experience = ConversationExperienceAdmission(experience_path, root_limits)
    monkeypatch.setenv("F3_CONVERSATION_EXPERIENCE_POLICY", str(experience_path))
    names = (
        ("v3-relation", "F3_CONVERSATION_RELATION_POLICY"),
        ("v3-relation-adoption", "F3_UNDERSTANDING_ADOPTION_POLICY"),
        ("v3-relation-adoption-source", "F3_UNDERSTANDING_SOURCE_ADOPTION_POLICY"),
        ("v3-relation-adoption-source-answers", "F3_TYPED_QUESTION_ANSWER_POLICY"),
        ("v4-structured-conversation", "F3_STRUCTURED_UNDERSTANDING_POLICY"),
    )
    services = []
    previous_digest = None
    for index, (revision, variable) in enumerate(names):
        service = copy.copy(root)
        schema = (
            "conversation-understanding-wire.v4"
            if revision == "v4-structured-conversation"
            else "conversation-understanding-output.v3-relation-adoption-answers"
            if revision == "v3-relation-adoption-source-answers"
            else "conversation-understanding-output.v3-relation-adoption"
            if revision.startswith("v3-relation-adoption")
            else "conversation-understanding-output.v3-relation"
        )
        from agent_console.draft_assistance_policy import policy_for

        policy_for(revision, schema)
        service.profile = replace(
            root.profile,
            profile_revision_id=f"profile:bridge:{index}",
            profile_digest=hashlib.sha256(revision.encode()).hexdigest(),
            adapter_revision=revision,
            output_schema_version=schema,
        )
        service.budget = copy.copy(budget)
        service.budget.profile = service.profile
        limits = configured_limits(service.profile, config, service.budget)
        policy = dict(
            schemaVersion="f3-conversation-relation-admission.v1"
            if index == 0
            else "f3-conversation-relation-admission.v2",
            predecessorUnderstandingPolicyDigest=experience.understanding_policy_digest,
            sharedAllowanceId=allowance["allowanceId"],
            configuration=limits,
            externalWrites=False,
            scopeMode="EXISTING_BUSINESS_WORK"
            if index == 0
            else "EXISTING_WORK_AND_INITIAL_UNDERSTANDING",
        )
        if previous_digest is not None:
            policy["predecessorRoutingPolicyDigest"] = previous_digest
        monkeypatch.setenv(variable, private(tmp_path / f"policy-{index}.json", policy))
        previous_digest = digest(policy)
        services.append(service)
    planning_budget = copy.copy(budget)
    provider = PlanningResponsesProvider(config, root.profile, None)
    deps = PlanningInvocationDependencies(
        None, None, PlanningBudget(planning_budget), None, provider, b"k" * 32, None
    )
    plan_path = tmp_path / "renewal.json"
    if plan_enabled:
        private(
            plan_path,
            dict(
                schema_version="context-readmission.v1",
                issuer_id="human:approver",
                generation=1,
                recovery_epoch=1,
                authorization_evidence_digest="a" * 64,
                global_expires_at=allowance["expiresAt"],
                entries=[
                    dict(
                        context_id="not-dispatched-plan-entry",
                        subject_id="human:reader",
                        tenant_id="tenant-a",
                        security_domain="quality",
                        request_digest="b" * 64,
                        configuration=root_limits,
                        allowance_id=allowance["allowanceId"],
                        allowance_authorization_digest=allowance["authorizationDigest"],
                        prior_admission_id="not-approved-test-prior",
                        prior_record_digest="c" * 64,
                        idempotency_key="not-submitted",
                        expires_at=(
                            datetime.now(UTC) + timedelta(minutes=5)
                        ).isoformat(),
                        lease_mode="KEEP_EXPIRY",
                    )
                ],
            ),
        )
        monkeypatch.setenv("CONTEXT_CALL_READMISSION_PLAN", str(plan_path))
        monkeypatch.setenv(
            "CONTEXT_CALL_READMISSION_PLAN_SHA256",
            hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        )
    captured = []
    install = context_call_admission_api.install_context_call_admission

    def observe(service):
        captured.append(service)
        return install(service)

    monkeypatch.setattr(
        context_call_admission_api, "install_context_call_admission", observe
    )
    problem = PostgresBusinessProblemRepository(
        url, migration_path=ROOT / "0013_business_problem_authority.sql"
    )
    before = counters(e.service.repository)
    composition = None
    try:
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
            draft_assistance=root,
            prepared_resource_services=resource_services,
            prepared_execution_coordinator=__import__(
                "agent_console.prepared_native_coordinator",
                fromlist=["PreparedNativeCoordinator"],
            ).PreparedNativeCoordinator(repository=problem),
            conversation_routing=services[0],
            conversation_adoption=services[1],
            conversation_source_adoption=services[2],
            conversation_typed_answers=services[3],
            conversation_structured_understanding=services[4],
            planning_v2_enabled=True,
            planning_invocations=deps,
        )
        routes = {r.path for r in composition.application.routes}
        assert any(path.endswith("/delivery-acceptance") for path in routes)
        assert any("tool-tests" in path for path in routes)
        with e.service.repository.connection_scope() as c:
            assert c.execute(
                "SELECT to_regclass('prepared_delivery.events') n"
            ).fetchone()["n"]
            assert (
                c.execute(
                    "SELECT version FROM authorization_admin.mcp_tool_test_migrations"
                ).fetchone()["version"]
                == 76
            )
            assert (
                c.execute(
                    "SELECT version FROM draft_provider_budget.schema_migrations "
                    "WHERE version=75"
                ).fetchone()["version"]
                == 75
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.mcp_tool_test_requests"
                ).fetchone()["n"]
                == 0
            )
            assert (
                c.execute("SELECT count(*) n FROM prepared_delivery.events").fetchone()[
                    "n"
                ]
                == 0
            )
        assert len(captured) == 1
        registry = captured[0]
        assert len(registry.entries) == 7
        owners = [owner for _, owner in registry.entries]
        assert owners == [
            root.authorization.context_admission,
            root.authorization.context_admission.planning,
            *[s.authorization.context_admission for s in services],
        ]
        assert type(owners[1]) is PlanningCallAdmission
        assert owners[1].conversation_experience.understanding is owners[0]
        assert all(type(o) is ContextCallAdmission for o in owners[:1] + owners[2:])
        assert (registry.readmission_plan is not None) is plan_enabled
        expected = [
            root_limits,
            configured_limits(root.profile, config, planning_budget, planning=True),
            *[configured_limits(s.profile, config, s.budget) for s in services],
        ]
        assert [o.configuration for o in owners] == expected
        # Persist exact read probes, not model calls. No prior decisions are
        # manufactured and no plan entry is submitted by this bridge test.
        context = e.contexts["approver"]
        with registry.repository.connection_scope() as c:
            for index, ((phase, _owner), limits) in enumerate(
                zip(registry.entries, expected, strict=True)
            ):
                record = dict(phase=phase, configuration=limits)
                c.execute(
                    "INSERT INTO authorization_admin.context_call_requests "
                    "(context_id,tenant_id,security_domain,subject_id,account_id,"
                    "account_revision,first_invocation_id,record,digest) "
                    "VALUES(%s,%s,%s,%s,%s,1,%s,%s,%s)",
                    (
                        f"probe-{index}",
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        context.principal_id,
                        "absent-probe-account",
                        f"probe-invocation-{index}",
                        Jsonb(record),
                        digest(record),
                    ),
                )
        for index, owner in enumerate(owners):
            assert registry.owner(context, f"probe-{index}") is owner
        assert counters(e.service.repository) == before
        assert any(
            r.path.endswith("/authorization/context-admissions/{context_id}")
            for r in composition.application.routes
        )
    finally:
        if composition:
            composition.close()
        problem.pool.close()
        budget.close()
