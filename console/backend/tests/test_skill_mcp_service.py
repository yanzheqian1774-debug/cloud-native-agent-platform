import pytest
from agent_console.skill_mcp_repository import InMemorySkillMcpRepository, ResourceScope
from agent_console.skill_mcp_service import SkillMcpFailure, SkillMcpService

SKILL = {
    "description": "Analyze quality",
    "capabilities": ["quality.lookup"],
    "instructions": "Return a bounded quality result",
    "endpoint": None,
}
MCP = {
    "description": "Quality MCP",
    "capabilities": ["quality.lookup"],
    "instructions": None,
    "endpoint": "https://example.invalid/mcp",
}


def publish(service, scope, kind, name, content):
    created = service.create(scope, kind, "human", name, content)
    rid = created["resourceId"]
    validated = service.validate(scope, kind, rid, "human", 1)["resource"]
    digest = validated["revisions"][-1]["digest"]
    reviewed = service.review(
        scope, kind, rid, "reviewer", 2, digest, "APPROVE", "exact digest reviewed"
    )["resource"]
    return service.publish(
        scope, kind, rid, "publisher", 3, digest, reviewed["reviews"][-1]["reviewId"]
    )["resource"]


def test_exact_digest_publication_successor_and_controlled_failure() -> None:
    service = SkillMcpService(InMemorySkillMcpRepository())
    scope = ResourceScope("tenant", "domain")
    created = service.create(scope, "skill", "human", "Quality", SKILL)
    service.validate(scope, "skill", created["resourceId"], "human", 1)
    with pytest.raises(SkillMcpFailure, match="EXACT_DIGEST_REQUIRED"):
        service.review(
            scope, "skill", created["resourceId"], "human", 2, "wrong", "APPROVE", "x"
        )
    published = publish(
        SkillMcpService(InMemorySkillMcpRepository()), scope, "mcp", "MCP", MCP
    )
    assert published["lifecycleState"] == "PUBLISHED"


def test_bind_requires_exact_published_revisions() -> None:
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
        "approved composition",
    )
    assert (
        bound["resource"]["bindings"][0]["mcpRevisionId"] == mcp["publishedRevisionId"]
    )
