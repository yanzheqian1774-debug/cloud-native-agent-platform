from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1] / "src"


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_business_workspace_uses_only_trusted_browser_routes() -> None:
    api = text("api/businessWorkspace.ts")
    assert 'const PREFIX="/api/workbench/v1"' in api
    assert "/api/internal/" not in api
    assert 'credentials:"same-origin"' in api
    assert '"X-CSRF-Token":csrfToken' in api
    assert "requestedGrants:[]" in api
    assert "continuationIds:[continuationId]" in api
    for forbidden in (
        "Authorization",
        "X-Principal-ID",
        "X-Tenant-ID",
        "X-Security-Domain",
    ):
        assert forbidden not in api


def test_first_slice_preserves_identity_cas_and_refresh() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    for marker in (
        "createBusinessProblem",
        "readBusinessProblem",
        "writeCriterion",
        "writeCriteriaSet",
        "predecessorRevisionId",
        "expectedVersion",
        'params.get("problem")',
        "current_revision_id",
        "aggregate_version",
        "有未保存修改",
        "creatorContinuation",
        "submitProblemReadGrantRequest",
        'params.get("request")',
        'request.state==="APPROVED"',
        'request.state==="PENDING"',
        'request.state==="REJECTED"',
        'continuation?.state==="CONSUMED"',
        'continuation?.state==="EXPIRED"',
        "requestKey",
        "persistAuthorization(selectedId,pending)",
    ):
        assert marker in page
    assert "problemPlanning" not in page
    assert "listDigitalEmployeeTemplates" not in page


def test_plan_execution_and_resource_gaps_are_not_fabricated() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    assert "尚未接线" in page
    assert (
        "本批不伪造 Workflow / Plan、执行、Human Intervention、Evidence 或 Outcome"
        in page
    )
    for boundary in ("数字员工", "Workflow / Plan", "Human Intervention"):
        assert boundary in page
    assert "尚无该页面可调用的 HTTP 投影" in page
    assert "不是执行成功证据" in page
    assert "本批不调用 <code>getKnowledge</code>" in page
    assert "也不据此新增功能" in page


def test_grant_administration_is_a_separate_exact_request_page() -> None:
    applicant = text("problems/ProblemWorkspacePage.tsx")
    admin = text("problems/GrantAdministrationPage.tsx")
    app = text("App.tsx")
    assert 'path="/authorization-admin" element={<GrantAdministrationPage/>}' in app
    assert "decideGrantRequest" not in applicant
    assert "decideGrantRequest" in admin
    assert "requestId.trim()" in admin
    for forbidden in ("listGrantRequests", "searchGrantRequests", "grantCount"):
        assert forbidden not in admin


def test_workbench_errors_keep_business_and_diagnostic_ids_distinct() -> None:
    notice = text("problems/WorkbenchErrorNotice.tsx")
    applicant = text("problems/ProblemWorkspacePage.tsx")
    admin = text("problems/GrantAdministrationPage.tsx")
    for status in ("401", "403", "404", "409", "422", "503"):
        assert f"status==={status}" in notice
    hidden_boundary = "该内容可能不存在" + "\uff0c" + "也可能对当前会话不可见"
    assert hidden_boundary in notice
    assert "结果暂时无法确认" in notice
    assert "系统会沿用本次操作标识" in notice
    assert "诊断 ID" in notice
    assert "申请编号" in applicant
    assert "申请编号" in admin
    assert "这不是诊断 ID" in admin
    assert "requestId" not in notice.replace("error.requestId", "")


def test_problem_form_has_one_submit_action_and_accessible_fields() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    assert page.count("onClick={create}") == 1
    assert 'htmlFor="problem-title"' in page
    assert 'id="problem-title"' in page
    assert 'htmlFor="problem-description"' in page
    assert 'id="problem-description"' in page
    assert "maxLength={200}" in page
    assert "maxLength={2_000}" in page
    assert "当前输入尚未保存" in page
    assert 'operation:"创建业务问题",mutation:true' in page
