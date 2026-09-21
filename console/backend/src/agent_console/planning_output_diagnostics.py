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
    payload = text.encode()
    return {
        "phase": phase,
        "output_bytes": len(payload),
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "error_count": len(errors),
        "issues": issues,
    }
