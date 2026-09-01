import pytest
from agent_console.product_evidence_service import ProductEvidenceService
from agent_console.resource_catalog_service import (
    ProductAssemblyFailure,
    ProductScope,
    ResourceCatalogService,
)

SCOPE = ProductScope("tenant-a", "supplier-quality")


def _catalog(kind="AGENT", *, model=False):
    identity_key = {
        "AGENT": "definitionId",
        "RUNTIME_PROFILE": "runtimeProfileId",
    }[kind]
    identity = "agent:quality" if kind == "AGENT" else "runtime:declared"
    revision = {
        "revisionId": "revision:1",
        "digest": "sha256:exact",
        "state": "PUBLISHED",
        "publishedAt": "2026-09-01T00:00:00Z",
        "content": {
            "bindings": {"model": {"resourceId": "model:unverified"} if model else None}
        },
    }
    record = {
        identity_key: identity,
        "name": "Quality resource",
        "lifecycleState": "PUBLISHED",
        "publishedRevisionId": revision["revisionId"],
        "currentDraftRevisionId": None,
        "revisions": [revision],
        "reviews": [
            {
                "reviewId": "review:1",
                "revisionId": revision["revisionId"],
                "digest": revision["digest"],
                "decision": "APPROVED",
                "actor": "human-reviewer",
                "reviewedAt": "2026-09-01T00:00:00Z",
            }
        ],
        "relationships": [],
        "limitations": [],
    }
    return ResourceCatalogService({kind: lambda _scope: [record]})


def test_claim_evidence_fact_mapping_is_bidirectional_and_exact():
    result = ProductEvidenceService(_catalog(model=True)).get(
        SCOPE, "AGENT", "agent:quality", "revision:1", "sha256:exact"
    )
    assert result.subject.model_dump() == {
        "kind": "AGENT",
        "resourceId": "agent:quality",
        "revisionId": "revision:1",
        "digest": "sha256:exact",
    }
    governed = next(x for x in result.claims if x.claimKey == "resource.lifecycle")
    assert governed.status == "SUPPORTED"
    assert governed.evidenceRefs == ["review:1"]
    assert governed.technicalFactKeys == ["resource.lifecycle"]
    lifecycle = next(
        x for x in result.technicalFacts if x.factKey == "resource.lifecycle"
    )
    assert lifecycle.affectedClaimKeys == ["resource.lifecycle"]
    review = next(x for x in result.evidence if x.evidenceId == "review:1")
    assert review.subject == result.subject
    model_claim = next(x for x in result.claims if x.claimKey == "model.verified")
    assert model_claim.status == "UNSUPPORTED"
    assert model_claim.limitationCodes == ["UNVERIFIED_MODEL_REFERENCE"]


def test_runtime_execution_remains_declaration_only():
    result = ProductEvidenceService(_catalog("RUNTIME_PROFILE")).get(
        SCOPE, "RUNTIME_PROFILE", "runtime:declared", "revision:1", "sha256:exact"
    )
    claim = next(x for x in result.claims if x.claimKey == "runtime.execution")
    assert claim.status == "UNSUPPORTED"
    assert claim.limitationCodes == ["DECLARATION_ONLY", "NO_EXECUTION_AUTHORITY"]


@pytest.mark.parametrize(
    ("resource_id", "revision_id", "digest"),
    [
        ("agent:absent", "revision:1", "sha256:exact"),
        ("agent:quality", "revision:latest", "sha256:exact"),
        ("agent:quality", "revision:1", "sha256:wrong"),
    ],
)
def test_absent_and_invalid_exact_context_are_indistinguishable(
    resource_id, revision_id, digest
):
    with pytest.raises(ProductAssemblyFailure) as failure:
        ProductEvidenceService(_catalog()).get(
            SCOPE, "AGENT", resource_id, revision_id, digest
        )
    assert failure.value.status == 404
    assert failure.value.reason == "PRODUCT_CONTEXT_NOT_FOUND"
