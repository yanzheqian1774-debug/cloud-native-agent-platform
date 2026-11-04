"""Explicit synthetic definition builder; does not publish or authorize resources."""

from .ontology_domain import OntologyContent
from .resource_use_domain import canonical_digest
from .sales_diagnostic_skill import FIELDS


def sales_content(source, source_reference, skill_reference, executor):
    properties = [
        {
            "code": f,
            "kind": "MONEY"
            if f in {"netSales", "cost"}
            else "PERIOD"
            if f == "period"
            else "TEXT",
        }
        for f in FIELDS
    ]
    objects = [
        {"code": "sales_record", "identity_fields": ["rowId"], "properties": properties}
    ]
    relations = []
    for dimension in ("region", "channel", "product"):
        objects.append(
            {
                "code": dimension,
                "identity_fields": [dimension],
                "properties": [{"code": dimension, "kind": "TEXT"}],
            }
        )
        relations.append(
            {
                "code": "sales_to_" + dimension,
                "source_object": "sales_record",
                "target_object": dimension,
                "source_key": dimension,
                "target_key": dimension,
                "cardinality": "MANY_TO_ONE",
            }
        )
    return OntologyContent.model_validate(
        {
            "name": "销售诊断业务定义",
            "business_owner": "销售分析负责人",
            "data_owner": "销售数据负责人",
            "objects": objects,
            "relations": relations,
            "metrics": [
                {
                    "code": "net_sales",
                    "name": "不含税净销售额",
                    "aliases": ["销售额"],
                    "object_code": "sales_record",
                    "expression": {"op": "SUM", "field": "netSales"},
                },
                {
                    "code": "gross_profit",
                    "name": "毛利额",
                    "object_code": "sales_record",
                    "expression": {
                        "op": "SUBTRACT",
                        "operands": [
                            {"op": "SUM", "field": "netSales"},
                            {"op": "SUM", "field": "cost"},
                        ],
                    },
                },
            ],
            "mappings": [
                {
                    "code": "sales_csv",
                    "source": source_reference,
                    "source_digest": canonical_digest(source),
                    "source_schema": "sales-diagnostic-source.v1",
                    "object_code": "sales_record",
                    "fields": {f: f for f in FIELDS},
                }
            ],
            "rules": {},
            "actions": [
                {
                    "skill": skill_reference,
                    "executor_id": executor.executor_id,
                    "executor_revision": executor.executor_revision,
                    "executor_digest": executor.configuration_digest,
                    "operation": op,
                }
                for op in ("READ_DATA", "VALIDATE_DATA", "SUMMARIZE", "RENDER_REPORT")
            ],
        }
    )
