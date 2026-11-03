# ruff: noqa: RUF001 -- Chinese resource descriptions.
"""Only the resource drafts needed by the approved synthetic cost execution."""

import json

from .agent_definition_schemas import DefinitionContent
from .prepared_native_composition import POLICY
from .runtime_profile_schemas import RuntimeProfileContent
from .skill_mcp_schemas import ResourceContent
from .synthetic_cost_skill import OPERATIONS, SyntheticCostSkillExecutor


def source_document():
    return {
        "schemaVersion": "synthetic-cost-source.v1",
        "synthetic": True,
        "periods": {
            "sep-partial": {
                "from": "2026-09-01",
                "through": "2026-09-20",
                "timezone": "Asia/Shanghai",
                "days": 20,
            },
            "oct-full": {
                "from": "2026-10-01",
                "through": "2026-10-31",
                "timezone": "Asia/Shanghai",
                "days": 31,
            },
        },
        "rows": [
            {
                "id": "synthetic-api-1",
                "project": "星河客服",
                "trial": False,
                "category": "MODEL_API",
                "currency": "CNY",
                "period": "sep-partial",
                "amount": "120.30",
            },
            {
                "id": "synthetic-compute-1",
                "project": "星河客服",
                "trial": False,
                "category": "COMPUTE",
                "currency": "CNY",
                "period": "sep-partial",
                "amount": "35.70",
            },
            {
                "id": "synthetic-trial-excluded",
                "project": "星河客服",
                "trial": True,
                "category": "MODEL_API",
                "currency": "CNY",
                "period": "sep-partial",
                "amount": "99.99",
            },
        ],
        "gaps": [
            "真实账单未提供",
            "Token及模型单价明细未提供",
            "共享算力分摊记录未提供",
            "整月同口径证据未提供",
        ],
    }


def resource_content():
    executor = SyntheticCostSkillExecutor.revision
    ref_schema = {
        "type": "object",
        "required": ["resource_id", "revision_id", "digest"],
        "properties": {
            "resource_id": {"type": "string"},
            "revision_id": {"type": "string"},
            "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
        "additionalProperties": False,
    }
    inputs = {
        "type": "object",
        "required": ["schemaVersion", "synthetic", "sourceSnapshot", "dependencies"],
        "properties": {
            "schemaVersion": {"type": "string", "enum": ["synthetic-cost-input.v1"]},
            "synthetic": {"type": "boolean", "enum": [True]},
            "sourceSnapshot": ref_schema,
            "dependencies": {"type": "object"},
            "source": {"type": "object"},
        },
        "additionalProperties": False,
    }
    outputs = {
        "type": "object",
        "required": [
            "schemaVersion",
            "synthetic",
            "operation",
            "sourceSnapshot",
            "limitations",
        ],
        "properties": {
            "schemaVersion": {"type": "string", "enum": ["synthetic-cost-output.v1"]},
            "synthetic": {"type": "boolean", "enum": [True]},
            "operation": {"type": "string", "enum": list(OPERATIONS)},
            "sourceSnapshot": ref_schema,
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    }
    skill = ResourceContent.model_validate(
        {
            "description": "隔离合成资料的只读成本核验；不读取企业账单或调用模型。",
            "capabilities": list(OPERATIONS),
            "instructions": (
                "仅处理固定合成来源及依赖产物；保留缺口，不推断真实节约或业务解决。"
            ),
            "sideEffect": "READ",
            "idempotency": "IDEMPOTENT",
            "operations": [
                {
                    "name": operation,
                    "inputSchema": inputs,
                    "outputSchema": outputs,
                    "sideEffectClass": "READ_ONLY",
                    "executorId": executor.executor_id,
                    "executorRevision": executor.executor_revision,
                    "executorConfigurationDigest": executor.configuration_digest,
                    "sideEffectPolicy": {
                        "policyId": POLICY.policy_id,
                        "policyRevision": POLICY.policy_revision,
                        "policyDigest": POLICY.policy_digest,
                    },
                    "ioLimits": {
                        "policyId": "synthetic-cost-bounds",
                        "policyRevision": "1",
                        "maxInputBytes": 524288,
                        "maxOutputBytes": 262144,
                        "maxObjectDepth": 16,
                        "maxProperties": 4096,
                        "timeoutMs": 10000,
                    },
                }
                for operation in OPERATIONS
            ],
        }
    ).model_dump(mode="json", exclude_none=True)
    runtime = RuntimeProfileContent.model_validate(
        {
            "provider": "NATIVE_KUBERNETES",
            "resources": {
                "cpuRequest": "100m",
                "cpuLimit": "500m",
                "memoryRequest": "128Mi",
                "memoryLimit": "256Mi",
            },
            "isolation": "NAMESPACE",
            "stateMode": "STATELESS",
            "sessionAffinity": "NONE",
        }
    ).model_dump(mode="json")
    agent = DefinitionContent.model_validate(
        {
            "title": "合成成本核验职责",
            "duties": ["按批准方案处理隔离合成资料", "保留来源、限制及产物"],
            "capabilities": list(OPERATIONS),
            "runtimes": ["NATIVE_KUBERNETES"],
            "businessPurpose": "验证只读执行与人工验收闭环，不处理真实企业账单。",
        }
    ).model_dump(mode="json")
    source = {
        "sourceId": "s5-324-synthetic-cost",
        "documentId": "s5-324-synthetic-billing",
        "documentVersion": "1",
        "kind": "TEXT",
        "provenance": "S5-V023-IMPL-324:MANUALLY_CONSTRUCTED_SYNTHETIC_ONLY",
        "content": json.dumps(
            source_document(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    }
    return {"skill": skill, "runtime": runtime, "agent": agent, "knowledge": source}
