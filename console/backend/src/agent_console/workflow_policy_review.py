"""D12 exact policy facts inside the original Workflow owner, never Human review."""

import copy

from .resource_policy_contract import DevelopmentAdministratorReview
from .workflow_definition_service import WorkflowDefinitionFailure, _id, _now


def _basis(proof, actor):
    if type(proof) is not DevelopmentAdministratorReview:
        raise WorkflowDefinitionFailure("WORKFLOW_POLICY_BASIS_UNSUPPORTED", 403)
    return proof.record(actor)


def review_policy(service, scope, identity, actor, expected, digest, proof):
    basis = _basis(proof, actor)
    record = service._load(scope, identity)
    service._expected(record, expected)
    draft = service._draft(record)
    if draft["state"] != "VALIDATED" or digest != draft["digest"]:
        raise WorkflowDefinitionFailure(
            "WORKFLOW_POLICY_VALIDATED_TARGET_REQUIRED", 409
        )
    service._validate_content(scope, draft["content"], resolve=True)
    review = {
        "schemaVersion": "workflow-policy-review.v1",
        "reviewId": _id("workflow-policy-review"),
        "revisionId": draft["revisionId"],
        "digest": digest,
        "actor": actor,
        "policyBasis": basis,
        "decision": "APPROVED",
        "reviewedAt": _now(),
    }
    record.setdefault("policyReviews", []).append(review)
    # Policy approval is a separate fact; do not relabel VALIDATED as Human review.
    return service._replace(record, expected, "POLICY_REVIEW_RECORDED", actor, review)


def publish_policy(service, scope, identity, actor, expected, digest, review_id, proof):
    basis = _basis(proof, actor)
    record = service._load(scope, identity)
    service._expected(record, expected)
    draft = service._draft(record)
    review = next(
        (r for r in record.get("policyReviews", []) if r["reviewId"] == review_id), None
    )
    if (
        not review
        or review["revisionId"] != draft["revisionId"]
        or review["digest"] != digest
        or review["policyBasis"] != basis
        or draft["digest"] != digest
        or draft["state"] != "VALIDATED"
    ):
        raise WorkflowDefinitionFailure("WORKFLOW_EXACT_POLICY_REVIEW_REQUIRED", 409)
    service._validate_content(scope, draft["content"], resolve=True)
    draft["state"] = "PUBLISHED"
    draft["publishedAt"] = _now()
    draft["publicationBasis"] = copy.deepcopy(review)
    record["publishedRevisionId"] = draft["revisionId"]
    record["currentDraftRevisionId"] = None
    record["lifecycleState"] = "PUBLISHED"
    return service._replace(record, expected, "POLICY_REVISION_PUBLISHED", actor, draft)
