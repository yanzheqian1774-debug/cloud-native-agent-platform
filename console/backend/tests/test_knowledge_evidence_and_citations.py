"""Knowledge Evidence and exact citation binding tests."""

from dataclasses import FrozenInstanceError, replace

import pytest
from agent_console.knowledge_citations import (
    KnowledgeCitationError,
    assemble_citations,
    sibling_citation_projections,
)
from agent_console.knowledge_evidence import (
    InMemoryKnowledgeEvidenceRepository,
    KnowledgeEvidenceError,
    KnowledgeRetrievalEvidence,
    reject_unknown_evidence_fields,
)
from agent_console.knowledge_retrieval import InMemoryKnowledgeSource, retrieve
from test_knowledge_authorization_security import request_and_decision
from test_knowledge_pack_contract import NOW


def evidence():
    pack, request, decision = request_and_decision()
    result = retrieve(
        request=request,
        authorization=decision,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    return (
        request,
        result,
        KnowledgeRetrievalEvidence.from_result(
            request=request, result=result, provenance="LIVE_EXECUTION"
        ),
    )


def test_evidence_is_immutable_idempotent_and_conflicts_fail_closed() -> None:
    _, _, record = evidence()
    repository = InMemoryKnowledgeEvidenceRepository()
    assert repository.append(record) is repository.append(record)
    with pytest.raises(FrozenInstanceError):
        record.status = "ERROR"  # type: ignore[misc]
    with pytest.raises(KnowledgeEvidenceError, match="EVIDENCE_REPLAY_CONFLICT"):
        repository.append(replace(record, reason_codes=("CHANGED",)))


def test_evidence_scope_and_allowlist_are_fail_closed() -> None:
    request, result, _ = evidence()
    with pytest.raises(KnowledgeEvidenceError, match="EVIDENCE_SCOPE_MISMATCH"):
        KnowledgeRetrievalEvidence.from_result(
            request=request,
            result=replace(result, tenant_id="tenant-b"),
            provenance="LIVE_EXECUTION",
        )
    with pytest.raises(
        KnowledgeEvidenceError, match="UNKNOWN_OR_MISSING_EVIDENCE_FIELD"
    ):
        reject_unknown_evidence_fields({"raw_prompt": "ignore authority"})
    payload = {name: "safe" for name in KnowledgeRetrievalEvidence.__dataclass_fields__}
    payload["provenance"] = "secret-token"
    with pytest.raises(KnowledgeEvidenceError, match="PROHIBITED_EVIDENCE_CONTENT"):
        reject_unknown_evidence_fields(payload)


def test_citations_bind_exact_reference_decision_evidence_and_provenance() -> None:
    _, _, record = evidence()
    citations = assemble_citations(record)
    assert len(citations) == len(record.references) == 1
    citation = citations[0]
    reference = record.references[0]
    assert citation.knowledge_pack_id == reference.knowledge_pack_id
    assert citation.knowledge_pack_version == reference.knowledge_pack_version
    assert citation.knowledge_pack_digest == reference.knowledge_pack_digest
    assert citation.document_version == reference.document_version
    assert citation.document_digest == reference.document_digest
    assert citation.section_id == reference.section_id
    assert citation.chunk_id == reference.chunk_id
    assert citation.chunk_digest == reference.chunk_digest
    assert citation.authorization_decision_id == record.authorization_decision_id
    assert citation.evidence_id == record.evidence_id
    assert citation.provenance == "LIVE_EXECUTION"
    product, technical = sibling_citation_projections(citations)
    assert product == technical and product is not technical


def test_citation_authorization_substitution_rejects() -> None:
    _, _, record = evidence()
    forged_ref = replace(record.references[0], authorization_decision_id="foreign")
    with pytest.raises(KnowledgeCitationError, match="CITATION_AUTHORIZATION_MISMATCH"):
        assemble_citations(replace(record, references=(forged_ref,)))


def test_evidence_reference_and_reason_ceilings_reject_overflow() -> None:
    request, result, _ = evidence()
    with pytest.raises(KnowledgeEvidenceError, match="EVIDENCE_LIMIT_EXCEEDED"):
        KnowledgeRetrievalEvidence.from_result(
            request=request,
            result=replace(result, references=result.references * 17),
            provenance="LIVE_EXECUTION",
        )
    exact = replace(
        result, references=(), reason_codes=tuple(f"R{i}" for i in range(32))
    )
    KnowledgeRetrievalEvidence.from_result(
        request=request, result=exact, provenance="LIVE_EXECUTION"
    )
    with pytest.raises(KnowledgeEvidenceError, match="EVIDENCE_LIMIT_EXCEEDED"):
        KnowledgeRetrievalEvidence.from_result(
            request=request,
            result=replace(exact, reason_codes=tuple(f"R{i}" for i in range(33))),
            provenance="LIVE_EXECUTION",
        )
