# ruff: noqa: E501, RUF001 -- Exact scoped SQL, audit labels and Chinese planning context.
"""Raw question to governed planning input, without a predecessor Plan input.

Deterministic context routing is deliberately labelled, never passed off as a
model's understanding. Planning's existing invocation owner forms durable tasks.
"""

import json
import re
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference, PlanningError, ProblemTarget
from .plan_suggestion_invocation import PlanningRequest
from .planning_candidates import read_published, require_read
from .planning_contracts import PlanningPolicy
from .planning_source_change import approved_source
from .resource_automation_validation import validate
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class QuestionActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=500)
    idempotencyKey: str = Field(min_length=1, max_length=120)
    contextToken: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


STOP = {
    "分析",
    "数据",
    "合成",
    "固定",
    "只读",
    "基于",
    "情况",
    "问题",
    "结果",
    "诊断",
    "本次",
    "进行",
    "哪些",
    "以及",
    "给出",
    "是否",
}


def terms(text):
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    return {
        s[i : i + n]
        for s in chinese
        for n in (2, 3, 4)
        for i in range(len(s) - n + 1)
        if s[i : i + n] not in STOP
    } | {x.lower() for x in re.findall(r"[A-Za-z]{3,}", text)}


def route_question(question, contexts, token=None):
    if token is not None:
        exact = [x for x in contexts if x["contextToken"] == token]
        if len(exact) != 1:
            raise WorkbenchOwnerError("ACTIVITY_CONTEXT_STALE_OR_UNREADABLE", 409)
        return exact[0], []
    words = terms(question)
    ranked = sorted(
        ((sum(len(t) for t in words & terms(x["title"])), x) for x in contexts),
        key=lambda pair: (-pair[0], pair[1]["contextToken"]),
    )
    if (
        not ranked
        or ranked[0][0] == 0
        or (len(ranked) > 1 and ranked[0][0] == ranked[1][0])
    ):
        return None, [
            {"label": x["title"], "contextToken": x["contextToken"]} for x in contexts
        ]
    return ranked[0][1], []


