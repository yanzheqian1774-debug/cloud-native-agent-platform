"""Portable CSV/minor-unit oracle. No producing Skill, validator or evaluator imports.

This writes local reproducible expectations, not Native evidence or acceptance.
"""

import csv
import hashlib
import io
import json
import re
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

DIMS = ("region", "channel", "product")
METRICS = ("netSales", "cost", "grossProfit")
UNKNOWN = {"", "UNKNOWN", "UNSPECIFIED", "N/A", "未知"}


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def minor(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"-?\d{1,13}(?:\.\d{1,2})?", value
    ):
        raise ValueError("ORACLE_MONEY_INVALID")
    negative = value.startswith("-")
    whole, _, fraction = value.lstrip("-").partition(".")
    result = int(whole) * 100 + int((fraction + "00")[:2])
    if result > 100000000000000:
        raise ValueError("ORACLE_MONEY_BOUNDS")
    return -result if negative else result


def display(cents):
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def metric(before, after):
    if before == 0:
        rate = {"status": "BASELINE_ZERO"}
    else:
        with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN)):
            rate = {
                "status": "DEFINED",
                "value": str(Decimal(after - before) / abs(before)),
            }
    return {
        "baseline": display(before),
        "current": display(after),
        "delta": display(after - before),
        "rate": rate,
    }


def committed_csv_rows(raw, source):
    snapshot = source["snapshot"]
    if hashlib.sha256(raw).hexdigest() != snapshot["sourceBytesSha256"]:
        raise ValueError("ORACLE_CSV_BYTES_MISMATCH")
    if (
        digest({k: v for k, v in snapshot.items() if k != "snapshotDigest"})
        != snapshot["snapshotDigest"]
    ):
        raise ValueError("ORACLE_SNAPSHOT_DIGEST_MISMATCH")
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    headers = next(reader)
    if len(set(headers)) != len(headers):
        raise ValueError("ORACLE_DUPLICATE_HEADER")
    mapping = snapshot["columnMapping"]
    positions = {field: headers.index(column) for field, column in mapping.items()}
    rows = []
    for values in reader:
        if not values:
            continue
        if len(values) != len(headers):
            raise ValueError("ORACLE_CSV_ROW_WIDTH")
        rows.append(
            {
                "sourceLine": reader.line_num,
                "values": {k: values[i] for k, i in positions.items()},
            }
        )
    if rows != snapshot["rows"]:
        raise ValueError("ORACLE_CSV_ROW_MAPPING_MISMATCH")
    return rows


