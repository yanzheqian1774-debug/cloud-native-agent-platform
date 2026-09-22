"""Delivery rules over explicitly synthetic orders, not business acceptance."""

from copy import deepcopy

import pytest
from agent_console.delivery_resource_bundle import resource_content, source_document
from agent_console.skill_executor import SkillExecutorFailure
from agent_console.synthetic_delivery_skill import (
    SyntheticDeliverySkillExecutor,
    analyze,
)


def test_fixed_snapshot_ranking_units_exclusions_and_anomalies():
    source = source_document()
    before = deepcopy(source)
    result = analyze(source)
    assert source == before
    assert result == analyze(source)
    assert result["assessmentDate"] == "2026-09-20"
    assert [s["supplierId"] for s in result["suppliers"]] == ["SYN-A", "SYN-B", "SYN-C"]
    first = result["suppliers"][0]
    assert first["remainingByUnit"] == {"件": "60", "箱": "15"}
    assert (first["maxOverdueDays"], first["overdueOrderCount"]) == (10, 2)
    assert {o["orderId"] for o in result["excludedOrders"]} == {"PO-S07", "PO-S08"}
    assert {o["orderId"] for o in result["anomalies"]} == {"PO-S09", "PO-S10"}
    assert not any(
        o["overdue"] for o in result["orderDetails"] if o["supplierId"] == "SYN-D"
    )


@pytest.mark.parametrize(
    "quantity", ["NaN", "Infinity", "-1", "0.0000001", "0e999999999", None]
)
def test_invalid_quantities_are_separate_not_guessed(quantity):
    source = source_document()
    source["orders"][0]["orderedQuantity"] = quantity
    result = analyze(source)
    assert result["anomalies"][0]["orderId"] == "PO-S01"
    assert all(o["orderId"] != "PO-S01" for o in result["orderDetails"])


def test_duplicate_orders_all_excluded_from_calculations():
    source = source_document()
    source["orders"].append(deepcopy(source["orders"][0]))
    result = analyze(source)
    duplicates = [a for a in result["anomalies"] if a["orderId"] == "PO-S01"]
    assert len(duplicates) == 2
    assert all(a["reasons"] == ["DUPLICATE_ORDER_ID"] for a in duplicates)
    assert all(o["orderId"] != "PO-S01" for o in result["orderDetails"])


def test_executor_dependency_provenance_and_resource_revision():
    executor = SyntheticDeliverySkillExecutor()
    inputs = {
        "schemaVersion": "synthetic-delivery-input.v1",
        "synthetic": True,
        "sourceSnapshot": {"digest": "a" * 64},
        "source": source_document(),
    }
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    downstream = {**inputs, "dependencies": {"read": read}}
    report = executor.invoke("report", "RENDER_REPORT", downstream, 1000).output
    assert report["businessConclusion"] == "UNDETERMINED"
    assert report["suppliers"] == read["suppliers"]
    read["source"]["orders"][0]["orderedQuantity"] = "200"
    with pytest.raises(SkillExecutorFailure, match="SOURCE_CONFLICT"):
        executor.invoke("tampered", "RENDER_REPORT", downstream, 1000)
    for operation in resource_content()["skill"]["operations"]:
        assert operation["executorId"] == executor.revision.executor_id
        assert (
            operation["executorConfigurationDigest"]
            == executor.revision.configuration_digest
        )


@pytest.mark.parametrize(
    "source",
    [
        {},
        {**source_document(), "synthetic": False},
        {**source_document(), "assessmentDate": "today"},
    ],
)
def test_no_real_data_or_dynamic_assessment_date(source):
    with pytest.raises(SkillExecutorFailure):
        analyze(source)
