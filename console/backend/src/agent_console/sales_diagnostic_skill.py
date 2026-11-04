"""Read-only two-period sales observations over an exact bounded CSV snapshot."""

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision
from .tabular_snapshot import SnapshotInputError, verify_snapshot

FIELDS = (
    "rowId",
    "period",
    "region",
    "channel",
    "product",
    "currency",
    "kind",
    "status",
    "netSales",
    "cost",
)
METRIC = "RECOGNIZED_NET_SALES_EXCLUDING_TAX"
OPERATIONS = (
    "READ_DATA",
    "VALIDATE_DATA",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RENDER_REPORT",
)
CONFIG = {
    "schemaVersion": "sales-diagnostic-skill.v1",
    "metric": METRIC,
    "operations": list(OPERATIONS),
    "currency": "SEPARATE_NO_IMPLICIT_FX",
    "claim": "OBSERVATIONAL_NOT_CAUSAL",
    "maxRows": 10000,
}


def fail(code):
    raise SkillExecutorFailure(code, outcome_unknown=False)


def money(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"-?\d{1,13}(?:\.\d{1,2})?", value
    ):
        raise ValueError
    number = Decimal(value)
    if (
        not number.is_finite()
        or abs(number) > Decimal("1000000000000")
        or number.as_tuple().exponent < -2
        or number.as_tuple().exponent > 12
    ):
        raise ValueError
    return number


def validate_source(source):
    if (
        not isinstance(source, dict)
        or source.get("schemaVersion") != "sales-diagnostic-source.v1"
        or source.get("synthetic") is not True
        or source.get("metric") != METRIC
    ):
        fail("SALES_EXACT_SYNTHETIC_SOURCE_REQUIRED")
    periods = source.get("periods")
    if (
        not isinstance(periods, list)
        or len(periods) != 2
        or not all(isinstance(p, str) and p.strip() for p in periods)
        or len(set(periods)) != 2
    ):
        fail("SALES_PERIOD_CONTRACT_INVALID")
    try:
        snapshot = verify_snapshot(source["snapshot"])
        if len(snapshot["rows"]) > 10000:
            raise ValueError
        seen = set()
        rows = []
        excluded = []
        for item in snapshot["rows"]:
            row = item["values"]
            if not all(isinstance(row.get(f), str) and row[f].strip() for f in FIELDS):
                raise ValueError
            if (
                row["rowId"] in seen
                or row["period"] not in periods
                or row["status"] not in {"POSTED", "CANCELLED"}
                or row["kind"] not in {"SALE", "RETURN"}
            ):
                raise ValueError
            seen.add(row["rowId"])
            if (
                len(row["currency"]) != 3
                or not row["currency"].isascii()
                or not row["currency"].isalpha()
                or not row["currency"].isupper()
            ):
                raise ValueError
            sales, cost = money(row["netSales"]), money(row["cost"])
            if (row["kind"] == "SALE" and (sales < 0 or cost < 0)) or (
                row["kind"] == "RETURN" and (sales > 0 or cost > 0)
            ):
                raise ValueError
            if row["status"] == "CANCELLED":
                excluded.append(
                    {
                        "rowId": row["rowId"],
                        "sourceLine": item["sourceLine"],
                        "reason": "CANCELLED",
                    }
                )
                continue
            rows.append(
                {
                    **row,
                    "sourceLine": item["sourceLine"],
                    "sales": sales,
                    "costAmount": cost,
                }
            )
        if not rows:
            fail("SALES_NO_POSTED_ROWS")
    except (
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        SnapshotInputError,
    ) as exc:
        raise SkillExecutorFailure(
            "SALES_SOURCE_ROWS_INVALID", outcome_unknown=False
        ) from exc
    return rows, excluded


def text(number):
    return format(number.quantize(Decimal("0.01")), "f")


def compare(before, after):
    return {
        "baseline": text(before),
        "current": text(after),
        "delta": text(after - before),
        "changeRate": None if before == 0 else str((after - before) / abs(before)),
        "rateReason": "BASELINE_ZERO" if before == 0 else None,
    }


