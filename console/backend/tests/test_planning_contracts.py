"""Finite declared semantics, historical compatibility, and variable graphs."""

import pytest
from agent_console.plan_suggestion_domain import FlexiblePlanSemantics, PlanSemantics
from agent_console.planning_contracts import OUTPUTS, PROCUREMENT, PlanningPolicy
from pydantic import ValidationError
from test_plan_suggestion_v2 import sample


def modern(operations=PROCUREMENT, mode="FREE"):
    value = sample()
    value.update(schema_version="planning.v3", policy={"mode": mode})
    if mode != "FREE":
        value["policy"]["template"] = "procurement-overdue.v1"
    prototype = value["tasks"][0]
    value["tasks"] = [
        {
            **prototype,
            "task_id": f"node-{i}",
            "depends_on": [f"node-{i - 1}"] if i else [],
            "operation": operation,
            "input_kinds": [OUTPUTS[operations[i - 1]]] if i else ["CONTEXT"],
            "output_kind": OUTPUTS[operation],
        }
        for i, operation in enumerate(operations)
    ]
    value["stages"] = [
        {
            "stage_id": "stage",
            "title": "分析准备",
            "task_ids": [t["task_id"] for t in value["tasks"]],
        }
    ]
    if mode == "STRICT_WORKFLOW":
        value["stages"] = [
            {"stage_id": str(i), "title": "阶段", "task_ids": ids}
            for i, ids in enumerate(
                (["node-0"], ["node-1", "node-2"], ["node-3", "node-4"])
            )
        ]
    return value


@pytest.mark.parametrize(
    "operations",
    [
        ("READ_DATA", "RENDER_REPORT"),
        ("READ_DATA", "SUMMARIZE", "RENDER_REPORT"),
        ("READ_DATA", "VALIDATE_DATA", "ANALYZE_DATA", "RECOMMEND", "RENDER_REPORT"),
        (*PROCUREMENT[:4], "ANALYZE_DATA", "RENDER_REPORT"),
    ],
)
def test_free_variable_graphs(operations):
    assert len(FlexiblePlanSemantics.model_validate(modern(operations)).tasks) == len(
        operations
    )


def test_assisted_is_advisory_strict_uses_operations_not_ids():
    FlexiblePlanSemantics.model_validate(
        modern(("READ_DATA", "RENDER_REPORT"), "TEMPLATE_ASSISTED")
    )
    FlexiblePlanSemantics.model_validate(modern(mode="STRICT_WORKFLOW"))
    invalid = modern(mode="STRICT_WORKFLOW")
    invalid["tasks"][2].update(operation="ANALYZE_DATA", output_kind="ANALYSIS")
    invalid["tasks"][3]["input_kinds"] = ["ANALYSIS"]
    with pytest.raises(ValidationError):
        FlexiblePlanSemantics.model_validate(invalid)


@pytest.mark.parametrize(
    "mutation",
    ["missing_criterion", "false_output", "false_input", "prohibited", "required"],
)
def test_declared_semantic_failures(mutation):
    value = modern()
    if mutation == "missing_criterion":
        value["target"]["criterion_revision_ids"].append("criterion:2")
    elif mutation == "false_output":
        value["tasks"][0]["output_kind"] = "REPORT"
    elif mutation == "false_input":
        value["tasks"][1]["input_kinds"] = ["REPORT"]
    elif mutation == "prohibited":
        value["policy"]["prohibited_operations"] = ["READ_DATA"]
    else:
        value["policy"]["required_operations"] = ["RECOMMEND"]
    with pytest.raises(ValidationError):
        FlexiblePlanSemantics.model_validate(value)


@pytest.mark.parametrize(
    "policy",
    [
        {"required_operations": ["READ_DATA"], "prohibited_operations": ["READ_DATA"]},
        {
            "mode": "STRICT_WORKFLOW",
            "template": "procurement-overdue.v1",
            "prohibited_operations": ["VALIDATE_DATA"],
        },
        {"business_acceptance_as_task": True},
        {"mode": "FREE", "template": "procurement-overdue.v1"},
    ],
)
def test_pre_generation_policy_conflicts(policy):
    with pytest.raises(ValidationError):
        PlanningPolicy.model_validate(policy)


def test_legacy_has_no_new_policy_fields():
    legacy = PlanSemantics.model_validate(sample())
    assert legacy.schema_version == "planning.v2"
    assert "policy" not in legacy.model_dump()
    assert "operation" not in legacy.tasks[0].model_dump()
