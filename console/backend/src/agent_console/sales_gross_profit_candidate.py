# ruff: noqa: RUF001 -- Chinese candidate resource content.
"""Content-addressed LOCAL Skill successor proposal; no repository/API writes."""

from copy import deepcopy

from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest
from .sales_diagnostic_skill import OPERATIONS, SalesDiagnosticSkillExecutor
from .sales_gross_profit_contract import (
    CONTRACT_DIGEST,
    INPUT_SCHEMA,
    LIMITS,
    OUTPUT_SCHEMA,
)
from .sales_gross_profit_skill import SalesGrossProfitSkillExecutor
from .skill_mcp_schemas import ResourceContent


def revision_candidate(
    predecessor, content, aggregate_version, source_reference, source_digest
):
    predecessor = ExactReference.model_validate(predecessor).model_dump(mode="json")
    source_reference = ExactReference.model_validate(source_reference).model_dump(
        mode="json"
    )
    if not predecessor["resource_id"].startswith("skill-definition:"):
        raise ValueError("CANDIDATE_SKILL_IDENTITY_REQUIRED")
    if type(aggregate_version) is not int or aggregate_version < 1:
        raise ValueError("CANDIDATE_AGGREGATE_VERSION_REQUIRED")
    original = ResourceContent.model_validate(content).model_dump(
        mode="json", exclude_none=True
    )
    old = SalesDiagnosticSkillExecutor.revision
    operations = original.get("operations", [])
    if (
        {op["name"] for op in operations} != set(OPERATIONS)
        or len(operations) != len(OPERATIONS)
        or any(
            (
                op["executorId"],
                op["executorRevision"],
                op["executorConfigurationDigest"],
            )
            != (old.executor_id, old.executor_revision, old.configuration_digest)
            for op in operations
        )
        or any(
            op["inputSchema"].get("properties", {}).get("schemaVersion", {}).get("enum")
            != ["sales-diagnostic-input.v1"]
            or op["outputSchema"]
            .get("properties", {})
            .get("schemaVersion", {})
            .get("enum")
            != ["sales-diagnostic-output.v1"]
            for op in operations
        )
        or original["sideEffect"] != "READ"
    ):
        raise ValueError("CANDIDATE_EXACT_SALES_V1_PREDECESSOR_REQUIRED")
    if (
        not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(c not in "0123456789abcdef" for c in source_digest)
    ):
        raise ValueError("CANDIDATE_SOURCE_DIGEST_INVALID")
    candidate = deepcopy(original)
    candidate.update(
        description="固定合成销售两期逐币种净销售额、成本及三维毛利变化贡献（v2本地候选）。",
        instructions="只读计算区域/渠道/产品各自的逐币种毛利变化贡献及来源行；退货保留金额/成本负号，取消行排除；缺成本或符号矛盾拒绝；未知维度保留未解析组，零基期无增长率。不跨币种或跨维度合并，不证明因果、真实业务改善或验收完成。",
        inputSchema=deepcopy(INPUT_SCHEMA),
        outputSchema=deepcopy(OUTPUT_SCHEMA),
        timeoutSeconds=5,
    )
    new = SalesGrossProfitSkillExecutor.revision
    for op in candidate["operations"]:
        op.update(
            inputSchema=deepcopy(INPUT_SCHEMA),
            outputSchema=deepcopy(OUTPUT_SCHEMA),
            executorId=new.executor_id,
            executorRevision=new.executor_revision,
            executorConfigurationDigest=new.configuration_digest,
            ioLimits={
                "policyId": "sales-gross-profit-candidate-bounds",
                "policyRevision": "2",
                **{k: v for k, v in LIMITS.items() if k != "maxRows"},
            },
        )
        op["inputSchema"]["description"] = (
            "Explicit v2 only; source commitment and bounded semantic checks "
            "remain mandatory."
        )
        op["outputSchema"]["properties"]["operation"] = {
            "type": "string",
            "enum": [op["name"]],
        }
    candidate = ResourceContent.model_validate(candidate).model_dump(
        mode="json", exclude_none=True
    )
    body = {
        "schemaVersion": "sales-skill-revision-candidate.v1",
        "status": "LOCAL_CANDIDATE_NOT_PUBLISHED_NOT_INSTALLED",
        "predecessor": predecessor,
        "expectedAggregateVersion": aggregate_version,
        "predecessorContentDigest": canonical_digest(content),
        "normalizedPredecessorContentDigest": canonical_digest(original),
        "candidateContent": candidate,
        "candidateContentDigest": canonical_digest(candidate),
        "executor": {
            "executorId": new.executor_id,
            "executorRevision": new.executor_revision,
            "executorConfigurationDigest": new.configuration_digest,
        },
        "contractDigest": CONTRACT_DIGEST,
        "sourceReference": source_reference,
        "sourceContentDigest": source_digest,
        "formalRevisionIdentity": "NOT_ASSIGNED_BY_RESOURCE_OWNER",
        "currentRuntimeRegistration": "NOT_REGISTERED",
        "publication": "NOT_REQUESTED",
        "metricCriterionConfirmation": "NOT_REQUESTED",
        "executionAdmission": "NOT_REQUESTED",
        "supplementRun": "NOT_CREATED",
        "businessAcceptance": "OPEN",
        "permissionsAdded": False,
    }
    return {**body, "candidateId": "skill-revision-candidate:" + canonical_digest(body)}
