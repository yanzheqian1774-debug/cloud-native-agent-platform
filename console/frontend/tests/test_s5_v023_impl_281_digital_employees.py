from pathlib import Path

ROOT = Path(__file__).parents[3] / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_employee_management_uses_independent_real_http_authority() -> None:
    api = source("api/digitalEmployees.ts")
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    for operation in ("/definitions", "/instances", "/assignments"):
        assert operation in api
    assert 'action:"validate"|"approve"|"publish"' in api
    assert "employeeDefinitionId" in api
    assert "employeeDefinitionRevisionId" in api
    assert "legacyDefinitionReference" in api
    assert "listDigitalEmployeeTemplates" not in page
    assert "管理已接通真实 HTTP/PostgreSQL authority" in page
    assert "发布不代表 matching" in page
    assert "执行未连接" in page


def test_exact_composition_and_independent_lifecycle_are_visible() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    assert "PRIMARY_AGENT_REQUIRED" in page
    assert "主 Agent" in page
    assert "64 位 digest" in page
    assert 'act("validate")' in page
    assert 'act("approve")' in page
    assert 'act("publish")' in page
    assert "CAS stale 后只刷新" in page
    assert "Revision history/list API 未提供" in page


def test_search_context_race_guard_and_responsive_focus_styles_exist() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    styles = source("styles/product-experience.css")
    assert 'params.get("q")' in page
    assert 'params.get("status")' in page
    assert "employeeDefinitionRevisionId" in page
    assert "generation.current" in page
    assert "createTrigger.current?.focus()" in page
    assert "@media(max-width:700px)" in styles
    assert ".employee-member-row" in styles
