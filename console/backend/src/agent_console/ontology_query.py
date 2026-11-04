"""Restricted, deterministic ontology query compiler for synthetic sales."""

from collections import defaultdict
from decimal import Decimal

from pydantic import Field

from .ontology_domain import Code, OntologyContent, OntologyError, Value
from .resource_use_domain import canonical_digest
from .sales_diagnostic_skill import compare, validate_source


class SemanticQuery(Value):
    metric: str = Field(min_length=1, max_length=200)
    dimensions: tuple[Code, ...] = Field(default=(), max_length=3)
    filters: dict[Code, tuple[str, ...]] = Field(default_factory=dict, max_length=3)


def resolve(content, query):
    matches = [
        m for m in content.metrics if query.metric in (m.code, m.name, *m.aliases)
    ]
    if len(matches) != 1:
        raise OntologyError("ONTOLOGY_METRIC_AMBIGUOUS_OR_UNKNOWN")
    metric = matches[0]
    if (
        len(set(query.dimensions)) != len(query.dimensions)
        or not set(query.dimensions) <= set(metric.dimensions)
        or not set(query.filters) <= set(metric.dimensions)
        or any(not values or len(values) > 64 for values in query.filters.values())
    ):
        raise OntologyError("ONTOLOGY_QUERY_UNSUPPORTED")
    return metric


def mapped_rows(content, source):
    # Source safety validation is retained independently of business aggregation.
    rows, cancelled = validate_source(source)
    if len(rows) + len(cancelled) > content.rules.max_rows:
        raise OntologyError("ONTOLOGY_ROW_LIMIT")
    if len(content.mappings) != 1:
        raise OntologyError("ONTOLOGY_SINGLE_MAPPING_REQUIRED")
    mapping = content.mappings[0]
    if mapping.source_digest != canonical_digest(source):
        raise OntologyError("ONTOLOGY_SOURCE_DIGEST_MISMATCH")
    fields = mapping.fields
    for field in ("rowId", "period", "currency", "kind", "status"):
        if fields.get(field) != field:
            raise OntologyError("ONTOLOGY_CONTROL_FIELD_MAPPING_UNSUPPORTED")
    kinds = {
        p.code: p.kind
        for o in content.objects
        if o.code == mapping.object_code
        for p in o.properties
    }
    source_kinds = {
        f: "MONEY"
        if f in {"netSales", "cost"}
        else "PERIOD"
        if f == "period"
        else "TEXT"
        for f in source["snapshot"]["columnMapping"]
    }
    if any(kinds[key] != source_kinds.get(value) for key, value in fields.items()):
        raise OntologyError("ONTOLOGY_MAPPING_TYPE_MISMATCH")
    required = {
        p.code
        for o in content.objects
        if o.code == mapping.object_code
        for p in o.properties
        if p.required
    }
    if not required <= fields.keys() or any(
        v not in source["snapshot"]["columnMapping"] for v in fields.values()
    ):
        raise OntologyError("ONTOLOGY_SOURCE_MAPPING_INCOMPATIBLE")
    mapped = [{k: row[v] for k, v in fields.items()} for row in rows]
    # Snapshot-local dimensions cannot multiply a fact row. Ambiguous keys fail.
    objects = {o.code: o for o in content.objects}
    for relation in content.relations:
        if relation.source_object != mapping.object_code:
            raise OntologyError("ONTOLOGY_RELATION_UNSUPPORTED")
        target = objects[relation.target_object]
        if target.identity_fields != (relation.target_key,):
            raise OntologyError("ONTOLOGY_RELATION_KEY_UNSUPPORTED")
        values = [row.get(relation.source_key) for row in mapped]
        if any(v is None or v == "" for v in values):
            raise OntologyError("ONTOLOGY_RELATION_MISSING")
        if relation.cardinality == "ONE_TO_ONE" and len(values) != len(set(values)):
            raise OntologyError("ONTOLOGY_RELATION_CARDINALITY")
    return mapped, cancelled


def evaluate_expression(expression, rows):
    if expression.op == "SUM":
        try:
            return sum((Decimal(r[expression.field]) for r in rows), Decimal(0))
        except (KeyError, ArithmeticError) as exc:
            raise OntologyError("ONTOLOGY_EXPRESSION_DATA_INVALID") from exc
    left, right = expression.operands
    return evaluate_expression(left, rows) - evaluate_expression(right, rows)


def query_sales(content: OntologyContent, source, query: SemanticQuery):
    metric = resolve(content, query)
    rows, cancelled = mapped_rows(content, source)
    included, excluded = [], [*cancelled]
    for row in rows:
        reason = None
        if row["kind"] not in content.rules.included_kinds:
            reason = "KIND_EXCLUDED_BY_ONTOLOGY"
        elif any(row[k] not in values for k, values in query.filters.items()):
            reason = "QUERY_FILTER"
        if reason:
            excluded.append({"rowId": row["rowId"], "reason": reason})
        else:
            included.append(row)
    if not included:
        raise OntologyError("ONTOLOGY_NO_MATCHING_ROWS")
    groups = defaultdict(list)
    for row in included:
        groups[(row["currency"], *(row[d] for d in query.dimensions))].append(row)
    periods = source["periods"]
    output = []
    for key, group in sorted(groups.items()):
        values = [
            evaluate_expression(
                metric.expression, [r for r in group if r[metric.time_field] == period]
            )
            for period in periods
        ]
        output.append(
            {
                "currency": key[0],
                "dimensions": dict(zip(query.dimensions, key[1:], strict=True)),
                **compare(*values),
                "sourceRows": {
                    p: [r["rowId"] for r in group if r[metric.time_field] == p]
                    for p in periods
                },
            }
        )
    return {
        "schemaVersion": "ontology-sales-output.v1",
        "synthetic": True,
        "metric": metric.code,
        "metricName": metric.name,
        "unit": metric.unit,
        "periods": periods,
        "query": query.model_dump(mode="json"),
        "rows": output,
        "excludedRows": excluded,
        "sourceDigest": canonical_digest(source),
        "businessConclusion": "UNDETERMINED",
        "limitations": [
            "SYNTHETIC_ONLY",
            "NO_CROSS_CURRENCY_SUM",
            "OBSERVATIONAL_NOT_CAUSAL",
            "NO_SALES_IMPROVEMENT_PROVEN",
        ],
    }
