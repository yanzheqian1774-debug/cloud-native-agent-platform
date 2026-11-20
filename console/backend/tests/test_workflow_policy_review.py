"""Policy facts remain separate from the unchanged Human Workflow lifecycle."""

from dataclasses import replace

import pytest
from agent_console.resource_policy_contract import DevelopmentAdministratorReview
from agent_console.workbench_workflow_policy import (
    PolicyPublicationCommand,
    policy_publication_operations,
)
from agent_console.workflow_definition_repository import (
    InMemoryWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import (
    WorkflowDefinitionFailure,
    WorkflowDefinitionService,
)
from pydantic import ValidationError
from test_workflow_definition_service import content


def test_policy_review_and_publication_preserve_digest_and_human_path():
    service = WorkflowDefinitionService(
        InMemoryWorkflowDefinitionRepository(), lambda *_: True
    )
    scope = service.scope("s5-323-demo", "isolated-real-demo")
    actor = "human:development-admin"
    value = service.create(scope, actor, "policy", content())
    identity = value["workflowDefinitionId"]
    value = service.validate(scope, identity, actor, 1)
    revision = value["revisions"][-1]
    proof = DevelopmentAdministratorReview(actor, 1, "c" * 64)
    value = service.review_policy(scope, identity, actor, 2, revision["digest"], proof)
    assert value["lifecycleState"] == "VALIDATED"
    assert value["reviews"] == []
    review = value["policyReviews"][-1]
    with pytest.raises(WorkflowDefinitionFailure, match="EXACT_REVIEW_REQUIRED"):
        service.publish(
            scope, identity, actor, 3, revision["digest"], review["reviewId"]
        )
    with pytest.raises(WorkflowDefinitionFailure, match="EXACT_POLICY_REVIEW_REQUIRED"):
        service.publish_policy(
            scope,
            identity,
            actor,
            3,
            revision["digest"],
            review["reviewId"],
            replace(proof, generation=2),
        )
    value = service.publish_policy(
        scope, identity, actor, 3, revision["digest"], review["reviewId"], proof
    )
    assert value["revisions"][-1]["digest"] == revision["digest"]
    assert value["revisions"][-1]["publicationBasis"] == review
    assert value["reviews"] == []
    assert value["lifecycleState"] == "PUBLISHED"
    assert not any(f["event"] == "HUMAN_REVIEWED" for f in value["facts"])
    old = value["revisions"][-1]
    value = service.successor(scope, identity, actor, 4)
    assert value["revisions"][0] == old
    value = service.validate(scope, identity, actor, 5)
    new = value["revisions"][-1]
    value = service.review(
        scope,
        identity,
        actor,
        6,
        new["digest"],
        "APPROVE",
        "actual fixture human review",
    )
    value = service.publish(
        scope, identity, actor, 7, new["digest"], value["reviews"][-1]["reviewId"]
    )
    assert "publicationBasis" not in value["revisions"][-1]


@pytest.mark.parametrize("field", ["proof", "policyBasis", "actor", "reviewId"])
def test_browser_cannot_supply_policy_proof(field):
    with pytest.raises(ValidationError):
        PolicyPublicationCommand.model_validate(
            dict(
                action="policy-publish",
                commandKey="one",
                workflowId="w",
                expectedVersion=2,
                digest="a" * 64,
                **{field: "forged"},
            )
        )


def test_policy_routes_default_off_without_dependency_reads():
    assert policy_publication_operations(None, None) == ()
