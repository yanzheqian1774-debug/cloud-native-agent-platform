"""Deterministic bounded Knowledge ingestion helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from agent_console.knowledge_pack import canonical_digest

MAX_SOURCE_BYTES = 512 * 1024
MAX_CHUNK_BYTES = 4 * 1024


def ingest_text(document_id: str, text: str) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(text, str):
        raise ValueError("INVALID_SOURCE_CONTENT")
    content = (
        unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    )
    if not content.strip():
        raise ValueError("EMPTY_SOURCE_CONTENT")
    if len(content.encode()) > MAX_SOURCE_BYTES:
        raise ValueError("SOURCE_LIMIT_EXCEEDED")
    if any(
        unicodedata.category(char) == "Cc" and char not in "\n\t" for char in content
    ):
        raise ValueError("INVALID_CONTROL_CHARACTER")
    paragraphs = [
        item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()
    ]
    chunks: list[dict[str, Any]] = []
    for ordinal, paragraph in enumerate(paragraphs, 1):
        if len(paragraph.encode()) > MAX_CHUNK_BYTES:
            raise ValueError("CHUNK_LIMIT_EXCEEDED")
        digest = canonical_digest(
            {"documentId": document_id, "ordinal": ordinal, "content": paragraph},
            domain="knowledge-operation-chunk.v1",
        )
        chunks.append(
            {
                "chunkId": f"{document_id}:chunk:{ordinal}",
                "ordinal": ordinal,
                "content": paragraph,
                "contentDigest": digest,
            }
        )
    return chunks, hashlib.sha256(content.encode()).hexdigest()


def ingest_parsed_segments(
    document_id: str,
    text: str,
    segments: object,
    expected_content_digest: object,
) -> tuple[list[dict[str, Any]], str]:
    """Validate parser output and retain only truthful, bounded locations."""

    if not isinstance(segments, list) or not segments:
        raise ValueError("INVALID_PARSED_SEGMENTS")
    normalized_text = (
        unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    )
    content_digest = hashlib.sha256(normalized_text.encode()).hexdigest()
    if expected_content_digest != content_digest:
        raise ValueError("PARSED_CONTENT_DIGEST_MISMATCH")
    chunks: list[dict[str, Any]] = []
    normalized_segments: list[str] = []
    for ordinal, segment in enumerate(segments, 1):
        if not isinstance(segment, dict) or set(segment) != {"content", "location"}:
            raise ValueError("INVALID_PARSED_SEGMENTS")
        paragraph = segment.get("content")
        location = segment.get("location")
        if not isinstance(paragraph, str) or not isinstance(location, dict):
            raise ValueError("INVALID_PARSED_SEGMENTS")
        paragraph = unicodedata.normalize("NFC", paragraph).strip()
        if not paragraph or len(paragraph.encode()) > MAX_CHUNK_BYTES:
            raise ValueError("CHUNK_LIMIT_EXCEEDED")
        if set(location) - {"pageNumber", "paragraphNumber"} or not location:
            raise ValueError("INVALID_PARSED_LOCATION")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in location.values()
        ):
            raise ValueError("INVALID_PARSED_LOCATION")
        digest = canonical_digest(
            {"documentId": document_id, "ordinal": ordinal, "content": paragraph},
            domain="knowledge-operation-chunk.v1",
        )
        chunks.append(
            {
                "chunkId": f"{document_id}:chunk:{ordinal}",
                "ordinal": ordinal,
                "content": paragraph,
                "contentDigest": digest,
                "location": dict(location),
            }
        )
        normalized_segments.append(paragraph)
    if "\n\n".join(normalized_segments) != normalized_text:
        raise ValueError("PARSED_CONTENT_MISMATCH")
    return chunks, content_digest


def deterministic_vector(content: str, dimensions: int = 8) -> list[float]:
    """Local deterministic test/reference embedding; not a model claim."""
    raw = hashlib.sha256(content.encode()).digest()
    return [round((raw[index] / 255.0) * 2 - 1, 8) for index in range(dimensions)]
