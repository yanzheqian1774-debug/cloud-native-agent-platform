import pytest
from agent_console.agent_definition_repository import (
    AgentDefinitionConflict,
    DefinitionScope,
    InMemoryAgentDefinitionRepository,
)


def record() -> dict:
    return {
        "namespace": "tenant-a",
        "securityDomain": "quality",
        "definitionId": "agent-definition:one",
        "aggregateVersion": 1,
        "facts": [{"factId": "fact:one"}],
    }


def test_repository_is_scoped_and_compare_and_set() -> None:
    repository = InMemoryAgentDefinitionRepository()
    repository.create(record())
    assert repository.list(DefinitionScope("tenant-a", "quality"))
    assert repository.list(DefinitionScope("tenant-b", "quality")) == []
    changed = {**record(), "aggregateVersion": 2}
    repository.replace(
        changed,
        expected_version=1,
        fact={"factId": "fact:two"},
    )
    with pytest.raises(AgentDefinitionConflict, match="STALE_AGENT_DEFINITION"):
        repository.replace(changed, expected_version=1, fact={"factId": "fact:x"})
