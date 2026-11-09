"""Bounded declarative numerical diagnostics; no business-specific column names."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorFailure, SkillExecutorResult
from .skill_invocation_domain import ExecutorRevision

SCHEMA = "tabular-diagnostic-source.v1"
OPERATIONS = (
    "READ_DATA",
    "VALIDATE_DATA",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RENDER_REPORT",
)
CONFIGURATION = {
    "schemaVersion": "tabular-diagnostic-skill.v1",
    "operations": list(OPERATIONS),
    "maxRows": 1000,
    "maxDimensions": 4,
    "comparison": "value > upperBound",
    "aggregation": "per dimension and unit; no mixed-unit totals",
    "missing": "exclude and disclose; never zero fill",
    "sideEffects": "READ_ONLY",
}


def fail(reason):
    raise SkillExecutorFailure(reason, outcome_unknown=False)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("decimal required")
    if len(str(value)) > 32:
        raise ValueError("number too long")
    n = Decimal(value)
    if not n.is_finite() or abs(n) > Decimal("1e15") or n.as_tuple().exponent < -8:
        raise ValueError("number bounds")
    return n


def validate_source(source):
    if not isinstance(source, dict) or source.get("schemaVersion") != SCHEMA:
        fail("TABULAR_SOURCE_SCHEMA_UNSUPPORTED")
    if source.get("synthetic") is not True:
        fail("TABULAR_SYNTHETIC_BOUNDARY_REQUIRED")
    mapping = source.get("mapping", {})
    if not isinstance(mapping, dict) or set(mapping) != {
        "identity",
        "value",
        "upperBound",
        "unit",
        "dimensions",
    }:
        fail("TABULAR_MAPPING_REQUIRED")
    dimensions = mapping["dimensions"]
    if not isinstance(dimensions, list) or not 1 <= len(dimensions) <= 4:
        fail("TABULAR_DIMENSIONS_INVALID")
    fields = [mapping[k] for k in ("identity", "value", "upperBound", "unit")]
    fields += dimensions
    if any(not isinstance(f, str) or not 1 <= len(f) <= 80 for f in fields):
        fail("TABULAR_FIELD_INVALID")
    if len(fields) != len(set(fields)):
        fail("TABULAR_MAPPING_CONFLICT")
    rows = source.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        fail("TABULAR_ROWS_INVALID")
    if any(not isinstance(row, dict) for row in rows):
        fail("TABULAR_ROW_INVALID")
    if any(not any(f in row for row in rows) for f in fields):
        fail("TABULAR_COLUMN_MISSING")
    return mapping


def analyze(source):
    mapping = validate_source(source)
    valid, invalid, seen = [], [], set()
    for index, row in enumerate(source["rows"]):
        identity = row.get(mapping["identity"])
        if not isinstance(identity, str) or not identity or identity in seen:
            fail("TABULAR_ID_MISSING_OR_DUPLICATE")
        seen.add(identity)
        try:
            value, bound = (
                number(row[mapping["value"]]),
                number(row[mapping["upperBound"]]),
            )
            labels = [row[f] for f in [mapping["unit"], *mapping["dimensions"]]]
            if any(not isinstance(v, str) or not 1 <= len(v) <= 120 for v in labels):
                raise ValueError("dimension or unit missing")
        except (KeyError, ValueError, InvalidOperation):
            invalid.append(
                {
                    "id": identity,
                    "rowIndex": index,
                    "reason": "MISSING_OR_INVALID_VALUE",
                }
            )
            continue
        valid.append(
            {
                "id": identity,
                "value": str(value),
                "upperBound": str(bound),
                "excess": str(max(Decimal(0), value - bound)),
                "exceeded": value > bound,
                "unit": labels[0],
                "dimensions": dict(zip(mapping["dimensions"], labels[1:], strict=True)),
                "sourceRow": row,
            }
        )
    groups = defaultdict(list)
    for row in valid:
        for dimension, label in row["dimensions"].items():
            groups[(dimension, label, row["unit"])].append(row)
    summaries = []
    for (dimension, label, unit), rows in sorted(groups.items()):
        exceptions = [r for r in rows if r["exceeded"]]
        summaries.append(
            {
                "dimension": dimension,
                "label": label,
                "unit": unit,
                "count": len(rows),
                "exceptionCount": len(exceptions),
                "totalExcess": str(
                    sum((Decimal(r["excess"]) for r in rows), Decimal(0))
                ),
                "sourceIds": [r["id"] for r in rows],
            }
        )
    return {
        "rows": valid,
        "invalidRows": invalid,
        "groups": summaries,
        "exceptionIds": [r["id"] for r in valid if r["exceeded"]],
        "inputCount": len(source["rows"]),
        "validCount": len(valid),
        "mapping": mapping,
        "sourceDigest": canonical_digest(source),
    }


class TabularDiagnosticSkillExecutor:
    revision = ExecutorRevision(
        "tabular-diagnostic-readonly", "1", canonical_digest(CONFIGURATION)
    )

    def invoke(self, invocation_id, operation, inputs, timeout_ms):
        if operation not in OPERATIONS or inputs.get("synthetic") is not True:
            fail("TABULAR_OPERATION_OR_BOUNDARY_UNSUPPORTED")
        if operation == "READ_DATA":
            source = inputs.get("source")
            validate_source(source)
        else:
            dependencies = list(inputs.get("dependencies", {}).values())
            if not dependencies or any(
                d.get("schemaVersion") != "tabular-diagnostic-output.v1"
                for d in dependencies
            ):
                fail("TABULAR_DEPENDENCY_INVALID")
            if any(
                d.get("sourceSnapshot") != inputs.get("sourceSnapshot")
                for d in dependencies
            ):
                fail("TABULAR_DEPENDENCY_SOURCE_MISMATCH")
            sources = [d.get("source") for d in dependencies]
            if len({canonical_digest(s) for s in sources}) != 1:
                fail("TABULAR_DEPENDENCY_CONTENT_MISMATCH")
            source = sources[0]
        result = {
            "schemaVersion": "tabular-diagnostic-output.v1",
            "operation": operation,
            "synthetic": True,
            "sourceSnapshot": inputs["sourceSnapshot"],
            "source": source,
            "limitations": [
                "SYNTHETIC_ONLY",
                "DECLARED_UPPER_BOUND_ONLY",
                "CAUSAL_ATTRIBUTION_UNVERIFIED",
            ],
        }
        if operation != "READ_DATA":
            result.update(analyze(source))
        if operation == "RENDER_REPORT":
            result.update(
                title=source.get("title", "Tabular diagnostics"),
                businessConclusion="UNDETERMINED",
                report=(
                    f"{result['validCount']} valid rows; "
                    f"{len(result['exceptionIds'])} above declared limits; "
                    f"{len(result['invalidRows'])} rows excluded with reasons. "
                    "Causes and corrective effects are unverified."
                ),
            )
        return SkillExecutorResult(True, result, "tabular-computation:" + invocation_id)