def analyze_sales(source, source_reference):
    rows, excluded = validate_source(source)
    periods = source["periods"]
    totals = defaultdict(lambda: defaultdict(lambda: [Decimal(0), Decimal(0), []]))
    groups = {
        d: defaultdict(lambda: defaultdict(lambda: [Decimal(0), []]))
        for d in ["region", "channel", "product"]
    }
    for r in rows:
        t = totals[r["currency"]][r["period"]]
        t[0] += r["sales"]
        t[1] += r["costAmount"]
        t[2].append(r["rowId"])
        for dimension in groups:
            g = groups[dimension][(r["currency"], r[dimension])][r["period"]]
            g[0] += r["sales"]
            g[1].append(r["rowId"])
    result = []
    for currency in sorted(totals):
        before, after = [totals[currency][p] for p in periods]
        result.append(
            {
                "currency": currency,
                "netSales": compare(before[0], after[0]),
                "grossProfit": compare(before[0] - before[1], after[0] - after[1]),
                "sourceRows": {periods[0]: before[2], periods[1]: after[2]},
            }
        )
    dimensions = {}
    for dimension, items in groups.items():
        values = []
        for (currency, name), by_period in items.items():
            before, after = [by_period[p] for p in periods]
            values.append(
                {
                    "currency": currency,
                    "value": name,
                    **compare(before[0], after[0]),
                    "sourceRows": {periods[0]: before[1], periods[1]: after[1]},
                }
            )
        dimensions[dimension] = sorted(
            values, key=lambda r: (r["currency"], Decimal(r["delta"]), r["value"])
        )
    return {
        "schemaVersion": "sales-diagnostic-output.v1",
        "synthetic": True,
        "metric": METRIC,
        "periods": periods,
        "sourceSnapshot": source_reference,
        "sourceDigest": canonical_digest(source),
        "source": source,
        "currencyComparisons": result,
        "dimensions": dimensions,
        "excludedRows": excluded,
        "limitations": [
            "SYNTHETIC_ONLY",
            "NO_CROSS_CURRENCY_SUM",
            "OBSERVATIONAL_NOT_CAUSAL",
            "NO_SALES_IMPROVEMENT_PROVEN",
        ],
        "businessConclusion": "UNDETERMINED",
    }


class SalesDiagnosticSkillExecutor:
    revision = ExecutorRevision(
        "sales-diagnostic-readonly", "1", canonical_digest(CONFIG)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        del timeout_ms
        if (
            operation not in OPERATIONS
            or not isinstance(inputs, dict)
            or inputs.get("schemaVersion") != "sales-diagnostic-input.v1"
            or inputs.get("synthetic") is not True
        ):
            fail("SALES_SKILL_CONTRACT_INVALID")
        source = inputs.get("source")
        if source is None:
            dependencies = inputs.get("dependencies")
            if isinstance(dependencies, dict) and dependencies:
                first = next(iter(dependencies.values()))
                if isinstance(first, dict):
                    source = first.get("source")
        ref = inputs.get("sourceSnapshot")
        if (
            not isinstance(ref, dict)
            or set(ref) != {"resource_id", "revision_id", "digest"}
            or not all(isinstance(v, str) and v for v in ref.values())
        ):
            fail("SALES_SOURCE_REFERENCE_REQUIRED")
        try:
            ExactReference.model_validate(ref)
        except ValueError:
            fail("SALES_SOURCE_REFERENCE_REQUIRED")
        if operation != "READ_DATA":
            deps = inputs.get("dependencies")
            if not isinstance(deps, dict) or not deps:
                fail("SALES_DEPENDENCY_REQUIRED")
            for report in deps.values():
                if (
                    not isinstance(report, dict)
                    or report.get("schemaVersion") != "sales-diagnostic-output.v1"
                    or report.get("sourceSnapshot") != ref
                    or report.get("sourceDigest") != canonical_digest(source)
                    or report.get("source") != source
                ):
                    fail("SALES_DEPENDENCY_SOURCE_MISMATCH")
        output = analyze_sales(source, ref)
        output["operation"] = operation
        if operation == "RENDER_REPORT":
            output["title"] = "销售变化诊断 · 固定合成数据"
        return SkillExecutorResult(True, output, "sales-diagnostic:" + invocation_id)
