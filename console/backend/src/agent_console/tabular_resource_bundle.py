# ruff: noqa: RUF001 -- Chinese resource content.
"""Drafts only: reusable adapter plus caller-supplied synthetic source mapping."""

import json

from .prepared_resource_bundle import resource_content as base_content
from .skill_mcp_schemas import ResourceContent
from .tabular_diagnostic_skill import (
    OPERATIONS,
    TabularDiagnosticSkillExecutor,
    analyze,
)


def resource_content(source):
    analyze(source)
    bundle = base_content()
    skill = bundle["skill"]
    skill.update(
        description="按资料声明字段、单位和上限检查指标，保留异常与来源。",
        instructions="使用已发布快照及其字段映射；只计算声明上限的超限记录，不能推断原因或执行整改。",
        capabilities=list(OPERATIONS),
    )
    skill["operations"] = [op for op in skill["operations"] if op["name"] in OPERATIONS]
    revision = TabularDiagnosticSkillExecutor.revision
    for op in skill["operations"]:
        op.update(
            executorId=revision.executor_id,
            executorRevision=revision.executor_revision,
            executorConfigurationDigest=revision.configuration_digest,
        )
        op["inputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "tabular-diagnostic-input.v1"
        ]
        op["outputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "tabular-diagnostic-output.v1"
        ]
        op["outputSchema"]["properties"]["operation"]["enum"] = list(OPERATIONS)
        op["ioLimits"]["policyId"] = "tabular-diagnostic-bounds"
    bundle["skill"] = ResourceContent.model_validate(skill).model_dump(
        mode="json", exclude_none=True
    )
    bundle["agent"].update(
        title="指标异常诊断",
        businessPurpose="依据已声明规则与字段映射核对异常，不推断因果或业务改善。",
    )
    bundle["knowledge"] = {
        "sourceId": "synthetic-tabular",
        "documentId": "synthetic-tabular-mapped",
        "documentVersion": "1",
        "kind": "TEXT",
        "provenance": "MANUALLY_CONSTRUCTED_SYNTHETIC_ONLY",
        "content": json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    }
    return bundle
