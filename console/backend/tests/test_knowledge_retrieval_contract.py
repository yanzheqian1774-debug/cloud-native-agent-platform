"""Deterministic bounded retrieval contract tests."""

import pytest
from agent_console.knowledge_pack import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgePack,
    KnowledgeSection,
    KnowledgeStatus,
)
from agent_console.knowledge_retrieval import (
    MAX_FILTERS,
    MAX_QUERY_CHARS,
    MAX_REQUEST_BYTES,
    MAX_RESULTS,
    MAX_RETURNED_CONTENT_BYTES,
    InMemoryKnowledgeSource,
    KnowledgeFilter,
    KnowledgeRetrievalError,
    KnowledgeRetrievalRequest,
    retrieve,
    validate_request_size,
    validate_returned_content_size,
)
from test_knowledge_authorization_security import request_and_decision
from test_knowledge_pack_contract import NOW, make_pack


def test_deterministic_retrieval_and_stable_ties() -> None:
    pack, request, decision = request_and_decision()
    first = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    second = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    assert first == second
    assert tuple(item.reference_id for item in first.references) == tuple(
        sorted(item.reference_id for item in first.references)
    )


def test_pack_permutations_and_equal_scores_use_stable_identity_order() -> None:
    original = make_pack()
    document = original.documents[0]
    chunks = (
        KnowledgeChunk.create(
            chunk_id="chunk-b", ordinal=2, content="supplier containment"
        ),
        KnowledgeChunk.create(
            chunk_id="chunk-a", ordinal=1, content="supplier containment"
        ),
    )
    section = KnowledgeSection.create(
        section_id="section-containment",
        ordinal=1,
        title="Containment",
        chunks=chunks,
    )
    rebuilt_document = KnowledgeDocument.create(
        document_id=document.document_id,
        document_version=document.document_version,
        document_type=document.document_type,
        owner=document.owner,
        classification=document.classification,
        tenant_id=document.tenant_id,
        security_domain=document.security_domain,
        effective_at=document.effective_at,
        expires_at=document.expires_at,
        status=document.status,
        sections=(section,),
    )
    pack = KnowledgePack.create(
        knowledge_pack_id=original.knowledge_pack_id,
        knowledge_pack_version=original.knowledge_pack_version,
        tenant_id=original.tenant_id,
        security_domain=original.security_domain,
        owner=original.owner,
        classification=original.classification,
        provenance=original.provenance,
        documents=(rebuilt_document,),
    )
    _, request, decision = request_and_decision(pack, query="supplier containment")
    result = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    assert [item.chunk_id for item in result.references] == ["chunk-a", "chunk-b"]


def test_filter_permutations_have_one_request_digest() -> None:
    _, request, _ = request_and_decision()
    values = {
        name: getattr(request, name)
        for name in (
            "request_id",
            "canonical_workflow_revision_id",
            "approved_workflow_digest",
            "task_requirement_id",
            "knowledge_binding_id",
            "tenant_id",
            "security_domain",
            "purpose",
            "authorization_decision_id",
            "knowledge_pack_id",
            "knowledge_pack_version",
            "knowledge_pack_digest",
            "document_id",
            "document_version",
            "document_digest",
            "retrieval_policy_version",
            "max_results",
            "required",
        )
    }
    filters = (
        KnowledgeFilter.create(key="classification", value="internal-demo"),
        KnowledgeFilter.create(key="document_type", value="procedure"),
    )
    one = KnowledgeRetrievalRequest.create(
        **values, query=request.normalized_query, filters=filters
    )
    two = KnowledgeRetrievalRequest.create(
        **values, query=request.normalized_query, filters=tuple(reversed(filters))
    )
    assert one == two


def test_exact_query_filter_and_result_boundaries() -> None:
    _, request, _ = request_and_decision()
    base = {
        name: getattr(request, name)
        for name in (
            "request_id",
            "canonical_workflow_revision_id",
            "approved_workflow_digest",
            "task_requirement_id",
            "knowledge_binding_id",
            "tenant_id",
            "security_domain",
            "purpose",
            "authorization_decision_id",
            "knowledge_pack_id",
            "knowledge_pack_version",
            "knowledge_pack_digest",
            "document_id",
            "document_version",
            "document_digest",
            "retrieval_policy_version",
            "required",
        )
    }
    assert (
        KnowledgeRetrievalRequest.create(
            **base, query="x" * MAX_QUERY_CHARS, filters=(), max_results=MAX_RESULTS
        ).max_results
        == 16
    )
    with pytest.raises(KnowledgeRetrievalError, match="TEXT_LIMIT_EXCEEDED"):
        KnowledgeRetrievalRequest.create(
            **base, query="x" * (MAX_QUERY_CHARS + 1), filters=(), max_results=1
        )
    with pytest.raises(KnowledgeRetrievalError, match="RESULT_LIMIT_EXCEEDED"):
        KnowledgeRetrievalRequest.create(
            **base, query="x", filters=(), max_results=MAX_RESULTS + 1
        )
    filters = tuple(
        KnowledgeFilter("status", "AVAILABLE") for _ in range(MAX_FILTERS + 1)
    )
    with pytest.raises(KnowledgeRetrievalError, match="FILTER_LIMIT_EXCEEDED"):
        KnowledgeRetrievalRequest.create(
            **base, query="x", filters=filters, max_results=1
        )
    validate_request_size(MAX_REQUEST_BYTES)
    with pytest.raises(KnowledgeRetrievalError, match="REQUEST_LIMIT_EXCEEDED"):
        validate_request_size(MAX_REQUEST_BYTES + 1)
    validate_returned_content_size(MAX_RETURNED_CONTENT_BYTES)
    with pytest.raises(
        KnowledgeRetrievalError, match="RETURNED_CONTENT_LIMIT_EXCEEDED"
    ):
        validate_returned_content_size(MAX_RETURNED_CONTENT_BYTES + 1)


@pytest.mark.parametrize(
    "status",
    [
        KnowledgeStatus.STALE,
        KnowledgeStatus.EXPIRED,
        KnowledgeStatus.UNAVAILABLE,
        KnowledgeStatus.UNKNOWN,
    ],
)
def test_document_status_vocabulary(status: KnowledgeStatus) -> None:
    pack = make_pack(status=status)
    _, request, decision = request_and_decision(pack)
    result = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    assert result.status is status


def test_not_found_and_error_are_distinct_and_required_failure_is_not_success() -> None:
    pack = make_pack()
    _, request, decision = request_and_decision(pack, query="no-overlap")
    not_found = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    assert not_found.status is KnowledgeStatus.NOT_FOUND
    assert not not_found.successful and not_found.references == ()

    class BrokenSource(InMemoryKnowledgeSource):
        def read_authorized(self, request):
            self.read_count += 1
            raise KnowledgeRetrievalError("BOUNDED_SOURCE_ERROR")

    error = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=BrokenSource(pack),
    )
    assert error.status is KnowledgeStatus.ERROR
    assert not error.successful and error.references == ()
