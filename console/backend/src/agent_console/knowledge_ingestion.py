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


def deterministic_vector(content: str, dimensions: int = 8) -> list[float]:
    """Local deterministic test/reference embedding; not a model claim."""
    raw = hashlib.sha256(content.encode()).digest()
    return [round((raw[index] / 255.0) * 2 - 1, 8) for index in range(dimensions)]
