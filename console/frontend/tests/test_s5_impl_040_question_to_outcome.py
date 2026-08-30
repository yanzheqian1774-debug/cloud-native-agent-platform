"""S5-IMPL-040 question-to-outcome presentation contract tests."""
# ruff: noqa: RUF001

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_question_is_explicit_and_suggestion_does_not_auto_submit() -> None:
    view = source("src/product/QuestionToOutcomeJourney.tsx")
    api = source("src/api/supplierQualityDemo.ts")
    assert "你希望解决什么问题？" in view
    assert "setQuestion(suggested)" in view
    assert "onClick={start}" in view
    assert "question," in api
    assert "useEffect(()=>{start" not in view


def test_access_denial_is_chinese_first_with_secondary_technical_reason() -> None:
    view = source("src/product/QuestionToOutcomeJourney.tsx")
    assert "当前无法进入供应商质量演示" in view
    assert (
        "你当前的访问环境未获得此演示的使用授权。系统没有启动分析或执行任务。" in view
    )
    assert "重新检查演示环境" in view
    assert "返回问题输入" in view
    assert "查看技术原因" in view and "Technical Details" in view
    assert '<span className="technical-value">{error.reasonCode}</span>' in view
    assert 'error?.reasonCode==="SUPPLIER_QUALITY_DEMO_ACCESS_DENIED"' in view


def test_review_precedes_exact_approval_and_explicit_execution() -> None:
    view = source("src/product/QuestionToOutcomeJourney.tsx")
    assert "确认系统理解" in view
    assert "问题拆解" in view
    assert "审查解决计划和数字员工团队" in view
    assert "submitExactApproval" in view
    assert "requestBoundedRerun" in view
    assert view.index("submitExactApproval") < view.index("requestBoundedRerun")


def test_product_and_technical_views_do_not_claim_unstarted_execution() -> None:
    product = source("src/product/QuestionToOutcomeJourney.tsx")
    technical = source("src/pages/TechnicalViewPage.tsx")
    assert "不是持久化 Task 权威" in product
    assert "不是模型自由推理结果" in product
    assert "不会自动启动旅程" in technical
    assert "liveJourney?.successor.outcome" in technical


def test_chinese_is_default_and_mobile_layout_is_present() -> None:
    messages = source("src/i18n/messages.ts")
    styles = source("src/styles/app.css")
    assert 'DEFAULT_LOCALE: Locale = "zh-CN"' in messages
    assert "@media (max-width: 700px)" in styles


def test_dependency_dag_uses_declared_dependencies_and_one_selected_detail() -> None:
    view = source("src/product/QuestionToOutcomeJourney.tsx")
    assert "task.dependencies.length>0" in view
    assert 'aria-label={`${task.dependencies.join(",")} → ${task.taskId}`}' in view
    assert "setSelectedTaskId(task.taskId)" in view
    assert "所选任务详情" in view
    assert "计划与执行任务依赖图" in view


def test_result_has_bounded_evidence_chain_and_governed_follow_up() -> None:
    view = source("src/product/QuestionToOutcomeJourney.tsx")
    for label in (
        "数据或知识来源",
        "引用",
        "Evidence",
        "分析发现",
        "业务结论",
        "整改动作",
        "执行结果",
        "主要发现",
        "根因",
        "整改措施",
    ):
        assert label in view
    assert "<InterventionFeedback journeyId={journey.journeyId}" in view
    assert "查看该结论的证据关系" in view
    assert 'technical("EVIDENCE"' in view


