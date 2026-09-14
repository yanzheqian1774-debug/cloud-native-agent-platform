from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[3]
ROOT = REPOSITORY_ROOT / "console" / "frontend" / "src"


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_real_browser_workflow_builds_the_live_digital_employee_route() -> None:
    workflow = (
        REPOSITORY_ROOT
        / ".github"
        / "workflows"
        / "s5-v023-impl-310-real-workbench.yml"
    ).read_text()
    build_step = workflow.split("      - name: Build frontend\n", maxsplit=1)[1].split(
        "      - name: Lint frontend\n", maxsplit=1
    )[0]
    assert "VITE_SUPPLIER_QUALITY_DEMO_MODE: live" in build_step


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
    assert "每次选择都会读取所选修订" in page
    assert "不是全局统计" in page
    assert "不能代表完整历史" in page
    assert "明确选择要查看的修订" in page
    assert "不会自动指定权威版本" not in page


def test_employee_profile_preserves_field_ownership_and_exact_agent_identity() -> None:
    profile = source("digital-employees/EmployeeProfile.tsx")
    assert "来源：Digital Employee Definition" in profile  # noqa: RUF001
    assert "来源：Agent Definition 所选修订" in profile  # noqa: RUF001
    for field in ("businessPurpose", "duties", "capabilities"):
        assert field in profile
    assert (
        "getAgentDefinitionRevision(primary.resourceId, primary.revisionId" in profile
    )
    assert "value.revisionId === primary.revisionId" in profile
    assert 'value.digest === primary.digest.replace(/^sha256:/, "")' in profile
    assert "查看员工列表的权限不包含已绑定 Agent 的详情权限" in profile
    assert "不成为员工名称或职责权威" in profile


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
    assert "可信只读关联" in work
    assert "不表示配置、放置、执行和结果已形成完整成功流程" in work
    assert "继续核对当前 Instance 与 Assignment 父链" in work


def test_unknown_runtime_execution_evidence_and_outcome_are_not_promoted() -> None:
    profile = source("digital-employees/EmployeeProfile.tsx")
    work = source("digital-employees/EmployeeWorkParticipation.tsx")
    assert "发布不等于已运行" in profile
    assert "不推导在线状态" in work
    assert "Execution、Evidence 与 Outcome 没有本页可用的正式读取端口" in work
    assert "不代表已经执行或已有业务结果" in work
    assert "Runtime Profile exact 详情未接通" in work
    assert "PLACED 不等于执行成功" in work
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
    assert "Initial route coordinates are consumed once" in page
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
    assert "@media (max-width: 800px)" in styles
    assert ".employee-work-fields" in styles


def test_fixed_commands_use_csrf_frozen_identity_and_no_private_fallback() -> None:
    api = source("api/digitalEmployees.ts")
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    assembly = source("digital-employees/EmployeeDefinitionAssembly.tsx")
    lifecycle = source("digital-employees/EmployeeLifecycleActions.tsx")
    assert "INSTANCE_DEFINITION_IDENTITY_MISMATCH" in page
    assert "ASSIGNMENT_INSTANCE_IDENTITY_MISMATCH" in page
    assert "ASSIGNMENT_IDENTITY_MISMATCH" in page
    assert "EMPLOYEE_DEFINITION_IDENTITY_MISMATCH" in page
    assert "readInstanceDefinition" in page
    assert "boundDefinition={instanceDefinition}" in page
    for required in (
        '"x-csrf-token": session.csrfToken',
        "createEmployeeDefinition",
        'lifecycleCommand("validation"',
        'lifecycleCommand("approvals"',
        'lifecycleCommand("publication"',
    ):
        assert required in api
    assert "Object.freeze(command)" in assembly
    assert "重放原命令" in assembly
    assert "当前无权读取详情" in assembly
    assert "这不表示创建失败" in assembly
    assert "Object.freeze" in lifecycle
    assert "WORKBENCH_SESSION_CONTEXT_CHANGED" in api
    assert "PUBLISH" in lifecycle
    assert "已实例化" not in lifecycle
    for source_text in (api, page, assembly, lifecycle):
        assert "/api/internal/" not in source_text
        assert "X-Principal-ID" not in source_text


def test_employee_management_visual_status_and_narrow_layout_are_page_scoped() -> None:
    page = source("digital-employees/DigitalEmployeesPage.tsx")
    assembly = source("digital-employees/EmployeeDefinitionAssembly.tsx")
    styles = source("styles/resource-management.css")
    assert "仅展示当前授权范围内的本批结果" in page
    assert "搜索当前结果" in page
    assert "个员工" in page
    assert "个修订" in page
    assert "部分实现" in assembly
    assert "关联列表暂未接通" in page
    assert ".employee-management .employee-object-center" in styles
    assert ".employee-management .employee-capability-state.missing" in styles
    assert "@media (max-width: 1500px)" in styles
    assert "@media (max-width: 800px)" in styles


def test_real_browser_private_api_observation_is_scoped_to_employee_work() -> None:
    scenario = (
        REPOSITORY_ROOT
        / "console"
        / "frontend"
        / "tests"
        / "e2e"
        / "digital-employee-work-participation.real.spec.ts"
    ).read_text()
    observation_start = scenario.index("observations.observePrivateRequests = true;")
    employee_navigation = scenario.index(
        "full.page.goto(`${baseURL}/digital-employees`)"
    )
    observation_end = scenario.index("observations.observePrivateRequests = false;")
    lister_login = scenario.index(
        'login(browser, credentials.list, observations, "LISTER")'
    )
    assert observation_start < employee_navigation < observation_end < lister_login
    assert "if (headers[name]) observations.identityHeaders.push(name);" in scenario
