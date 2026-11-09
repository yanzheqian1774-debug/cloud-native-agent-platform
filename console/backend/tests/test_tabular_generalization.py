from copy import deepcopy

import pytest
from agent_console.conversation_capability import describe
from agent_console.skill_executor import SkillExecutorFailure
from agent_console.tabular_diagnostic_skill import (
    TabularDiagnosticSkillExecutor,
    analyze,
)
from agent_console.tabular_evaluation import checks


def sample():
    return {
        "schemaVersion": "tabular-diagnostic-source.v1",
        "synthetic": True,
        "mapping": {
            "identity": "sample",
            "value": "consumption",
            "upperBound": "limit",
            "unit": "unit",
            "dimensions": ["site"],
        },
        "rows": [
            {
                "sample": "A",
                "consumption": "120",
                "limit": "100",
                "unit": "kWh",
                "site": "North",
            },
            {
                "sample": "B",
                "consumption": "100",
                "limit": "100",
                "unit": "kWh",
                "site": "North",
            },
            {
                "sample": "C",
                "consumption": None,
                "limit": "100",
                "unit": "kWh",
                "site": "South",
            },
            {
                "sample": "D",
                "consumption": "8",
                "limit": "5",
                "unit": "m3",
                "site": "North",
            },
        ],
    }


def execute(source):
    executor = TabularDiagnosticSkillExecutor()
    inputs = {
        "synthetic": True,
        "source": source,
        "sourceSnapshot": {"digest": "a" * 64},
    }
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    report = executor.invoke(
        "report", "RENDER_REPORT", {**inputs, "dependencies": {"read": read}}, 1000
    ).output
    return report, inputs["sourceSnapshot"]


def test_energy_and_lab_use_same_adapter_with_different_columns():
    for source in (
        sample(),
        {
            "schemaVersion": "tabular-diagnostic-source.v1",
            "synthetic": True,
            "mapping": {
                "identity": "testId",
                "value": "measured",
                "upperBound": "tolerance",
                "unit": "measurementUnit",
                "dimensions": ["instrument", "batch"],
            },
            "rows": [
                {
                    "testId": "L1",
                    "measured": "0.21",
                    "tolerance": "0.20",
                    "measurementUnit": "mm",
                    "instrument": "M1",
                    "batch": "B1",
                }
            ],
        },
    ):
        report, ref = execute(source)
        assert all(c["result"] == "SATISFIED" for c in checks(source, report, ref))
        report["exceptionIds"] = []
        assert any(c["result"] == "NOT_SATISFIED" for c in checks(source, report, ref))


def test_no_unit_mixing_or_zero_filling_and_strict_bound():
    result = analyze(sample())
    assert result["exceptionIds"] == ["A", "D"]
    assert result["validCount"] == 3
    assert result["invalidRows"][0]["id"] == "C"
    assert {(g["unit"], g["totalExcess"]) for g in result["groups"]} == {
        ("kWh", "20"),
        ("m3", "3"),
    }


@pytest.mark.parametrize("change", ["duplicate", "column", "mapping", "real"])
def test_structural_gap_blocks(change):
    source = deepcopy(sample())
    if change == "duplicate":
        source["rows"][1]["sample"] = "A"
    elif change == "column":
        source["mapping"]["value"] = "unknown"
    elif change == "mapping":
        source["mapping"]["expression"] = "eval()"
    else:
        source["synthetic"] = False
    with pytest.raises(SkillExecutorFailure):
        analyze(source)


def test_foreign_dependency_and_write_operation_rejected():
    executor = TabularDiagnosticSkillExecutor()
    with pytest.raises(SkillExecutorFailure):
        executor.invoke("x", "SEND_EMAIL", {"synthetic": True}, 1000)
    with pytest.raises(SkillExecutorFailure):
        executor.invoke(
            "x",
            "RENDER_REPORT",
            {
                "synthetic": True,
                "dependencies": {"x": {"schemaVersion": "sales-diagnostic-output.v1"}},
            },
            1000,
        )


def test_capability_assessment_and_source_specific_criteria():
    source = sample()
    blocked = describe(source, {"operations": []})
    assert blocked["assessment"]["state"] == "MISSING_TOOLS"
    available = describe(
        source,
        {
            "operations": [
                {"operation": n} for n in ["READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"]
            ]
        },
    )
    assert available["assessment"]["executionReady"] is False
    assert available["assessment"]["state"] == "BOUNDED_ANALYSIS_AVAILABLE"
    assert "consumption" in available["completionCriteria"][0]
    assert not any("销售" in c for c in available["completionCriteria"])


def test_published_operation_contracts_resolve_and_reject_foreign_schema():
    from agent_console.authority_contracts import AuthorityError
    from agent_console.resource_automation_validation import executor_registry, validate
    from agent_console.tabular_resource_bundle import resource_content

    bundle = resource_content(sample())
    for enabled in (False, True):
        validate(
            "skill",
            bundle["skill"],
            None,
            expected_source_schema="tabular-diagnostic-source.v1",
            sales_v2_candidate=enabled,
        )
        assert executor_registry(sales_v2_candidate=enabled).resolve(
            TabularDiagnosticSkillExecutor.revision
        )
        with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
            validate(
                "skill",
                bundle["skill"],
                None,
                expected_source_schema="sales-diagnostic-source.v1",
                sales_v2_candidate=enabled,
            )
    broken = deepcopy(bundle["skill"])
    broken["operations"][0]["name"] = "SEND_EMAIL"
    with pytest.raises(AuthorityError, match="OPERATION_UNAVAILABLE"):
        validate("skill", broken, None)