def test_team_is_prominent_and_directory_is_bounded_to_current_snapshot() -> None:
    directory = source("src/product/DigitalEmployeeDirectory.tsx")
    assert "当前 Demo 可用的数字员工" in directory
    assert "团队准备度摘要" in directory
    assert "当前范围：受控供应商质量 Demo" in directory
    assert "不代表企业全部数字员工和能力" in directory
    assert "tasks.map" in directory
    assert "fetch(" not in directory
    assert "first.requiredRole" in directory
    assert "first.matchedRole" in directory
    assert "当前 Demo 可用的能力与资源" in directory
    for action in (
        "查看业务职责",
        "查看能力与资源",
        "查看技术实现",
        "查看本次参与记录",
    ):
        assert action in directory
    assert "unique(agent.tasks.map(task => task.purpose))" not in directory
    for resource in (
        "Agent Definitions",
        "Skills",
        "MCP Servers",
        "Knowledge Packs",
        "Runtimes",
    ):
        assert resource in directory


def test_resource_taxonomy_keeps_categories_and_semantics_distinct() -> None:
    directory = source("src/product/DigitalEmployeeDirectory.tsx")
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    for category in (
        "业务能力（Business Capabilities）",
        "技能（Skills）",
        "MCP与工具（MCP Servers, Capabilities and Operations）",
        "知识库（Knowledge Packs）",
        "当前 Demo Runtime（Runtimes）",
    ):
        assert category in directory
    assert "业务能力回答任务“需要什么能力”" in technical
    assert "Skill 回答“如何完成”" in technical
    assert "Knowledge 回答“依据什么判断”" in technical
    assert "MCP Server、Capability、Operation/Tool 与实际调用记录保持分离" in technical
    assert "businessCapabilities=unique(" in technical
    assert "revision.projectedTasks.flatMap(task=>task.actions)" in technical
    assert "Model" not in directory


def test_runtime_scene_distinguishes_definition_execution_runtime_and_outputs() -> None:
    directory = source("src/product/DigitalEmployeeDirectory.tsx")
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    assert "本次运行现场" in technical and "Execution Runtime" in technical
    assert "数字员工定义" in technical and "Agent Definition" in technical
    assert "本次执行身份" in technical and "Platform Execution Identity" in technical
    assert "未创建独立持久化数字员工实例" in technical
    assert "Runtime / Placement" in technical
    assert "Execution Timeline" in technical
    assert "Execution Outputs" in technical
    assert "event.eventId" in technical
    assert "event.occurredAt" in technical
    assert "event.reasonCode" in technical
    assert "identity.platformExecutionIdentity" in directory
    assert "identity.placementDecisionId" in directory


def test_missing_runtime_facts_and_sensitive_environment_are_not_fabricated() -> None:
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    assert "当前版本尚未采集该运行信息。" in technical
    assert "NATIVE_PROVIDER" not in technical
    for forbidden in (
        "process.env",
        "import.meta.env",
        "localhost",
        "127.0.0.1",
        "/Users/",
        "token usage",
        "CPU",
        "GPU",
    ):
        assert forbidden not in technical


def test_bidirectional_navigation_preserves_selected_context_without_mutation() -> None:
    product = source("src/product/QuestionToOutcomeJourney.tsx")
    product_page = source("src/pages/ProductViewPage.tsx")
    technical_page = source("src/pages/TechnicalViewPage.tsx")
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    assert 'query.set("taskId",taskId)' in product
    assert "revisionId:" in product and "snapshotId:" in product
    assert "navigate(`/technical?${query}`)" in product
    assert 'next.set("step",step)' in technical
    assert "navigate(`/product?${next}`)" in technical
    assert 'to={{ pathname: "/technical", search }}' in product_page
    assert 'to={{ pathname: "/product", search }}' in technical_page
    assert "submitExactApproval" not in technical
    assert "requestBoundedRerun" not in technical


