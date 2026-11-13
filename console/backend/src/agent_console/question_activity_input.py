# ruff: noqa: E501, RUF001 -- Exact scoped SQL, audit labels and Chinese planning context.
"""Raw question to governed planning input, without a predecessor Plan input.

Deterministic context routing is deliberately labelled, never passed off as a
model's understanding. Planning's existing invocation owner forms durable tasks.
"""

import json
import re
from types import SimpleNamespace

from psycopg import Error as StorageError
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import (
    ExactReference,
    Identity,
    PlanningError,
    ProblemTarget,
)
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
    problemId: Identity | None = None
    source: ExactReference | None = None


def member_contract_answers(operations):
    """Preserve complete observed I/O entries within Planning's Text boundary."""
    prefix = (
        "可读成员I/O候选(op,至少一种兼容输入,输出；非固定图、非必须操作、非执行授权)："
    )
    chunks, current = [], []
    for operation in operations:
        row = [
            operation["operation"],
            operation["inputKinds"],
            operation["outputKind"],
        ]
        candidate = [*current, row]
        if len(prefix + json.dumps(candidate, separators=(",", ":"))) > 500:
            chunks.append(prefix + json.dumps(current, separators=(",", ":")))
            current = [row]
        else:
            current = candidate
    if current:
        chunks.append(prefix + json.dumps(current, separators=(",", ":")))
    if any(len(chunk) > 500 for chunk in chunks):
        raise WorkbenchOwnerError("QUESTION_MEMBER_CONTRACT_TOO_LARGE", 422)
    return tuple(chunks)


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
    # Shared words rank suggestions, never establish the user's business target.
    # Even a single visible context can belong to an unrelated new goal.
    return None, [
        {"label": x["title"], "contextToken": x["contextToken"]} for _, x in ranked
    ]


class QuestionActivityInput:
    def __init__(self, automation):
        self.automation = automation

    def __call__(self, call):
        a = self.automation
        request = QuestionActivityRequest.model_validate(call.payload)
        # Browser session/CSRF and entry grants have already passed the BFF.
        # This step authenticates the preparation service, not the browser user.
        try:
            a.authenticate(call.context)
        except AuthorityError as exc:
            denied = exc.reason_code == "RESOURCE_POLICY_SCOPE_DENIED"
            raise WorkbenchOwnerError(
                "QUESTION_INPUT_SERVICE_ACCESS_DENIED"
                if denied
                else "QUESTION_INPUT_SERVICE_UNAVAILABLE",
                403 if denied else 503,
            ) from exc
        except (StorageError, OSError, TimeoutError) as exc:
            raise WorkbenchOwnerError(
                "QUESTION_INPUT_SERVICE_UNAVAILABLE", 503
            ) from exc
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
            if (
                request.problemId is not None
                and work.problem.resource_id != request.problemId
            ):
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
                    "SELECT p.plan_id,p.version,p.record->'semantics'->'boundaries' boundaries, "
                    "p.record->'semantics'->'target' target FROM workflow_planning.plans p "
                    "JOIN workflow_planning.approvals a USING(namespace,security_domain,plan_id,version) "
                    "WHERE p.namespace=%s AND p.security_domain=%s "
                    "AND p.record->'semantics'->'target'->'problem'->>'resource_id'=%s "
                    "ORDER BY (a.record->>'decided_at')::timestamptz DESC,p.plan_id,p.version DESC LIMIT 1",
                    (scope.namespace, scope.security_domain, work.problem.resource_id),
                ).fetchall()
                if not rows:
                    continue
                row = rows[0]
                call.authority.require(p, "PLAN", "READ", "plan:v2:" + row["plan_id"])
                if ProblemTarget.model_validate(row["target"]) != target:
                    continue
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
        if request.source is not None and request.problemId is not None:
            from .conversation_sources import sources

            current = app.current_input(p, request.problemId, call.connection)
            target = ProblemTarget.model_validate(current["target"])
            available = sources(a, call, target.problem)
            selected_source = next(
                (
                    x
                    for x in available
                    if x["source"] == request.source.model_dump(mode="json")
                ),
                None,
            )
            if selected_source is None:
                raise WorkbenchOwnerError(
                    "CONVERSATION_SOURCE_STALE_OR_UNREADABLE", 409
                )
            contexts = [
                {
                    **current,
                    **selected_source,
                    "sourceName": selected_source["name"],
                    "_work": a.work(call.context, target.problem, now),
                    "contextToken": canonical_digest(
                        [current["target"], selected_source["source"]]
                    ),
                    "sourceProvenance": {
                        "usage": "USER_CONFIRMED_READABLE_SOURCE_NO_HISTORICAL_PLAN"
                    },
                }
            ]
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
        if request.problemId is not None and request.contextToken is None:
            selected, choices = (contexts[0], []) if len(contexts) == 1 else (None, [])
        else:
            selected, choices = route_question(
                request.question, contexts, request.contextToken
            )
        base = {
            "schemaVersion": "question-activity-input.v1",
            "originalQuestion": request.question,
            "questionDigest": canonical_digest(request.question),
            "contextRouting": "EXPLICIT_CURRENT_PROBLEM_REAUTHORIZED"
            if request.problemId is not None
            else "EXPLICIT_CONTEXT_TOKEN_REAUTHORIZED"
            if request.contextToken is not None
            else "READABLE_CHOICES_REQUIRE_EXPLICIT_BUSINESS_CONTEXT",
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
        required = {"READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"}
        available_operations = {op["operation"] for op in capabilities["operations"]}
        if not required <= available_operations:
            return {
                **base,
                "state": "BLOCKED_MISSING_COMPATIBLE_TOOLS",
                "planningRequest": None,
                "gaps": [
                    {"kind": "TOOL", "operation": name}
                    for name in sorted(required - available_operations)
                ],
                "executionReady": False,
            }
        capability_answers = member_contract_answers(capabilities["operations"])
        hint = f"唯一批准的只读来源，来源族：{selected['sourceSchema']}。将下一行原样保留为boundaries中的一条：\n隔离合成来源：{source.resource_id}；修订：{source.revision_id}；SHA256：{source.digest}"
        planning = PlanningRequest(
            target=ProblemTarget.model_validate(selected["target"]),
            answers=(
                request.question,
                hint,
                "按原始提问、已确认目标/标准/来源形成FREE任务图，不固定步骤或数量，不要求用户选资源/角色/技术ID。业务字段用短标题、单句职责和简短I/O；技术引用只放对应字段，同样覆盖可复用逻辑角色。每个非READ任务的input_kinds集合必须等于全部depends_on任务的output_kind去重集合，且至少含该操作的一种兼容输入；候选表中的兼容集合不是本任务的实际输入。READ仅CONTEXT且无依赖。若需其它能力保留缺口，不声称就绪；缺业务事实时集中补问，不虚构事实、流程实例或效果。",
                "本次来源是平台已发布的Knowledge只读快照。已观察到的READ_DATA技能可读取该内部快照，不需要为此虚构外部MCP连接器依赖；只有确实另需外部系统数据时才提出连接能力缺口，不得用内部快照冒充外部数据。",
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
