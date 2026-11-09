"""Local read-only operations for a bounded Native diagnostic task.

Reuses the tabular computation and independent evaluation. This is an internal
operation library, not an authorization service or a callable public endpoint.
Its source must be resolved by the existing Knowledge/Skill owners before use.
"""

from agent_runtime.native_loop import Tool, digest, snapshot

from .tabular_diagnostic_skill import analyze, validate_source
from .tabular_evaluation import checks


class NativeDiagnosticTools:
    def __init__(self, source, reference):
        self.source = snapshot(source)
        self.reference = snapshot(reference)
        self.mapping = validate_source(self.source)
        self.source_digest = digest(self.source)
        self._report = None
        self.tools = tuple(
            self._tool(name)
            for name in (
                "inspect_data",
                "check_limits",
                "inspect_records",
                "build_report",
            )
        )

    def _tool(self, name):
        descriptions = {
            "inspect_data": "Inspect fields, units and missing-value row IDs.",
            "check_limits": "Compute declared-limit exceptions and per-unit groups.",
            "inspect_records": "Read original rows for exceptions or gaps.",
            "build_report": "Build an evidence report, without business acceptance.",
        }
        schema = {"type": "object", "properties": {}, "additionalProperties": False}
        if name == "inspect_records":
            schema["properties"] = {
                "ids": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": {"type": "string"},
                    "uniqueItems": True,
                }
            }
            schema["required"] = ["ids"]
        else:
            schema["required"] = []
        return Tool(
            name,
            "1",
            digest(
                {
                    "name": name,
                    "schema": schema,
                    "implementation": "native-diagnostic-operations.v1",
                }
            ),
            descriptions[name],
            schema,
            lambda arguments: self.validate(name, arguments),
        )

    def validate(self, name, arguments):
        if name == "inspect_records":
            ids = arguments.get("ids")
            valid_ids = {row[self.mapping["identity"]] for row in self.source["rows"]}
            if (
                set(arguments) != {"ids"}
                or not isinstance(ids, list)
                or not 1 <= len(ids) <= 20
                or any(not isinstance(x, str) for x in ids)
                or len(set(ids)) != len(ids)
                or not set(ids) <= valid_ids
            ):
                raise ValueError("INVALID_RECORD_SELECTION")
        elif name not in {"inspect_data", "check_limits", "build_report"} or arguments:
            raise ValueError("INVALID_DIAGNOSTIC_OPERATION")

    def invoke(self, name, arguments):
        self.validate(name, arguments)
        result = analyze(self.source)
        provenance = {
            "sourceSnapshot": self.reference,
            "sourceDigest": result["sourceDigest"],
        }
        if name == "inspect_data":
            return {
                **provenance,
                "mapping": self.mapping,
                "inputCount": result["inputCount"],
                "invalidRows": result["invalidRows"],
                "units": sorted({row["unit"] for row in result["rows"]}),
            }
        if name == "check_limits":
            return {
                **provenance,
                "exceptionIds": result["exceptionIds"],
                "groups": result["groups"],
                "invalidRows": result["invalidRows"],
            }
        if name == "inspect_records":
            return {
                **provenance,
                "rows": [
                    row
                    for row in self.source["rows"]
                    if row[self.mapping["identity"]] in arguments["ids"]
                ],
            }
        report = {**result, **provenance, "businessConclusion": "UNDETERMINED"}
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
        if report.get("reportDigest") != digest(
            {k: v for k, v in report.items() if k != "reportDigest"}
        ):
            return {"passed": False, "missing": ["REPORT_DIGEST_MISMATCH"]}
        result = checks(self.source, report, self.reference)
        if any(item["result"] != "SATISFIED" for item in result):
            return {"passed": False, "missing": ["INDEPENDENT_CHECK_FAILED"]}
        # An independently correct report alone is not enough: the task requires
        # checking original exception and missing-data records before concluding.
        required = set(report["exceptionIds"]) | {
            r["id"] for r in report["invalidRows"]
        }
        inspected = {
            row[self.mapping["identity"]]
            for o in observations
            if o["tool"] == "inspect_records"
            for row in o["output"]["rows"]
        }
        missing = sorted(required - inspected)
        if missing:
            return {
                "passed": False,
                "missing": ["ORIGINAL_ROWS_NOT_CHECKED"],
                "rowIds": missing,
            }
        if (
            set(answer) != {"reportDigest", "exceptionIds", "invalidIds"}
            or answer["reportDigest"] != report["reportDigest"]
            or answer["exceptionIds"] != report["exceptionIds"]
            or answer["invalidIds"] != [r["id"] for r in report["invalidRows"]]
        ):
            return {"passed": False, "missing": ["ANSWER_EVIDENCE_MISMATCH"]}
        return {"passed": True, "checks": result, "businessAcceptance": False}
