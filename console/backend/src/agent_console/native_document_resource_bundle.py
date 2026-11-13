# ruff: noqa: RUF001 -- Chinese resource descriptions.
"""Published document tools reuse existing resource owners and typed task I/O."""

import json

from .native_document_skill import (
    OPERATIONS,
    NativeDefinitionQuerySkillExecutor,
    NativeDocumentSkillExecutor,
    NativeEmployeeDocumentSkillExecutor,
    NativeRuleDocumentSkillExecutor,
    NativeUserScopeDocumentSkillExecutor,
)
from .native_document_tools import validate_source
from .prepared_resource_bundle import resource_content as base_content
from .skill_mcp_schemas import ResourceContent


def resource_content(
    source,
    *,
    bound_employee=False,
    confirmed_user_scope=False,
    rule_bound=False,
    definition_query=False,
):
    if definition_query and not rule_bound:
        raise ValueError("DOCUMENT_RULE_BINDING_REQUIRED")
    validate_source(source)
    bundle = base_content()
    skill = bundle["skill"]
    skill.update(
        description="读取文本与规范，必要时在原会话追问，按确认范围核对文档完整性并引用原文。",
        instructions="读取资料、校验文本、分析文档、返回报告；分析内部由真实模型选择工具，范围不明确时追问，不代替业务批准。",
        capabilities=list(OPERATIONS),
    )
    skill["operations"] = [op for op in skill["operations"] if op["name"] in OPERATIONS]
    revision = (
        NativeDefinitionQuerySkillExecutor
        if definition_query
        else NativeRuleDocumentSkillExecutor
        if rule_bound
        else NativeUserScopeDocumentSkillExecutor
        if confirmed_user_scope
        else NativeEmployeeDocumentSkillExecutor
        if bound_employee
        else NativeDocumentSkillExecutor
    ).revision
    for op in skill["operations"]:
        op.update(
            executorId=revision.executor_id,
            executorRevision=revision.executor_revision,
            executorConfigurationDigest=revision.configuration_digest,
        )
        op["inputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "document-review-input.v1"
        ]
        if rule_bound:
            op["inputSchema"]["properties"].update(
                ontologyContent={"type": "object"}, businessSemantics={"type": "object"}
            )
            op["inputSchema"]["required"] = [
                *op["inputSchema"]["required"],
                "ontologyContent",
                "businessSemantics",
            ]
        op["outputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "document-review-output.v1"
        ]
        op["outputSchema"]["properties"]["operation"]["enum"] = list(OPERATIONS)
        op["ioLimits"].update(
            timeoutMs=480000,
            maxObjectDepth=24,
            maxProperties=20000,
            policyId="native-document-bounds",
        )
    bundle["skill"] = ResourceContent.model_validate(skill).model_dump(
        mode="json", exclude_none=True
    )
    bundle["agent"].update(
        title="文档完整性检查助手",
        businessPurpose="按用户确认规范检查文本交接材料，并保留准确原文依据。",
    )
    bundle["knowledge"] = {
        "sourceId": "synthetic-document-review",
        "documentId": "synthetic-document-package",
        "documentVersion": "1",
        "kind": "TEXT",
        "provenance": "MANUALLY_CONSTRUCTED_SYNTHETIC_ONLY",
        "content": json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    }
    return bundle
