import pytest
from agent_console.skill_mcp_repository import InMemorySkillMcpRepository, ResourceScope
from agent_console.skill_mcp_service import SkillMcpFailure, SkillMcpService
from test_skill_mcp_service import MCP, SKILL, publish


def test_publication_does_not_authorize_bounded_invocation() -> None:
    service = SkillMcpService(InMemorySkillMcpRepository())
    scope = ResourceScope("tenant", "domain")
    skill = publish(service, scope, "skill", "Quality", SKILL)
    mcp = publish(service, scope, "mcp", "MCP", MCP)
    bound = service.bind(
        scope,
        skill["resourceId"],
        "human",
        4,
        skill["publishedRevisionId"],
        mcp["resourceId"],
        mcp["publishedRevisionId"],
        "quality.lookup",
        "approved",
    )["resource"]
    binding = bound["bindings"][0]
    with pytest.raises(SkillMcpFailure, match="INVOCATION_NOT_AUTHORIZED"):
        service.invoke(
            scope, skill["resourceId"], "human", 5, binding["bindingId"], "", {}
        )
    result = service.invoke(
        scope,
        skill["resourceId"],
        "human",
        5,
        binding["bindingId"],
        "ALLOW_BOUNDED_CAPABILITY_TEST",
        {"supplier": "redacted"},
    )
    assert (
        result["invocation"]["status"] == "SUCCEEDED"
        and result["invocation"]["evidence"]["redacted"]
    )
