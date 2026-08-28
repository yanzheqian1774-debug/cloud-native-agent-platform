"""Deterministic, in-memory, authorization-first Knowledge retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from agent_console.knowledge_authorization import (
    AuthorizationExpectation,
    KnowledgeAuthorizationError,
    require_current_allow,
)
from agent_console.knowledge_pack import (
    KnowledgeDocument,
    KnowledgePack,
    KnowledgePackError,
    KnowledgeStatus,
    canonical_digest,
    canonical_json,
    identifier,
    normalize_text,
    utc,
)

MAX_REQUEST_BYTES = 16 * 1024
MAX_QUERY_CHARS = 2_000
MAX_FILTERS = 16
MAX_RESULTS = 16
MAX_RETURNED_CONTENT_BYTES = 32 * 1024
MAX_REASON_CODES = 32
RETRIEVAL_POLICY_VERSION = "bounded-retrieval.v1"
_FILTER_KEYS = frozenset({"document_type", "classification", "status"})
_TOKEN = re.compile(r"[\w-]+", re.UNICODE)


class KnowledgeRetrievalError(ValueError):
    """Stable bounded retrieval failure."""


def validate_request_size(size: int) -> None:
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or not 0 <= size <= MAX_REQUEST_BYTES
    ):
        raise KnowledgeRetrievalError("REQUEST_LIMIT_EXCEEDED")


def validate_returned_content_size(size: int) -> None:
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or not 0 <= size <= MAX_RETURNED_CONTENT_BYTES
    ):
        raise KnowledgeRetrievalError("RETURNED_CONTENT_LIMIT_EXCEEDED")


@dataclass(frozen=True, slots=True)
class KnowledgeFilter:
    key: str
    value: str

    @classmethod
    def create(cls, *, key: object, value: object) -> KnowledgeFilter:
        normalized_key = identifier(key, "INVALID_FILTER")
        if normalized_key not in _FILTER_KEYS:
            raise KnowledgeRetrievalError("FILTER_NOT_ALLOWED")
        return cls(normalized_key, normalize_text(value, "INVALID_FILTER", limit=200))


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalRequest:
    request_id: str
    canonical_workflow_revision_id: str
    approved_workflow_digest: str
    task_requirement_id: str
    knowledge_binding_id: str
    tenant_id: str
    security_domain: str
    purpose: str
    authorization_decision_id: str
    knowledge_pack_id: str
    knowledge_pack_version: str
    knowledge_pack_digest: str
    document_id: str
    document_version: str
    document_digest: str
    retrieval_policy_version: str
    normalized_query: str
    query_digest: str
    filters: tuple[KnowledgeFilter, ...]
    max_results: int
    required: bool
    request_digest: str

    @classmethod
    def create(cls, **values: object) -> KnowledgeRetrievalRequest:
        filters = values.get("filters", ())
        if not isinstance(filters, (tuple, list)) or len(filters) > MAX_FILTERS:
            raise KnowledgeRetrievalError("FILTER_LIMIT_EXCEEDED")
        filter_items = tuple(filters)
        if not all(isinstance(item, KnowledgeFilter) for item in filter_items):
            raise KnowledgeRetrievalError("INVALID_FILTER")
        if len({item.key for item in filter_items}) != len(filter_items):
            raise KnowledgeRetrievalError("AMBIGUOUS_FILTER")
        ordered_filters = tuple(
            sorted(filter_items, key=lambda item: (item.key, item.value))
        )
        try:
            query = " ".join(
                normalize_text(
                    values.get("query"), "INVALID_QUERY", limit=MAX_QUERY_CHARS
                ).split()
            )
        except KnowledgePackError as exc:
            raise KnowledgeRetrievalError(str(exc)) from exc
        ceiling = values.get("max_results")
        if (
            not isinstance(ceiling, int)
            or isinstance(ceiling, bool)
            or not 1 <= ceiling <= MAX_RESULTS
        ):
            raise KnowledgeRetrievalError("RESULT_LIMIT_EXCEEDED")
        required = values.get("required")
        if not isinstance(required, bool):
            raise KnowledgeRetrievalError("INVALID_REQUIRED_FLAG")
        names = (
            "request_id",
            "canonical_workflow_revision_id",
            "task_requirement_id",
            "knowledge_binding_id",
            "tenant_id",
            "security_domain",
            "purpose",
            "authorization_decision_id",
            "knowledge_pack_id",
            "knowledge_pack_version",
            "document_id",
            "document_version",
            "retrieval_policy_version",
        )
        normalized = {
            name: identifier(values.get(name), f"INVALID_{name.upper()}")
            for name in names
        }
        for name in (
            "approved_workflow_digest",
            "knowledge_pack_digest",
            "document_digest",
        ):
            value = values.get(name)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise KnowledgeRetrievalError(f"INVALID_{name.upper()}")
            normalized[name] = value
        if normalized["retrieval_policy_version"] != RETRIEVAL_POLICY_VERSION:
            raise KnowledgeRetrievalError("UNSUPPORTED_RETRIEVAL_POLICY")
        query_digest = canonical_digest(query, domain="knowledge-query.v1")
        semantic = {
            **normalized,
            "queryDigest": query_digest,
            "filters": ordered_filters,
            "maxResults": ceiling,
            "required": required,
        }
        validate_request_size(len(canonical_json(semantic).encode("utf-8")))
        return cls(
            **normalized,
            normalized_query=query,
            query_digest=query_digest,
            filters=ordered_filters,
            max_results=ceiling,
            required=required,
            request_digest=canonical_digest(
                semantic, domain="knowledge-retrieval-request.v1"
            ),
        )


@dataclass(frozen=True, slots=True)
class AuthorizedKnowledgeReference:
    reference_id: str
    knowledge_pack_id: str
    knowledge_pack_version: str
    knowledge_pack_digest: str
    document_id: str
    document_version: str
    document_digest: str
    section_id: str
    chunk_id: str
    chunk_digest: str
    authorization_decision_id: str
    score: int
    content: str


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalResult:
    result_id: str
    request_id: str
    request_digest: str
    tenant_id: str
    security_domain: str
    status: KnowledgeStatus
    reason_codes: tuple[str, ...]
    references: tuple[AuthorizedKnowledgeReference, ...]
    source_read_count: int
    required: bool

    @property
    def successful(self) -> bool:
        return self.status in {
            KnowledgeStatus.AVAILABLE,
            KnowledgeStatus.STALE,
        } and bool(self.references)


class KnowledgeSource(Protocol):
    read_count: int

    def read_authorized(self, request: KnowledgeRetrievalRequest) -> KnowledgePack: ...


class InMemoryKnowledgeSource:
    """One-Pack source with an observable read count and no mutation methods."""

    def __init__(self, pack: KnowledgePack):
        if not isinstance(pack, KnowledgePack):
            raise KnowledgeRetrievalError("KNOWLEDGE_SOURCE_INVALID")
        self._pack = pack
        self.read_count = 0

    def read_authorized(self, request: KnowledgeRetrievalRequest) -> KnowledgePack:
        self.read_count += 1
        if (
            self._pack.knowledge_pack_id != request.knowledge_pack_id
            or self._pack.knowledge_pack_version != request.knowledge_pack_version
            or self._pack.canonical_digest != request.knowledge_pack_digest
        ):
            raise KnowledgeRetrievalError("KNOWLEDGE_NOT_FOUND")
        return self._pack


def _expectation(request: KnowledgeRetrievalRequest) -> AuthorizationExpectation:
    return AuthorizationExpectation(
        tenant_id=request.tenant_id,
        security_domain=request.security_domain,
        purpose=request.purpose,
        knowledge_pack_id=request.knowledge_pack_id,
        knowledge_pack_version=request.knowledge_pack_version,
        knowledge_pack_digest=request.knowledge_pack_digest,
        document_id=request.document_id,
        document_version=request.document_version,
        document_digest=request.document_digest,
        policy_version=request.retrieval_policy_version,
    )


def _validate_request(request: KnowledgeRetrievalRequest) -> None:
    if not isinstance(request, KnowledgeRetrievalRequest):
        raise KnowledgeAuthorizationError("KNOWLEDGE_ACCESS_DENIED")
    try:
        rebuilt = KnowledgeRetrievalRequest.create(
            request_id=request.request_id,
            canonical_workflow_revision_id=request.canonical_workflow_revision_id,
            approved_workflow_digest=request.approved_workflow_digest,
            task_requirement_id=request.task_requirement_id,
            knowledge_binding_id=request.knowledge_binding_id,
            tenant_id=request.tenant_id,
            security_domain=request.security_domain,
            purpose=request.purpose,
            authorization_decision_id=request.authorization_decision_id,
            knowledge_pack_id=request.knowledge_pack_id,
            knowledge_pack_version=request.knowledge_pack_version,
            knowledge_pack_digest=request.knowledge_pack_digest,
            document_id=request.document_id,
            document_version=request.document_version,
            document_digest=request.document_digest,
            retrieval_policy_version=request.retrieval_policy_version,
            query=request.normalized_query,
            filters=request.filters,
            max_results=request.max_results,
            required=request.required,
        )
    except KnowledgeRetrievalError as exc:
        raise KnowledgeAuthorizationError("KNOWLEDGE_ACCESS_DENIED") from exc
    if rebuilt != request:
        raise KnowledgeAuthorizationError("KNOWLEDGE_ACCESS_DENIED")


def _tokens(value: str) -> frozenset[str]:
    return frozenset(item.casefold() for item in _TOKEN.findall(value))


def _filter(document: KnowledgeDocument, filters: tuple[KnowledgeFilter, ...]) -> bool:
    values = {
        "document_type": document.document_type,
        "classification": document.classification,
        "status": document.status.value,
    }
    return all(values[item.key] == item.value for item in filters)


def retrieve(
    *,
    request: KnowledgeRetrievalRequest,
    authorization: object,
    evaluation_time: datetime,
    source: KnowledgeSource,
) -> KnowledgeRetrievalResult:
    """Authorize from request/decision fields before the first source operation."""
    try:
        _validate_request(request)
        decision = require_current_allow(
            authorization, _expectation(request), evaluation_time=evaluation_time
        )
        if decision.decision_id != request.authorization_decision_id:
            raise KnowledgeAuthorizationError("KNOWLEDGE_ACCESS_DENIED")
    except KnowledgeAuthorizationError:
        return KnowledgeRetrievalResult(
            "knowledge-result:denied",
            request.request_id,
            request.request_digest,
            request.tenant_id,
            request.security_domain,
            KnowledgeStatus.DENIED,
            ("KNOWLEDGE_ACCESS_DENIED",),
            (),
            0,
            request.required,
        )
    before = source.read_count
    try:
        pack = source.read_authorized(request)
        documents = [
            item
            for item in pack.documents
            if item.document_id == request.document_id
            and item.document_version == request.document_version
            and item.content_digest == request.document_digest
        ]
        if not documents:
            return _failure(
                request,
                KnowledgeStatus.NOT_FOUND,
                "KNOWLEDGE_NOT_FOUND",
                source.read_count - before,
            )
        document = documents[0]
        if (
            document.tenant_id != request.tenant_id
            or document.security_domain != request.security_domain
        ):
            return _failure(
                request,
                KnowledgeStatus.DENIED,
                "KNOWLEDGE_ACCESS_DENIED",
                source.read_count - before,
                disclose=False,
            )
        now = utc(evaluation_time, "INVALID_EVALUATION_TIME")
        if now >= document.expires_at or document.status is KnowledgeStatus.EXPIRED:
            return _failure(
                request,
                KnowledgeStatus.EXPIRED,
                "KNOWLEDGE_EXPIRED",
                source.read_count - before,
            )
        if document.status in {KnowledgeStatus.UNAVAILABLE, KnowledgeStatus.UNKNOWN}:
            return _failure(
                request,
                document.status,
                f"KNOWLEDGE_{document.status.value}",
                source.read_count - before,
            )
        if not _filter(document, request.filters):
            return _failure(
                request,
                KnowledgeStatus.NOT_FOUND,
                "KNOWLEDGE_NOT_FOUND",
                source.read_count - before,
            )
        query_tokens = _tokens(request.normalized_query)
        ranked = []
        for section in document.sections:
            for chunk in section.chunks:
                score = len(query_tokens & _tokens(chunk.content))
                if score:
                    ranked.append((score, document, section, chunk))
        ranked.sort(
            key=lambda row: (
                -row[0],
                row[1].document_id,
                row[1].document_version,
                row[2].section_id,
                row[3].chunk_id,
            )
        )
        selected = ranked[: request.max_results]
        if not selected:
            return _failure(
                request,
                KnowledgeStatus.NOT_FOUND,
                "KNOWLEDGE_NOT_FOUND",
                source.read_count - before,
            )
        total = sum(len(row[3].content.encode("utf-8")) for row in selected)
        validate_returned_content_size(total)
        references = tuple(
            AuthorizedKnowledgeReference(
                reference_id="knowledge-reference:"
                + canonical_digest(
                    [request.request_digest, row[2].section_id, row[3].chunk_id],
                    domain="knowledge-reference.v1",
                ),
                knowledge_pack_id=pack.knowledge_pack_id,
                knowledge_pack_version=pack.knowledge_pack_version,
                knowledge_pack_digest=pack.canonical_digest,
                document_id=row[1].document_id,
                document_version=row[1].document_version,
                document_digest=row[1].content_digest,
                section_id=row[2].section_id,
                chunk_id=row[3].chunk_id,
                chunk_digest=row[3].content_digest,
                authorization_decision_id=decision.decision_id,
                score=row[0],
                content=row[3].content,
            )
            for row in selected
        )
        status = (
            KnowledgeStatus.STALE
            if document.status is KnowledgeStatus.STALE
            else KnowledgeStatus.AVAILABLE
        )
        result_digest = canonical_digest(
            [
                request.request_digest,
                [item.reference_id for item in references],
                status,
            ],
            domain="knowledge-result.v1",
        )
        result_id = f"knowledge-result:{result_digest}"
        return KnowledgeRetrievalResult(
            result_id,
            request.request_id,
            request.request_digest,
            request.tenant_id,
            request.security_domain,
            status,
            (),
            references,
            source.read_count - before,
            request.required,
        )
    except KnowledgeRetrievalError as exc:
        return _failure(
            request, KnowledgeStatus.ERROR, str(exc), source.read_count - before
        )


def _failure(
    request: KnowledgeRetrievalRequest,
    status: KnowledgeStatus,
    reason: str,
    reads: int,
    *,
    disclose: bool = True,
) -> KnowledgeRetrievalResult:
    safe_reason = reason if disclose else "KNOWLEDGE_ACCESS_DENIED"
    result_id = f"knowledge-result:{status.value.lower()}"
    return KnowledgeRetrievalResult(
        result_id,
        request.request_id,
        request.request_digest,
        request.tenant_id,
        request.security_domain,
        status,
        (safe_reason,),
        (),
        reads,
        request.required,
    )
