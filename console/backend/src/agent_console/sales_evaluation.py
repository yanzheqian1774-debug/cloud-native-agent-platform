"""Independent minor-unit checks for synthetic sales artifacts; no business verdict.

This evaluator deliberately does not call the producing Skill or its validators.
The formal wrapper binds exact criterion applicability and source commitment.
"""

import re
from collections import defaultdict
from decimal import Decimal

from .resource_use_domain import canonical_digest
from .tabular_snapshot import SnapshotInputError, verify_snapshot

CHECKS = ("source", "totals", "contributions", "exceptions", "claim_boundary")


def minor(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"-?\d{1,13}(?:\.\d{1,2})?", value
    ):
        raise ValueError("SALES_EVALUATION_MONEY_INVALID")
    return int(Decimal(value) * 100)


def evaluate_sales(check, source, report, reference):
    if (
        check not in CHECKS
        or not isinstance(source, dict)
        or not isinstance(report, dict)
    ):
        return "UNKNOWN", "SALES_EVIDENCE_MISSING"
    try:
        snapshot = verify_snapshot(source["snapshot"])
        periods = source["periods"]
        if (
            source.get("synthetic") is not True
            or source.get("schemaVersion") != "sales-diagnostic-source.v1"
            or source.get("metric") != "RECOGNIZED_NET_SALES_EXCLUDING_TAX"
            or not isinstance(periods, list)
            or len(periods) != 2
            or not all(isinstance(p, str) and p for p in periods)
            or periods[0] == periods[1]
            or report.get("schemaVersion") != "sales-diagnostic-output.v1"
            or report.get("operation") != "RENDER_REPORT"
        ):
            return "UNKNOWN", "SALES_EVIDENCE_CONTRACT_INVALID"
        provenance_valid = (
            report.get("sourceSnapshot") == reference
            and report.get("sourceDigest") == canonical_digest(source)
            and report.get("source") == source
            and report.get("periods") == periods
        )
        if not provenance_valid:
            return "NOT_SATISFIED", "SALES_SOURCE_MISMATCH"
        totals = defaultdict(lambda: [0, 0, []])
        groups = {
            d: defaultdict(lambda: [0, []]) for d in ("region", "channel", "product")
        }
        excluded = []
        seen = set()
        for item in snapshot["rows"]:
            row = item["values"]
            identity, period, currency = row["rowId"], row["period"], row["currency"]
            if (
                identity in seen
                or not identity
                or period not in periods
                or not re.fullmatch(r"[A-Z]{3}", currency)
            ):
                raise ValueError
            seen.add(identity)
            sales, cost = minor(row["netSales"]), minor(row["cost"])
            if row["kind"] == "SALE":
                if min(sales, cost) < 0:
                    raise ValueError
            elif row["kind"] == "RETURN":
                if max(sales, cost) > 0:
                    raise ValueError
            else:
                raise ValueError
            if row["status"] == "CANCELLED":
                excluded.append(
                    {
                        "rowId": identity,
                        "sourceLine": item["sourceLine"],
                        "reason": "CANCELLED",
                    }
                )
                continue
            if row["status"] != "POSTED":
                raise ValueError
            total = totals[currency, period]
            total[0] += sales
            total[1] += sales - cost
            total[2].append(identity)
            for dimension in groups:
                if not row[dimension]:
                    raise ValueError
                group = groups[dimension][currency, row[dimension], period]
                group[0] += sales
                group[1].append(identity)
        if not totals:
            raise ValueError
        if check == "source":
            valid = (
                report.get("sourceSnapshot") == reference
                and report.get("sourceDigest") == canonical_digest(source)
                and report.get("source") == source
                and report.get("periods") == periods
            )
        elif check == "totals":
            rows = report["currencyComparisons"]
            currencies = {c for c, _ in totals}
            valid = (
                len(rows) == len(currencies)
                and {r["currency"] for r in rows} == currencies
            )
            for result in rows:
                before, after = (totals[result["currency"], p] for p in periods)
                valid = (
                    valid
                    and matches(result["netSales"], before[0], after[0])
                    and matches(result["grossProfit"], before[1], after[1])
                    and result["sourceRows"]
                    == dict(zip(periods, (before[2], after[2]), strict=True))
                )
        elif check == "contributions":
            valid = set(report["dimensions"]) == set(groups)
            for dimension, expected in groups.items():
                rows = report["dimensions"][dimension]
                keys = {(c, name) for c, name, _ in expected}
                valid = (
                    valid
                    and len(rows) == len(keys)
                    and {(r["currency"], r["value"]) for r in rows} == keys
                )
                for result in rows:
                    before, after = (
                        expected[result["currency"], result["value"], p]
                        for p in periods
                    )
                    valid = (
                        valid
                        and matches(result, before[0], after[0])
                        and result["sourceRows"]
                        == dict(zip(periods, (before[1], after[1]), strict=True))
                    )
        elif check == "exceptions":
            valid = report.get("excludedRows") == excluded
        else:
            valid = (
                report.get("synthetic") is True
                and report.get("businessConclusion") == "UNDETERMINED"
                and report.get("metric") == source["metric"]
                and report.get("limitations")
                == [
                    "SYNTHETIC_ONLY",
                    "NO_CROSS_CURRENCY_SUM",
                    "OBSERVATIONAL_NOT_CAUSAL",
                    "NO_SALES_IMPROVEMENT_PROVEN",
                ]
            )
        return (
            ("SATISFIED", "SALES_SYNTHETIC_CHECK_PASSED")
            if valid
            else ("NOT_SATISFIED", "SALES_REPORT_MISMATCH")
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, SnapshotInputError):
        return "UNKNOWN", "SALES_EVIDENCE_INVALID"


def matches(result, before, after):
    return (
        minor(result["baseline"]) == before
        and minor(result["current"]) == after
        and minor(result["delta"]) == after - before
        and (
            result["changeRate"] is None and result["rateReason"] == "BASELINE_ZERO"
            if before == 0
            else result["rateReason"] is None
            and Decimal(result["changeRate"]) == Decimal(after - before) / abs(before)
        )
    )


def evaluate(criterion, source, report, reference):
    if (
        not isinstance(criterion, dict)
        or criterion.get("criterion_type") != "DETERMINISTIC_BOOLEAN"
        or criterion.get("measurement", {}).get("expected") is not True
        or criterion.get("evaluator_type") != "SYNTHETIC_SALES"
        or criterion.get("evaluator_version") != "1"
        or set(criterion.get("required_evidence_kinds", []))
        != {"NATIVE_EXECUTION_ARTIFACT", "PUBLISHED_SYNTHETIC_SOURCE"}
        or not isinstance(source, dict)
        or criterion.get("applicability", {}).get("sourceContentDigest")
        != canonical_digest(source)
    ):
        return "UNKNOWN", "SALES_EXACT_CRITERION_EVIDENCE_REQUIRED"
    return evaluate_sales(
        criterion.get("applicability", {}).get("check"), source, report, reference
    )
