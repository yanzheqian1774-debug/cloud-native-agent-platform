# ruff: noqa: F401,F811,RUF001 -- Original fixtures and Chinese domain text.
"""Actual published document7 resources on the original fixed service fixture.

Publication/Human BOUND setup and model output are controlled, never live facts.
The service registry, grant owner, Plan and START transactions remain original.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
import test_fixed_work_cycle_host_postgres as host
from agent_console.authority_contracts import AuthorityScope
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import OPERATIONS
from agent_console.native_typed_document_skill import (
    NativeTypedQuestionDocumentSkillExecutor as Executor,
)
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.readonly_continuation import ReadonlyContinuation
from agent_console.readonly_continuation_policy import (
    ReadonlyContinuationPolicy,
    ReadonlyWork,
)
from test_fixed_chat_delivery_postgres import automation as base_automation
from test_fixed_work_activity_read_postgres import repository, services
from test_native_document_tools import SOURCE
from test_planning_contracts import modern


@pytest.fixture
def case(repository, monkeypatch):
    import prepared_execution_support
    from agent_console.execution_domain import ScopeIdentity

    original_preparation = prepared_execution_support.preparation
    monkeypatch.setattr(
        prepared_execution_support,
        "preparation",
        lambda: original_preparation().model_copy(
            update={"namespace": "s5-323-demo", "security_domain": "isolated-real-demo"}
        ),
    )

    monkeypatch.setattr(
        host.original_case,
        "ScopeIdentity",
        lambda *_: ScopeIdentity("s5-323-demo", "isolated-real-demo"),
    )
    generator = host.case.__wrapped__(repository)
    e = next(generator)
    value = modern(OPERATIONS)
    value.update(
        target=e.p.semantics.target.model_dump(mode="json"),
        scenario="GENERAL_READ_ONLY",
        title="核对已授权的交接材料",
        business_rules=["只核对材料和规范，不执行上线或回退。"],
        boundaries=["只读合成资料，不写外部系统。"],
        requirements=[
            dict(
                requirement_id="employee",
                kind="EMPLOYEE",
                name="文档核对员工",
                purpose="核对材料",
                required=True,
                preparation="使用已发布资源",
            ),
            dict(
                requirement_id="snapshot",
                kind="KNOWLEDGE",
                name="资料快照",
                purpose="提供核对依据",
                required=True,
                preparation="使用已授权来源",
            ),
        ],
    )
    for n, task in enumerate(value["tasks"]):
        task.update(
            title=("读取资料", "核验资料", "核对差异", "返回报告")[n],
            responsibility="核对文档资料",
            criterion_revision_ids=value["target"]["criterion_revision_ids"],
            inputs=["资料快照"],
            outputs=[f"output-{n}"],
        )
    e.source = SOURCE
    e.p = e.p.model_copy(
        update={"semantics": type(e.p.semantics).model_validate(value)}
    )
    try:
        yield e
    finally:
        generator.close()


@pytest.fixture
def automation(repository, case, services, tmp_path, request, monkeypatch):
    import agent_console.sales_resource_bundle as bundle

    monkeypatch.setattr(
        bundle,
        "resource_content",
        lambda source: resource_content(
            source, rule_bound=True, durable_wait=True, typed_questions=True
        ),
    )
    from dataclasses import replace

    import test_fixed_work_activity_read_postgres as activity
    from agent_console.authority_configuration import (
        LocalAccountBinding,
        RequestabilityRule,
        StaticGrant,
    )
    from agent_console.authority_contracts import CredentialId, ExactGrant, GrantSource

    original_credential = activity.CredentialConfiguration

    def credential(*args, **kwargs):
        value = original_credential(*args, **kwargs)
        return (
            replace(value, principal_id="human:demo323-approver")
            if value.principal_id == "human:fixed-viewer"
            else value
        )

    monkeypatch.setattr(activity, "CredentialConfiguration", credential)
    from agent_console.conversation_experience_admission import LEDGER

    original_budget = host.PostgresProviderCallBudget

    def budget(*args, **kwargs):
        return original_budget(
            *args,
            **{
                **kwargs,
                "ledger_id": LEDGER,
                "call_cap": 20,
                "total_cost_cap_microusd": 1_000_000,
            },
        )

    monkeypatch.setattr(host, "PostgresProviderCallBudget", budget)

    original_generation = host.resources.StaticAuthorityGeneration

    def generation(*args, **kwargs):
        g = original_generation(*args, **kwargs)
        return replace(
            g,
            local_accounts=(
                LocalAccountBinding(
                    CredentialId("local-account:reviewer324"),
                    "reviewer324",
                    "human:demo323-approver",
                    AuthorityScope(case.scope.namespace, case.scope.security_domain),
                    CredentialId("viewer"),
                    tuple(
                        StaticGrant(grant, GrantSource.BROWSER_BOOTSTRAP)
                        for grant in (
                            ExactGrant("TEAM", "READ", "team:fixed-team:r"),
                            ExactGrant(
                                "BUSINESS_PROBLEM",
                                "READ",
                                "business-problem:"
                                + case.p.semantics.target.problem.resource_id,
                            ),
                            ExactGrant(
                                "KNOWLEDGE",
                                "READ_RESOURCE",
                                "knowledge:prepared-resource:"
                                + case.p.source_snapshot.resource_id
                                + ":"
                                + case.p.source_snapshot.revision_id,
                            ),
                        )
                    ),
                ),
            ),
            requestability=(
                *g.requestability,
                RequestabilityRule(
                    "BUSINESS_ONTOLOGY",
                    "USE",
                    "business-ontology:",
                    "READONLY_WORK_EXECUTION",
                ),
                RequestabilityRule(
                    "EXECUTION",
                    "QUESTION_ANSWER",
                    "governed-execution:question:",
                    "FIXED_QUESTION_ANSWER",
                ),
                *(
                    RequestabilityRule(
                        "DRAFT_ASSISTANCE", action, prefix, "PROBLEM_DRAFT_ASSISTANCE"
                    )
                    for action, prefix in (
                        ("REQUEST_DRAFT_ASSISTANCE", "draft-assistance:context:"),
                        (
                            "READ_DRAFT_ASSISTANCE_INVOCATION",
                            "draft-assistance:invocation:",
                        ),
                        (
                            "CANCEL_DRAFT_ASSISTANCE_INVOCATION",
                            "draft-assistance:invocation:",
                        ),
                    )
                ),
                RequestabilityRule(
                    "MODEL_GOVERNANCE",
                    "INVOKE_MODEL",
                    "model:",
                    "PROBLEM_DRAFT_MODEL_INVOKE",
                ),
            ),
        )

    monkeypatch.setattr(host.resources, "StaticAuthorityGeneration", generation)
    generator = base_automation.__wrapped__(
        repository, case, services, tmp_path, request, monkeypatch
    )
    a = next(generator)
    from agent_console.local_accounts import migrate as migrate_accounts
    from agent_console.local_accounts import operate

    migrate_accounts(a.authority)
    for account in a.gen.local_accounts:
        operate(
            a.authority,
            account,
            action="CREATE",
            command_id="document7-account",
            operator_id="operator:isolated",
            now=datetime.now(UTC),
            password="isolated-document7-password",
        )
    from agent_console.fixed_question_grants import QuestionGrantTargets
    from agent_console.ontology_authorization import OntologyTargets

    targets = a.automation.grants.target_validator
    targets.additional = (
        *targets.additional,
        OntologyTargets(),
        QuestionGrantTargets(),
    )
    from owned_business_consumer_support import configure_scope

    document = {"scopes": [{}]}
    setup = NS(
        repo=a.authority,
        context=NS(
            scope=AuthorityScope(a.e.scope.namespace, a.e.scope.security_domain)
        ),
        consumer_refs=a.refs,
    )
    with patch(
        "owned_business_consumer_support.NativeRuleDocumentSkillExecutor", Executor
    ):
        configure_scope(
            setup,
            {"inputSource": {"source": a.refs["knowledge"].model_dump(mode="json")}},
            document,
        )
    rules = document["scopes"][0]["documentRules"]
    original_work = ReadonlyWork

    def document_work(**kwargs):
        return original_work(**{**kwargs, "case": "document", "documentRules": rules})

    monkeypatch.setattr(host, "ReadonlyWork", document_work)
    native = PostgresExecutionAuthorityRepository(
        a.repository.pool.conninfo,
        migration_path=host.M / "0008_execution_runtime_authority.sql",
    )
    native.migrate_native_dispatch(host.M / "0022_native_execution_dispatch.sql")
    policy = ReadonlyContinuationPolicy(
        policyId="document7-service",
        policyVersion="1",
        enabled=True,
        works=(
            document_work(
                namespace=a.e.scope.namespace,
                securityDomain=a.e.scope.security_domain,
                subject=a.subject.principal_id,
                problem=a.e.p.semantics.target.problem,
                sourceContentDigests=a.policy.workScopes[0].sourceContentDigests,
                nativeAgentName="document7-service",
                expiresAt=datetime.now(UTC) + timedelta(hours=1),
            ),
        ),
    )
    a.automation.continuation = ReadonlyContinuation(
        a.automation, policy, PreparedNativeCoordinator(native)
    )
    from agent_console.ontology_execution import migrate as migrate_bindings

    with a.repository.pool.connection() as c:
        migrate_bindings(c)
    a.document_rules = rules
    try:
        yield a
    finally:
        native.pool.close()
        generator.close()