def test_technical_view_is_structured_chinese_first_with_collapsed_raw_appendix() -> (
    None
):
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    for module in (
        "供应商质量整改工作流",
        "数字员工",
        "业务能力",
        "技能",
        "MCP与工具",
        "知识与引用",
        "运行环境与执行位置",
        "执行事件",
        "证据与业务结果",
    ):
        assert module in technical
    for term in (
        "Plan and Workflow",
        "Agent Definitions",
        "Business Capabilities",
        "Skills",
        "MCP Servers, Capabilities and Operations",
        "Raw JSON",
    ):
        assert term in technical
    assert '<details className="raw-json">' in technical
    assert (
        "JSON.stringify({identity,revision,selected:{objectType,objectId}},null,2)"
        in technical
    )
    assert "NOT_EXPOSED" in technical
    assert 'relatedTasks("skills",id)' in technical
    assert 'relatedTasks("mcpCapabilities",id)' in technical
    assert 'relatedTasks("knowledgeRefs",id)' in technical


def test_stepper_is_clickable_but_gated_and_review_only() -> None:
    view = source("src/product/QuestionToOutcomeJourney.tsx")
    assert "aria-disabled={index>stage}" in view
    assert "if(index<=stage)" in view
    assert "lockedExplanation" in view
    assert "需要先完成前置旅程步骤" in view
    assert "仅切换当前查看，不改变旅程进度" in view
    assert "旅程当前进度" in view
    assert "当前查看" in view
    assert "qto-mobile-steps" in view


def test_workspace_first_navigation_and_contextual_technical_tabs() -> None:
    app = source("src/App.tsx")
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    for route in ("/workspace", "/tasks", "/employees", "/resources", "/runtime"):
        assert route in app
    for label in ("工作台", "任务", "数字员工", "能力与资源", "运行环境"):
        assert label in app
    for label in ("对象关系", "工作流", "执行现场", "事件", "Evidence", "原始数据"):
        assert label in technical
    assert "data-active-section={technicalSection}" in technical


def test_complete_approval_and_truthful_state_projections() -> None:
    product = source("src/product/QuestionToOutcomeJourney.tsx")
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    for label in (
        "审批用于确认业务目标",
        "计划摘要",
        "依赖关系",
        "参与数字员工",
        "资源、风险与影响",
        "计划审批状态",
        "执行授权状态",
        "任务执行状态",
        "旅程总体状态",
        "审批人",
        "审批时间",
        "批准计划",
        "拒绝",
        "退回修改",
        "查看修订差异",
        "查看精确技术标识",
    ):
        assert label in product
    assert 'revision.approvalState==="PENDING"' in product
    assert 'revision.approvalState==="APPROVED"' in product
    assert 'revision.approvalState==="REJECTED"' in product
    assert 'revision.executionState==="FAILED"' in product
    assert 'revision.projectedTasks.some(task=>task.state==="RUNNING")' in product
    assert "已批准参与执行" not in technical
    assert "查看原始状态枚举" in technical


def test_workflow_and_evidence_are_business_first_with_collapsed_identities() -> None:
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    for label in (
        "提供输入",
        "完成后进入",
        "生成计划",
        "批准后执行",
        "产生结果",
        "Human 审批边界",
        "受控执行边界",
        "查看精确技术标识",
        "数据或知识来源",
        "Evidence 证明什么",
        "来源分类",
    ):
        assert label in technical
    assert "shortId(identity.canonicalWorkflowRevisionId)" in technical
    assert "查看 Evidence 与 Outcome 技术标识" in technical


def test_typography_and_status_semantics_are_bounded_and_accessible() -> None:
    styles = source("src/styles/app.css")
    product = source("src/product/QuestionToOutcomeJourney.tsx")
    directory = source("src/product/DigitalEmployeeDirectory.tsx")
    technical = source("src/technical/LivePlanningJourneyPanel.tsx")
    for size in ("28px", "20px", "17px", "15px", "13px"):
        assert size in styles
    for family in (
        "status-success",
        "status-running",
        "status-warning",
        "status-human",
        "status-failure",
        "status-unavailable",
    ):
        assert family in styles
    assert 'aria-hidden="true"' in product
    assert 'aria-hidden="true"' in directory
    assert 'aria-hidden="true"' in technical
    assert "TechnicalStatus value={revision.executionState}" in technical
    assert "technical-value" in technical
