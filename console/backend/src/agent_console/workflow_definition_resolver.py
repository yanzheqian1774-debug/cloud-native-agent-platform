"""Workflow authoring reads domain-owned facts; publication grants no execution."""

from agent_console.runtime_profile_api import get_service as get_runtime_profile_service
from agent_console.skill_mcp_api import get_skill_mcp_service
from agent_console.skill_mcp_schemas import validate_skill_operations


def resolve_workflow_reference(scope, reference):
    kind = reference["kind"]
    if kind not in {"RUNTIME_PROFILE", "SKILL"}:
        return False
    try:
        if kind == "RUNTIME_PROFILE":
            service = get_runtime_profile_service()
            record = service.repository.get(
                service.scope(scope.namespace, scope.security_domain),
                reference["resourceId"],
            )
        else:
            service = get_skill_mcp_service()
            record = service.repository.get(
                service.scope(scope.namespace, scope.security_domain),
                "skill",
                reference["resourceId"],
            )
            if (
                record["kind"] != "skill"
                or record["publishedRevisionId"] != reference["revisionId"]
                or not record["enabled"]
                or record.get("archived", False)
                or record.get("lifecycleState") == "DEPRECATED"
            ):
                return False
        revision = next(
            (
                item
                for item in record["revisions"]
                if item["revisionId"] == reference["revisionId"]
                and item["state"] == "PUBLISHED"
                and item["digest"] == reference.get("digest", item["digest"])
            ),
            None,
        )
        if revision is None:
            return False
        if "operation" in reference:
            operations = [
                item
                for item in revision["content"].get("operations", ())
                if item.get("name") == reference["operation"]
            ]
            if len(operations) != 1:
                return False
            validate_skill_operations(operations)
            return True
        return True
    except Exception:
        # Unavailable owner or malformed stored identity must fail closed.
        return False
