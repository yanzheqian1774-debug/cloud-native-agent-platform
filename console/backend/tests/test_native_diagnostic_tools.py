"""Actual computation with scripted decisions; NOT real-model acceptance."""

from copy import deepcopy

import pytest
from agent_console.native_diagnostic_tools import NativeDiagnosticTools
from agent_runtime.native_loop import NativeLoop

SOURCE = {
    "schemaVersion": "tabular-diagnostic-source.v1",
    "synthetic": True,
    "title": "Synthetic application response-time diagnostics",
    "mapping": {
        "identity": "measurement",
        "value": "response_ms",
        "upperBound": "limit_ms",
        "unit": "unit",
        "dimensions": ["service"],
    },
    "rows": [
        {
            "measurement": "M1",
            "response_ms": "120",
            "limit_ms": "100",
            "unit": "ms",
            "service": "search",
        },
        {
            "measurement": "M2",
            "response_ms": "80",
            "limit_ms": "100",
            "unit": "ms",
            "service": "login",
        },
    ],
}
REFERENCE = {
    "resource_id": "monitoring-fixture",
    "revision_id": "1",
    "digest": "a" * 64,
}


class Journal:
    def __init__(self):
        self.records = {}

    def claim(self, key, request_digest):
        if key in self.records:
            return deepcopy(self.records[key])
        self.records[key] = {"requestDigest": request_digest}
        return None

    def finish(self, key, request_digest, result):
        assert self.records[key]["requestDigest"] == request_digest
        self.records[key]["result"] = deepcopy(result)


class ScriptedDecisionsWithRealTools:
    def __init__(self, source):
        self.library = NativeDiagnosticTools(source, REFERENCE)
        self.called = []

    def authorize(self, kind, request):
        return True  # Test seam only, never production composition.

    def decide(self, context, **kwargs):
        observations = context["observations"]
        outputs = {
            o["tool"]: o["output"] for o in observations if o["kind"] == "TOOL_RESULT"
        }
        if "inspect_data" not in outputs:
            name, arguments = "inspect_data", {}
        elif "check_limits" not in outputs:
            name, arguments = "check_limits", {}
        elif "build_report" not in outputs:
            result = outputs["check_limits"]
            ids = result["exceptionIds"] + [row["id"] for row in result["invalidRows"]]
            if ids and "inspect_records" not in outputs:
                name, arguments = "inspect_records", {"ids": ids}
            else:
                name, arguments = "build_report", {}
        else:
            report = outputs["build_report"]
            return {
                "action": "FINISH",
                "answer": {
                    "reportDigest": report["reportDigest"],
                    "exceptionIds": report["exceptionIds"],
                    "invalidIds": [row["id"] for row in report["invalidRows"]],
                },
            }
        return {"action": "TOOL", "tool": name, "arguments": arguments}

    def invoke(self, tool, arguments, **kwargs):
        self.called.append((tool.name, arguments))
        return self.library.invoke(tool.name, arguments)

    def verify(self, context, answer):
        return self.library.verify(context, answer)


@pytest.mark.parametrize(
    "value,expected_exception,expected_invalid,drilldown",
    [
        ("120", ["M1"], [], True),
        ("80", [], [], False),
        (None, [], ["M1"], True),
    ],
)
def test_real_observation_changes_selected_tool(
    value, expected_exception, expected_invalid, drilldown
):
    source = deepcopy(SOURCE)
    source["rows"][0]["response_ms"] = value
    ports = ScriptedDecisionsWithRealTools(source)
    result = NativeLoop(ports.library.tools, ports, Journal()).run(
        "fixture-attempt",
        "Check response-time problems",
        ["Trace anomalies and gaps to original rows"],
        {"sourceSnapshot": REFERENCE},
    )
    assert result["status"] == "SUCCEEDED"
    assert result["answer"]["exceptionIds"] == expected_exception
    assert result["answer"]["invalidIds"] == expected_invalid
    assert ("inspect_records" in [name for name, _ in ports.called]) is drilldown
    assert result["trace"][-1]["verification"]["businessAcceptance"] is False


def test_premature_correct_report_requires_original_rows():
    library = NativeDiagnosticTools(SOURCE, REFERENCE)
    report = library.invoke("build_report", {})
    result = library.verify(
        {
            "observations": [
                {"kind": "TOOL_RESULT", "tool": "build_report", "output": report}
            ]
        },
        {},
    )
    assert result == {
        "passed": False,
        "missing": ["ORIGINAL_ROWS_NOT_CHECKED"],
        "rowIds": ["M1"],
    }


def test_unknown_ids_and_operations_are_rejected():
    library = NativeDiagnosticTools(SOURCE, REFERENCE)
    for name, arguments in [
        ("inspect_records", {"ids": ["other"]}),
        ("exec", {}),
        ("check_limits", {"source": "different"}),
    ]:
        with pytest.raises(ValueError):
            library.invoke(name, arguments)


def test_source_is_a_snapshot_not_mutable_caller_data():
    source = deepcopy(SOURCE)
    library = NativeDiagnosticTools(source, REFERENCE)
    source["rows"][0]["response_ms"] = "0"
    assert library.invoke("check_limits", {})["exceptionIds"] == ["M1"]
