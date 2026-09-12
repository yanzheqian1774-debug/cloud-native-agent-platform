from pathlib import Path

ROOT = Path(__file__).parents[3] / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_employee_management_uses_bounded_trusted_browser_reads() -> None:
    api = source("api/digitalEmployees.ts")
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    for operation in ("/employees", "/instances", "/assignments"):
        assert operation in api
    assert "/api/workbench/v1" in api
    assert 'credentials: "same-origin"' in api
    assert "employeeDefinitionId" in api
    assert "employeeDefinitionRevisionId" in api
    assert "legacyDefinitionReference" in api
    assert "listDigitalEmployeeTemplates" not in page
    assert "TRUSTED READ BFF" in page
    assert "LIST 仅用于发现，不授予详情 READ" in page  # noqa: RUF001
    assert "publicationState 不等于 matchability" in page
    assert "通用 Execution" in page


def test_exact_composition_and_independent_lifecycle_are_visible() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    profile = source("digital-employees/EmployeeProfile.tsx")
    assert "精确能力与资源绑定" in profile
    assert "member.revisionId" in profile
    assert "member.digest" in profile
    assert "验证 exact revision" in page
    assert "人工审核 exact digest" in page
    assert "发布 immutable revision" in page
    assert "可信写端口未在固定 305 候选中注册" in page
    assert "history、aggregate facts 或相邻 revision" in page


def test_search_context_race_guard_and_responsive_focus_styles_exist() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    styles = source("styles/product-experience.css")
    assert 'params.get("q")' in page
    assert 'params.get("status")' in page
    assert "employeeDefinitionRevisionId" in page
    assert "detailGeneration.current" in page
    assert "workGeneration.current" in page
    assert "activeDetailRead.current?.abort()" in page
    assert "@media(max-width:700px)" in styles
    assert ".employee-member-row" in styles