class QuestionActivityInput:
    def __init__(self, automation):
        self.automation = automation

    def __call__(self, call):
        a = self.automation
        request = QuestionActivityRequest.model_validate(call.payload)
        a.authenticate(call.context)
        p = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        app = a.bound_app(call)
        scope = app.scope(p)
        contexts = []
        now = a.grants.clock()
        for work in a.policy.workScopes:
            if (work.namespace, work.securityDomain, work.subject) != (
                scope.namespace,
                scope.security_domain,
                p.principal_id,
            ) or work.expiresAt <= now:
                continue
            try:
                current = app.current_input(
                    p, work.problem.resource_id, call.connection
                )
                target = ProblemTarget.model_validate(current["target"])
                if target.problem != work.problem:
                    continue
                # Read only the prior source commitment, not tasks/stages/goal.
                rows = call.connection.execute(
                    "SELECT plan_id,version,record->'semantics'->'boundaries' boundaries "
                    "FROM workflow_planning.plans WHERE namespace=%s AND security_domain=%s "
                    "AND record->'semantics'->'target'->'problem'->>'resource_id'=%s "
                    "ORDER BY version DESC LIMIT 1",
                    (scope.namespace, scope.security_domain, work.problem.resource_id),
                ).fetchall()
                if not rows:
                    continue
                row = rows[0]
                call.authority.require(p, "PLAN", "READ", "plan:v2:" + row["plan_id"])
                source = approved_source(SimpleNamespace(boundaries=row["boundaries"]))
                require_read(call.authority, p, "KNOWLEDGE", source)
                content, name = read_published(
                    call.connection, scope, "KNOWLEDGE", source
                )
                check = validate("knowledge", content, work)
                token = canonical_digest(
                    [
                        target.model_dump(mode="json"),
                        source.model_dump(mode="json"),
                        a.policy.digest,
                    ]
                )
                contexts.append(
                    {
                        **current,
                        "_work": work,
                        "contextToken": token,
                        "source": source.model_dump(mode="json"),
                        "sourceName": name,
                        "sourceSchema": check["sourceSchema"],
                        "sourceContentDigest": check["sourceContentDigest"],
                        "sourceProvenance": {
                            "planId": row["plan_id"],
                            "version": row["version"],
                            "usage": "SOURCE_COMMITMENT_ONLY_NO_TASK_GRAPH_COPIED",
                        },
                    }
                )
            except (AuthorityError, PlanningError, ValueError):
                continue  # No hidden context names, IDs or counts.
        if any(
            word in request.question
            for word in ("流程实例", "当前活动", "审批到", "采购流程")
        ):
            return {
                "state": "BLOCKED_PROCESS_CONTEXT_NOT_AVAILABLE",
                "originalQuestion": request.question,
                "planningRequest": None,
                "executionStarted": False,
                "reason": "EXISTING_BUSINESS_PROCESS_CONTEXT_REFERENCE_REQUIRED_NOT_FABRICATED",
            }
        if any(
            word in request.question
            for word in (
                "发送邮件",
                "联系供应商",
                "自动下单",
                "修改订单",
                "删除记录",
                "调整价格",
            )
        ):
            return {
                "state": "BLOCKED_ACTION_OUTSIDE_READONLY_CONTEXT",
                "originalQuestion": request.question,
                "planningRequest": None,
                "executionStarted": False,
            }
        selected, choices = route_question(
            request.question, contexts, request.contextToken
        )
        base = {
            "schemaVersion": "question-activity-input.v1",
            "originalQuestion": request.question,
            "questionDigest": canonical_digest(request.question),
            "contextRouting": "DETERMINISTIC_AUTHORIZED_TITLE_OVERLAP_NOT_MODEL_UNDERSTANDING",
            "formalBusinessProcess": None,
            "newResourceOrEmployeeCreated": False,
            "executionStarted": False,
            "modelCalls": 0,
        }
        if selected is None:
            return {
                **base,
                "state": "NEEDS_BUSINESS_CONTEXT_CLARIFICATION"
                if choices
                else "BLOCKED_NO_READABLE_CONTEXT",
                "question": "本次要办理哪一类已授权只读分析？" if choices else None,
                "choices": choices,
                "planningRequest": None,
            }
        source = ExactReference.model_validate(selected["source"])
        from .question_member_capabilities import observe

        capabilities = observe(
            a, call, source, selected["sourceSchema"], selected["_work"]
        )
        capability_answers = ()
        if capabilities["operations"]:
            capability_answers = (
                "平台只读观察到的已发布员工成员候选操作（不是固定任务图、不是必须操作、不是执行授权）："
                + json.dumps(
                    [op["operation"] for op in capabilities["operations"]],
                    ensure_ascii=False,
                )
                + "。按业务需要形成自由任务图；若需其它能力，保留真实缺口，不声称已有或就绪。",
            )
        hint = f"本次唯一已批准只读来源：{source.resource_id}；修订：{source.revision_id}；SHA256：{source.digest}。来源族：{selected['sourceSchema']}。新方案boundaries保留：隔离合成来源：{source.resource_id}；修订：{source.revision_id}；SHA256：{source.digest}"
        planning = PlanningRequest(
            target=ProblemTarget.model_validate(selected["target"]),
            answers=(
                request.question,
                hint,
                "围绕用户原始提问形成开放分析活动和任务I/O依赖，复用给定目标/标准/来源。不要照搬固定五步，不要求用户选资源/角色或技术ID；员工与技能候选交由平台发现。缺少必要业务事实时集中补问，不虚构事实、流程实例或效果。",
                *capability_answers,
            ),
            policy=PlanningPolicy(),
            output_language="zh-CN",
            idempotency_key=request.idempotencyKey,
        )
        return {
            **base,
            "state": "ACTIVITY_REQUEST_READY_FOR_GOVERNED_PLANNING",
            "activityRequirement": {
                "goal": request.question,
                "scope": "OPEN_ANALYSIS_WITHIN_EXISTING_AUTHORIZED_READ_ONLY_CONTEXT",
                "authorizedContextTitle": selected["title"],
                "target": selected["target"],
                "successCriteria": selected["criteria"],
                "source": selected["source"],
                "sourceSchema": selected["sourceSchema"],
                "sourceContentDigest": selected["sourceContentDigest"],
                "sourceProvenance": selected["sourceProvenance"],
                "priorTaskGraphCopied": False,
                "memberCapabilityObservation": capabilities,
                "naturalLanguageGoalCoverage": "REQUIRES_GOVERNED_PLANNING_AND_SCOPE_VALIDATION",
            },
            "planningRequest": planning.model_dump(mode="json"),
            "durableActivityBasis": "NORMAL_PLANNING_INVOCATION_REQUEST_AND_PROPOSAL_OWNERS",
            "next": "EXISTING_PLANNING_PREFLIGHT_AND_INVOCATION",
            "executionReady": False,
        }
