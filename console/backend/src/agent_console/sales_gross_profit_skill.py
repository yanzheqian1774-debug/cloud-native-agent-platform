"""Opt-in local v2 candidate; never registered by current live compositions."""

import json
from collections import defaultdict
from copy import deepcopy
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from time import monotonic

from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest
from .sales_diagnostic_skill import METRIC, OPERATIONS, money
from .sales_gross_profit_contract import (
    CONTRACT_DIGEST,
    DIMENSIONS,
    INPUT_SCHEMA,
    LIMITS,
    METRICS,
    OUTPUT_SCHEMA,
    UNKNOWN_LABELS,
)
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision, SkillInvocationError
from .skill_resource_testing import schema_check
from .tabular_snapshot import SnapshotInputError, verify_snapshot

CONFIG = {
    "schemaVersion": "sales-diagnostic-skill.v2",
    "contractDigest": CONTRACT_DIGEST,
    "operations": list(OPERATIONS),
    "limits": LIMITS,
    "currency": "SEPARATE_NO_IMPLICIT_FX",
    "claim": "OBSERVATIONAL_NOT_CAUSAL",
    "decimalPrecision": 38,
    "decimalRounding": "ROUND_HALF_EVEN",
}
LIMITATIONS = [
    "SYNTHETIC_ONLY",
    "NO_CROSS_CURRENCY_SUM",
    "DIMENSION_DECOMPOSITIONS_NOT_ADDITIVE_TO_EACH_OTHER",
    "SOURCE_LABELS_AND_CURRENCY_CODES_NOT_CANONICALLY_VERIFIED",
    "CANCELLED_AMOUNTS_EXCLUDED_NOT_FINANCIALLY_VALIDATED",
    "OBSERVATIONAL_NOT_CAUSAL",
    "NO_SALES_IMPROVEMENT_PROVEN",
]


class SalesGrossProfitFailure(SkillExecutorFailure):
    """Local row diagnostic; does not create formal invocation/Run evidence."""

    def __init__(self, code, *, row_id="", source_line=0, field=""):
        super().__init__(code, outcome_unknown=False)
        self.details = {
            "rowId": row_id if isinstance(row_id, str) else "",
            "sourceLine": source_line if type(source_line) is int else 0,
            "field": field,
        }


def reject(code, item=None, field=""):
    item = item or {}
    row = item.get("values", {})
    raise SalesGrossProfitFailure(
        code,
        row_id=row.get("rowId", "") if isinstance(row, dict) else "",
        source_line=item.get("sourceLine", 0),
        field=field,
    )


def bounded(value, maximum):
    stack, properties = [(value, 1)], 0
    while stack:
        item, depth = stack.pop()
        if depth > LIMITS["maxObjectDepth"]:
            reject("SALES_V2_OBJECT_BOUNDS_EXCEEDED")
        if isinstance(item, dict):
            if any(not isinstance(k, str) for k in item):
                reject("SALES_V2_JSON_INVALID")
            properties += len(item)
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
        if properties > LIMITS["maxProperties"]:
            reject("SALES_V2_OBJECT_BOUNDS_EXCEEDED")
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError, RecursionError) as exc:
        raise SalesGrossProfitFailure("SALES_V2_JSON_INVALID") from exc
    if size > maximum:
        reject("SALES_V2_BYTE_BOUNDS_EXCEEDED")


def amount(number):
    if number == 0:
        number = Decimal(0)
    return format(number.quantize(Decimal("0.01")), "f")


def comparison(before, current):
    return {
        "baseline": amount(before),
        "current": amount(current),
        "delta": amount(current - before),
        "rate": {"status": "BASELINE_ZERO"}
        if before == 0
        else {"status": "DEFINED", "value": str((current - before) / abs(before))},
    }


def label(row, dimension):
    present = dimension in row
    raw = row.get(dimension, "")
    if not isinstance(raw, str) or len(raw) > 200:
        raise ValueError
    normalized = raw.strip()
    unresolved = normalized.upper() in UNKNOWN_LABELS
    return {
        "rawValue": raw,
        "sourceValueState": "PRESENT" if present else "MISSING",
        "value": "" if unresolved else normalized,
        "valueStatus": "UNRESOLVED" if unresolved else "PROVIDED_UNVERIFIED",
    }


