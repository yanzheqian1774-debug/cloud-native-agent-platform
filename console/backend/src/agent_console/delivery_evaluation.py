"""Versioned deterministic checks for exact, authorized synthetic delivery reports."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from .resource_use_domain import canonical_digest

EVALUATOR = "synthetic-delivery-evidence.v1"
CHECKS = (
    "snapshot",
    "eligibility",
    "quantities",
    "ranking",
    "traceability",
    "anomalies",
)


def expected(source):
    """Independent evaluation algorithm; never call the producing Skill executor."""
    if (
        source.get("schemaVersion") != "synthetic-delivery-source.v1"
        or source.get("synthetic") is not True
    ):
        raise ValueError("SYNTHETIC_SOURCE_REQUIRED")
    assessment = date.fromisoformat(source["assessmentDate"])
    rows = source["orders"]
    counts = Counter(
        r.get("orderId")
        for r in rows
        if isinstance(r, dict) and isinstance(r.get("orderId"), str)
    )
    valid, excluded, anomalies = {}, set(), set()
    for i, r in enumerate(rows):
        if (
            not isinstance(r, dict)
            or not isinstance(r.get("orderId"), str)
            or not r["orderId"].strip()
            or counts[r["orderId"]] != 1
        ):
            anomalies.add(i)
            continue
        if r.get("status") == "CANCELLED":
            excluded.add(r["orderId"])
            continue
        try:
            values = [r["orderedQuantity"], r["deliveredQuantity"]]
            if any(not isinstance(v, str) or len(v) > 20 for v in values):
                raise ValueError
            ordered, delivered = map(Decimal, values)
            if (
                any(
                    not n.is_finite()
                    or not 0 <= n <= 10**9
                    or not -6 <= n.as_tuple().exponent <= 9
                    for n in (ordered, delivered)
                )
                or delivered > ordered
            ):
                raise ValueError
            if ordered == delivered:
                excluded.add(r["orderId"])
                continue
            if r.get("status") not in ("OPEN", "PARTIALLY_DELIVERED") or any(
                not isinstance(r.get(k), str) or not r[k].strip()
                for k in ("supplierId", "unit")
            ):
                raise ValueError
            promised = date.fromisoformat(r["promisedDate"])
            if promised.isoformat() != r["promisedDate"]:
                raise ValueError
            valid[r["orderId"]] = {
                "supplier": r["supplierId"],
                "unit": r["unit"],
                "remaining": ordered - delivered,
                "days": max(0, (assessment - promised).days),
                "rowIndex": i,
            }
        except (KeyError, ValueError, TypeError, InvalidOperation):
            anomalies.add(i)
    groups = defaultdict(list)
    for identity, row in valid.items():
        if row["days"] > 0:
            groups[row["supplier"]].append(identity)
    ranking = sorted(
        groups,
        key=lambda s: (-max(valid[o]["days"] for o in groups[s]), -len(groups[s]), s),
    )
    return valid, excluded, anomalies, groups, ranking


def checks(source, report, source_reference):
    valid, excluded, anomalies, groups, ranking = expected(source)
    details = report.get("orderDetails", [])
    by_id = {r["orderId"]: r for r in details}
    suppliers = report.get("suppliers", [])
    by_supplier = {r["supplierId"]: r for r in suppliers}
    eligible = (
        set(by_id) == set(valid)
        and len(details) == len(valid)
        and all(
            by_id[k].get("overdue") is (v["days"] > 0)
            and by_id[k].get("overdueDays") == v["days"]
            for k, v in valid.items()
        )
    )
    eligible = (
        eligible
        and {r["orderId"] for r in report.get("excludedOrders", [])} == excluded
        and len(report.get("excludedOrders", [])) == len(excluded)
    )
    quantity_ok = set(by_supplier) == set(groups) and all(
        by_id[k].get("unit") == v["unit"]
        and Decimal(by_id[k]["remainingQuantity"]) == v["remaining"]
        and all(
            Decimal(by_id[k][field]) == Decimal(source["orders"][v["rowIndex"]][field])
            for field in ("orderedQuantity", "deliveredQuantity")
        )
        for k, v in valid.items()
    )
    for supplier, ids in groups.items():
        units = defaultdict(Decimal)
        for identity in ids:
            units[valid[identity]["unit"]] += valid[identity]["remaining"]
        actual = {
            u: Decimal(q)
            for u, q in by_supplier.get(supplier, {}).get("remainingByUnit", {}).items()
        }
        quantity_ok = quantity_ok and dict(units) == actual
    ranking_ok = [r["supplierId"] for r in suppliers] == ranking and all(
        by_supplier[s].get("rank") == i
        and by_supplier[s].get("maxOverdueDays")
        == max(valid[o]["days"] for o in groups[s])
        and by_supplier[s].get("overdueOrderCount") == len(groups[s])
        for i, s in enumerate(ranking, 1)
    )
    trace = set(by_supplier) == set(groups) and all(
        {o["orderId"] for o in by_supplier[s].get("orders", [])} == set(ids)
        and len(by_supplier[s]["orders"]) == len(ids)
        and all(o == by_id.get(o["orderId"]) for o in by_supplier[s]["orders"])
        and bool(by_supplier[s].get("rankingReason"))
        for s, ids in groups.items()
    )
    trace = trace and all(
        by_id[k].get("rowIndex") == v["rowIndex"]
        and by_id[k].get("supplierId") == v["supplier"]
        and by_id[k].get("promisedDate")
        == source["orders"][v["rowIndex"]]["promisedDate"]
        and bool(by_id[k].get("calculation"))
        for k, v in valid.items()
    )
    return {
        "snapshot": report.get("synthetic") is True
        and report.get("source") == source
        and report.get("sourceDigest") == canonical_digest(source)
        and report.get("sourceSnapshot") == source_reference
        and report.get("assessmentDate") == source["assessmentDate"],
        "eligibility": eligible,
        "quantities": quantity_ok,
        "ranking": ranking_ok,
        "traceability": trace,
        "anomalies": {a["rowIndex"] for a in report.get("anomalies", [])} == anomalies
        and len(report.get("anomalies", [])) == len(anomalies)
        and all(
            a.get("reasons")
            and a.get("orderId") == source["orders"][a["rowIndex"]].get("orderId")
            for a in report.get("anomalies", [])
        )
        and bool(report.get("gaps"))
        and bool(report.get("suggestedChecks")),
    }


def evaluate(criterion, source, report, source_reference):
    check = criterion.get("applicability", {}).get("check")
    if (
        criterion.get("evaluator_type") != "SYNTHETIC_DELIVERY"
        or criterion.get("evaluator_version") != "1"
        or criterion.get("criterion_type") != "DETERMINISTIC_BOOLEAN"
        or criterion.get("measurement") != {"expected": True}
        or check not in CHECKS
    ):
        return "UNKNOWN", "NO_EXACT_MEASUREMENT_EVIDENCE"
    if not isinstance(source, dict) or not isinstance(report, dict):
        return "UNKNOWN", "EXACT_DELIVERY_REPORT_OR_SOURCE_MISSING"
    if criterion["applicability"].get("sourceContentDigest") != canonical_digest(
        source
    ):
        return "UNKNOWN", "EXACT_DELIVERY_SOURCE_MISMATCH"
    if set(criterion.get("required_evidence_kinds", [])) != {
        "NATIVE_EXECUTION_ARTIFACT",
        "PUBLISHED_SYNTHETIC_SOURCE",
    }:
        return "UNKNOWN", "DELIVERY_EVIDENCE_REQUIREMENTS_UNSUPPORTED"
    if (
        report.get("schemaVersion") != "synthetic-delivery-output.v1"
        or report.get("operation") != "RENDER_REPORT"
    ):
        return "UNKNOWN", "EXACT_DELIVERY_REPORT_REQUIRED"
    try:
        results = checks(source, report, source_reference)
    except (
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        IndexError,
        InvalidOperation,
    ):
        return "UNKNOWN", "DELIVERY_EVIDENCE_CONTRACT_INVALID"
    return (
        ("SATISFIED", "EXACT_DELIVERY_CHECK_PASSED")
        if results[check]
        else ("NOT_SATISFIED", "EXACT_DELIVERY_CHECK_FAILED")
    )
