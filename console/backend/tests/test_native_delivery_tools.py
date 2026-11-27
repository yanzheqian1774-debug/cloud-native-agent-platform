"""Controlled model decisions with real Native loop/tools, not model acceptance."""

from copy import deepcopy

import pytest
from agent_console.delivery_resource_bundle import source_document
from agent_console.native_delivery_tools import NativeDeliveryTools
from agent_runtime.native_loop import NativeLoop
from test_native_diagnostic_tools import REFERENCE, Journal


class Decisions:
    def __init__(self, source):
        self.library = NativeDeliveryTools(source, REFERENCE)
        self.called = []

    def authorize(self, kind, request):
        return True  # Explicit controlled port, not owner authorization evidence.

    def decide(self, context, **kwargs):
        observed = {
            o["tool"]: o["output"]
            for o in context["observations"]
            if o["kind"] == "TOOL_RESULT"
        }
        if "inspect_source" not in observed:
            name, args = "inspect_source", {}
        elif "check_delivery" not in observed:
            name, args = "check_delivery", {}
        elif (
            observed["check_delivery"]["requiredRowIndices"]
            and "inspect_rows" not in observed
        ):
            name, args = (
                "inspect_rows",
                {"rowIndices": observed["check_delivery"]["requiredRowIndices"]},
            )
        elif "build_report" not in observed:
            name, args = "build_report", {}
        else:
            report = observed["build_report"]
            return {
                "action": "FINISH",
                "answer": {
                    "reportDigest": report["reportDigest"],
                    "inspectedRowIndices": report["requiredRowIndices"],
                    "businessAcceptance": False,
                },
            }
        return {"action": "TOOL", "tool": name, "arguments": args}

    def invoke(self, tool, arguments, **kwargs):
        self.called.append(tool.name)
        return self.library.invoke(tool.name, arguments)

    def verify(self, context, answer):
        return self.library.verify(context, answer)


@pytest.mark.parametrize("overdue", [True, False])
def test_actual_observations_control_drilldown_and_finish(overdue):
    source = source_document()
    source["orders"] = [source["orders"][0]]
    if not overdue:
        source["orders"][0]["promisedDate"] = "2026-10-01"
    ports = Decisions(source)
    result = NativeLoop(ports.library.tools, ports, Journal()).run(
        "delivery-attempt",
        "Check declared delivery snapshot",
        ["Evidence only"],
        {"sourceSnapshot": REFERENCE},
    )
    assert result["status"] == "SUCCEEDED"
    assert ("inspect_rows" in ports.called) is overdue
    assert result["trace"][-1]["verification"]["businessAcceptance"] is False
    assert len(ports.called) >= 3


def test_report_alone_cannot_complete_and_tampered_rows_do_not_count():
    library = NativeDeliveryTools(source_document(), REFERENCE)
    report = library.invoke("build_report", {})
    answer = {
        "reportDigest": report["reportDigest"],
        "inspectedRowIndices": report["requiredRowIndices"],
        "businessAcceptance": False,
    }
    context = {
        "observations": [
            {"kind": "TOOL_RESULT", "tool": "build_report", "output": report}
        ]
    }
    assert library.verify(context, answer)["missing"] == ["ORIGINAL_ROWS_NOT_CHECKED"]
    rows = library.invoke("inspect_rows", {"rowIndices": report["requiredRowIndices"]})
    rows["rows"][0]["sourceRow"]["supplierId"] = "fabricated"
    context["observations"].append(
        {"kind": "TOOL_RESULT", "tool": "inspect_rows", "output": rows}
    )
    assert library.verify(context, answer)["missing"] == ["ROW_PROVENANCE_MISMATCH"]


@pytest.mark.parametrize("indices", [[True], [-1], [999], [0, 0], []])
def test_only_exact_bounded_row_indices(indices):
    with pytest.raises(ValueError):
        NativeDeliveryTools(source_document(), REFERENCE).invoke(
            "inspect_rows", {"rowIndices": indices}
        )


def test_report_identity_and_business_acceptance_cannot_be_forged():
    ports = Decisions(source_document())
    library = ports.library
    report = library.invoke("build_report", {})
    rows = library.invoke("inspect_rows", {"rowIndices": report["requiredRowIndices"]})
    context = {
        "observations": [
            {"kind": "TOOL_RESULT", "tool": "inspect_rows", "output": rows},
            {"kind": "TOOL_RESULT", "tool": "build_report", "output": deepcopy(report)},
        ]
    }
    answer = {
        "reportDigest": report["reportDigest"],
        "inspectedRowIndices": report["requiredRowIndices"],
        "businessAcceptance": True,
    }
    assert library.verify(context, answer)["missing"] == ["ANSWER_EVIDENCE_MISMATCH"]
    context["observations"][-1]["output"]["gaps"] = []
    assert library.verify(context, answer)["missing"] == ["REPORT_IDENTITY_MISMATCH"]
