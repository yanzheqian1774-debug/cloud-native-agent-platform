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
    assert "不伪造 Plan、执行、Evidence 或 Outcome" in page
    assert "本批不伪造 Plan、执行、Evidence 或 Outcome" in page
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