def validate_rows(source):
    if (
        not isinstance(source, dict)
        or source.get("schemaVersion") != "sales-diagnostic-source.v1"
        or source.get("synthetic") is not True
        or source.get("metric") != METRIC
    ):
        reject("SALES_V2_EXACT_SYNTHETIC_SOURCE_REQUIRED")
    periods = source.get("periods")
    if (
        not isinstance(periods, list)
        or len(periods) != 2
        or not all(
            isinstance(p, str) and p.strip() == p and 0 < len(p) <= 40 for p in periods
        )
        or periods[0] == periods[1]
    ):
        reject("SALES_V2_PERIODS_INVALID")
    try:
        snapshot = verify_snapshot(source["snapshot"])
    except (KeyError, SnapshotInputError, TypeError, ValueError) as exc:
        raise SalesGrossProfitFailure("SALES_V2_SNAPSHOT_INVALID") from exc
    entries = snapshot.get("rows")
    if not isinstance(entries, list) or not 1 <= len(entries) <= LIMITS["maxRows"]:
        reject("SALES_V2_ROW_BOUNDS_INVALID")
    seen, previous_line, posted, excluded, issues = set(), 1, [], [], []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("values"), dict):
            reject("SALES_V2_ROW_INVALID")
        row, line = item["values"], item.get("sourceLine")
        if type(line) is not int or line <= previous_line:
            reject("SALES_V2_SOURCE_LINE_INVALID", item)
        previous_line = line
        for field in ("rowId", "period", "currency", "kind", "status"):
            value = row.get(field)
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 200
            ):
                reject("SALES_V2_ROW_IDENTITY_INVALID", item, field)
        if row["rowId"] in seen:
            reject("SALES_V2_DUPLICATE_ROW", item, "rowId")
        seen.add(row["rowId"])
        if row["period"] not in periods:
            reject("SALES_V2_PERIOD_INVALID", item, "period")
        currency = row["currency"]
        if (
            len(currency) != 3
            or not currency.isascii()
            or not currency.isalpha()
            or not currency.isupper()
        ):
            reject("SALES_V2_CURRENCY_INVALID", item, "currency")
        if row["kind"] not in {"SALE", "RETURN"} or row["status"] not in {
            "POSTED",
            "CANCELLED",
        }:
            reject("SALES_V2_CLASSIFICATION_INVALID", item)
        if row["status"] == "CANCELLED":
            excluded.append(
                {
                    "rowId": row["rowId"],
                    "sourceLine": line,
                    "reason": "CANCELLED",
                    "rawValues": deepcopy(row),
                }
            )
            continue
        numbers = {}
        for field in ("netSales", "cost"):
            if row.get(field) in (None, ""):
                reject(
                    "SALES_V2_COST_REQUIRED"
                    if field == "cost"
                    else "SALES_V2_NET_SALES_REQUIRED",
                    item,
                    field,
                )
            try:
                numbers[field] = money(row[field])
            except (ValueError, ArithmeticError) as exc:
                raise SalesGrossProfitFailure(
                    "SALES_V2_MONEY_INVALID",
                    row_id=row["rowId"],
                    source_line=line,
                    field=field,
                ) from exc
            if (row["kind"] == "SALE" and numbers[field] < 0) or (
                row["kind"] == "RETURN" and numbers[field] > 0
            ):
                reject("SALES_V2_SIGN_INCONSISTENT", item, field)
        numbers["grossProfit"] = numbers["netSales"] - numbers["cost"]
        labels = {}
        for dimension in DIMENSIONS:
            try:
                labels[dimension] = label(row, dimension)
            except ValueError as exc:
                raise SalesGrossProfitFailure(
                    "SALES_V2_DIMENSION_INVALID",
                    row_id=row["rowId"],
                    source_line=line,
                    field=dimension,
                ) from exc
            value = labels[dimension]
            if value["valueStatus"] == "UNRESOLVED":
                issues.append(
                    {
                        "rowId": row["rowId"],
                        "sourceLine": line,
                        "field": dimension,
                        "reason": "DIMENSION_UNRESOLVED_INCLUDED",
                        "rawValue": value["rawValue"],
                        "sourceValueState": value["sourceValueState"],
                    }
                )
        posted.append(
            {"row": row, "sourceLine": line, "numbers": numbers, "dimensions": labels}
        )
    if not posted:
        reject("SALES_V2_NO_POSTED_ROWS")
    return periods, posted, excluded, issues


