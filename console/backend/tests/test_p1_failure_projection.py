"""Bounded evidence improvements; strict rejection and original facts stay intact."""

import json
from copy import deepcopy

import pytest
from agent_console.plan_suggestion_runtime import project_business_context
from agent_console.planning_contracts import INPUTS, OUTPUTS, input_conflict
from agent_console.planning_output_diagnostics import diagnostic
from agent_console.question_activity_input import member_contract_answers


def test_transport_deduplicates_only_equal_outer_facts_without_losing_context():
    target = {"problem": {"resource_id": "exact", "digest": "a" * 64}}
    policy = {"mode": "FREE", "required_operations": []}
    context = {
        "target": deepcopy(target),
        "planning_policy": deepcopy(policy),
        "criteria": [
            {"revision_id": "criterion", "measurement": {"rubric": "不可删标准"}}
        ],
        "description": "固定日期、币种和异常边界",
        "planning_context": {"previous_questions": ["已补充内容"]},
        "validation_feedback": {"rule": "old-error"},
    }
    original = deepcopy(context)
    projected = project_business_context(target, {"planning_policy": policy}, context)
    assert projected == {
        k: v for k, v in original.items() if k not in {"target", "planning_policy"}
    }
    assert context == original
    assert len(json.dumps(projected)) < len(json.dumps(original))
    context["target"] = {"problem": {"resource_id": "different"}}
    context["planning_policy"] = {"mode": "STRICT_WORKFLOW"}
    assert (
        project_business_context(target, {"planning_policy": policy}, context)
        == context
    )


def test_observed_contract_entries_are_complete_bounded_and_not_a_task_graph():
    ops = [
        {"operation": op, "inputKinds": sorted(INPUTS[op]), "outputKind": OUTPUTS[op]}
        for op in sorted(OUTPUTS)
    ]
    chunks = member_contract_answers(ops)
    assert 1 < len(chunks) <= 13
    assert all(1 <= len(value) <= 500 for value in chunks)
    rows = [
        row for chunk in chunks for row in json.loads(chunk.split(chr(0xFF1A), 1)[1])
    ]
    assert rows == [[op["operation"], op["inputKinds"], op["outputKind"]] for op in ops]
    assert not any(
        word in "".join(chunks)
        for word in ["task_id", "depends_on", "employee_requirement_id"]
    )
    assert member_contract_answers([]) == ()


@pytest.mark.parametrize(
    "operation,incoming,produced,deps,reason",
    [
        ("READ_DATA", {"CONTEXT"}, set(), False, None),
        ("READ_DATA", {"CONTEXT"}, {"SOURCE_SNAPSHOT"}, True, "READ_ROOT_MISMATCH"),
        ("ANALYZE_DATA", {"VALIDATED_DATA"}, set(), False, "EMPTY_PRODUCER_SET"),
        (
            "RENDER_REPORT",
            {"ANALYSIS"},
            {"ANALYSIS", "RECOMMENDATIONS"},
            True,
            "DECLARED_PRODUCER_SET_MISMATCH",
        ),
        (
            "ANALYZE_DATA",
            {"SOURCE_SNAPSHOT"},
            {"SOURCE_SNAPSHOT"},
            True,
            "NO_COMPATIBLE_INPUT_KIND",
        ),
        # Mixed predecessors remain valid when every produced kind is declared and
        # at least one is compatible; the original contract never required a subset.
        (
            "ANALYZE_DATA",
            {"SOURCE_SNAPSHOT", "SUMMARY"},
            {"SOURCE_SNAPSHOT", "SUMMARY"},
            True,
            None,
        ),
    ],
)
def test_original_input_contract_and_finite_subconditions(
    operation, incoming, produced, deps, reason
):
    assert input_conflict(operation, incoming, produced, deps) == reason


def test_future_diagnostic_facts_explain_edge_mismatch_without_arbitrary_values():
    from test_planning_contracts import modern

    plan = modern()
    task = plan["tasks"][3]
    task["input_kinds"] = ["ANALYSIS", "private provider value"]
    text = json.dumps({"kind": "VALID_SUGGESTION", "semantics": plan})
    result = diagnostic(text, "SCHEMA_OR_CONTRACT")
    item = next(
        x
        for x in result["locations"]
        if x["path"] == ["semantics", "tasks", 3, "input_kinds"]
    )
    assert item["rule"] == "PLANNING_OPERATION_INPUT_CONFLICT"
    facts = item["contractFacts"]
    assert facts["subcondition"] == "DECLARED_PRODUCER_SET_MISMATCH"
    assert facts["hasUnknownValue"] is True
    assert facts["declaredInputKinds"] == ["ANALYSIS"]
    assert set(facts["dependencyOutputKinds"]) <= set(OUTPUTS.values())
    assert "private provider value" not in json.dumps(result)
    assert task["task_id"] not in json.dumps(facts)
