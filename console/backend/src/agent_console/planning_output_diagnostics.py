"""Bounded validation metadata; never retain provider text or input values."""

import hashlib

from .plan_suggestion_policy import output_schema

RULES = frozenset(
    {
        "PLAN_STRUCTURE_INVALID",
        "PLAN_REFERENCE_INVALID",
        "PLAN_DEPENDENCY_CYCLE",
        "PROCUREMENT_STAGE_TASK_CONTRACT",
        "PROCUREMENT_DEPENDENCY_CONTRACT",
        "PLANNING_RESULT_INVALID",
        "PLANNING_MODE_TEMPLATE_CONFLICT",
        "PLANNING_TEMPLATE_OPERATION_CONFLICT",
        "PLANNING_OPERATION_CONFLICT",
        "BUSINESS_ACCEPTANCE_IS_NOT_A_PLANNING_TASK",
        "PLANNING_CRITERION_COVERAGE_MISSING",
        "PLANNING_OPERATION_OUTPUT_CONFLICT",
        "PLANNING_OPERATION_INPUT_CONFLICT",
        "PLANNING_STRICT_OPERATION_CONFLICT",
        "PLANNING_STRICT_DEPENDENCY_CONFLICT",
        "PLANNING_STRICT_STAGE_CONFLICT",
    }
)


def diagnostic(text, phase, error=None):
    fields = set()

    def collect(value):
        if isinstance(value, dict):
            fields.update(value.get("properties", {}))
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(output_schema(modern=True))
    errors = error.errors(include_input=False, include_url=False) if error else []
    issues = []
    for item in errors[:16]:
        rule = str(item.get("ctx", {}).get("error", ""))
        issues.append(
            {
                "path": [
                    part
                    if (isinstance(part, int) and 0 <= part < 128) or part in fields
                    else "UNKNOWN_FIELD"
                    for part in item["loc"][:12]
                ],
                "type": item["type"],
                "rule": rule if rule in RULES else None,
            }
        )
    located = located_contract_issues(text)
    payload = text.encode()
    return {
        "locations": located,
        "phase": phase,
        "output_bytes": len(payload),
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "error_count": len(errors),
        "issues": issues,
    }


def located_contract_issues(text):
    """Locate finite graph violations without disclosing arbitrary provider values."""
    import json

    from .planning_contracts import INPUTS, OUTPUTS

    try:
        plan = json.loads(text).get("semantics") or {}
        tasks = plan.get("tasks", [])
        if not isinstance(tasks, list) or len(tasks) > 32:
            return []
        by_id = {t["task_id"]: t for t in tasks}
        requirements = {r["requirement_id"]: r for r in plan.get("requirements", [])}
        criteria = set(plan["target"]["criterion_revision_ids"])
        found = []
        for index, task in enumerate(tasks):

            def add(field, rule, index=index):
                found.append(
                    {
                        "path": ["semantics", "tasks", index, field],
                        "type": "contract",
                        "rule": rule,
                    }
                )

            if (
                task.get("employee_requirement_id") not in requirements
                or requirements[task["employee_requirement_id"]].get("kind")
                != "EMPLOYEE"
            ):
                add("employee_requirement_id", "PLAN_REFERENCE_INVALID")
            if not set(task.get("requirement_ids", [])) <= requirements.keys():
                add("requirement_ids", "PLAN_REFERENCE_INVALID")
            if not set(task.get("criterion_revision_ids", [])) <= criteria:
                add("criterion_revision_ids", "PLANNING_CRITERION_COVERAGE_MISSING")
            deps = task.get("depends_on", [])
            if not set(deps) <= by_id.keys() or task["task_id"] in deps:
                add("depends_on", "PLAN_REFERENCE_INVALID")
                continue
            operation = task.get("operation")
            if operation not in OUTPUTS:
                continue
            if task.get("output_kind") != OUTPUTS[operation]:
                add("output_kind", "PLANNING_OPERATION_OUTPUT_CONFLICT")
            incoming = set(task.get("input_kinds", []))
            produced = {by_id[dep].get("output_kind") for dep in deps}
            valid = (
                (not deps and incoming == {"CONTEXT"})
                if operation == "READ_DATA"
                else (
                    bool(produced)
                    and incoming == produced
                    and bool(incoming & INPUTS[operation])
                )
            )
            if not valid:
                add("input_kinds", "PLANNING_OPERATION_INPUT_CONFLICT")
        return found[:16]
    except (ValueError, TypeError, KeyError, AttributeError):
        return []
