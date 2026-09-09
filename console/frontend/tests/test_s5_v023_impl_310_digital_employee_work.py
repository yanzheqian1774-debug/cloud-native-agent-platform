from pathlib import Path

ROOT = Path(__file__).parents[3] / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_employee_profile_preserves_field_ownership_and_exact_agent_identity() -> None:
    profile = source("digital-employees/EmployeeProfile.tsx")
    assert "当前正式契约没有 display name 字段" in profile
    assert "来源：Digital Employee Definition" in profile  # noqa: RUF001
    assert "来源：Agent Definition" in profile  # noqa: RUF001
    for field in ("businessPurpose", "duties", "capabilities"):
        assert field in profile
    assert "revisionId === primary.revisionId" in profile
    assert "digest === primary.digest" in profile
    assert "不代表企业 HR 岗位身份" in profile
    assert "不复制为新的员工或岗位权威事实" in profile


def test_work_participation_uses_only_existing_exact_read_coordinates() -> None:
    api = source("api/digitalEmployees.ts")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    assert "getEmployeePlacement" in api
    for identity in (
        "instanceId",
        "assignmentId",
        "placementId",
        "attemptId",
        "agentInstanceId",
    ):
        assert identity in api
    assert "/placements/" in api
    assert "exact read only" in work
    assert "当前没有 Instance、Assignment 或 Placement 列表端口" in work
    for boundary in (
        "configured",
        "bound",
        "assigned",
        "实际执行 execution",
        "实际终态 terminal",
    ):
        assert boundary in work
    assert "当前 Placement 投影没有 Evidence reference" in work
    assert "Evidence 内容仍需独立授权" in work


def test_unknown_runtime_and_execution_states_are_not_promoted() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    assert "Runtime Profile 绑定不代表 Runtime 已启动" in page
    assert "Assignment 创建不代表员工正在工作" in page
    assert "不推导在线状态" in work
    assert '"unknown"' in work
    assert "未知 / 尚未接通" in work
    assert "Business Outcome 完成" in work
    assert "在线" not in work.replace("不推导在线状态", "")
    assert "空闲" not in work


def test_refresh_race_scope_and_narrow_layout_guards_exist() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    styles = source("styles/resource-management.css")
    assert 'params.get("instanceId")' in page
    assert 'params.get("assignmentId")' in page
    assert "URL identities are read once as coordinates" in page
    assert "workGeneration.current" in page
    assert "turn !== workGeneration.current" in page
    assert "AbortController" in page
    assert "activeRead.current?.abort()" in work
    assert "changeCoordinate" in work
    assert "setPlacement(null)" in work
    assert "employeeControlledState" in work
    assert 'error.kind === "denied" || error.kind === "not found"' in work
    assert "@media (max-width: 700px)" in styles
    assert ".employee-work-fields" in styles
