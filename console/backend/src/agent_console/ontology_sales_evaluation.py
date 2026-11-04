"""Independent minor-unit reference checks; never calls the producing compiler."""

from collections import defaultdict
from decimal import Decimal

from .resource_use_domain import canonical_digest
from .tabular_snapshot import verify_snapshot

CHECKS = ("source", "totals", "contributions", "exceptions", "claim_boundary")


def _cents(value):
    number = Decimal(value)
    if not number.is_finite() or number * 100 != (number * 100).to_integral_value():
        raise ValueError("BAD_MONEY")
    return int(number * 100)


def _amount(expression, rows):
    if expression["op"] == "SUM":
        return sum(_cents(row[expression["field"]]) for row in rows)
    if expression["op"] != "SUBTRACT" or len(expression["operands"]) != 2:
        raise ValueError("BAD_EXPRESSION")
    left, right = expression["operands"]
    return _amount(left, rows) - _amount(right, rows)


def evaluate(criterion, source, report, preparation, content):
    binding = preparation.business_semantics
    applicability = criterion.get("applicability", {})
    check = applicability.get("check")
    if (
        criterion.get("evaluator_type") != "SYNTHETIC_ONTOLOGY_SALES"
        or criterion.get("evaluator_version") != "1"
        or criterion.get("criterion_type") != "DETERMINISTIC_BOOLEAN"
        or criterion.get("measurement") != {"expected": True}
        or set(criterion.get("required_evidence_kinds", []))
        != {"NATIVE_EXECUTION_ARTIFACT", "PUBLISHED_SYNTHETIC_SOURCE"}
        or applicability.get("bindingDigest") != binding.digest
        or applicability.get("sourceContentDigest") != canonical_digest(source)
        or check not in CHECKS
    ):
        return "UNKNOWN", "ONTOLOGY_CRITERION_NOT_APPLICABLE"
    try:
        if (
            report["operation"] != "RENDER_REPORT"
            or report.get("schemaVersion") != "ontology-sales-output.v1"
            or report.get("synthetic") is not True
            or report["binding"] != binding.model_dump(mode="json")
            or report["bindingDigest"] != binding.digest
            or report["source"] != source
            or report["sourceSnapshot"] != binding.source.model_dump(mode="json")
            or report.get("businessConclusion") != "UNDETERMINED"
        ):
            raise ValueError("BINDING_MISMATCH")
        source_rows = verify_snapshot(source["snapshot"])["rows"]
        mapping = next(
            m for m in content["mappings"] if m["code"] == binding.mapping_code
        )
        metric_defs = {m["code"]: m for m in content["metrics"]}
        reports = report["reports"]
        if len(reports) != len(binding.queries):
            raise ValueError("REPORT_COUNT")
        for query, result in zip(binding.queries, reports, strict=True):
            matching = [
                m
                for m in metric_defs.values()
                if query.metric in (m["code"], m["name"], *m.get("aliases", []))
            ]
            if len(matching) != 1:
                raise ValueError("METRIC_AMBIGUOUS")
            metric = matching[0]
            if (
                result["metric"],
                result["metricName"],
                result["unit"],
                result["periods"],
                result["query"],
            ) != (
                metric["code"],
                metric["name"],
                metric["unit"],
                source["periods"],
                query.model_dump(mode="json"),
            ):
                raise ValueError("REPORT_SEMANTICS_MISMATCH")
            groups, exclusions = defaultdict(list), []
            for item in source_rows:
                original = item["values"]
                if original["status"] == "CANCELLED":
                    exclusions.append(
                        {
                            "rowId": original["rowId"],
                            "sourceLine": item["sourceLine"],
                            "reason": "CANCELLED",
                        }
                    )
                    continue
                row = {key: original[value] for key, value in mapping["fields"].items()}
                reason = (
                    "KIND_EXCLUDED_BY_ONTOLOGY"
                    if row["kind"] not in content["rules"]["included_kinds"]
                    else "QUERY_FILTER"
                    if any(row[k] not in values for k, values in query.filters.items())
                    else None
                )
                if reason:
                    exclusions.append({"rowId": row["rowId"], "reason": reason})
                    continue
                groups[(row["currency"], *(row[d] for d in query.dimensions))].append(
                    row
                )
            actual = result["rows"]
            if len(actual) != len(groups) or result["sourceDigest"] != canonical_digest(
                source
            ):
                raise ValueError("TOTAL_COUNT")
            for row, (key, values) in zip(actual, sorted(groups.items()), strict=True):
                periods = source["periods"]
                a, b = [
                    _amount(
                        metric["expression"], [r for r in values if r["period"] == p]
                    )
                    for p in periods
                ]
                if row["currency"] != key[0] or row["dimensions"] != dict(
                    zip(query.dimensions, key[1:], strict=True)
                ):
                    raise ValueError("GROUP_MISMATCH")
                if (
                    _cents(row["baseline"]),
                    _cents(row["current"]),
                    _cents(row["delta"]),
                ) != (a, b, b - a):
                    raise ValueError("TOTAL_MISMATCH")
                if (
                    a == 0
                    and (
                        row["changeRate"] is not None
                        or row["rateReason"] != "BASELINE_ZERO"
                    )
                ) or (a != 0 and Decimal(row["changeRate"]) != Decimal(b - a) / abs(a)):
                    raise ValueError("RATE_MISMATCH")
                if row["sourceRows"] != {
                    p: [r["rowId"] for r in values if r["period"] == p] for p in periods
                }:
                    raise ValueError("SOURCE_ROWS")
            if (
                sorted(result["excludedRows"], key=lambda r: (r["rowId"], r["reason"]))
                != sorted(exclusions, key=lambda r: (r["rowId"], r["reason"]))
                or result["businessConclusion"] != "UNDETERMINED"
                or result["synthetic"] is not True
                or result["limitations"]
                != [
                    "SYNTHETIC_ONLY",
                    "NO_CROSS_CURRENCY_SUM",
                    "OBSERVATIONAL_NOT_CAUSAL",
                    "NO_SALES_IMPROVEMENT_PROVEN",
                ]
            ):
                raise ValueError("BOUNDARY_MISMATCH")
        return "SATISFIED", "ONTOLOGY_SALES_INDEPENDENT_CHECK_PASSED"
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return "NOT_SATISFIED", "ONTOLOGY_SALES_EVIDENCE_MISMATCH"
