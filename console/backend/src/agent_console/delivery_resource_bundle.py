# ruff: noqa: RUF001 -- Chinese resource content.
"""Exact synthetic purchase-order resource drafts; no publication or execution."""

import json

from .agent_definition_schemas import DefinitionContent
from .prepared_resource_bundle import resource_content as cost_resource_content
from .skill_mcp_schemas import ResourceContent
from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor


def source_document():
    def order(
        identity, supplier, due, ordered, delivered="0", unit="件", status="OPEN"
    ):
        return {
            "orderId": identity,
            "supplierId": supplier,
            "promisedDate": due,
            "orderedQuantity": ordered,
            "deliveredQuantity": delivered,
            "unit": unit,
            "status": status,
        }

    return {
        "schemaVersion": "synthetic-delivery-source.v1",
        "synthetic": True,
        "snapshotId": "s5-324-delivery-orders-v1",
        "assessmentDate": "2026-09-20",
        "provenance": (
            "MANUALLY_CONSTRUCTED_SYNTHETIC_PURCHASE_ORDERS_NOT_ENTERPRISE_DATA"
        ),
        "orders": [
            order(
                "PO-S01",
                "SYN-A",
                "2026-09-10",
                "100",
                "40",
                status="PARTIALLY_DELIVERED",
            ),
            order(
                "PO-S02", "SYN-A", "2026-09-15", "20", "5", "箱", "PARTIALLY_DELIVERED"
            ),
            order("PO-S03", "SYN-B", "2026-09-10", "30"),
            order(
                "PO-S04",
                "SYN-C",
                "2026-09-18",
                "50",
                "10",
                status="PARTIALLY_DELIVERED",
            ),
            order("PO-S05", "SYN-D", "2026-09-20", "20"),
            order("PO-S06", "SYN-D", "2026-09-21", "20"),
            order("PO-S07", "SYN-A", "2026-09-01", "10", "10", status="DELIVERED"),
            order("PO-S08", "SYN-B", "2026-09-01", "10", status="CANCELLED"),
            order("PO-S09", "SYN-E", None, "10"),
            order(
                "PO-S10",
                "SYN-F",
                "2026-09-01",
                "10",
                "12",
                status="PARTIALLY_DELIVERED",
            ),
        ],
    }


def resource_content():
    # Reuse the resource envelope and READ_ONLY policy, not cost logic/data.
    bundle = cost_resource_content()
    skill = bundle["skill"]
    skill.update(
        description="固定合成采购订单快照的供应商交付及时性分析。",
        instructions="严格早于判定日且有未交余量才逾期；取消和交清排除；分单位、异常不猜补；仅演示排序。",
    )
    revision = SyntheticDeliverySkillExecutor.revision
    for op in skill["operations"]:
        op.update(
            executorId=revision.executor_id,
            executorRevision=revision.executor_revision,
            executorConfigurationDigest=revision.configuration_digest,
        )
        op["inputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "synthetic-delivery-input.v1"
        ]
        op["outputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "synthetic-delivery-output.v1"
        ]
        op["ioLimits"]["policyId"] = "synthetic-delivery-bounds"
    bundle["skill"] = ResourceContent.model_validate(skill).model_dump(
        mode="json", exclude_none=True
    )
    bundle["agent"] = DefinitionContent.model_validate(
        {
            **bundle["agent"],
            "title": "合成供应商交付及时性核验职责",
            "businessPurpose": "按固定合成订单分析逾期、排序和异常，不推断真实损失。",
        }
    ).model_dump(mode="json")
    bundle["knowledge"] = {
        "sourceId": "s5-324-synthetic-delivery",
        "documentId": "s5-324-synthetic-purchase-orders",
        "documentVersion": "1",
        "kind": "TEXT",
        "provenance": "S5-V023-IMPL-324:MANUALLY_CONSTRUCTED_SYNTHETIC_ONLY",
        "content": json.dumps(
            source_document(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    }
    return bundle
