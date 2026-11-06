"""Explicit synthetic reproduction of the observed six logical roles."""

from copy import deepcopy

from agent_console.plan_suggestion_domain import FlexiblePlanSemantics
from agent_console.planning_contracts import OUTPUTS

SIX_OPERATIONS = (
    "READ_DATA",
    "VALIDATE_DATA",
    "CLASSIFY_OVERDUE",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RENDER_REPORT",
)


def six_roles(semantics):
    doc = (
        semantics.model_dump(mode="json")
        if hasattr(semantics, "model_dump")
        else deepcopy(semantics)
    )
    employee = next(r for r in doc["requirements"] if r["kind"] == "EMPLOYEE")
    knowledge = next(r for r in doc["requirements"] if r["kind"] == "KNOWLEDGE")
    doc["requirements"] = [
        knowledge,
        *[
            {**employee, "requirement_id": f"role-{i}", "operation": operation}
            for i, operation in enumerate(SIX_OPERATIONS)
        ],
    ]
    template = doc["tasks"][0]
    links = [[], [0], [1], [2], [1, 3], [3, 4]]
    doc["tasks"] = [
        {
            **template,
            "task_id": f"step-{i}",
            "operation": operation,
            "employee_requirement_id": f"role-{i}",
            "requirement_ids": [knowledge["requirement_id"]] if not i else [],
            "depends_on": [f"step-{j}" for j in links[i]],
            "input_kinds": [OUTPUTS[SIX_OPERATIONS[j]] for j in links[i]]
            if i
            else ["CONTEXT"],
            "output_kind": OUTPUTS[operation],
        }
        for i, operation in enumerate(SIX_OPERATIONS)
    ]
    doc["stages"] = [
        {
            "stage_id": "six-roles",
            "title": "Isolated six-role contract",
            "task_ids": [t["task_id"] for t in doc["tasks"]],
        }
    ]
    return FlexiblePlanSemantics.model_validate(doc)
