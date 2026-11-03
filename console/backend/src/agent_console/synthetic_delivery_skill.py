# ruff: noqa: RUF001 -- Chinese evidence descriptions.
"""Deterministic, read-only supplier delivery analysis over an explicit snapshot."""

from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation

from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision

OPERATIONS = (
    "READ_DATA",
    "VALIDATE_DATA",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RECOMMEND",
    "RENDER_REPORT",
)
CONFIGURATION = {
    "schemaVersion": "synthetic-delivery-skill.v1",
    "maxRows": 128,
    "operations": list(OPERATIONS),
    "overdue": "promisedDate < assessmentDate and orderedQuantity > deliveredQuantity",
    "excluded": ["CANCELLED", "FULLY_DELIVERED"],
    "ranking": ["maxOverdueDays:desc", "overdueOrderCount:desc", "supplierId:asc"],
    "aggregateQuantity": "PER_UNIT_ONLY",
    "realBusinessConclusion": False,
}


def fail(reason):
    raise SkillExecutorFailure(reason, outcome_unknown=False)


def parse_date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("date required")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("canonical calendar date required")
    return parsed


def quantity(value):
    if not isinstance(value, str) or len(value) > 20:
        raise ValueError("decimal string required")
    number = Decimal(value)
    if not number.is_finite() or not 0 <= number <= Decimal("1000000000"):
        raise ValueError("quantity bounds")
    if not -6 <= number.as_tuple().exponent <= 9:
        raise ValueError("quantity precision")
    return number


def decimal_text(value):
    return format(value, "f")


def analyze(source):
    if (
        not isinstance(source, dict)
        or source.get("synthetic") is not True
        or source.get("schemaVersion") != "synthetic-delivery-source.v1"
    ):
        fail("SYNTHETIC_DELIVERY_SOURCE_REQUIRED")
    try:
        assessment = parse_date(source.get("assessmentDate"))
    except (ValueError, TypeError):
        fail("SYNTHETIC_DELIVERY_ASSESSMENT_DATE_INVALID")
    rows = source.get("orders")
    if not isinstance(rows, list) or not 1 <= len(rows) <= CONFIGURATION["maxRows"]:
        fail("SYNTHETIC_DELIVERY_ROWS_INVALID")
    ids = Counter(
        row.get("orderId")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("orderId"), str)
    )
    anomalies, excluded, orders = [], [], []
    for index, row in enumerate(rows):
        identity = row.get("orderId") if isinstance(row, dict) else None
        reasons = []
        if (
            not isinstance(row, dict)
            or not isinstance(identity, str)
            or not identity.strip()
        ):
            reasons.append("MISSING_ORDER_ID_OR_INVALID_ROW")
        elif ids[identity] != 1:
            reasons.append("DUPLICATE_ORDER_ID")
        if reasons:
            anomalies.append(
                {"rowIndex": index, "orderId": identity, "reasons": reasons}
            )
            continue
        if row.get("status") == "CANCELLED":
            excluded.append(
                {"rowIndex": index, "orderId": identity, "reason": "CANCELLED"}
            )
            continue
        try:
            ordered = quantity(row.get("orderedQuantity"))
            delivered = quantity(row.get("deliveredQuantity"))
            if delivered > ordered:
                raise ValueError("delivered exceeds ordered")
        except (ValueError, InvalidOperation):
            anomalies.append(
                {
                    "rowIndex": index,
                    "orderId": identity,
                    "reasons": ["QUANTITY_CONTRADICTION_OR_MISSING"],
                }
            )
            continue
        if ordered == delivered:
            excluded.append(
                {"rowIndex": index, "orderId": identity, "reason": "FULLY_DELIVERED"}
            )
            continue
        if row.get("status") not in ("OPEN", "PARTIALLY_DELIVERED"):
            reasons.append("UNKNOWN_OR_INCONSISTENT_STATUS")
        if not isinstance(row.get("supplierId"), str) or not row["supplierId"].strip():
            reasons.append("SUPPLIER_REQUIRED")
        if not isinstance(row.get("unit"), str) or not row["unit"].strip():
            reasons.append("UNIT_REQUIRED")
        try:
            promised = parse_date(row.get("promisedDate"))
        except (ValueError, TypeError):
            reasons.append("PROMISED_DATE_MISSING_OR_INVALID")
        if reasons:
            anomalies.append(
                {"rowIndex": index, "orderId": identity, "reasons": reasons}
            )
            continue
        days = max(0, (assessment - promised).days)
        orders.append(
            {
                "rowIndex": index,
                "orderId": identity,
                "supplierId": row["supplierId"],
                "unit": row["unit"],
                "promisedDate": promised.isoformat(),
                "orderedQuantity": decimal_text(ordered),
                "deliveredQuantity": decimal_text(delivered),
                "remainingQuantity": decimal_text(ordered - delivered),
                "overdueDays": days,
                "overdue": days > 0,
                "calculation": (
                    "remaining=ordered-delivered; "
                    "overdueDays=max(0,assessmentDate-promisedDate)"
                ),
            }
        )
    suppliers = {}
    for order in orders:
        if not order["overdue"]:
            continue
        supplier = suppliers.setdefault(
            order["supplierId"],
            {
                "supplierId": order["supplierId"],
                "orders": [],
                "remainingByUnit": {},
                "maxOverdueDays": 0,
            },
        )
        supplier["orders"].append(order)
        unit = order["unit"]
        supplier["remainingByUnit"][unit] = decimal_text(
            Decimal(supplier["remainingByUnit"].get(unit, "0"))
            + Decimal(order["remainingQuantity"])
        )
        supplier["maxOverdueDays"] = max(
            supplier["maxOverdueDays"], order["overdueDays"]
        )
    ranked = list(suppliers.values())
    for supplier in ranked:
        supplier["orders"].sort(key=lambda row: row["orderId"])
        supplier["overdueOrderCount"] = len(supplier["orders"])
    ranked.sort(
        key=lambda row: (
            -row["maxOverdueDays"],
            -row["overdueOrderCount"],
            row["supplierId"],
        )
    )
    for rank, supplier in enumerate(ranked, 1):
        supplier["rank"] = rank
        supplier["rankingReason"] = (
            f"最长逾期{supplier['maxOverdueDays']}天，逾期订单{supplier['overdueOrderCount']}笔；同分按供应商编号稳定排列。仅演示优先级，不代表真实损失。"
        )
    return {
        "assessmentDate": assessment.isoformat(),
        "suppliers": ranked,
        "orderDetails": orders,
        "anomalies": anomalies,
        "excludedOrders": excluded,
        "gaps": ["仅合成订单，真实企业状况与损失未验证"],
        "suggestedChecks": [
            "核对异常记录的原始日期、数量及单位",
            "与供应商核对未交数量和最新承诺，不自动执行业务变更",
        ],
    }


