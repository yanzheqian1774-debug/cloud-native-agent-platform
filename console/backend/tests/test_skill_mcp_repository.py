import pytest
from agent_console.skill_mcp_repository import (
    InMemorySkillMcpRepository,
    ResourceScope,
    SkillMcpConflict,
)


def test_repository_scopes_and_optimistic_concurrency() -> None:
    repository = InMemorySkillMcpRepository()
    record = {
        "namespace": "a",
        "securityDomain": "d",
        "kind": "skill",
        "resourceId": "s",
        "aggregateVersion": 1,
        "publishedRevisionId": None,
        "facts": [],
    }
    repository.create(record)
    changed = {**record, "aggregateVersion": 2}
    repository.replace(changed, expected_version=1, fact={"factId": "f"})
    with pytest.raises(SkillMcpConflict, match="STALE_RESOURCE"):
        repository.replace(changed, expected_version=1, fact={"factId": "f2"})
    assert repository.list(ResourceScope("other", "d"), "skill") == []
