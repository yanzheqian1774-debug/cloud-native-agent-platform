import pytest
from agent_console.agent_binding_validation import BindingResolution
from agent_console.agent_definition_repository import (
    DefinitionScope,
    InMemoryAgentDefinitionRepository,
)
from agent_console.agent_definition_service import (
    AgentDefinitionFailure,
    AgentDefinitionService,
)

CONTENT = {
    "title": "Supplier Quality Analyst",
    "duties": ["analyze supplier quality"],
    "capabilities": ["supplier-quality-analysis"],
}


def create_service():
    repository = InMemoryAgentDefinitionRepository()
    return AgentDefinitionService(repository), DefinitionScope("tenant-a", "quality")


def test_exact_digest_lifecycle_and_successor_protect_published_revision() -> None:
    service, scope = create_service()
    created = service.create(scope, "human:owner", "Quality Agent", CONTENT)
    definition_id = created["definitionId"]
    validated = service.validate(scope, definition_id, "human:owner", 1)
    draft = validated["definition"]["revisions"][-1]
    reviewed = service.review(
        scope,
        definition_id,
        "human:reviewer",
        2,
        draft["digest"],
        "APPROVE",
        "verified",
    )
    review = reviewed["definition"]["reviews"][-1]
    published = service.publish(
        scope,
        definition_id,
        "human:publisher",
        3,
        draft["digest"],
        review["reviewId"],
    )
    assert published["definition"]["publishedRevisionId"] == draft["revisionId"]
    assert service.eligible(scope)[0]["revision"]["digest"] == draft["digest"]
    successor = service.successor(scope, definition_id, "human:owner", 4)
    assert successor["definition"]["revisions"][0]["state"] == "PUBLISHED"
    assert (
        successor["definition"]["revisions"][-1]["predecessorRevisionId"]
        == draft["revisionId"]
    )
    assert service.eligible(scope)[0]["revision"]["revisionId"] == draft["revisionId"]
    assert service.impact(scope, definition_id)["publishedHistoryProtected"] is True
    with pytest.raises(AgentDefinitionFailure, match="PROTECTED_OR_REFERENCED"):
        service.delete_draft(scope, definition_id, "human:owner", 5)


def test_stale_review_and_published_deletion_fail_closed() -> None:
    service, scope = create_service()
    created = service.create(scope, "human:owner", "Quality Agent", CONTENT)
    definition_id = created["definitionId"]
    service.validate(scope, definition_id, "human:owner", 1)
    with pytest.raises(AgentDefinitionFailure, match="EXACT_DIGEST_REQUIRED"):
        service.review(scope, definition_id, "human", 2, "wrong", "APPROVE", "x")


def test_disabled_and_deprecated_revisions_are_not_eligible() -> None:
    service, scope = create_service()
    created = service.create(scope, "human", "Quality Agent", CONTENT)
    definition_id = created["definitionId"]
    validated = service.validate(scope, definition_id, "human", 1)["definition"]
    digest = validated["revisions"][-1]["digest"]
    reviewed = service.review(
        scope, definition_id, "human", 2, digest, "APPROVE", "ok"
    )["definition"]
    published = service.publish(
        scope, definition_id, "human", 3, digest, reviewed["reviews"][-1]["reviewId"]
    )["definition"]
    service.lifecycle(
        scope,
        definition_id,
        "human",
        published["aggregateVersion"],
        "DISABLE",
        "maintenance",
    )
    assert service.eligible(scope) == []


class ExactResolver:
    def resolve(self, scope, kind, resource_id):
        return BindingResolution(resource_id, "skill-revision:1", "a" * 64, True, True)


def test_exact_binding_is_digest_bound_and_rematches_only_after_publication() -> None:
    service = AgentDefinitionService(
        InMemoryAgentDefinitionRepository(), ExactResolver()
    )
    scope = DefinitionScope("tenant-a", "quality")
    content = {
        **CONTENT,
        "bindings": {
            "skills": [
                {
                    "resourceId": "skill:1",
                    "revisionId": "skill-revision:1",
                    "digest": "a" * 64,
                }
            ]
        },
    }
    created = service.create(scope, "human", "Bound Agent", content)
    assert (
        service.rematch(scope, ["supplier-quality-analysis"])["outcome"]
        == "CAPABILITY_GAP"
    )
    validated = service.validate(scope, created["definitionId"], "human", 1)[
        "definition"
    ]
    revision = validated["revisions"][-1]
    reviewed = service.review(
        scope,
        created["definitionId"],
        "human",
        2,
        revision["digest"],
        "APPROVE",
        "exact",
    )["definition"]
    service.publish(
        scope,
        created["definitionId"],
        "human",
        3,
        revision["digest"],
        reviewed["reviews"][-1]["reviewId"],
    )
    result = service.rematch(scope, ["supplier-quality-analysis"])
    assert result["outcome"] == "GOVERNED_MATCH"
    assert result["digest"] == revision["digest"]
    assert result["executionAuthorityGranted"] is False