def expectations(raw, source, reference, contract, *, operation="RENDER_REPORT"):
    periods = source["periods"]
    if len(periods) != 2 or periods[0] == periods[1]:
        raise ValueError("ORACLE_PERIODS_INVALID")
    posted, excluded, issues = [], [], []
    identities = set()
    for item in committed_csv_rows(raw, source):
        row = item["values"]
        if row["rowId"] in identities or row["period"] not in periods:
            raise ValueError("ORACLE_ROW_ID_OR_PERIOD_INVALID")
        identities.add(row["rowId"])
        if not re.fullmatch(r"[A-Z]{3}", row["currency"]) or row["kind"] not in {
            "SALE",
            "RETURN",
        }:
            raise ValueError("ORACLE_ROW_CLASSIFICATION_INVALID")
        if row["status"] == "CANCELLED":
            excluded.append(
                {
                    "rowId": row["rowId"],
                    "sourceLine": item["sourceLine"],
                    "reason": "CANCELLED",
                    "rawValues": row.copy(),
                }
            )
            continue
        if row["status"] != "POSTED":
            raise ValueError("ORACLE_ROW_STATUS_INVALID")
        sales, cost = minor(row["netSales"]), minor(row["cost"])
        if (row["kind"] == "SALE" and min(sales, cost) < 0) or (
            row["kind"] == "RETURN" and max(sales, cost) > 0
        ):
            raise ValueError("ORACLE_SIGN_INVALID")
        labels = {}
        for d in DIMS:
            raw_label = row.get(d, "")
            unresolved = raw_label.strip().upper() in UNKNOWN
            labels[d] = {
                "rawValue": raw_label,
                "sourceValueState": "PRESENT" if d in row else "MISSING",
                "value": "" if unresolved else raw_label.strip(),
                "valueStatus": "UNRESOLVED" if unresolved else "PROVIDED_UNVERIFIED",
            }
            if unresolved:
                issues.append(
                    {
                        "rowId": row["rowId"],
                        "sourceLine": item["sourceLine"],
                        "field": d,
                        "reason": "DIMENSION_UNRESOLVED_INCLUDED",
                        "rawValue": raw_label,
                        "sourceValueState": labels[d]["sourceValueState"],
                    }
                )
        posted.append(
            {
                "row": row,
                "line": item["sourceLine"],
                "numbers": {
                    "netSales": sales,
                    "cost": cost,
                    "grossProfit": sales - cost,
                },
                "labels": labels,
            }
        )
    if not posted:
        raise ValueError("ORACLE_NO_POSTED_ROWS")
    currencies = sorted({p["row"]["currency"] for p in posted})

    def aggregate(selected):
        sums = {
            p: {
                m: sum(x["numbers"][m] for x in selected if x["row"]["period"] == p)
                for m in METRICS
            }
            for p in periods
        }
        return {
            **{m: metric(sums[periods[0]][m], sums[periods[1]][m]) for m in METRICS},
            "sourceRows": [
                {
                    "period": p,
                    "rowIds": [
                        x["row"]["rowId"] for x in selected if x["row"]["period"] == p
                    ],
                }
                for p in periods
            ],
        }

    totals = [
        {
            "currency": currency,
            **aggregate([x for x in posted if x["row"]["currency"] == currency]),
        }
        for currency in currencies
    ]
    dimensions, proofs = {}, {}
    for d in DIMS:
        groups = sorted(
            {
                (
                    p["row"]["currency"],
                    p["labels"][d]["valueStatus"],
                    p["labels"][d]["value"],
                )
                for p in posted
            }
        )
        dimensions[d] = []
        for currency, status, value in groups:
            selected = [
                p
                for p in posted
                if (
                    p["row"]["currency"],
                    p["labels"][d]["valueStatus"],
                    p["labels"][d]["value"],
                )
                == (currency, status, value)
            ]
            dimensions[d].append(
                {
                    "currency": currency,
                    "value": value,
                    "valueStatus": status,
                    **aggregate(selected),
                }
            )
        proofs[d] = []
        for total in totals:
            selected = [g for g in dimensions[d] if g["currency"] == total["currency"]]
            checks = {}
            for m in METRICS:
                terms = sum(minor(g[m]["delta"]) for g in selected)
                delta = minor(total[m]["delta"])
                if terms != delta:
                    raise ValueError("ORACLE_PARTITION_RECONCILIATION_FAILED")
                checks[m] = {
                    "sumGroupDelta": display(terms),
                    "currencyDelta": display(delta),
                    "matches": True,
                }
            proofs[d].append(
                {"currency": total["currency"], "groupCount": len(selected), **checks}
            )
    row_terms = []
    for p in posted:
        r = p["row"]
        sign = -1 if r["period"] == periods[0] else 1
        row_terms.append(
            {
                "rowId": r["rowId"],
                "sourceLine": p["line"],
                "period": r["period"],
                "periodRole": "BASELINE" if sign < 0 else "CURRENT",
                "changeSign": sign,
                "currency": r["currency"],
                "kind": r["kind"],
                **{m: display(p["numbers"][m]) for m in METRICS},
                "deltaContributions": {
                    m: display(sign * p["numbers"][m]) for m in METRICS
                },
                "dimensions": p["labels"],
            }
        )
    return {
        "schemaVersion": "sales-diagnostic-output.v2",
        "contractDigest": digest(contract),
        "synthetic": True,
        "metric": "RECOGNIZED_NET_SALES_EXCLUDING_TAX",
        "grossProfitDefinition": "NET_SALES_MINUS_SIGNED_COST",
        "periods": periods,
        "sourceSnapshot": reference,
        "sourceDigest": digest(source),
        "source": source,
        "currencyComparisons": totals,
        "dimensions": dimensions,
        "rowContributions": row_terms,
        "excludedRows": excluded,
        "inputIssues": issues,
        "reconciliations": proofs,
        "limitations": [
            "SYNTHETIC_ONLY",
            "NO_CROSS_CURRENCY_SUM",
            "DIMENSION_DECOMPOSITIONS_NOT_ADDITIVE_TO_EACH_OTHER",
            "SOURCE_LABELS_AND_CURRENCY_CODES_NOT_CANONICALLY_VERIFIED",
            "CANCELLED_AMOUNTS_EXCLUDED_NOT_FINANCIALLY_VALIDATED",
            "OBSERVATIONAL_NOT_CAUSAL",
            "NO_SALES_IMPROVEMENT_PROVEN",
        ],
        "businessConclusion": "UNDETERMINED",
        "operation": operation,
    }


def check(raw, source, reference, contract, observed, *, operation="RENDER_REPORT"):
    expected = expectations(raw, source, reference, contract, operation=operation)
    return {
        "status": "LOCAL_MATCHED"
        if digest(expected) == digest(observed)
        else "LOCAL_MISMATCH",
        "basis": "INDEPENDENT_CSV_INTEGER_MINOR_UNITS_NOT_FORMAL_ACCEPTANCE",
        "expectedDigest": digest(expected),
        "observedDigest": digest(observed),
        "currencyDimensionChecks": [
            {"dimension": d, **row}
            for d in DIMS
            for row in expected["reconciliations"][d]
        ],
        "expected": expected,
    }
