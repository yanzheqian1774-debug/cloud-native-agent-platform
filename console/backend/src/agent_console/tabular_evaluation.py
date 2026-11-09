"""Independent row/count/group checks, not business acceptance or causal proof."""

from decimal import Decimal, InvalidOperation

from .resource_use_domain import canonical_digest


def checks(source, report, reference):
    mapping = source["mapping"]
    expected, rejected, groups = [], [], {}
    for row in source["rows"]:
        identity = row[mapping["identity"]]
        try:
            raw = [row[mapping[k]] for k in ("value", "upperBound")]
            if any(
                isinstance(x, bool) or not isinstance(x, (str, int)) or len(str(x)) > 32
                for x in raw
            ):
                raise ValueError("number")
            value, bound = map(Decimal, raw)
            if any(
                not n.is_finite()
                or abs(n) > Decimal("1e15")
                or n.as_tuple().exponent < -8
                for n in (value, bound)
            ):
                raise ValueError("bounds")
            labels = [row[f] for f in [mapping["unit"], *mapping["dimensions"]]]
            if any(not isinstance(v, str) or not 1 <= len(v) <= 120 for v in labels):
                raise ValueError("labels")
        except (KeyError, ValueError, InvalidOperation):
            rejected.append(identity)
            continue
        if value > bound:
            expected.append(identity)
        for field in mapping["dimensions"]:
            key = (field, row[field], row[mapping["unit"]])
            count, exceptions, excess, ids = groups.get(key, (0, 0, Decimal(0), []))
            groups[key] = (
                count + 1,
                exceptions + int(value > bound),
                excess + max(Decimal(0), value - bound),
                [*ids, identity],
            )
    actual_groups = {
        (g["dimension"], g["label"], g["unit"]): (
            g["count"],
            g["exceptionCount"],
            Decimal(g["totalExcess"]),
            g["sourceIds"],
        )
        for g in report.get("groups", [])
    }
    facts = {
        "EXACT_SOURCE": report.get("sourceSnapshot") == reference
        and report.get("sourceDigest") == canonical_digest(source),
        "EXCEPTION_IDS": report.get("exceptionIds") == expected,
        "INVALID_ROWS": [r["id"] for r in report.get("invalidRows", [])] == rejected,
        "ROW_ACCOUNTING": report.get("validCount")
        == len(source["rows"]) - len(rejected)
        and report.get("inputCount") == len(source["rows"]),
        "GROUPS_AND_UNITS": actual_groups == groups
        and len(report.get("groups", [])) == len(groups),
        "NO_BUSINESS_ACCEPTANCE": report.get("businessConclusion") == "UNDETERMINED",
    }
    return [
        {
            "check": key,
            "result": "SATISFIED" if ok else "NOT_SATISFIED",
            "reason": "INDEPENDENT_TABULAR_RECOMPUTATION",
        }
        for key, ok in facts.items()
    ]
