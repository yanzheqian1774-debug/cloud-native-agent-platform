from pathlib import Path

ROOT = Path(__file__).parents[3] / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_employee_management_uses_bounded_trusted_browser_reads() -> None:
    api = source("api/digitalEmployees.ts")
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    profile = source("digital-employees/EmployeeProfile.tsx")
    for operation in ("/employees", "/instances", "/assignments"):
        assert operation in api
    assert "/api/workbench/v1" in api
    assert 'credentials: "same-origin"' in api
    assert "employeeDefinitionId" in api
    assert "employeeDefinitionRevisionId" in api
    assert "legacyDefinitionReference" in api
    assert "listDigitalEmployeeTemplates" not in page
    assert "listEmployeeDefinitions" in page
    assert "getEmployeeDefinition" in page
    assert "每次选择都会独立读取精确修订" in page
    assert "发布不等于已运行" in profile


def test_exact_composition_and_independent_lifecycle_are_visible() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    profile = source("digital-employees/EmployeeProfile.tsx")
    assert "职责与能力装配" in profile
    assert "member.revisionId" in profile
    assert "member.digest" in profile
    assert "EmployeeLifecycleActions" in page
    assert "完整版本历史" in page
    assert "不能代表完整历史" in page
    assert "不推断 latest" in page


def test_search_context_race_guard_and_responsive_focus_styles_exist() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    styles = source("styles/resource-management.css")
    assert 'params.get("q")' in page
    assert 'params.get("status")' in page
    assert "employeeDefinitionRevisionId" in page
    assert "detailGeneration.current" in page
    assert "workGeneration.current" in page
    assert "activeDetailRead.current?.abort()" in page
    assert "@media (max-width: 800px)" in styles
    assert ".employee-member-list" in styles
