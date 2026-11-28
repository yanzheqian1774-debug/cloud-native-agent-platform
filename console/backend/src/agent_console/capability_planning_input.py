# ruff: noqa: RUF001 -- Existing exact Chinese source commitment and planning instructions.
"""Fresh planning input from an owned capability preparation; no model invocation."""

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .capability_conversation_source import verify_work_association
from .capability_execution_constraints import exclusion_boundaries, verify_current
from .plan_suggestion_domain import ExactReference, Identity, ProblemTarget
from .plan_suggestion_invocation import PlanningRequest
from .planning_candidates import read_employee_member, require_read
from .planning_contracts import PlanningPolicy
from .question_activity_input import member_contract_answers
from .question_member_capabilities import observe
from .resource_automation_validation import validate
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class CapabilityPlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: str = Field(min_length=1, max_length=128)
    sourceMessageId: str = Field(min_length=1, max_length=128)
    contractDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    problemId: Identity
    idempotencyKey: Identity


class CapabilityPlanningInput:
    def __init__(self, automation):
        self.automation = automation

    def __call__(self, call):
        a = self.automation
        request = CapabilityPlanningRequest.model_validate(call.payload)
        a.authenticate(call.context)
        reader = getattr(a, "capability_contract_reader", None)
        if reader is None:
            raise WorkbenchOwnerError("CAPABILITY_CONTRACT_READER_UNAVAILABLE", 503)
        resolved = reader(call, request.conversationId, request.sourceMessageId)
        if resolved["contractDigest"] != request.contractDigest:
            raise WorkbenchOwnerError("CAPABILITY_CONTRACT_DIGEST_MISMATCH", 409)
        contract = resolved["contract"]
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        app = a.bound_app(call)
        current = app.current_input(principal, request.problemId, call.connection)
        verify_current(resolved, current)
        target = ProblemTarget.model_validate(current["target"])
        verify_work_association(call, resolved, current["target"]["problem"])
        bindings = contract["bindings"]
        sources = [b["reference"] for b in bindings if b["kind"] == "KNOWLEDGE"]
        employees = [b for b in bindings if b["kind"] == "EMPLOYEE"]
        if (
            len(sources) != 1
            or len(employees) != 1
            or any(
                b["kind"]
                not in {
                    "EMPLOYEE",
                    "SKILL",
                    "MCP",
                    "KNOWLEDGE",
                    "RUNTIME_PROFILE",
                    "ONTOLOGY",
                }
                for b in bindings
            )
        ):
            raise WorkbenchOwnerError("CAPABILITY_PLANNING_ADAPTER_UNAVAILABLE", 409)
        from .ontology_capability_binding import document_binding

        semantics = document_binding(call, resolved)
        source = ExactReference.model_validate(sources[0])
        require_read(call.authority, principal, "KNOWLEDGE", source)
        content, _ = read_employee_member(
            call.connection,
            app.scope(principal),
            ExactReference.model_validate(employees[0]["reference"]),
            "KNOWLEDGE",
            source,
        )
        work = a.work(call.context, target.problem, a.grants.clock())
        check = validate("knowledge", content, work)
        raw = json.loads(content["documents"][0]["chunks"][0]["content"])
        if raw.get("synthetic") is not True:
            raise WorkbenchOwnerError("CAPABILITY_PLANNING_ADAPTER_UNAVAILABLE", 409)
        facts = observe(
            a,
            call,
            source,
            check["sourceSchema"],
            work,
            fixed_bindings=bindings,
            **({"ontology_binding": semantics} if semantics is not None else {}),
        )
        if not {"READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"} <= {
            item["operation"] for item in facts["operations"]
        }:
            return {
                "state": "BLOCKED_FIXED_CAPABILITY_TOOLS",
                "planningRequest": None,
                "executionStarted": False,
                "modelCalls": 0,
            }
        boundaries = exclusion_boundaries(contract)
        source_boundary = (
            f"隔离合成来源：{source.resource_id}；修订：{source.revision_id}；"
            f"SHA256：{source.digest}"
        )
        try:
            planning = PlanningRequest(
                target=target,
                answers=(
                    "按已确认业务目标和标准生成新方案，不复制历史任务图。完整目标、资料说明、"
                    "范围和固定资源保存在 business_context 的 "
                    "criteria[0].applicability."
                    "capabilityConstraints；必须遵守，不得替换资源或扩大执行范围。",
                    "以下来源承诺和排除范围分段须逐条原样保留在 boundaries。"
                    "选用 capabilityConstraints.bindings 中的固定数字人与业务资源。"
                    "仅在这些成员的已登记操作内规划；缺少能力时明确缺口，不虚构执行。",
                    source_boundary,
                    *boundaries,
                    *member_contract_answers(facts["operations"]),
                ),
                policy=PlanningPolicy(),
                output_language="zh-CN",
                idempotency_key=request.idempotencyKey,
            )
        except ValidationError as exc:
            raise WorkbenchOwnerError(
                "CAPABILITY_PLANNING_CONTEXT_TOO_LARGE", 422
            ) from exc
        return {
            "state": "CAPABILITY_READY_FOR_GOVERNED_PLANNING",
            "planningRequest": planning.model_dump(mode="json"),
            "capabilitySource": {
                "conversationId": request.conversationId,
                "sourceMessageId": request.sourceMessageId,
                "contractDigest": request.contractDigest,
            },
            "source": source.model_dump(mode="json"),
            "fixedMemberObservation": facts,
            **(
                {"ontologyBinding": semantics.model_dump(mode="json")}
                if semantics
                else {}
            ),
            "executionStarted": False,
            "modelCalls": 0,
        }
