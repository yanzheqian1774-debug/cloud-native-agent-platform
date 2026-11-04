# ruff: noqa: RUF001 -- Chinese resource content.
"""Sales drafts using existing resource schemas; no publication or authority."""

import json

from .agent_definition_schemas import DefinitionContent
from .prepared_resource_bundle import resource_content as base_content
from .sales_diagnostic_skill import (
    FIELDS,
    METRIC,
    OPERATIONS,
    SalesDiagnosticSkillExecutor,
)
from .skill_mcp_schemas import ResourceContent
from .tabular_snapshot import read_csv_snapshot


def source_document(raw: bytes, *, columns=None):
    return {
        "schemaVersion": "sales-diagnostic-source.v1",
        "synthetic": True,
        "metric": METRIC,
        "periods": ["2026-08", "2026-09"],
        "provenance": "MANUALLY_CONSTRUCTED_SYNTHETIC_NOT_ENTERPRISE_DATA",
        "snapshot": read_csv_snapshot(
            raw,
            source_id="synthetic-sales-v1",
            columns=columns or {f: f for f in FIELDS},
            required=FIELDS,
        ),
    }


def resource_content(source):
    bundle = base_content()
    skill = bundle["skill"]
    skill.update(
        description="固定合成销售快照的两期变化诊断。",
        instructions="按币种分别核算不含税净销售额与毛利；退货冲减、取消排除；变化贡献不证明因果或改善效果。",
    )
    skill["capabilities"] = list(OPERATIONS)
    skill["operations"] = [op for op in skill["operations"] if op["name"] in OPERATIONS]
    revision = SalesDiagnosticSkillExecutor.revision
    for op in skill["operations"]:
        op.update(
            executorId=revision.executor_id,
            executorRevision=revision.executor_revision,
            executorConfigurationDigest=revision.configuration_digest,
        )
        op["inputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "sales-diagnostic-input.v1"
        ]
        op["outputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "sales-diagnostic-output.v1"
        ]
        op["ioLimits"]["policyId"] = "sales-diagnostic-bounds"
    bundle["skill"] = ResourceContent.model_validate(skill).model_dump(
        mode="json", exclude_none=True
    )
    bundle["agent"] = DefinitionContent.model_validate(
        {
            **bundle["agent"],
            "title": "合成销售变化诊断职责",
            "businessPurpose": "核对两期销售变化贡献，不推断真实原因或未来改善。",
        }
    ).model_dump(mode="json")
    bundle["knowledge"] = {
        "sourceId": "synthetic-sales",
        "documentId": "synthetic-sales-two-periods",
        "documentVersion": "1",
        "kind": "TEXT",
        "provenance": "MANUALLY_CONSTRUCTED_SYNTHETIC_ONLY",
        "content": json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    }
    return bundle
