# ruff: noqa: RUF001
"""Static Product projection guards for the S5-IMPL-041 correction gate."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text()


def test_business_timeline_has_required_semantic_deltas_and_no_primary_json() -> None:
    view = text("src/problems/ProblemPlanningPage.tsx")
    for label in (
        "已理解的问题",
        "已识别的对象和范围",
        "仍需确认的信息",
        "正在检索的知识",
        "已采用的知识依据",
        "初步判断",
        "新增的任务及依赖",
        "正在匹配的数字员工、Agent 和资源",
        "发现的能力缺口",
        "校验结果",
        "待人工审核计划",
    ):
        assert label in view
    assert "business-timeline" in view
    assert "<pre>{JSON.stringify({events,problem},null,2)}</pre>" in view
    assert "技术事件详情" in view
    assert "analysis-artifact" not in view


def test_heartbeat_is_one_updatable_semantic_record() -> None:
    view = text("src/problems/ProblemPlanningPage.tsx")
    assert 'key:"working"' in view
    assert "deltas.set(d.key,d)" in view
    assert "elapsedSeconds" not in view
    assert "心跳只更新此状态，不会重复添加业务记录" in view


def test_human_pause_replay_and_approval_states_are_consistent() -> None:
    view = text("src/problems/ProblemPlanningPage.tsx")
    api = text("src/api/problemPlanning.ts")
    assert 'event.eventType==="CLARIFICATION_SUBMITTED"' in view
    assert "继续同一分析流" in view
    assert "计划已批准，当前版本不执行" in view
    assert "正在调整计划" in view
    assert "等待人工审核" in view
    assert "批准精确当前计划版本" in view
    assert "replayProblemAnalysis" in view
    assert "response.body.getReader()" in api


def test_task_dag_and_governed_interventions_remain_visible() -> None:
    view = text("src/problems/ProblemPlanningPage.tsx")
    for claim in (
        "个唯一任务",
        "负责角色",
        "查看该任务的资源匹配",
        "确认采用授权知识来源",
        "接受能力缺口后续建议",
        "保存任务调整",
        "不可变版本",
    ):
        assert claim in view
    for binding in (
        "agentRevision",
        "skillRevisions",
        "mcpRevisions",
        "knowledgeSnapshotId",
        "runtimeRequirements",
    ):
        assert binding in view


def test_catalog_consumers_are_deduplicated_by_stable_task_id() -> None:
    directory = text("src/problems/PlanningDirectoryPage.tsx")
    assert "const byId=new Map<string,CatalogConsumer>()" in directory
    assert "byId.set(task.taskId" in directory
    assert "unique tasks" in directory
    assert "个唯一任务" in directory
    assert "/technical?selected=" in directory
    assert "Agent 定义（·）" not in directory


def test_mobile_and_desktop_layout_guards() -> None:
    css = text("src/styles/app.css")
    assert ".business-timeline" in css
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".v021-grid,.v021-dag { grid-template-columns:1fr; }" in css
    assert ".journey-navigator { position:relative" in css
    assert "overflow-wrap:anywhere" in css


def test_primary_navigation_keeps_dedicated_relationship_view() -> None:
    app = text("src/App.tsx")
    assert 'path="/relationships"' in app
    assert "对象关系" in app
    assert app.count("className={`semantic-graph") == 1
