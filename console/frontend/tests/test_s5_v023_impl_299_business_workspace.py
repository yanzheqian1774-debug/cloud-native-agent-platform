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
        "persistAuthorization(problemId,currentSession,pending)",
        "stored.contextKey===contextKey",
    ):
        assert marker in page
    assert "writeCriterion" in page
    assert "writeCriteriaSet" in page
    assert "problemPlanning" not in page
    assert "listDigitalEmployeeTemplates" not in page


def test_plan_execution_and_resource_gaps_are_not_fabricated() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    assert (
        "本批不伪造 Workflow / Plan、执行、Human Intervention、Evidence 或 Outcome"
        in page
    )
    for boundary in (
        "数字员工",
        "Workflow / Plan",
        "Human Intervention",
        "当前不接入模型分析或任务执行",
    ):
        assert boundary in page
    assert "成功标准不等于已经达成" in page


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


def test_conversation_has_one_composer_and_confirmation_gate() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    conversation = text("problems/ProblemConversation.tsx")
    model = text("problems/problemConversationModel.ts")
    assert page.count("<ConversationComposer") == 1
    assert page.count("<DraftCard") == 1
    assert "onConfirm={()=>void create()}" in page
    assert 'htmlFor="problem-composer"' in conversation
    assert 'id="problem-composer"' in conversation
    assert "event.nativeEvent.isComposing" in conversation
    assert "event.keyCode===229" in conversation
    assert "发送后仍需确认" in conversation
    assert "待处理补充" + "\uff08" + "仅本页" + "\uff09" in conversation
    assert "尚未修改正式问题" + "\uff0c" + "管理员不会自动收到" in conversation
    assert "保留补充" in conversation
    assert "未提交草稿只保存在当前页面" in conversation
    assert "suggestProblemTitle" in model
    assert "无模型模式" in conversation
    assert 'operation:"创建业务问题",mutation:true' in page


def test_editors_are_exclusive_and_task_summary_is_read_only() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    conversation = text("problems/ProblemConversation.tsx")
    summary = text("problems/ProblemTaskSummary.tsx")
    for marker in (
        'composerTarget==="SUPPLEMENT"',
        'composerTarget==="DRAFT"',
        'composerTarget==="FORMAL"',
        "采用字段修改",
        "正在底部输入框完整替换描述",
        "旧确认和更新操作已经失效",
        "问题名称" + "\uff08" + "可选修改" + "\uff09",
    ):
        assert marker in page or marker in conversation
    for marker in (
        "根据当前问题与授权状态汇总",
        "获得查看权限后显示问题详情",
        "授权状态",
        "内容读取",
        "暂时无法读取",
        "定位问题消息",
        "定位授权消息",
        "showModal",
    ):
        assert marker in summary
    for forbidden in (
        "createBusinessProblem",
        "submitProblemReadGrantRequest",
        "decideGrantRequest",
    ):
        assert forbidden not in summary
    assert (
        'mode?:"NEW"|"SUPPLEMENT"|"DRAFT_REPLACE"|"FORMAL_REPLACE"|"CRITERION"|"CRITERION_REPLACE"'
        in conversation
    )
    assert "px-composer-locked" not in conversation
    assert "supplements" not in summary
    assert "px-task-summary-trigger>span:first-child" in text(
        "styles/product-experience.css"
    )


def test_conversation_isolates_context_and_freezes_unknown_create() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    conversation = text("problems/ProblemConversation.tsx")
    for marker in (
        "mutationFlight.current",
        "pendingCreate",
        "command.payload",
        "command.key",
        "command.epoch",
        "sessionKey",
        "epoch.current+=1",
        "可信身份或安全范围已经变化",
        "页内补充和在途响应已隔离",
        "恢复原创建结果",
        "setSupplements([])",
    ):
        assert marker in page or marker in conversation
    assert "localStorage" not in page
    assert "localStorage" not in conversation
    assert "sessionStorage" in page


def test_success_criterion_draft_uses_the_single_composer_and_explicit_type() -> None:
    page = text("problems/ProblemWorkspacePage.tsx")
    conversation = text("problems/ProblemConversation.tsx")
    card = text("problems/SuccessCriterionCard.tsx")
    model = text("problems/successCriteriaModel.ts")
    assert page.count("<ConversationComposer") == 1
    assert "定义成功标准" in page
    assert 'composerTarget==="CRITERION"' in page
    assert 'composerTarget==="CRITERION_EDIT"' in page
    assert "明确采用为成功标准" in page
    assert "createSuccessCriterionTurn" in model
    assert "originalText:text" in model
    assert "没有用关键词推断标准类型" in card
    assert 'source?"HUMAN_EVALUATED":null' in model
    assert 'kind:"HUMAN_EVALUATED"' in card
    assert "确认前只保存在当前页面" in card
    assert "确认并保存" in card
    assert "已保存并完成正式关联" in card
    assert "没有调用正式保存接口" in card
    assert "当前针对" + "\uff1a" in conversation
    for marker in (
        "criterionPayload",
        "criterionKey",
        "setPayload",
        "setKey",
        "expectedProblemVersion",
        "UNKNOWN_CRITERION",
        "UNKNOWN_SET",
        "原命令、payload 和幂等键已冻结",
        "predecessorSetRevisionId",
        "predecessorRevisionId",
    ):
        assert marker in page or marker in card or marker in model
    assert "SavedCriteriaHistory" in page
    assert "列表按 revision 倒序显示不等于自动选择 latest" in card
