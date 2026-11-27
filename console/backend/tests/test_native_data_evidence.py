"""Independent measurement adapter, with controlled model decisions only."""

from copy import deepcopy

import pytest
from agent_console.delivery_evaluation import CHECKS, evaluate
from agent_console.delivery_resource_bundle import source_document
from agent_console.native_data_adapters import ADAPTERS
from agent_console.native_data_evidence import verified_report
from agent_console.native_data_skill import NativeDataSkillExecutor
from agent_console.synthetic_delivery_skill import SyntheticDeliverySkillExecutor
from agent_runtime.native_loop import NativeLoop
from test_delivery_evaluation import criterion
from test_native_delivery_tools import Decisions
from test_native_diagnostic_tools import REFERENCE, Journal


def evidence():
    source = source_document()
    ports = Decisions(source)
    loop = NativeLoop(ports.library.tools, ports, Journal()).run(
        "measurement-fixture", "Check original source", ["Evidence only"], {}
    )
    executor = NativeDataSkillExecutor(ADAPTERS[1], lambda *_: loop)
    inputs = {
        "schemaVersion": "native-data-input.v1",
        "synthetic": True,
        "source": source,
        "sourceSnapshot": REFERENCE,
    }
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    inputs["dependencies"] = {"read": read}
    report = executor.invoke("report", "RENDER_REPORT", inputs, 1000).output
    return report, executor.revision, source


def test_actual_native_artifact_measures_all_six_checks_without_skill_or_model(
    monkeypatch,
):
    output, revision, source = evidence()
    before = deepcopy(output)

    def forbidden(*args, **kwargs):
        raise AssertionError("Evaluation must not invoke the producing Skill or model")

    monkeypatch.setattr(NativeDataSkillExecutor, "invoke", forbidden)
    report = verified_report(output, revision, source, REFERENCE)
    assert report is not None
    assert all(
        evaluate(criterion(check), source, report, REFERENCE)[0] == "SATISFIED"
        for check in CHECKS
    )
    report["assessmentDate"] = "tampered consumer copy"
    assert output == before


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "sourceSnapshot",
        "sourceDigest",
        "adapter",
        "receipt",
        "report",
        "rows",
        "finish",
        "acceptance",
        "executor",
    ],
)
def test_wrong_or_self_reported_evidence_stays_unmeasurable(field):
    output, revision, source = evidence()
    if field == "source":
        output["source"]["assessmentDate"] = "2026-09-19"
        source = source_document()
    elif field == "sourceSnapshot":
        output["sourceSnapshot"]["revision_id"] = "different"
    elif field == "sourceDigest":
        output["sourceDigest"] = "f" * 64
    elif field == "adapter":
        output["adapter"]["configurationDigest"] = "f" * 64
    elif field == "receipt":
        output["nativeReportVerification"]["digest"] = "f" * 64
    elif field == "report":
        output["nativeReport"]["suppliers"][0]["remainingByUnit"] = {"件": "75"}
    elif field == "rows":
        output["nativeLoop"]["trace"] = [
            s
            for s in output["nativeLoop"]["trace"]
            if s.get("observation", {}).get("tool") != "inspect_rows"
        ]
    elif field == "finish":
        output["nativeLoop"]["trace"][-1]["verification"]["passed"] = False
    elif field == "acceptance":
        output["nativeLoop"]["answer"]["businessAcceptance"] = True
    elif field == "executor":
        revision = SyntheticDeliverySkillExecutor.revision
    assert verified_report(output, revision, source, REFERENCE) is None


@pytest.mark.parametrize("malformed", [None, {}, [], "raw text"])
def test_malformed_envelope_is_not_a_success_report(malformed):
    _, revision, source = evidence()
    assert verified_report(malformed, revision, source, REFERENCE) is None
