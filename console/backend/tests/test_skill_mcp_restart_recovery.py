from agent_console.skill_mcp_repository import InMemorySkillMcpRepository, ResourceScope
from agent_console.skill_mcp_service import SkillMcpService
from test_skill_mcp_service import SKILL, publish


def test_new_service_recovers_exact_identity_revision_and_digest() -> None:
    repository = InMemorySkillMcpRepository()
    scope = ResourceScope("tenant", "domain")
    before = publish(SkillMcpService(repository), scope, "skill", "Quality", SKILL)
    after = SkillMcpService(repository).get(scope, "skill", before["resourceId"])[
        "resource"
    ]
    assert after["resourceId"] == before["resourceId"]
    assert after["publishedRevisionId"] == before["publishedRevisionId"]
    assert after["revisions"][-1]["digest"] == before["revisions"][-1]["digest"]
