"""Fixed capability constraints consumed by the existing execution owner."""

from .capability_work_input import work_input
from .workbench_owner_authorization import WorkbenchOwnerError


def expected_problem_description(contract):
    return contract["objective"]


def exclusion_boundaries(contract):
    text = contract["exclusions"]
    if len(text) <= 500:
        return [text]
    parts = [text[i : i + 480] for i in range(0, len(text), 480)]
    return [f"[{i + 1}/{len(parts)}] {part}" for i, part in enumerate(parts)]


def verify_current(resolved, current):
    contract = resolved["contract"]
    if current["description"] != expected_problem_description(contract):
        raise WorkbenchOwnerError("CAPABILITY_PROBLEM_INPUT_MISMATCH", 409)
    criteria = current["criteria"]
    if len(criteria) != 1:
        raise WorkbenchOwnerError("CAPABILITY_COMPLETION_CRITERIA_MISMATCH", 409)
    expected = work_input(resolved)["criterion"]
    if (
        criteria[0]["measurement"] != expected["measurement"]
        or criteria[0].get("applicability") != expected["applicability"]
        or criteria[0].get("criterion_type") != expected["criterionType"]
        or criteria[0].get("evaluator_type") != expected["evaluatorType"]
        or criteria[0].get("evaluator_version") != expected["evaluatorVersion"]
    ):
        raise WorkbenchOwnerError("CAPABILITY_COMPLETION_CRITERIA_MISMATCH", 409)


def verify_plan(resolved, plan, current):
    target = plan.semantics.target.model_dump(mode="json")
    if any(
        current["target"][key] != target[key]
        for key in ("problem", "criteria", "criterion_revision_ids")
    ):
        raise WorkbenchOwnerError("CAPABILITY_PLAN_TARGET_MISMATCH", 409)
    verify_current(resolved, current)
    if not all(
        boundary in plan.semantics.boundaries
        for boundary in exclusion_boundaries(resolved["contract"])
    ):
        raise WorkbenchOwnerError("CAPABILITY_PLAN_BOUNDARY_MISMATCH", 409)


def verify_resources(resolved, ready, *, ontology_binding=None):
    bindings = resolved["contract"]["bindings"]
    employees = [
        binding["reference"] for binding in bindings if binding["kind"] == "EMPLOYEE"
    ]
    if (
        len(employees) != 1
        or ready.get("assembly", {}).get("definition") != employees[0]
    ):
        raise WorkbenchOwnerError("CAPABILITY_PREPARED_EMPLOYEE_MISMATCH", 409)
    allowed = {"SKILL", "MCP", "KNOWLEDGE", "RUNTIME_PROFILE"}
    resources = [
        (
            {"runtime": "RUNTIME_PROFILE"}.get(item["kind"], item["kind"].upper()),
            item["reference"],
        )
        for item in ready["resources"]
    ]
    for binding in bindings:
        if binding["kind"] == "EMPLOYEE":
            continue
        if binding["kind"] == "ONTOLOGY":
            if (
                ontology_binding is None
                or ontology_binding.ontology.model_dump(mode="json")
                != binding["reference"]
            ):
                raise WorkbenchOwnerError(
                    "CAPABILITY_ONTOLOGY_WORK_BINDING_MISMATCH", 409
                )
            continue
        if binding["kind"] not in allowed:
            raise WorkbenchOwnerError("CAPABILITY_EXECUTION_ADAPTER_UNAVAILABLE", 409)
        if (binding["kind"], binding["reference"]) not in resources:
            raise WorkbenchOwnerError("CAPABILITY_PREPARED_RESOURCE_MISMATCH", 409)
    for kind, reference in resources:
        if kind in {"SKILL", "MCP", "KNOWLEDGE"} and not any(
            binding["kind"] == kind and binding["reference"] == reference
            for binding in bindings
        ):
            raise WorkbenchOwnerError("CAPABILITY_UNDECLARED_BUSINESS_RESOURCE", 409)
