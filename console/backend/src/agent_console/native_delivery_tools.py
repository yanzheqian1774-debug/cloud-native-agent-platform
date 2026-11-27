"""Opt-in Native delivery tools; computation is not autonomous execution authority."""

from typing import ClassVar

from agent_runtime.native_loop import Tool, digest, snapshot

from .delivery_evaluation import checks
from .resource_use_domain import canonical_digest
from .synthetic_delivery_skill import CONFIGURATION, analyze

SCHEMA = "synthetic-delivery-source.v1"
ADAPTER_ID = "native-synthetic-delivery-readonly"
REVISION = "1"
CONTRACT = {
    "schemaVersion": "native-data-adapter.v1",
    "adapterId": ADAPTER_ID,
    "adapterRevision": REVISION,
    "sourceSchema": SCHEMA,
    "computation": CONFIGURATION,
    "verification": "synthetic-delivery-evidence.v1",
    "tools": ["inspect_source", "check_delivery", "inspect_rows", "build_report"],
    "effects": "READ_ONLY",
    "finish": "INDEPENDENT_CHECKS_AND_ORIGINAL_ROW_INDICES",
    "externalWrites": False,
}
CONFIGURATION_DIGEST = canonical_digest(CONTRACT)


class NativeDeliveryTools:
    answer_schema: ClassVar[dict] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reportDigest": {"type": "string"},
            "inspectedRowIndices": {"type": "array", "items": {"type": "integer"}},
            "businessAcceptance": {"type": "boolean", "enum": [False]},
        },
        "required": ["reportDigest", "inspectedRowIndices", "businessAcceptance"],
    }

    def __init__(self, source, reference):
        self.source, self.reference = snapshot(source), snapshot(reference)
        analyze(self.source)  # Original bounded schema/parser; no model or effect.
        self._report = None
        self.tools = tuple(self._tool(name) for name in CONTRACT["tools"])

    def _tool(self, name):
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        if name == "inspect_rows":
            schema["properties"] = {
                "rowIndices": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 32,
                    "items": {"type": "integer", "minimum": 0, "maximum": 127},
                    "uniqueItems": True,
                }
            }
            schema["required"] = ["rowIndices"]
        description = {
            "inspect_source": "Read assessment date, row count and limitations.",
            "check_delivery": "Check overdue rows and anomalies; no cause inference.",
            "inspect_rows": "Read original rows by index, including missing order IDs.",
            "build_report": "Build a report with limitations; no business acceptance.",
        }[name]
        return Tool(
            name,
            REVISION,
            digest({"adapter": CONFIGURATION_DIGEST, "tool": name, "schema": schema}),
            description,
            schema,
            lambda args: self.validate(name, args),
        )

    def validate(self, name, args):
        if not isinstance(args, dict):
            raise ValueError("NATIVE_DELIVERY_ARGUMENTS_INVALID")
        if name == "inspect_rows":
            rows = args.get("rowIndices")
            if (
                set(args) != {"rowIndices"}
                or not isinstance(rows, list)
                or not 1 <= len(rows) <= 32
                or any(
                    type(i) is not int or not 0 <= i < len(self.source["orders"])
                    for i in rows
                )
                or len(set(rows)) != len(rows)
            ):
                raise ValueError("NATIVE_DELIVERY_ROW_SELECTION_INVALID")
        elif name not in CONTRACT["tools"] or args:
            raise ValueError("NATIVE_DELIVERY_ARGUMENTS_INVALID")

    def invoke(self, name, arguments):
        return snapshot(self._invoke(name, arguments))

    def _invoke(self, name, arguments):
        self.validate(name, arguments)
        provenance = {
            "sourceSnapshot": self.reference,
            "sourceDigest": canonical_digest(self.source),
            "adapterDigest": CONFIGURATION_DIGEST,
        }
        if name == "inspect_source":
            return {
                **provenance,
                "assessmentDate": self.source["assessmentDate"],
                "rowCount": len(self.source["orders"]),
                "synthetic": True,
                "limitations": [
                    "Synthetic snapshot only",
                    "No causal evidence or business acceptance",
                ],
            }
        if name == "inspect_rows":
            return {
                **provenance,
                "rows": [
                    {"rowIndex": i, "sourceRow": self.source["orders"][i]}
                    for i in arguments["rowIndices"]
                ],
            }
        result = analyze(self.source)
        required = sorted(
            {r["rowIndex"] for r in result["orderDetails"] if r["overdue"]}
            | {r["rowIndex"] for r in result["anomalies"]}
        )
        if name == "check_delivery":
            return {
                **provenance,
                "suppliers": result["suppliers"],
                "anomalies": result["anomalies"],
                "excludedOrders": result["excludedOrders"],
                "requiredRowIndices": required,
            }
        report = {
            **result,
            **provenance,
            "source": self.source,
            "synthetic": True,
            "schemaVersion": "synthetic-delivery-output.v1",
            "operation": "RENDER_REPORT",
            "title": "供应商交付及时性 · 合成订单分析",
            "requiredRowIndices": required,
            "businessConclusion": "UNDETERMINED",
        }
        report["reportDigest"] = digest(report)
        self._report = snapshot(report)
        return report

    def verify(self, context, answer):
        observations = [
            o for o in context["observations"] if o["kind"] == "TOOL_RESULT"
        ]
        reports = [o["output"] for o in observations if o["tool"] == "build_report"]
        if not reports or self._report is None:
            return {"passed": False, "missing": ["REPORT_REQUIRED"]}
        report = reports[-1]
        if report != self._report or report.get("reportDigest") != digest(
            {k: v for k, v in report.items() if k != "reportDigest"}
        ):
            return {"passed": False, "missing": ["REPORT_IDENTITY_MISMATCH"]}
        verified = checks(self.source, report, self.reference)
        if not all(verified.values()):
            return {"passed": False, "missing": ["INDEPENDENT_CHECK_FAILED"]}
        inspected = set()
        for observation in observations:
            if observation["tool"] != "inspect_rows":
                continue
            value = observation["output"]
            if (
                value.get("sourceSnapshot") != self.reference
                or value.get("sourceDigest") != canonical_digest(self.source)
                or value.get("adapterDigest") != CONFIGURATION_DIGEST
            ):
                return {"passed": False, "missing": ["ROW_PROVENANCE_MISMATCH"]}
            for row in value.get("rows", []):
                i = row.get("rowIndex")
                if (
                    type(i) is not int
                    or not 0 <= i < len(self.source["orders"])
                    or row.get("sourceRow") != self.source["orders"][i]
                ):
                    return {"passed": False, "missing": ["ROW_PROVENANCE_MISMATCH"]}
                inspected.add(i)
        missing = sorted(set(report["requiredRowIndices"]) - inspected)
        if missing:
            return {
                "passed": False,
                "missing": ["ORIGINAL_ROWS_NOT_CHECKED"],
                "rowIndices": missing,
            }
        if answer != {
            "reportDigest": report["reportDigest"],
            "inspectedRowIndices": report["requiredRowIndices"],
            "businessAcceptance": False,
        }:
            return {"passed": False, "missing": ["ANSWER_EVIDENCE_MISMATCH"]}
        return {"passed": True, "checks": verified, "businessAcceptance": False}
