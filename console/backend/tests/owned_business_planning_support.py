"""Same-case owner operations for the isolated mixed-lineage integration."""

# ruff: noqa: RUF001 -- Exact currently shipped Chinese completion rubric.

from agent_console.context_call_admission import bind_criterion
from agent_console.workbench_business_problem import business_problem_operations


def activate_created(e):
    """Use the actual BFF operation contracts, grants and owner; no direct inserts."""
    identity = e.created["revision"]["business_problem_id"]

    def binding(c, context, owner, result, **kw):
        assert owner == "SUCCESS_CRITERION"
        assert bind_criterion(c, context, result, kw["problem_id"])
        return result

    operations = {
        op.name: op
        for op in business_problem_operations(
            e.business_app,
            task_binding=binding,
        )
    }

    def perform(name, payload, path):
        operation = operations[name]
        grants = operation.grant_builder(e.context, path, payload, {})
        e.business_members.update(grants)
        e.business_work.before(e.context, name, payload, path, grants)
        return e.draft.authorization.owner_authorization.execute(
            e.context,
            grants,
            operation=name,
            payload=payload,
            path=path,
            query={},
            handler=operation.handler,
        )

    def detail():
        return perform("READ_PROBLEM", {}, {"problem_id": identity})

    criterion = perform(
        "WRITE_CRITERION",
        {
            "problemId": identity,
            "criterionType": "HUMAN_EVALUATED",
            "measurement": {
                "rubric": "回答已确认的用户目标："
                + e.created["revision"]["description"]
                + "。展示来源依据、异常与资料缺口；区分观察和推测。"
                "仅作为测试资料分析，不代表真实业务问题已经解决。"
            },
            "requiredEvidenceKinds": [],
            "evaluatorType": "HUMAN",
            "evaluatorVersion": "v1",
            "applicability": {
                "sourceReference": e.business_result["inputSource"]["source"]
            },
            "idempotencyKey": "owned-criterion",
        },
        {},
    )
    criteria = perform(
        "WRITE_CRITERIA_SET",
        {
            "problemRevisionId": e.created["revision"]["revision_id"],
            "orderedCriterionRevisionIds": [criterion["revision"]["revision_id"]],
            "expectedVersion": detail()["problem"]["aggregate_version"],
            "idempotencyKey": "owned-criteria-set",
        },
        {"problem_id": identity},
    )
    active = perform(
        "TRANSITION_PROBLEM",
        {
            "toState": "ACTIVE",
            "expectedVersion": detail()["problem"]["aggregate_version"],
            "idempotencyKey": "owned-activate",
        },
        {"problem_id": identity},
    )
    e.business_criterion, e.business_criteria = criterion, criteria
    e.business_active, e.business_detail = active, detail()
    return e


def planning_application(e):
    from agent_console.plan_suggestion_application import PlanningApplication
    from agent_console.plan_suggestion_authorization import PlanningCurrentAuthority
    from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
    from agent_console.workbench_business_problem import OwnerPrincipal

    repository = PostgresPlanningRepository(e.repo.pool)
    repository.migrate()
    authorization = e.admission.delegation.grants.authorization
    app = PlanningApplication(
        repository,
        e.business_repository,
        PlanningCurrentAuthority(e.context, authorization),
    )
    principal = OwnerPrincipal(
        e.context.principal_id,
        e.context.scope.tenant_id,
        e.context.scope.security_domain,
    )
    with e.repo.connection_scope() as c:
        current = app.current_input(
            principal,
            e.created["revision"]["business_problem_id"],
            c,
        )
    e.consumer_planning_app, e.consumer_planning_principal = app, principal
    e.consumer_planning_input = current
    return app, principal, current