def analyze_gross_profit(source, reference, *, deadline=float("inf")):
    """Pure candidate computation; no persistence, publication or business action."""
    with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN)):
        periods, rows, excluded, issues = validate_rows(source)
        totals = defaultdict(
            lambda: defaultdict(lambda: {m: Decimal(0) for m in METRICS})
        )
        groups = {
            d: defaultdict(
                lambda: defaultdict(lambda: {m: Decimal(0) for m in METRICS})
            )
            for d in DIMENSIONS
        }
        refs = defaultdict(list)
        group_refs = {d: defaultdict(list) for d in DIMENSIONS}
        terms = []
        for entry in rows:
            if monotonic() >= deadline:
                reject("SALES_V2_COMPUTATION_DEADLINE")
            row, numbers = entry["row"], entry["numbers"]
            currency, period = row["currency"], row["period"]
            sign = -1 if period == periods[0] else 1
            refs[currency, period].append(row["rowId"])
            for metric in METRICS:
                totals[currency][period][metric] += numbers[metric]
            for dimension, value in entry["dimensions"].items():
                key = (currency, value["valueStatus"], value["value"])
                group_refs[dimension][key, period].append(row["rowId"])
                for metric in METRICS:
                    groups[dimension][key][period][metric] += numbers[metric]
            terms.append(
                {
                    "rowId": row["rowId"],
                    "sourceLine": entry["sourceLine"],
                    "period": period,
                    "periodRole": "BASELINE" if sign == -1 else "CURRENT",
                    "changeSign": sign,
                    "currency": currency,
                    "kind": row["kind"],
                    **{m: amount(numbers[m]) for m in METRICS},
                    "deltaContributions": {
                        m: amount(sign * numbers[m]) for m in METRICS
                    },
                    "dimensions": entry["dimensions"],
                }
            )
        currency_rows = []
        for currency in sorted(totals):
            currency_rows.append(
                {
                    "currency": currency,
                    **{
                        m: comparison(
                            totals[currency][periods[0]][m],
                            totals[currency][periods[1]][m],
                        )
                        for m in METRICS
                    },
                    "sourceRows": [
                        {"period": p, "rowIds": refs[currency, p]} for p in periods
                    ],
                }
            )
        dimensions, reconciliations = {}, {}
        for dimension in DIMENSIONS:
            dimensions[dimension] = []
            for key in sorted(groups[dimension]):
                currency, status, name = key
                values = groups[dimension][key]
                dimensions[dimension].append(
                    {
                        "currency": currency,
                        "value": name,
                        "valueStatus": status,
                        **{
                            m: comparison(values[periods[0]][m], values[periods[1]][m])
                            for m in METRICS
                        },
                        "sourceRows": [
                            {"period": p, "rowIds": group_refs[dimension][key, p]}
                            for p in periods
                        ],
                    }
                )
            reconciliations[dimension] = []
            for total in currency_rows:
                selected = [
                    g
                    for g in dimensions[dimension]
                    if g["currency"] == total["currency"]
                ]
                matches = {}
                for metric in METRICS:
                    delta = sum(
                        (Decimal(g[metric]["delta"]) for g in selected), Decimal(0)
                    )
                    if amount(delta) != total[metric]["delta"]:
                        reject("SALES_V2_RECONCILIATION_FAILED")
                    matches[metric] = {
                        "sumGroupDelta": amount(delta),
                        "currencyDelta": total[metric]["delta"],
                        "matches": True,
                    }
                reconciliations[dimension].append(
                    {
                        "currency": total["currency"],
                        "groupCount": len(selected),
                        **matches,
                    }
                )
        return {
            "schemaVersion": "sales-diagnostic-output.v2",
            "contractDigest": CONTRACT_DIGEST,
            "synthetic": True,
            "metric": METRIC,
            "grossProfitDefinition": "NET_SALES_MINUS_SIGNED_COST",
            "periods": list(periods),
            "sourceSnapshot": deepcopy(reference),
            "sourceDigest": canonical_digest(source),
            "source": deepcopy(source),
            "currencyComparisons": currency_rows,
            "dimensions": dimensions,
            "rowContributions": terms,
            "excludedRows": excluded,
            "inputIssues": issues,
            "reconciliations": reconciliations,
            "limitations": list(LIMITATIONS),
            "businessConclusion": "UNDETERMINED",
        }


class SalesGrossProfitSkillExecutor:
    revision = ExecutorRevision(
        "sales-diagnostic-readonly", "2", canonical_digest(CONFIG)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        if (
            operation not in OPERATIONS
            or not isinstance(invocation_id, str)
            or not invocation_id
            or type(timeout_ms) is not int
            or timeout_ms <= 0
        ):
            reject("SALES_V2_SKILL_CONTRACT_INVALID")
        deadline = monotonic() + min(timeout_ms, LIMITS["timeoutMs"]) / 1000
        bounded(inputs, LIMITS["maxInputBytes"])
        try:
            schema_check(inputs, INPUT_SCHEMA, "SALES_V2_INPUT_SHAPE_INVALID")
            reference = ExactReference.model_validate(
                inputs["sourceSnapshot"]
            ).model_dump(mode="json")
        except (ValueError, SkillInvocationError) as exc:
            raise SalesGrossProfitFailure("SALES_V2_INPUT_CONTRACT_INVALID") from exc
        output = analyze_gross_profit(inputs["source"], reference, deadline=deadline)
        dependencies = inputs["dependencies"]
        if operation == "READ_DATA" and dependencies:
            reject("SALES_V2_READ_DEPENDENCY_FORBIDDEN")
        if operation != "READ_DATA" and not dependencies:
            reject("SALES_V2_DEPENDENCY_REQUIRED")
        for dependency in dependencies.values():
            if (
                not isinstance(dependency, dict)
                or dependency.get("operation") not in OPERATIONS
                or canonical_digest(
                    {k: v for k, v in dependency.items() if k != "operation"}
                )
                != canonical_digest(output)
            ):
                reject("SALES_V2_DEPENDENCY_SOURCE_OR_CONTENT_MISMATCH")
        output["operation"] = operation
        bounded(output, LIMITS["maxOutputBytes"])
        schema_check(output, OUTPUT_SCHEMA, "SALES_V2_OUTPUT_CONTRACT_INVALID")
        if monotonic() >= deadline:
            reject("SALES_V2_COMPUTATION_DEADLINE")
        return SkillExecutorResult(
            True, output, "local-sales-gp-candidate:" + invocation_id
        )
