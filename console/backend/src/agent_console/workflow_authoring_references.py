"""Exact workflow dependencies read through their owners in the authorized UoW."""

import re

from .skill_mcp_schemas import validate_skill_operations
from .workbench_business_problem import OwnerPrincipal
from .workbench_prepared_resources import bind_service
from .workbench_resource_directory import target

KINDS = {
    "RUNTIME_PROFILE": "runtime",
    "SKILL": "skill",
    "MCP": "mcp",
    "AGENT": "agent",
    "KNOWLEDGE": "knowledge",
}
IDENTITIES = {
    "runtime": "runtimeProfileId",
    "skill": "resourceId",
    "mcp": "resourceId",
    "agent": "definitionId",
    "knowledge": "knowledgeId",
}


def digest(value):
    match = (
        re.fullmatch(r"(?:sha256:)?([a-f0-9]{64})", value)
        if isinstance(value, str)
        else None
    )
    return match[1] if match else None


class WorkflowReferenceChecker:
    def __init__(self, services):
        self.services = services

    def __call__(self, call, ref, require_published):
        kind = KINDS.get(ref.get("kind"))
        if kind is None or not digest(ref.get("digest")):
            return False
        identity, revision_id = ref.get("resourceId"), ref.get("revisionId")
        if not identity or not revision_id or kind not in self.services:
            return False
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        grant = target(kind, identity, revision_id)
        call.authority.require(
            principal, grant.owner, grant.action, grant.exact_resource
        )
        service = bind_service(self.services[kind], call.connection)
        scope = service.scope(principal.tenant_id, principal.security_domain)
        args = (
            (scope, kind, identity) if kind in {"skill", "mcp"} else (scope, identity)
        )
        record = service.repository.get(*args)
        # Compare the owning service's identity, not a display label.
        if record.get(IDENTITIES[kind]) != identity:
            return False
        exact = next(
            (r for r in record["revisions"] if r["revisionId"] == revision_id), None
        )
        if exact is None or digest(exact.get("digest")) != digest(ref["digest"]):
            return False
        if require_published and (
            exact["state"] != "PUBLISHED"
            or not record.get("enabled", True)
            or record.get("archived", False)
            or record.get("lifecycleState") in {"ARCHIVED", "DEPRECATED"}
            or (
                kind in {"skill", "mcp"}
                and record.get("publishedRevisionId") != revision_id
            )
        ):
            return False
        if "operation" in ref:
            if kind != "skill":
                return False
            operations = [
                op
                for op in exact["content"].get("operations", [])
                if op.get("name") == ref["operation"]
            ]
            if len(operations) != 1:
                return False
            validate_skill_operations(operations)
        return True
