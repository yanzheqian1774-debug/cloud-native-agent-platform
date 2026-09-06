from pathlib import Path

ROOT = Path(__file__).parents[3]
FRONTEND = ROOT / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (FRONTEND / path).read_text()


def test_wave_1_has_ten_first_class_routes_and_chinese_navigation() -> None:
    app = source("App.tsx")
    shell = source("components/ConsoleShell.tsx")
    routes = (
        "/dashboard",
        "/work",
        "/digital-employees",
        "/skills",
        "/mcp",
        "/knowledge",
        "/workflow-definitions",
        "/runtime-profiles",
        "/evidence",
        "/outcomes",
    )
    for route in routes:
        assert route in app
        assert route in shell
    for label in (
        "首页",
        "业务问题",
        "数字员工",
        "Skill",
        "MCP",
        "Knowledge",
        "Workflow",
        "Runtime",
        "Evidence",
        "Outcome",
    ):
        assert label in shell


def test_evidence_center_uses_real_problem_projection_without_claiming_execution() -> (
    None
):
    evidence = source("evidence/EvidenceCenterPage.tsx")
    for marker in ("REAL", "NOT_CONNECTED", "UNAVAILABLE"):
        assert marker in evidence
    for fact in (
        "knowledge.citations",
        "humanDecisions",
        "approval.evidence",
        "events",
    ):
        assert fact in evidence
    assert "不代表执行成功" in evidence
    assert "本页不会模拟成功" in evidence
    assert "产品视图" in evidence and "技术视图" in evidence


def test_outcome_center_never_turns_missing_authority_into_zero_or_success() -> None:
    outcome = source("outcomes/OutcomeCenterPage.tsx")
    for phrase in (
        "尚未采集",
        "不可度量",
        "NOT_CONNECTED",
        "不显示 0",
        "不把计划批准当作业务成功",
    ):
        assert phrase in outcome
    assert "产品视图" in outcome and "技术视图" in outcome
    assert "canonicalDigest" in outcome


def test_digital_employee_keeps_core_concepts_separate() -> None:
    employee = source("digital-employees/DigitalEmployeesPage.tsx")
    for concept in (
        "Agent Definition",
        "Agent Instance",
        "Runtime Instance",
        "Application",
        "执行权限固定为 NONE",
    ):
        assert concept in employee
    for state in ("REAL", "NOT_CONNECTED", "UNAVAILABLE", "未执行", "尚未采集"):
        assert state in employee


def test_wave_1_new_surfaces_have_responsive_and_focus_foundations() -> None:
    styles = source("styles/product-experience.css")
    assert ".px-center-page,.agent-workbench{overflow-x:hidden}" in styles
    assert ".px-record-list>article{grid-template-columns:1fr" in styles
    assert ".px-shell :focus-visible" in styles