class SyntheticDeliverySkillExecutor:
    revision = ExecutorRevision(
        "synthetic-delivery-readonly", "1", canonical_digest(CONFIGURATION)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        del timeout_ms
        if (
            not isinstance(inputs, dict)
            or operation not in OPERATIONS
            or inputs.get("synthetic") is not True
            or inputs.get("schemaVersion") != "synthetic-delivery-input.v1"
        ):
            fail("SYNTHETIC_DELIVERY_BOUNDARY_REQUIRED")
        if not isinstance(inputs.get("sourceSnapshot"), dict):
            fail("SYNTHETIC_DELIVERY_SNAPSHOT_REQUIRED")
        source = inputs.get("source")
        if operation != "READ_DATA":
            if not isinstance(inputs.get("dependencies"), dict):
                fail("SYNTHETIC_DELIVERY_DEPENDENCY_REQUIRED")
            dependencies = list(inputs["dependencies"].values())
            if not dependencies or any(
                not isinstance(item, dict)
                or item.get("schemaVersion") != "synthetic-delivery-output.v1"
                or item.get("sourceSnapshot") != inputs.get("sourceSnapshot")
                for item in dependencies
            ):
                fail("SYNTHETIC_DELIVERY_DEPENDENCY_REQUIRED")
            source = dependencies[0].get("source")
            if any(
                item.get("sourceDigest") != canonical_digest(source)
                or item.get("source") != source
                for item in dependencies
            ):
                fail("SYNTHETIC_DELIVERY_SOURCE_CONFLICT")
        analysis = analyze(source)
        output = {
            "schemaVersion": "synthetic-delivery-output.v1",
            "synthetic": True,
            "operation": operation,
            "sourceSnapshot": inputs["sourceSnapshot"],
            "sourceDigest": canonical_digest(source),
            "source": source,
            "limitations": [
                "SYNTHETIC_ONLY",
                "DEMO_RANKING_NOT_BUSINESS_LOSS",
                "REAL_BUSINESS_OUTCOME_UNPROVEN",
            ],
            **analysis,
        }
        if operation == "RENDER_REPORT":
            output["title"] = "供应商交付及时性 · 合成订单分析"
            output["businessConclusion"] = "UNDETERMINED"
        return SkillExecutorResult(True, output, "synthetic-delivery:" + invocation_id)
