"""Synthetic analytical computations, not production billing or acceptance evidence."""

import pytest
from agent_console.skill_executor import SkillExecutorFailure
from agent_console.synthetic_cost_skill import SyntheticCostSkillExecutor


def source():
    return {
        "schemaVersion": "synthetic-cost-source.v1",
        "synthetic": True,
        "periods": {"sep-partial": {"days": 20}, "oct-full": {"days": 31}},
        "rows": [
            {
                "id": "a",
                "project": "星河客服",
                "trial": False,
                "category": "MODEL_API",
                "currency": "CNY",
                "period": "sep-partial",
                "amount": "100.10",
            },
            {
                "id": "b",
                "project": "星河客服",
                "trial": False,
                "category": "MODEL_API",
                "currency": "CNY",
                "period": "sep-partial",
                "amount": "0.20",
            },
            {
                "id": "trial",
                "project": "星河客服",
                "trial": True,
                "category": "COMPUTE",
                "currency": "CNY",
                "period": "oct-full",
                "amount": "99000",
            },
        ],
        "gaps": ["shared-allocation-unavailable"],
    }


def invoke(operation, dependencies=None, snapshot=None):
    return (
        SyntheticCostSkillExecutor()
        .invoke(
            "test:" + operation,
            operation,
            {
                "synthetic": True,
                "sourceSnapshot": {"digest": "a" * 64},
                "dependencies": dependencies or {},
                "source": snapshot or source(),
            },
            1000,
        )
        .output
    )


def test_full_graph_preserves_exclusions_and_uncertainty():
    read = invoke("READ_DATA")
    validated = invoke("VALIDATE_DATA", {"read": read})
    assert validated["excludedIds"] == ["trial"]
    summarized = invoke("SUMMARIZE", {"validate": validated})
    assert summarized["totals"] == {"sep-partial": {"MODEL_API": "100.30"}}
    analyzed = invoke("ANALYZE_DATA", {"validate": validated, "summary": summarized})
    assert analyzed["comparableMonths"] is False
    report = invoke(
        "RENDER_REPORT",
        {"recommendations": invoke("RECOMMEND", {"analysis": analyzed})},
    )
    assert report["businessConclusion"] == "UNDETERMINED"
    assert report["verifiedSavingsCny"] is None
    assert all(not r["executed"] for r in report["recommendations"])
    assert report["analysis"]["gaps"] == ["shared-allocation-unavailable"]


def test_non_synthetic_and_wrong_dependencies_fail_without_effects():
    with pytest.raises(SkillExecutorFailure, match="SYNTHETIC_SOURCE_REQUIRED"):
        invoke("READ_DATA", snapshot={**source(), "synthetic": False})
    with pytest.raises(SkillExecutorFailure, match="DEPENDENCY_MISMATCH"):
        invoke("ANALYZE_DATA", {"read": invoke("READ_DATA")})


def test_duplicate_rows_rejected_and_unknown_cost_not_filled_with_zero():
    value = source()
    value["rows"].append(value["rows"][0])
    with pytest.raises(SkillExecutorFailure, match="DUPLICATE"):
        invoke("VALIDATE_DATA", {"read": invoke("READ_DATA", snapshot=value)})
    value = source()
    value["rows"][0]["amount"] = "NaN"
    validated = invoke("VALIDATE_DATA", {"read": invoke("READ_DATA", snapshot=value)})
    assert validated["invalidIds"] == ["a"]
    assert len(validated["rows"]) == 1
