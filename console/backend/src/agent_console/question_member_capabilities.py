"""Read-only capability facts before planning; no predecessor task graph input."""

from .authority_contracts import AuthorityError
from .execution_domain import ScopeIdentity
from .plan_suggestion_domain import ExactReference, PlanningError
from .planning_candidates import identities, read_published, require_read
from .planning_contracts import INPUTS, OUTPUTS
from .resource_automation_validation import validate
from .workbench_business_problem import OwnerPrincipal


def observe(automation, call, source, source_schema, work, *, fixed_bindings=None):
    if not getattr(automation, "services", None):
        return {"state": "NOT_CONFIGURED", "operations": [], "executionReady": False}
    scope = ScopeIdentity(
        call.context.scope.tenant_id, call.context.scope.security_domain
    )
    principal = OwnerPrincipal(
        call.context.principal_id, scope.namespace, scope.security_domain
    )
    operations = set()
    rows = (
        identities(call.connection, scope, "EMPLOYEE", limit=201)
        if fixed_bindings is None
        else [
            {
                "identity": b["reference"]["resource_id"],
                "revision": b["reference"]["revision_id"],
                "digest": b["reference"]["digest"],
            }
            for b in fixed_bindings
            if b["kind"] == "EMPLOYEE"
        ]
    )
    for row in rows:
        try:
            employee = ExactReference(
                resource_id=row["identity"],
                revision_id=row["revision"],
                digest=row["digest"].removeprefix("sha256:"),
            )
            require_read(call.authority, principal, "EMPLOYEE", employee)
            definition, _ = read_published(call.connection, scope, "EMPLOYEE", employee)
            if fixed_bindings is not None:
                declared = {
                    (
                        b["kind"],
                        b["reference"]["resource_id"],
                        b["reference"]["revision_id"],
                        b["reference"]["digest"].removeprefix("sha256:"),
                    )
                    for b in fixed_bindings
                    if b["kind"] != "EMPLOYEE"
                }
                actual = {
                    (
                        m["kind"],
                        m["resource_id"],
                        m["revision_id"],
                        m["digest"].removeprefix("sha256:"),
                    )
                    for m in definition["members"]
                }
                if not declared <= actual or any(
                    m[0] in {"SKILL", "MCP", "KNOWLEDGE"} and m not in declared
                    for m in actual
                ):
                    continue
            contents = {}
            sources = []
            for member in definition["members"]:
                kind = {"RUNTIME_PROFILE": "RUNTIME"}.get(
                    member["kind"], member["kind"]
                )
                ref = ExactReference(
                    resource_id=member["resource_id"],
                    revision_id=member["revision_id"],
                    digest=member["digest"].removeprefix("sha256:"),
                )
                require_read(call.authority, principal, kind, ref)
                content, _ = read_published(call.connection, scope, kind, ref)
                contents.setdefault(kind, []).append(content)
                if kind == "KNOWLEDGE":
                    sources.append(ref)
            if sources != [source] or set(contents) != {
                "AGENT",
                "KNOWLEDGE",
                "RUNTIME",
                "SKILL",
            }:
                continue
            if any(len(contents[k]) != 1 for k in ("AGENT", "KNOWLEDGE", "RUNTIME")):
                continue
            declared = set()
            for kind, values in contents.items():
                for content in values:
                    validate(
                        kind.lower(),
                        content,
                        work,
                        expected_source_schema=source_schema,
                        sales_v2_candidate=automation.sales_v2_candidate,
                    )
                    if kind == "SKILL":
                        declared.update(
                            op["name"]
                            for op in content["operations"]
                            if op["name"] in OUTPUTS
                        )
            operations.update(declared)
        except (AuthorityError, PlanningError, ValueError, KeyError):
            continue  # No hidden names, references, counts or readiness inference.
    return {
        "state": "AUTHORIZED_MEMBER_DECLARATIONS_OBSERVED"
        if operations
        else "NO_COMPATIBLE_VISIBLE_DECLARATIONS",
        "operations": [
            {
                "operation": name,
                "inputKinds": sorted(INPUTS[name]),
                "outputKind": OUTPUTS[name],
            }
            for name in sorted(operations)
        ],
        "executionReady": False,
        "coverageComplete": False,
        "basis": "READABLE_PUBLISHED_MEMBERS_REGISTERED_METADATA_NOT_ACTUAL_TESTS",
    }
