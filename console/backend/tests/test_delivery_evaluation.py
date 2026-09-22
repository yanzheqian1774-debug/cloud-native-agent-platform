"""Mutated reports must not satisfy exact delivery criteria."""

from copy import deepcopy

import pytest
from agent_console.delivery_evaluation import CHECKS, evaluate
from agent_console.delivery_resource_bundle import source_document
from agent_console.resource_use_domain import canonical_digest
from agent_console.synthetic_delivery_skill import SyntheticDeliverySkillExecutor

REF = {"resource_id": "fixture", "revision_id": "v1", "digest": "a" * 64}


def criterion(check):
    return {
        "criterion_type": "DETERMINISTIC_BOOLEAN",
        "measurement": {"expected": True},
        "evaluator_type": "SYNTHETIC_DELIVERY",
        "evaluator_version": "1",
        "required_evidence_kinds": [
            "NATIVE_EXECUTION_ARTIFACT",
            "PUBLISHED_SYNTHETIC_SOURCE",
        ],
        "applicability": {
            "check": check,
            "sourceContentDigest": canonical_digest(source_document()),
        },
    }


def report():
    executor = SyntheticDeliverySkillExecutor()
    inputs = {
        "schemaVersion": "synthetic-delivery-input.v1",
        "synthetic": True,
        "sourceSnapshot": REF,
        "source": source_document(),
    }
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    return executor.invoke(
        "report", "RENDER_REPORT", {**inputs, "dependencies": {"read": read}}, 1000
    ).output


@pytest.mark.parametrize("check", CHECKS)
def test_actual_computation_satisfies_exact_synthetic_checks(check):
    assert (
        evaluate(criterion(check), source_document(), report(), REF)[0] == "SATISFIED"
    )


@pytest.mark.parametrize("check", CHECKS)
def test_each_required_dimension_detects_mutation(check):
    value = report()
    if check == "snapshot":
        value["assessmentDate"] = "2026-09-21"
    elif check == "eligibility":
        value["orderDetails"][-1]["overdue"] = True
    elif check == "quantities":
        value["suppliers"][0]["remainingByUnit"] = {"件": "75"}
    elif check == "ranking":
        value["suppliers"].reverse()
    elif check == "traceability":
        value["suppliers"][0]["orders"] = []
    else:
        value["anomalies"] = []
    assert (
        evaluate(criterion(check), source_document(), value, REF)[0] == "NOT_SATISFIED"
    )


def test_missing_source_report_wrong_version_and_wrong_source_never_pass():
    c = criterion("snapshot")
    for source, result in [(None, report()), (source_document(), None)]:
        assert evaluate(c, source, result, REF)[0] == "UNKNOWN"
    altered = deepcopy(c)
    altered["evaluator_version"] = "unregistered"
    assert evaluate(altered, source_document(), report(), REF)[0] == "UNKNOWN"
    altered = source_document()
    altered["assessmentDate"] = "2026-09-19"
    assert evaluate(c, altered, report(), REF)[0] == "UNKNOWN"
    value = report()
    value["operation"] = "ANALYZE_DATA"
    assert evaluate(c, source_document(), value, REF)[0] == "UNKNOWN"
