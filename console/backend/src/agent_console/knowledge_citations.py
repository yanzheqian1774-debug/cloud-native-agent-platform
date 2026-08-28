"""Deterministic citations over exact authorized Knowledge Evidence."""

from __future__ import annotations

from dataclasses import dataclass

from agent_console.knowledge_evidence import KnowledgeRetrievalEvidence
from agent_console.knowledge_pack import KnowledgeStatus, canonical_digest


class KnowledgeCitationError(ValueError):
    """Citation binding or projection failure."""


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    citation_id: str
    reference_id: str
    knowledge_pack_id: str
    knowledge_pack_version: str
    knowledge_pack_digest: str
    document_version: str
    document_digest: str
    section_id: str
    chunk_id: str
    chunk_digest: str
    authorization_decision_id: str
    evidence_id: str
    provenance: str


def assemble_citations(
    evidence: KnowledgeRetrievalEvidence,
) -> tuple[KnowledgeCitation, ...]:
    if not isinstance(evidence, KnowledgeRetrievalEvidence):
        raise KnowledgeCitationError("INVALID_KNOWLEDGE_EVIDENCE")
    if evidence.status not in {KnowledgeStatus.AVAILABLE, KnowledgeStatus.STALE}:
        if evidence.references:
            raise KnowledgeCitationError("FAILED_RETRIEVAL_HAS_REFERENCES")
        return ()
    citations = []
    for item in evidence.references:
        if item.authorization_decision_id != evidence.authorization_decision_id:
            raise KnowledgeCitationError("CITATION_AUTHORIZATION_MISMATCH")
        identity = canonical_digest(
            [
                item.reference_id,
                item.knowledge_pack_id,
                item.knowledge_pack_version,
                item.knowledge_pack_digest,
                item.document_version,
                item.document_digest,
                item.section_id,
                item.chunk_id,
                item.chunk_digest,
                item.authorization_decision_id,
                evidence.evidence_id,
                evidence.provenance,
            ],
            domain="knowledge-citation.v1",
        )
        citation_id = f"knowledge-citation:{identity}"
        citations.append(
            KnowledgeCitation(
                citation_id,
                item.reference_id,
                item.knowledge_pack_id,
                item.knowledge_pack_version,
                item.knowledge_pack_digest,
                item.document_version,
                item.document_digest,
                item.section_id,
                item.chunk_id,
                item.chunk_digest,
                item.authorization_decision_id,
                evidence.evidence_id,
                evidence.provenance,
            )
        )
    return tuple(citations)


def sibling_citation_projections(
    citations: tuple[KnowledgeCitation, ...],
) -> tuple[tuple[dict[str, str], ...], tuple[dict[str, str], ...]]:
    """Return independent copies with the same authority spine."""
    payload = tuple(
        {name: getattr(item, name) for name in item.__dataclass_fields__}
        for item in citations
    )
    return tuple(dict(item) for item in payload), tuple(dict(item) for item in payload)
