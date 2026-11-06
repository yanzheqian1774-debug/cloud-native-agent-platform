"""Resolve declarations inside owner-read exact employee members, never outside."""

from .plan_suggestion_domain import ExactReference


def resolve(semantics, members, contents):
    grouped = {}
    for member in members:
        kind = {"RUNTIME_PROFILE": "RUNTIME"}.get(member["kind"], member["kind"])
        ref = ExactReference(
            resource_id=member["resource_id"],
            revision_id=member["revision_id"],
            digest=member["digest"].removeprefix("sha256:"),
        )
        grouped.setdefault(kind, []).append(ref)
    skills = dict(contents.get("_skills", []))
    result = semantics.model_dump(mode="json")
    bindings = []
    referenced = {
        identity for task in semantics.tasks for identity in task.requirement_ids
    }
    for requirement, encoded in zip(
        semantics.requirements, result["requirements"], strict=True
    ):
        if requirement.kind == "EMPLOYEE":
            continue
        options = grouped.get(requirement.kind, [])
        if requirement.selected is not None:
            if requirement.selected not in options:
                raise ValueError("EXPLICIT_REQUIREMENT_MAPPING_MISMATCH")
            chosen = requirement.selected
        elif not requirement.required and requirement.requirement_id not in referenced:
            continue
        else:
            if requirement.kind == "SKILL":
                operations = {
                    task.operation
                    for task in semantics.tasks
                    if requirement.requirement_id in task.requirement_ids
                }
                if not operations:
                    raise ValueError("PENDING_SKILL_REQUIREMENT_UNUSED")
                options = [
                    ref
                    for ref in options
                    if operations
                    <= {op["name"] for op in skills.get(ref, {}).get("operations", [])}
                ]
            if not options:
                raise ValueError("PENDING_MEMBER_REQUIREMENT_UNAVAILABLE")
            if len(options) != 1:
                raise ValueError("PENDING_MEMBER_REQUIREMENT_AMBIGUOUS")
            chosen = options[0]
        encoded["selected"] = chosen.model_dump(mode="json")
        bindings.append(
            {
                "requirementId": requirement.requirement_id,
                "kind": requirement.kind,
                "reference": chosen.model_dump(mode="json"),
                "basis": "EXPLICIT_EXACT_MEMBER"
                if requirement.selected
                else "SYSTEM_EXACT_MEMBER_CONTRACT",
            }
        )
    return type(semantics).model_validate(result), bindings


def read_and_resolve(call, semantics, employee):
    from .execution_domain import ScopeIdentity
    from .planning_candidates import read_published, require_read
    from .workbench_business_problem import OwnerPrincipal

    scope = ScopeIdentity(
        call.context.scope.tenant_id, call.context.scope.security_domain
    )
    p = OwnerPrincipal(
        call.context.principal_id, scope.namespace, scope.security_domain
    )
    require_read(call.authority, p, "EMPLOYEE", employee)
    definition, _ = read_published(call.connection, scope, "EMPLOYEE", employee)
    contents = {"_skills": []}
    for member in definition["members"]:
        kind = {"RUNTIME_PROFILE": "RUNTIME"}.get(member["kind"], member["kind"])
        ref = ExactReference(
            resource_id=member["resource_id"],
            revision_id=member["revision_id"],
            digest=member["digest"].removeprefix("sha256:"),
        )
        require_read(call.authority, p, kind, ref)
        content, _ = read_published(call.connection, scope, kind, ref)
        if kind == "SKILL":
            contents["_skills"].append((ref, content))
    try:
        return resolve(semantics, definition["members"], contents)
    except ValueError as exc:
        import re

        from .workbench_owner_authorization import WorkbenchOwnerError

        reason = str(exc)
        if not re.fullmatch(r"[A-Z0-9_]{1,120}", reason):
            reason = "PENDING_MEMBER_REQUIREMENTS_INVALID"
        raise WorkbenchOwnerError(reason, 409) from exc
