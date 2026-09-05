from pathlib import Path

ROOT = Path(__file__).parents[3]
FRONTEND = ROOT / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (FRONTEND / path).read_text()


def test_chinese_first_product_shell_and_routes_are_wired() -> None:
    shell = source("components/ConsoleShell.tsx")
    app = source("App.tsx")
    for label in ("首页", "业务问题", "数字员工", "工作与流程", "知识", "能力资源"):
        assert label in shell
    assert 'path="/work" element={<ProblemWorkspacePage/>}' in app
    assert (
        'path="/workspace" element={<PlanningDirectoryPage kind="workspace"/>}' in app
    )
    assert "path={technicalPath}" in app
    assert 'aria-label={to==="/attention"?"Attention":undefined}' in shell


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
    assert "规划采用的知识引用" in workspace
    assert "不是执行成功证据" in workspace
    assert "getKnowledge" in workspace
    for knowledge_state in ("已发布", "已绑定", "已选择", "已检索", "已引用"):
        assert knowledge_state in workspace
    assert "尚无该页面可调用的 HTTP 投影" in workspace


def test_shared_styles_cover_desktop_narrow_and_keyboard_states() -> None:
    styles = source("styles/product-experience.css")
    assert "grid-template-columns:258px minmax(430px,1fr) 300px" in styles
    assert "@media(max-width:700px)" in styles
    assert ":focus-visible" in styles
    assert "overflow-x:auto" in styles
