"""Task-local binding within existing exact employee members; no owner effects."""

from .plan_suggestion_domain import ExactReference
from .resource_automation_validation import validate


def bind_steps(semantics, skills, *, source_schema, case, sales_v2_candidate=False):
    """skills contains only authorized, published members, never external candidates."""
    from .planning_contracts import validation_report

    validation_report(semantics)
    requirements = {r.requirement_id: r for r in semantics.requirements}
    if not skills:
        raise ValueError("TASK_MEMBER_SKILL_REQUIRED")
    available = []
    for ref, content in skills:
        validate(
            "skill",
            content,
            None,
            expected_source_schema=source_schema,
            sales_v2_candidate=sales_v2_candidate,
        )
        available.append((ref, content))
    result = {}
    selected_operations = []
    for task in semantics.tasks:
        commitments = {
            requirements[r].selected
            for r in task.requirement_ids
            if requirements[r].kind == "SKILL" and requirements[r].required
        }
        if None in commitments or len(commitments) > 1:
            raise ValueError("TASK_EXACT_SKILL_COMMITMENT_REQUIRED")
        choices = []
        for ref, content in available:
            if commitments and ref not in commitments:
                continue
            op = next(
                (o for o in content["operations"] if o["name"] == task.operation), None
            )
            if op:
                choices.append((ref, op))
        choices.sort(key=lambda x: (x[0].resource_id, x[0].revision_id, x[0].digest))
        if not choices:
            raise ValueError("TASK_MEMBER_OPERATION_UNAVAILABLE")
        ref, operation = choices[0]
        result[task.task_id] = {
            "reference": ref,
            "operation": operation,
            "basis": "EXPLICIT_TASK_REQUIREMENT"
            if commitments
            else "EXACT_APPROVED_MEMBER_OPERATION",
        }
        selected_operations.append(operation)
    if case == "delivery":
        from .prepared_delivery_contract import validate_delivery_mapping

        validate_delivery_mapping(
            semantics.model_dump(mode="json"), selected_operations
        )
    elif case == "sales":
        from .prepared_readonly_contract import validate_mapping
        from .sales_diagnostic_skill import SalesDiagnosticSkillExecutor
        from .sales_gross_profit_integration import is_v2, revision

        any_v2 = any(
            is_v2(
                op["executorId"],
                op["executorRevision"],
                op["executorConfigurationDigest"],
            )
            for op in selected_operations
        )
        validate_mapping(
            semantics.model_dump(mode="json"),
            selected_operations,
            revision()
            if any_v2 and sales_v2_candidate
            else SalesDiagnosticSkillExecutor.revision,
        )
    elif case == "tabular":
        from .prepared_readonly_contract import validate_mapping
        from .tabular_diagnostic_skill import TabularDiagnosticSkillExecutor

        validate_mapping(
            semantics.model_dump(mode="json"),
            selected_operations,
            TabularDiagnosticSkillExecutor.revision,
        )
    else:
        raise ValueError("TASK_MEMBER_CASE_UNSUPPORTED")
    return result


def resource_groups(resources):
    """Never overwrite two skills under the same kind as the old projection did."""
    groups = {}
    seen = set()
    for row in resources:
        ref = ExactReference(
            resource_id=row["identity"],
            revision_id=row["revisionId"],
            digest=row["digest"].removeprefix("sha256:"),
        )
        key = (row["kind"], ref.resource_id)
        if key in seen:
            raise ValueError("TASK_MEMBER_DUPLICATE_RESOURCE")
        seen.add(key)
        groups.setdefault(row["kind"], []).append(ref)
    if set(groups) != {"agent", "skill", "knowledge", "runtime"} or any(
        len(groups[k]) != 1 for k in ("agent", "knowledge", "runtime")
    ):
        raise ValueError("EXACT_READONLY_COMPOSITION_REQUIRED")
    return groups
