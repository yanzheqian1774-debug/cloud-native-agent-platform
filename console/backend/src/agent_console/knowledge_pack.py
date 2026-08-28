"""Immutable, bounded Knowledge Pack contracts for the v0.2 demo slice."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

MAX_DOCUMENTS = 8
MAX_SECTIONS_PER_DOCUMENT = 32
MAX_CHUNKS_PER_DOCUMENT = 128
MAX_PACK_CHUNKS = 256
MAX_CHUNK_BYTES = 4 * 1024
MAX_PACK_CONTENT_BYTES = 512 * 1024
MAX_IDENTIFIER = 200
MAX_TEXT = 500
PACK_SCHEMA_VERSION = "knowledge-pack.v1"
DIGEST_ALGORITHM = "sha256-canonical-json-utf8-nfc-v1"

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class KnowledgePackError(ValueError):
    """Stable validation failure for a malformed or oversized Pack."""


class KnowledgeStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    DENIED = "DENIED"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


def _fail(code: str) -> KnowledgePackError:
    return KnowledgePackError(code)


def normalize_text(value: object, code: str, *, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = unicodedata.normalize("NFC", value)
    if not normalized or len(normalized.encode("utf-8")) > limit:
        raise _fail(code if not normalized else "TEXT_LIMIT_EXCEEDED")
    if any(unicodedata.category(char) == "Cc" for char in normalized):
        raise _fail("INVALID_CONTROL_CHARACTER")
    return normalized


def identifier(value: object, code: str) -> str:
    normalized = normalize_text(value, code, limit=MAX_IDENTIFIER)
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise _fail(code)
    return normalized


def utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _fail(code)
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise _fail(code)
    return value.astimezone(UTC)


def canonical_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return utc(value, "INVALID_UTC_TIMESTAMP").isoformat().replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return canonical_value(asdict(value))
    if isinstance(value, (tuple, list)):
        return [canonical_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")
        normalized = [
            (unicodedata.normalize("NFC", key), item) for key, item in value.items()
        ]
        if len({key for key, _ in normalized}) != len(normalized):
            raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")
        return {key: canonical_value(item) for key, item in sorted(normalized)}
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")


def canonical_json(value: object) -> str:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_digest(value: object, *, domain: str) -> str:
    return hashlib.sha256(f"{domain}\n{canonical_json(value)}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    chunk_id: str
    ordinal: int
    content: str
    content_digest: str

    @classmethod
    def create(
        cls, *, chunk_id: object, ordinal: object, content: object
    ) -> KnowledgeChunk:
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            raise _fail("INVALID_CHUNK_ORDINAL")
        normalized = normalize_text(
            content, "INVALID_CHUNK_CONTENT", limit=MAX_CHUNK_BYTES
        )
        identity = identifier(chunk_id, "INVALID_CHUNK_ID")
        digest = canonical_digest(
            {"chunkId": identity, "ordinal": ordinal, "content": normalized},
            domain="knowledge-chunk.v1",
        )
        return cls(identity, ordinal, normalized, digest)


@dataclass(frozen=True, slots=True)
class KnowledgeSection:
    section_id: str
    ordinal: int
    title: str
    chunks: tuple[KnowledgeChunk, ...]

    @classmethod
    def create(
        cls, *, section_id: object, ordinal: object, title: object, chunks: object
    ) -> KnowledgeSection:
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            raise _fail("INVALID_SECTION_ORDINAL")
        if not isinstance(chunks, (tuple, list)) or not chunks:
            raise _fail("INVALID_CHUNK_COLLECTION")
        if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
            raise _fail("CHUNK_LIMIT_EXCEEDED")
        items = tuple(chunks)
        if not all(isinstance(item, KnowledgeChunk) for item in items):
            raise _fail("INVALID_CHUNK_COLLECTION")
        if len({item.chunk_id for item in items}) != len(items) or len(
            {item.ordinal for item in items}
        ) != len(items):
            raise _fail("AMBIGUOUS_CHUNK_IDENTITY")
        return cls(
            identifier(section_id, "INVALID_SECTION_ID"),
            ordinal,
            normalize_text(title, "INVALID_SECTION_TITLE"),
            tuple(sorted(items, key=lambda item: (item.ordinal, item.chunk_id))),
        )


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    document_id: str
    document_version: str
    document_type: str
    owner: str
    classification: str
    tenant_id: str
    security_domain: str
    effective_at: datetime
    expires_at: datetime
    status: KnowledgeStatus
    sections: tuple[KnowledgeSection, ...]
    content_digest: str

    @classmethod
    def create(cls, **values: Any) -> KnowledgeDocument:
        sections = values.get("sections")
        if not isinstance(sections, (tuple, list)) or not sections:
            raise _fail("INVALID_SECTION_COLLECTION")
        items = tuple(sections)
        if len(items) > MAX_SECTIONS_PER_DOCUMENT:
            raise _fail("SECTION_LIMIT_EXCEEDED")
        if not all(isinstance(item, KnowledgeSection) for item in items):
            raise _fail("INVALID_SECTION_COLLECTION")
        if len({item.section_id for item in items}) != len(items) or len(
            {item.ordinal for item in items}
        ) != len(items):
            raise _fail("AMBIGUOUS_SECTION_IDENTITY")
        ordered = tuple(sorted(items, key=lambda item: (item.ordinal, item.section_id)))
        effective = utc(values.get("effective_at"), "INVALID_EFFECTIVE_AT")
        expires = utc(values.get("expires_at"), "INVALID_EXPIRES_AT")
        if expires <= effective:
            raise _fail("INVALID_EFFECTIVE_INTERVAL")
        status = values.get("status")
        if status not in {
            KnowledgeStatus.AVAILABLE,
            KnowledgeStatus.STALE,
            KnowledgeStatus.EXPIRED,
            KnowledgeStatus.UNAVAILABLE,
            KnowledgeStatus.UNKNOWN,
        }:
            raise _fail("INVALID_DOCUMENT_STATUS")
        semantic = {
            "documentId": identifier(values.get("document_id"), "INVALID_DOCUMENT_ID"),
            "documentVersion": identifier(
                values.get("document_version"), "INVALID_DOCUMENT_VERSION"
            ),
            "documentType": identifier(
                values.get("document_type"), "INVALID_DOCUMENT_TYPE"
            ),
            "owner": identifier(values.get("owner"), "INVALID_OWNER"),
            "classification": identifier(
                values.get("classification"), "INVALID_CLASSIFICATION"
            ),
            "tenantId": identifier(values.get("tenant_id"), "INVALID_TENANT"),
            "securityDomain": identifier(
                values.get("security_domain"), "INVALID_SECURITY_DOMAIN"
            ),
            "effectiveAt": effective,
            "expiresAt": expires,
            "status": status,
            "sections": ordered,
        }
        return cls(
            semantic["documentId"],
            semantic["documentVersion"],
            semantic["documentType"],
            semantic["owner"],
            semantic["classification"],
            semantic["tenantId"],
            semantic["securityDomain"],
            effective,
            expires,
            status,
            ordered,
            canonical_digest(semantic, domain="knowledge-document.v1"),
        )


@dataclass(frozen=True, slots=True)
class KnowledgePack:
    knowledge_pack_id: str
    knowledge_pack_version: str
    tenant_id: str
    security_domain: str
    owner: str
    classification: str
    provenance: str
    documents: tuple[KnowledgeDocument, ...]
    canonical_digest: str
    schema_version: str = PACK_SCHEMA_VERSION
    digest_algorithm: str = DIGEST_ALGORITHM

    @classmethod
    def create(cls, **values: Any) -> KnowledgePack:
        documents = values.get("documents")
        if not isinstance(documents, (tuple, list)) or not documents:
            raise _fail("INVALID_DOCUMENT_COLLECTION")
        items = tuple(documents)
        if len(items) > MAX_DOCUMENTS:
            raise _fail("DOCUMENT_LIMIT_EXCEEDED")
        if not all(isinstance(item, KnowledgeDocument) for item in items):
            raise _fail("INVALID_DOCUMENT_COLLECTION")
        if len({(item.document_id, item.document_version) for item in items}) != len(
            items
        ):
            raise _fail("AMBIGUOUS_DOCUMENT_IDENTITY")
        pack_tenant = identifier(values.get("tenant_id"), "INVALID_TENANT")
        pack_domain = identifier(
            values.get("security_domain"), "INVALID_SECURITY_DOMAIN"
        )
        if any(
            item.tenant_id != pack_tenant or item.security_domain != pack_domain
            for item in items
        ):
            raise _fail("DOCUMENT_SCOPE_MISMATCH")
        chunk_count = sum(
            len(section.chunks) for item in items for section in item.sections
        )
        if chunk_count > MAX_PACK_CHUNKS:
            raise _fail("PACK_CHUNK_LIMIT_EXCEEDED")
        content_bytes = sum(
            len(chunk.content.encode("utf-8"))
            for item in items
            for section in item.sections
            for chunk in section.chunks
        )
        if content_bytes > MAX_PACK_CONTENT_BYTES:
            raise _fail("PACK_CONTENT_LIMIT_EXCEEDED")
        ordered = tuple(
            sorted(items, key=lambda item: (item.document_id, item.document_version))
        )
        semantic = {
            "schemaVersion": PACK_SCHEMA_VERSION,
            "knowledgePackId": identifier(
                values.get("knowledge_pack_id"), "INVALID_PACK_ID"
            ),
            "knowledgePackVersion": identifier(
                values.get("knowledge_pack_version"), "INVALID_PACK_VERSION"
            ),
            "tenantId": pack_tenant,
            "securityDomain": pack_domain,
            "owner": identifier(values.get("owner"), "INVALID_OWNER"),
            "classification": identifier(
                values.get("classification"), "INVALID_CLASSIFICATION"
            ),
            "provenance": identifier(values.get("provenance"), "INVALID_PROVENANCE"),
            "documents": ordered,
        }
        return cls(
            semantic["knowledgePackId"],
            semantic["knowledgePackVersion"],
            pack_tenant,
            pack_domain,
            semantic["owner"],
            semantic["classification"],
            semantic["provenance"],
            ordered,
            canonical_digest(semantic, domain=PACK_SCHEMA_VERSION),
        )
