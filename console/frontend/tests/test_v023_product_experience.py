from pathlib import Path

ROOT = Path(__file__).parents[3]
FRONTEND = ROOT / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (FRONTEND / path).read_text()


def test_chinese_first_product_shell_and_routes_are_wired() -> None:
    shell = source("components/ConsoleShell.tsx")
    app = source("App.tsx")
    for label in (
        "首页",
        "业务问题",
        "数字员工",
        "Skill",
        "Knowledge",
        "Evidence",
        "Outcome",
    ):
        assert label in shell
    assert 'path="/work" element={<ProblemWorkspacePage/>}' in app
    assert (
        'path="/workspace" element={<PlanningDirectoryPage kind="workspace"/>}' in app
    )
    assert "path={technicalPath}" in app
    assert 'aria-label={to==="/attention"?"Attention":undefined}' in shell


def test_w2a_shell_uses_session_facts_and_marks_unavailable_controls() -> None:
    shell = source("components/ConsoleShell.tsx")
    assert "readWorkbenchSession" in shell
    assert "new AbortController()" in shell
    assert "request?.abort()" in shell
    assert "readWorkbenchSession(controller.signal)" in shell
    assert "session.principal.principalId" in shell
    assert (
        'document.addEventListener("visibilitychange",refreshVisibleSession)' in shell
    )
    assert 'window.addEventListener("focus",refreshFocusedSession)' in shell
    assert 'window.removeEventListener("focus",refreshFocusedSession)' in shell
    assert "request===controller" in shell
    assert "当前可信身份" in shell
    assert "未显示可信身份" in shell
    assert "审核人员" not in shell
    assert "px-notification" not in shell
    assert "⌘ K" not in shell
    assert 'aria-label="全局搜索\uff08暂未接线\uff09"' in shell
    assert "全局搜索暂未接线" in shell
    assert '<Link to="/work">可信问题工作台</Link>' in shell


def test_w2a_keeps_legacy_planning_ids_out_of_the_trusted_problem_route() -> None:
    home = source("dashboard/ProductDashboardPage.tsx")
    evidence = source("evidence/EvidenceCenterPage.tsx")
    outcomes = source("outcomes/OutcomeCenterPage.tsx")
    directory = source("problems/PlanningDirectoryPage.tsx")
    assert 'className="px-primary-button" to="/work">提出业务问题' in home
    assert "/work?problem=" not in home
    assert "/work?problem=" not in evidence
    assert "/work?problem=" not in outcomes
    for marker in ("旧规划来源", "v0.2.1", "不属于当前 /work 权威"):
        assert marker in home
    assert "这些记录不会作为 ID 进入当前 /work Problem 权威" in evidence
    assert "旧规划 ID 不会进入当前 /work Problem 权威" in outcomes
    for marker in (
        "搜索计划\uff08暂未接线\uff09",
        "状态筛选\uff08暂未接线\uff09",
        "业务问题筛选\uff08暂未接线\uff09",
        "排序\uff08暂未接线\uff09",
    ):
        assert marker in directory
    assert directory.count(" disabled") >= 4


def test_home_uses_authorized_projections_and_truthful_unavailable_states() -> None:
    home = source("dashboard/ProductDashboardPage.tsx")
    for projection in (
        "getProductDashboard",
        "listDigitalEmployeeTemplates",
        "listProblems",
        "listAttention",
    ):
        assert projection in home
    for label in ("模板不代表运行实例", "暂不可用", "规划中", "建设中"):
        assert label in home
    for fabricated_metric in ("98.3%", "128.6", "24.5", "2.45"):
        assert fabricated_metric not in home
    assert '<h2 className="sr-only">Dashboard</h2>' in home


def test_problem_workspace_preserves_governed_execution_boundaries() -> None:
    workspace = source("problems/ProblemWorkspacePage.tsx")
    for concept in (
        "成功标准",
        "数字员工",
        "Workflow / Plan",
        "Human Intervention",
        "Evidence",
        "Outcome",
    ):
        assert concept in workspace
    for truthful_state in ("未配置", "未绑定", "未执行", "暂不可用", "执行失败"):
        assert truthful_state in workspace
    assert "只有 Attempt 事实才能证明本次实际使用" in workspace
    assert "当前不接入模型分析或任务执行" in workspace
    assert "getKnowledge" not in workspace
    assert "listDigitalEmployeeTemplates" not in workspace


def test_problem_rematch_exposes_one_authoritative_accessible_lifecycle() -> None:
    planning = source("problems/ProblemPlanningPage.tsx")
    api = source("api/problemPlanning.ts")
    assert 'type RematchState="idle"|"pending"|"succeeded"|"failed"' in planning
    assert 'setRematchState("pending")' in planning
    assert (
        "const authoritativeProblem=await rematchProblem(problem.problemId)" in planning
    )
    assert planning.count("rematchProblem(problem.problemId)") == 1
    assert planning.index("setProblem(authoritativeProblem)") < planning.index(
        'setRematchState("succeeded")'
    )
    assert "disabled={busy} onClick={rematch}" in planning
    assert 'role="status" aria-label="重新匹配状态" aria-live="polite"' in planning
    assert "正在重新匹配已发布的 Agent 定义……" in planning
    assert "已完成重新匹配" in planning
    assert 'rematchState==="failed"' in planning
    assert 'role="alert"' in planning
    assert "重新匹配失败\uff0c请检查当前状态后重试" in planning
    assert (
        api.count(
            'request<ProblemPlan>(`/api/internal/v0.2.1/problems/${encodeURIComponent(id)}/rematches`,{method:"POST"}'
        )
        == 1
    )


def test_shared_styles_cover_desktop_narrow_and_keyboard_states() -> None:
    styles = source("styles/product-experience.css")
    assert "grid-template-columns:258px minmax(430px,1fr) 300px" in styles
    assert "@media(max-width:700px)" in styles
    assert ":focus-visible" in styles
    assert "overflow-x:auto" in styles
    for selector in (
        ".px-workspace .px-form-fields",
        ".px-workspace .px-form-actions",
        ".px-workspace .px-workbench-error",
        ".px-admin-page .px-admin-status",
        ".px-admin-page .px-field",
    ):
        assert selector in styles
    assert "env(safe-area-inset-bottom)" in styles
