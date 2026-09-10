from pathlib import Path

ROOT = Path(__file__).parents[3] / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_employee_reads_use_only_the_trusted_workbench_bff() -> None:
    api = source("api/digitalEmployees.ts")
    assert 'const root = "/api/workbench/v1"' in api
    assert 'credentials: "same-origin"' in api
    assert 'headers: { Accept: "application/json" }' in api
    for forbidden in (
        "X-Tenant-ID",
        "X-Security-Domain",
        "X-Principal-ID",
        "/api/internal/",
        "VITE_DIGITAL_EMPLOYEE_PRINCIPAL_ID",
    ):
        assert forbidden not in api
    for route in (
        "/agents?",
        "/agents/${encodeURIComponent(definitionId)}/revisions/",
        "/employees?",
        "/employees/${encodeURIComponent(id)}/revisions/",
        "/instances/",
        "/assignments/",
        "/placements/",
    ):
        assert route in api


def test_lists_preserve_cursor_and_do_not_substitute_for_exact_reads() -> None:
    api = source("api/digitalEmployees.ts")
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    assert "WorkbenchPage" in api
    assert "nextCursor" in api
    assert "pageSize" in api
    assert "listAgentDefinitions(agentNextCursor)" in page
    assert "listEmployeeDefinitions(cursor)" in page
    assert "getEmployeeDefinition(exact.id, exact.revision" in page
    assert "LIST 仅用于发现，不授予详情 READ" in page  # noqa: RUF001
    assert "每次选择都独立执行 exact READ" in page
    assert "单页结果冒充完整集合" in page


def test_employee_profile_preserves_field_ownership_and_exact_agent_identity() -> None:
    profile = source("digital-employees/EmployeeProfile.tsx")
    assert "当前正式契约没有 display name 字段" in profile
    assert "来源：Digital Employee Definition" in profile  # noqa: RUF001
    assert "来源：Agent Definition exact revision" in profile  # noqa: RUF001
    for field in ("businessPurpose", "duties", "capabilities"):
        assert field in profile
    assert (
        "getAgentDefinitionRevision(primary.resourceId, primary.revisionId" in profile
    )
    assert "value.revisionId === primary.revisionId" in profile
    assert 'value.digest === primary.digest.replace(/^sha256:/, "")' in profile
    assert "Employee LIST 权限不授予 Agent exact READ" in profile
    assert "publicationState 不等于 matchability" in profile


def test_work_participation_preserves_exact_coordinates_and_parent_binding() -> None:
    api = source("api/digitalEmployees.ts")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    for identity in (
        "instanceId",
        "assignmentId",
        "placementId",
        "attemptId",
        "agentInstanceId",
    ):
        assert identity in api
        assert identity in work
    assert "verifyPlacementBinding" in work
    assert "PLACEMENT_BINDING_IDENTITY_MISMATCH" in work
    assert "exact read only" in work
    assert "当前没有 Instance、Assignment 或 Placement 列表端口" in work
    assert "正式 owner 在当前授权事务内核对" in work


def test_unknown_runtime_execution_evidence_and_outcome_are_not_promoted() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    assert "Runtime Profile 绑定不代表 Runtime 已启动" in page
    assert "Assignment 存在不代表员工正在工作" in page
    assert "不推导在线状态" in work
    assert 'state="unknown"' in work
    assert "正式 Execution READ 尚未接通" in work
    assert "Outcome READ 尚未接通" in work
    assert "当前 Placement 最小投影没有 Evidence reference" in work
    assert "Business Outcome 完成" in work
    assert "在线" not in work.replace("不推导在线状态", "")
    assert "空闲" not in work


def test_refresh_race_scope_and_narrow_layout_guards_exist() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    profile = source("digital-employees/EmployeeProfile.tsx")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    styles = source("styles/resource-management.css")
    assert 'params.get("instanceId")' in page
    assert 'params.get("assignmentId")' in page
    assert "URL identities are read once as coordinates" in page
    assert "workGeneration.current" in page
    assert "detailGeneration.current" in page
    assert "AbortController" in page
    assert "controller.abort()" in profile
    assert "activeRead.current?.abort()" in work
    assert "changeCoordinate" in work
    assert "setPlacement(null)" in work
    assert "employeeControlledState" in work
    assert "authentication required" in page
    assert "authentication required" in work
    assert "@media (max-width: 700px)" in styles
    assert ".employee-work-fields" in styles


def test_write_fallbacks_are_disabled_and_identity_boundaries_are_explicit() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    assert "INSTANCE_DEFINITION_IDENTITY_MISMATCH" in page
    assert "ASSIGNMENT_INSTANCE_IDENTITY_MISMATCH" in page
    assert "ASSIGNMENT_IDENTITY_MISMATCH" in page
    assert "EMPLOYEE_DEFINITION_IDENTITY_MISMATCH" in page
    assert "readInstanceDefinition" in page
    assert "boundDefinition={instanceDefinition}" in page
    assert "可信写端口未在固定 305 候选中注册" in page
    assert "不退回私有 header API" in page
    for removed_call in (
        "createEmployeeDefinition(",
        "decideEmployeeDefinition(",
        "createEmployeeInstance(",
        "createEmployeeAssignment(",
    ):
        assert removed_call not in page
