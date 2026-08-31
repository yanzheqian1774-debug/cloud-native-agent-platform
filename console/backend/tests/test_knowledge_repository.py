import pytest
from agent_console.knowledge_repository import (
    InMemoryKnowledgeRepository,
    KnowledgeConflict,
    KnowledgeScope,
)


def record():
    return {
        "namespace": "tenant-a",
        "securityDomain": "quality",
        "knowledgeId": "knowledge:one",
        "aggregateVersion": 1,
        "facts": [{"factId": "fact:one"}],
    }


def test_repository_scope_and_compare_and_set():
    store = InMemoryKnowledgeRepository()
    store.create(record())
    assert store.list(KnowledgeScope("tenant-a", "quality"))
    assert store.list(KnowledgeScope("tenant-b", "quality")) == []
    store.replace(
        {**record(), "aggregateVersion": 2},
        expected_version=1,
        fact={"factId": "fact:two"},
    )
    with pytest.raises(KnowledgeConflict):
        store.replace(
            {**record(), "aggregateVersion": 2},
            expected_version=1,
            fact={"factId": "fact:x"},
        )
