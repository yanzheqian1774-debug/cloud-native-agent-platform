"""Immutable append-only in-memory Evidence for bounded Knowledge retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agent_console.knowledge_pack import KnowledgeStatus, canonical_digest, identifier
from agent_console.knowledge_retrieval import (
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResult,
)

MAX_EVIDENCE_REFERENCES = 16
MAX_REASON_CODES = 32
MAX_EVIDENCE_BYTES = 32 * 1024
_PROHIBITED = re.compile(
    r"(?:api[_-]?key|bearer|credential|password|secret|token|"
    r"raw[_-]?(?:prompt|provider|request|response|body)|stack[_-]?trace|"
    r"/Users/|/home/|/private/|[A-Za-z]:\\)",
    re.IGNORECASE,
)


class KnowledgeEvidenceError(ValueError):
    """Stable Evidence validation or append failure."""


@dataclass(frozen=True, slots=True)
class KnowledgeEvidenceReference:
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


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalEvidence:
    evidence_id: str
    schema_version: str
    request_id: str
    request_digest: str
    result_id: str
    tenant_id: str
    security_domain: str
    retrieval_policy_version: str
    authorization_decision_id: str
    status: KnowledgeStatus
    source_read_count: int
    reason_codes: tuple[str, ...]
    references: tuple[KnowledgeEvidenceReference, ...]
    provenance: str
    evidence_digest: str

    @classmethod
    def from_result(
        cls,
        *,
        request: KnowledgeRetrievalRequest,
        result: KnowledgeRetrievalResult,
        provenance: object,
    ) -> KnowledgeRetrievalEvidence:
        if (
            request.request_id != result.request_id
            or request.request_digest != result.request_digest
        ):
            raise KnowledgeEvidenceError("EVIDENCE_SUBJECT_MISMATCH")
        if (
            request.tenant_id != result.tenant_id
            or request.security_domain != result.security_domain
        ):
            raise KnowledgeEvidenceError("EVIDENCE_SCOPE_MISMATCH")
        if (
            len(result.references) > MAX_EVIDENCE_REFERENCES
            or len(result.reason_codes) > MAX_REASON_CODES
        ):
            raise KnowledgeEvidenceError("EVIDENCE_LIMIT_EXCEEDED")
        refs = tuple(
            KnowledgeEvidenceReference(
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
            )
            for item in result.references
        )
        semantic = {
            "schemaVersion": "knowledge-retrieval-evidence.v1",
            "requestId": request.request_id,
            "requestDigest": request.request_digest,
            "resultId": result.result_id,
            "tenantId": request.tenant_id,
            "securityDomain": request.security_domain,
            "retrievalPolicyVersion": request.retrieval_policy_version,
            "authorizationDecisionId": request.authorization_decision_id,
            "status": result.status,
            "sourceReadCount": result.source_read_count,
            "reasonCodes": result.reason_codes,
            "references": refs,
            "provenance": identifier(provenance, "INVALID_EVIDENCE_PROVENANCE"),
        }
        encoded = str(semantic)
        if len(encoded.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            raise KnowledgeEvidenceError("EVIDENCE_LIMIT_EXCEEDED")
        if _PROHIBITED.search(encoded):
            raise KnowledgeEvidenceError("PROHIBITED_EVIDENCE_CONTENT")
        digest = canonical_digest(semantic, domain="knowledge-retrieval-evidence.v1")
        return cls(
            f"knowledge-evidence:{digest}",
            "knowledge-retrieval-evidence.v1",
            request.request_id,
            request.request_digest,
            result.result_id,
            request.tenant_id,
            request.security_domain,
            request.retrieval_policy_version,
            request.authorization_decision_id,
            result.status,
            result.source_read_count,
            result.reason_codes,
            refs,
            semantic["provenance"],
            digest,
        )


class InMemoryKnowledgeEvidenceRepository:
    """Append/replay only; intentionally exposes no mutation or delete operations."""

    def __init__(self) -> None:
        self._records: dict[str, KnowledgeRetrievalEvidence] = {}

    def append(self, record: KnowledgeRetrievalEvidence) -> KnowledgeRetrievalEvidence:
        if not isinstance(record, KnowledgeRetrievalEvidence):
            raise KnowledgeEvidenceError("INVALID_EVIDENCE_RECORD")
        existing = self._records.get(record.evidence_id)
        if existing is not None and existing != record:
            raise KnowledgeEvidenceError("EVIDENCE_REPLAY_CONFLICT")
        self._records[record.evidence_id] = record
        return record

    def records(
        self, *, tenant_id: str, security_domain: str
    ) -> tuple[KnowledgeRetrievalEvidence, ...]:
        tenant = identifier(tenant_id, "INVALID_TENANT")
        domain = identifier(security_domain, "INVALID_SECURITY_DOMAIN")
        return tuple(
            item
            for item in self._records.values()
            if item.tenant_id == tenant and item.security_domain == domain
        )


def reject_unknown_evidence_fields(payload: object) -> None:
    """Testable allowlist boundary for external mappings without constructing them."""
    if not isinstance(payload, dict) or set(payload) != set(
        KnowledgeRetrievalEvidence.__dataclass_fields__
    ):
        raise KnowledgeEvidenceError("UNKNOWN_OR_MISSING_EVIDENCE_FIELD")
    if _PROHIBITED.search(str(payload)):
        raise KnowledgeEvidenceError("PROHIBITED_EVIDENCE_CONTENT")