def governed_planning_service(e, semantics):
    """Real planning/admission/grants/ledger; only model resolution/output fixtures."""
    import json
    from contextlib import contextmanager
    from dataclasses import replace
    from pathlib import Path
    from types import SimpleNamespace

    from agent_console.conversation_planning_admission import (
        ConversationPlanningAdmission,
    )
    from agent_console.draft_assistance import ProviderBudgetQuote
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
    from agent_console.model_binding_resolution import ExactModelUse, ModelUseAction
    from agent_console.model_governance_authorization import (
        ModelUseAuthorizationAdapter,
    )
    from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
    from agent_console.plan_model_use_postgres import PostgresPlanModelUseOwner
    from agent_console.plan_suggestion_domain import ExactReference
    from agent_console.plan_suggestion_invocation import (
        PlanningProfile,
        PlanningRequest,
    )
    from agent_console.plan_suggestion_runtime import PlanningBudget
    from agent_console.plan_suggestion_service import PlanningSuggestionService
    from agent_console.planning_call_admission import (
        BoundPlanningAdmission,
        PlanningCallAdmission,
    )

    app, principal, current = planning_application(e)
    assert semantics.target.model_dump(mode="json") == current["target"]
    model = e.draft.profile.binding
    profile = PlanningProfile(
        profile_revision_id=e.draft.profile.profile_revision_id,
        profile_digest=e.draft.profile.profile_digest,
        model=ExactReference(
            resource_id=model.resource_id,
            revision_id=model.revision_id,
            digest=model.digest,
        ),
        adapter_id="controlled-owned-business-planning",
        adapter_revision="1",
        maximum_input_bytes=65536,
        maximum_output_tokens=500,
    )
    admission = PlanningCallAdmission(
        e.admission.delegation, e.business_planning.configuration
    )
    admission.migrate()
    admission.conversation_experience = ConversationPlanningAdmission(
        e.admission, admission.configuration
    )
    invocations = PostgresPlanningInvocations(app.repository)
    invocations.migrate()
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=replace(e.draft.profile, maximum_output_tokens=500),
        ledger_id=e.business_owner.policy.ledgerId,
        call_cap=20,
        total_cost_cap_microusd=1_000_000,
        input_price_microusd_per_million_tokens=0,
        output_price_microusd_per_million_tokens=0,
        allowance_id=e.business_owner.policy.allowanceId,
    )
    budget.delegation_configuration = admission.configuration
    budget.owned_business = e.business_owner.work_reader

    class Provider:
        synthetic = True
        calls = 0

        def suggest(self, request, binding, profile, business_context):
            self.calls += 1
            assert business_context["target"] == current["target"]
            return json.dumps(
                {
                    "kind": "VALID_SUGGESTION",
                    "semantics": semantics.model_dump(mode="json"),
                }
            )

    provider = Provider()

    def resolve(scope, binding):
        assert binding == model
        # The model resolver is explicitly controlled, while exact invocation
        # authority is evaluated by the real ModelUseAuthorizationAdapter above.
        from agent_console.model_governance import ModelScope

        resolved = e.draft.model_resolver.resolve_exact(
            e.draft.profile,
            ExactModelUse(
                model,
                ModelUseAction.INVOKE_MODEL,
                admission.configuration["model_target"],
            ),
        )
        return replace(
            resolved,
            scope=scope,
            eligibility=replace(
                resolved.eligibility,
                scope=ModelScope(scope.namespace, scope.security_domain),
            ),
        )

    service = PlanningSuggestionService(
        app,
        invocations,
        profile,
        model_authorizer=ModelUseAuthorizationAdapter(
            e.context, e.admission.delegation.grants.authorization
        ),
        model_resolver=SimpleNamespace(resolve_exact=resolve),
        budget=PlanningBudget(budget),
        quote=ProviderBudgetQuote(1000, 500, 0),
        provider=provider,
        model_use_owner=PostgresPlanModelUseOwner(app.repository),
        commitment_key=b"isolated-owned-planning-commitment-not-a-secret",
        prepare_resources=lambda *_: None,
        exact_admission=BoundPlanningAdmission(admission, e.context),
    )
    request = PlanningRequest(
        target=semantics.target,
        policy=semantics.policy,
        answers=semantics.boundaries,
        idempotency_key="owned-actual-plan",
    )

    if getattr(e, "consumer_question_input", None) is not None:
        request = PlanningRequest.model_validate(
            e.consumer_question_input["planningRequest"]
        )

    @contextmanager
    def opened():
        try:
            yield service, principal, request, provider
        finally:
            budget.close()

    return opened()


def document_semantics(e, target):
    """Controlled model response grounded in this same case's published resources."""
    from agent_console.native_document_skill import OPERATIONS
    from agent_console.plan_suggestion_domain import FlexiblePlanSemantics
    from test_conversation_planning_source import boundary
    from test_planning_contracts import modern

    value = modern(OPERATIONS)
    value.update(
        scenario="GENERAL_READ_ONLY",
        target=target,
        title="核对本次生产上线交接材料",
        business_rules=[
            "分别核对交接说明对象与生产规范，不能把规范当检查对象。",
            "报告冲突、缺失和不确定项；字段存在不代表业务验证已通过。",
        ],
        boundaries=[
            boundary(e.consumer_refs["knowledge"].model_dump()),
            "仅检查合成资料；不执行上线或外部写入。",
        ],
        requirements=[
            {
                "requirement_id": "employee",
                "kind": "EMPLOYEE",
                "name": "已发布文档核查员工",
                "purpose": "执行只读资料核查",
                "required": True,
                "preparation": "核对当前精确版本和授权",
                "selected": e.consumer_employee.model_dump(),
            },
            {
                "requirement_id": "snapshot",
                "kind": "KNOWLEDGE",
                "name": "已选交接说明与规范",
                "purpose": "提供对象及检查依据",
                "required": True,
                "preparation": "核对当前精确内容摘要",
                "selected": e.consumer_refs["knowledge"].model_dump(),
            },
        ],
    )
    titles = (
        "读取交接说明及规范",
        "检查资料角色和范围",
        "定位交接缺口",
        "返回核查报告",
    )
    for i, task in enumerate(value["tasks"]):
        task.update(
            title=titles[i],
            responsibility="文档核查职责",
            criterion_revision_ids=target["criterion_revision_ids"],
            inputs=["已选合成资料" if i == 0 else f"document-output-{i - 1}"],
            outputs=[f"document-output-{i}"],
        )
    return FlexiblePlanSemantics.model_validate(value)


def generate_proposal(e, *, before_planning=None):
    activate_created(e)
    _, _, current = planning_application(e)
    if before_planning is not None:
        before_planning(e, current)
    semantics = document_semantics(e, current["target"])
    with governed_planning_service(e, semantics) as (
        service,
        principal,
        request,
        provider,
    ):
        result = service.begin(principal, request)
        assert result["result"]["technical_status"] == "SUCCEEDED", result
        assert result["result"]["kind"] == "VALID_SUGGESTION", result
        assert result["result"]["proposal"]["semantics"]["target"] == current["target"]
        repeat = service.begin(principal, request)
        assert repeat["result"] == result["result"]
        assert provider.calls == 1
    e.consumer_planning_result = result
    e.consumer_proposal = result["result"]["proposal"]
    return e
