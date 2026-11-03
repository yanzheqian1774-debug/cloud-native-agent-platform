# ruff: noqa: RUF001 -- Preserve approved Chinese boundary text exactly.
"""D324's narrow human-reviewable successor, without understanding/model calls."""

from typing import Literal

from pydantic import Field

from .plan_suggestion_domain import (
    ConfirmedPlanRevision,
    Digest,
    ExactReference,
    FlexiblePlanSemantics,
    Immutable,
    PlanningConflict,
    ProposalRevision,
)
from .resource_use_domain import canonical_digest

PLANNING_ONLY = (
    "本轮只规划与确认，不创建Assignment、Run或TaskRun，不执行业务或调整配置；"
    "人工业务验收在执行产物之后，不作为任务。"
)
READ_ONLY_PLANNING = "仅进行只读数据采集与分析规划，不执行任何业务操作。"
EXECUTION_ONLY = (
    "本次仅在隔离环境以明确标注的合成资料执行只读任务；"
    "允许创建本执行修订对应的Assignment、单Run及TaskRun，"
    "禁止外部写入、生产操作及配置调整；人工业务验收在执行产物之后，不作为任务。"
)
SYNTHETIC_ONLY = (
    "仅对本次固定的隔离合成资料进行只读采集与分析；"
    "产物不能证明星河客服真实费用、超支原因或节约效果。"
)
DELIVERY_SYNTHETIC_ONLY = (
    "仅对本次固定快照及判定日期的合成采购订单分析交付及时性；"
    "不得读取真实企业数据，产物不证明真实业务损失或真实企业问题已解决。"
)


class CostExecutionRevisionRequest(Immutable):
    case: Literal["cost", "delivery"] = "cost"
    plan_version: int = Field(ge=1)
    plan_digest: Digest
    source_snapshot: ExactReference
    mapping_digest: Digest
    selections: dict[str, ExactReference] = Field(min_length=1, max_length=128)

    @property
    def digest(self):
        record = self.model_dump(mode="json")
        if self.case == "cost":
            record.pop("case")  # Preserve all existing request/replay identities.
        return canonical_digest(record)


def execution_successor(
    plan: ConfirmedPlanRevision,
    source: ProposalRevision,
    request: CostExecutionRevisionRequest,
):
    """Preserve the exact graph, criteria, policy, cost rules and missing evidence."""
    if (
        plan.version != request.plan_version
        or plan.digest != request.plan_digest
        or source.proposal_id != plan.source_proposal_id
        or source.revision != plan.source_proposal_revision
        or source.digest != plan.source_proposal_digest
        or source.semantics != plan.semantics
        or not isinstance(plan.semantics, FlexiblePlanSemantics)
    ):
        raise PlanningConflict("EXECUTION_REVISION_SOURCE_MISMATCH")
    old = plan.semantics
    if (
        old.business_rules.count(PLANNING_ONLY) != 1
        or old.boundaries.count(READ_ONLY_PLANNING) != 1
    ):
        raise PlanningConflict("EXECUTION_REVISION_BOUNDARY_MISMATCH")
    required = {r.requirement_id for r in old.requirements if r.required}
    known = {r.requirement_id for r in old.requirements}
    if not required <= request.selections.keys() <= known:
        raise PlanningConflict("EXECUTION_REVISION_RESOURCE_SELECTIONS")
    record = old.model_dump(mode="json")
    record["business_rules"] = [
        EXECUTION_ONLY if text == PLANNING_ONLY else text for text in old.business_rules
    ]
    record["boundaries"] = [
        (DELIVERY_SYNTHETIC_ONLY if request.case == "delivery" else SYNTHETIC_ONLY)
        if text == READ_ONLY_PLANNING
        else text
        for text in old.boundaries
    ] + [
        f"隔离合成来源：{request.source_snapshot.resource_id}；"
        f"修订：{request.source_snapshot.revision_id}；"
        f"SHA256：{request.source_snapshot.digest}",
        f"执行准备映射SHA256：{request.mapping_digest}；"
        "确认本修订不等于执行准入；派发前须重新校验资源和独立权限。",
    ]
    for requirement in record["requirements"]:
        selected = request.selections.get(requirement["requirement_id"])
        if selected is not None:
            requirement["selected"] = selected.model_dump(mode="json")
    semantics = FlexiblePlanSemantics.model_validate(record)
    successor = ProposalRevision(
        proposal_id=source.proposal_id,
        revision=source.revision + 1,
        predecessor_digest=source.digest,
        invocation_id=None if source.origin else "execution-revision:" + request.digest,
        origin=source.origin,
        semantics=semantics,
    )
    changes = [
        {"path": key, "before": old.model_dump(mode="json")[key], "after": record[key]}
        for key in ("business_rules", "boundaries", "requirements")
        if old.model_dump(mode="json")[key] != record[key]
    ]
    return successor, changes
