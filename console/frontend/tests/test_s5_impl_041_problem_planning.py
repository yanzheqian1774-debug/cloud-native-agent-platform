# ruff: noqa: RUF001
"""Static Product/Technical acceptance guard for S5-IMPL-041."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text()


def test_problem_first_navigation_and_dynamic_plan_ui() -> None:
    app = text("src/App.tsx")
    view = text("src/problems/ProblemPlanningPage.tsx")
    assert 'path="/problems"' in app
    for label in (
        "业务问题",
        "计划与任务",
        "数字员工与 Agent",
        "Skills（技能）· MCP · 知识",
        "运行环境要求",
        "对象关系",
        "技术视图",
    ):
        assert label in app
    for claim in (
        "知识带来的变化",
        "动态任务依赖图",
        "待审核计划",
        "保存摘要为新修订版本",
        "批准精确当前计划版本",
        "计划已批准（当前版本暂不执行）",
        "原始 JSON（技术附录）",
    ):
        assert claim in view
    assert "当前版本暂不执行" in view


def test_mobile_layout_has_single_column_breakpoint() -> None:
    css = text("src/styles/app.css")
    assert ".v021-grid,.v021-dag { grid-template-columns:1fr; }" in css
    assert ".v021-compare { overflow-x:auto; }" in css


def test_relationship_graph_is_deduplicated_and_contextual() -> None:
    app = text("src/App.tsx")
    css = text("src/styles/app.css")
    assert 'path="/relationships"' in app
    assert app.count("className={`semantic-graph") == 1
    assert "完整对象关系" in app
    assert "关系对象类型" in app
    assert "查看精确技术身份与修订" in app
    assert "返回原上下文" in app
    assert 'section==="relationships"' in app
    assert "RelationshipSummary" in app
    assert "grid-template-columns: minmax(0,1fr)" in css
    assert ".relationship-panel.dedicated .semantic-node" in css


def test_progress_approval_localization_and_canonical_directories() -> None:
    app = text("src/App.tsx")
    view = text("src/problems/ProblemPlanningPage.tsx")
    directory = text("src/problems/PlanningDirectoryPage.tsx")
    api = text("src/api/problemPlanning.ts")
    for claim in (
        "当前阶段：正在检索知识并生成计划",
        "已完成：",
        "剩余：",
        "比较进行中，请勿重复提交",
        "规划超时",
        "知识带来的变化",
        "计划已批准（当前版本暂不执行）",
        "本次审批已绑定当前计划版本及校验摘要",
    ):
        assert claim in view
    assert "setAction(kind)" in view and "正在审批当前版本" in view
    assert "PlanningRequestError" in api and "PLANNING_TIMEOUT" in api
    for kind in (
        "workspace",
        "plans",
        "agents",
        "resources",
        "runtime",
        "relationships",
        "technical",
    ):
        assert f'kind="{kind}"' in app
    for binding in (
        "agentRevision",
        "skillRevisions",
        "mcpRevisions",
        "knowledgeSnapshotId",
        "runtimeRequirements",
    ):
        assert binding in directory
    assert "原始 JSON（技术附录）" in view
    assert "Raw JSON (technical appendix)" in view


def test_primary_journey_and_governed_intervention_are_visible() -> None:
    view = text("src/problems/ProblemPlanningPage.tsx")
    api = text("src/api/problemPlanning.ts")
    for stage in (
        "提出业务问题",
        "理解与确认问题",
        "检索相关知识",
        "搜索解决方案蓝图",
        "拆解任务与依赖",
        "匹配数字员工、Agent 和资源",
        "识别能力缺口",
        "人工调整",
        "生成可审核计划",
        "审批当前计划版本",
        "当前版本暂不执行",
    ):
        assert stage in view
    for intervention in (
        "问题理解与确认",
        "知识选择",
        "解决方案蓝图",
        "任务拆解调整",
        "资源匹配选择",
        "能力缺口决定",
        "前后差异、原因与摘要",
    ):
        assert intervention in view
    assert "/interventions" in api
    assert "predecessorDigest" in api
    assert "采用方案 B 并返回当前业务问题" in view
    assert "次要证据工具" in view


def test_enterprise_catalog_relationship_and_status_patterns() -> None:
    directory = text("src/problems/PlanningDirectoryPage.tsx")
    css = text("src/styles/app.css")
    for claim in (
        "搜索目录",
        "状态筛选",
        "使用者筛选",
        "MCP 服务",
        "MCP 工具",
        "MCP 操作",
        "目录状态",
        "操作权限",
        "有向关系图",
        "展开下一层",
        "适配屏幕并重置",
        "产生",
        "包含",
        "分配给",
        "调用",
    ):
        assert claim in directory
    for code in ("DE-", "AGT-", "SKL-", "MSV-", "MTL-", "MOP-", "KB-", "DOC-"):
        assert code in directory
    assert ".catalog-master-detail" in css
    assert ".typed-edge" in css


def test_real_ai_analysis_streaming_and_structured_artifacts() -> None:
    view = text("src/problems/ProblemPlanningPage.tsx")
    api = text("src/api/problemPlanning.ts")
    app = text("../backend/src/agent_console/app.py")
    for claim in (
        "实时 AI 辅助问题分析",
        "实时结构化分析",
        "问题理解",
        "知识依据",
        "初步判断",
        "任务拆解与依赖",
        "资源匹配",
        "计划校验",
        "等待人工补充信息",
        "提交补充信息并恢复规划",
        "返回当前进度",
        "不展示隐藏思维链",
        "服务器实时 SSE；不是完成结果回放",
    ):
        assert claim in view
    assert "response.body.getReader()" in api
    assert "beginProblemAnalysis" in api and "resumeProblemAnalysis" in api
    assert "text/event-stream" in app
    assert "Math.floor(elapsed" not in view
