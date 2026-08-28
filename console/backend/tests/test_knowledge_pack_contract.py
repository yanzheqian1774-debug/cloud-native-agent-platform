"""Contract and exact-boundary tests for the immutable Knowledge Pack."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agent_console.knowledge_pack import (
    MAX_CHUNK_BYTES,
    MAX_CHUNKS_PER_DOCUMENT,
    MAX_DOCUMENTS,
    MAX_PACK_CHUNKS,
    MAX_PACK_CONTENT_BYTES,
    MAX_SECTIONS_PER_DOCUMENT,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgePack,
    KnowledgePackError,
    KnowledgeSection,
    KnowledgeStatus,
)

NOW = datetime(2026, 8, 29, 12, tzinfo=UTC)


def make_pack(
    *,
    status: KnowledgeStatus = KnowledgeStatus.AVAILABLE,
    content: str = "Containment root cause corrective action closure supplier quality",
    tenant_id: str = "tenant-a",
    security_domain: str = "supplier-quality",
) -> KnowledgePack:
    chunk = KnowledgeChunk.create(chunk_id="chunk-001", ordinal=1, content=content)
    section = KnowledgeSection.create(
        section_id="section-containment",
        ordinal=1,
        title="Containment",
        chunks=(chunk,),
    )
    document = KnowledgeDocument.create(
        document_id="document-8d-procedure",
        document_version="v1",
        document_type="procedure",
        owner="quality-office",
        classification="internal-demo",
        tenant_id=tenant_id,
        security_domain=security_domain,
        effective_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=365),
        status=status,
        sections=(section,),
    )
    return KnowledgePack.create(
        knowledge_pack_id="supplier-quality-pack",
        knowledge_pack_version="v1",
        tenant_id=tenant_id,
        security_domain=security_domain,
        owner="quality-office",
        classification="internal-demo",
        provenance="DEMO_CONFIGURATION",
        documents=(document,),
    )


def test_identity_digest_nfc_ordering_and_immutability() -> None:
    composed = make_pack(content="Café containment")
    decomposed = make_pack(content="Cafe\u0301 containment")
    assert composed == decomposed
    assert composed.canonical_digest == decomposed.canonical_digest
    assert (
        composed.documents[0].content_digest == decomposed.documents[0].content_digest
    )
    with pytest.raises(FrozenInstanceError):
        composed.knowledge_pack_version = "v2"  # type: ignore[misc]


def test_semantic_mutation_requires_new_digest_and_version() -> None:
    original = make_pack()
    changed = make_pack(content="Changed corrective action procedure")
    assert original.canonical_digest != changed.canonical_digest
    assert original.documents[0].content_digest != changed.documents[0].content_digest
    forged = replace(original.documents[0], sections=changed.documents[0].sections)
    assert forged.content_digest == original.documents[0].content_digest
    assert forged != KnowledgeDocument.create(
        document_id=forged.document_id,
        document_version="v2",
        document_type=forged.document_type,
        owner=forged.owner,
        classification=forged.classification,
        tenant_id=forged.tenant_id,
        security_domain=forged.security_domain,
        effective_at=forged.effective_at,
        expires_at=forged.expires_at,
        status=forged.status,
        sections=forged.sections,
    )


def _section(index: int, *, chunks: int = 1, content: str = "x") -> KnowledgeSection:
    return KnowledgeSection.create(
        section_id=f"section-{index:03d}",
        ordinal=index + 1,
        title=f"Section {index}",
        chunks=tuple(
            KnowledgeChunk.create(
                chunk_id=f"chunk-{index:03d}-{item:03d}",
                ordinal=item + 1,
                content=content,
            )
            for item in range(chunks)
        ),
    )


def _document(index: int, sections: tuple[KnowledgeSection, ...]) -> KnowledgeDocument:
    return KnowledgeDocument.create(
        document_id=f"document-{index:03d}",
        document_version="v1",
        document_type="procedure",
        owner="quality-office",
        classification="internal-demo",
        tenant_id="tenant-a",
        security_domain="supplier-quality",
        effective_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=1),
        status=KnowledgeStatus.AVAILABLE,
        sections=sections,
    )


def _pack(documents: tuple[KnowledgeDocument, ...]) -> KnowledgePack:
    return KnowledgePack.create(
        knowledge_pack_id="bounded-pack",
        knowledge_pack_version="v1",
        tenant_id="tenant-a",
        security_domain="supplier-quality",
        owner="quality-office",
        classification="internal-demo",
        provenance="DEMO_CONFIGURATION",
        documents=documents,
    )


def test_exact_document_section_chunk_and_content_boundaries() -> None:
    assert (
        len(
            _pack(
                tuple(_document(i, (_section(i),)) for i in range(MAX_DOCUMENTS))
            ).documents
        )
        == 8
    )
    with pytest.raises(KnowledgePackError, match="DOCUMENT_LIMIT_EXCEEDED"):
        _pack(tuple(_document(i, (_section(i),)) for i in range(MAX_DOCUMENTS + 1)))

    assert (
        len(
            _document(
                0, tuple(_section(i) for i in range(MAX_SECTIONS_PER_DOCUMENT))
            ).sections
        )
        == 32
    )
    with pytest.raises(KnowledgePackError, match="SECTION_LIMIT_EXCEEDED"):
        _document(0, tuple(_section(i) for i in range(MAX_SECTIONS_PER_DOCUMENT + 1)))

    assert len(_section(0, chunks=MAX_CHUNKS_PER_DOCUMENT).chunks) == 128
    with pytest.raises(KnowledgePackError, match="CHUNK_LIMIT_EXCEEDED"):
        _section(0, chunks=MAX_CHUNKS_PER_DOCUMENT + 1)

    exact = "x" * MAX_CHUNK_BYTES
    assert (
        len(KnowledgeChunk.create(chunk_id="exact", ordinal=1, content=exact).content)
        == MAX_CHUNK_BYTES
    )
    with pytest.raises(KnowledgePackError, match="TEXT_LIMIT_EXCEEDED"):
        KnowledgeChunk.create(chunk_id="over", ordinal=1, content=exact + "x")


def test_exact_pack_chunk_and_content_boundaries() -> None:
    documents = (
        _document(0, (_section(0, chunks=128),)),
        _document(1, (_section(1, chunks=128),)),
    )
    assert (
        sum(
            len(section.chunks)
            for doc in _pack(documents).documents
            for section in doc.sections
        )
        == MAX_PACK_CHUNKS
    )
    with pytest.raises(KnowledgePackError, match="PACK_CHUNK_LIMIT_EXCEEDED"):
        _pack((*documents, _document(2, (_section(2),))))
    exact_content = "x" * MAX_CHUNK_BYTES
    exact_document = _document(0, (_section(0, chunks=128, content=exact_content),))
    assert (
        sum(
            len(chunk.content.encode())
            for section in _pack((exact_document,)).documents[0].sections
            for chunk in section.chunks
        )
        == MAX_PACK_CONTENT_BYTES
    )
    with pytest.raises(KnowledgePackError, match="PACK_CONTENT_LIMIT_EXCEEDED"):
        _pack(
            (
                exact_document,
                _document(1, (_section(1, content="overflow"),)),
            )
        )


def test_paths_load_time_rank_and_labels_are_not_semantic_inputs() -> None:
    pack = make_pack()
    assert not any(
        field in pack.__dataclass_fields__
        for field in (
            "repository_path",
            "loaded_at",
            "rank",
            "cache_key",
            "display_label",
            "transport_metadata",
        )
    )


def test_demo_assets_are_sanitized_exact_version_and_checksum_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    directory = root / "examples/s5-v0.2-supplier-quality/knowledge"
    manifest = json.loads((directory / "knowledge-pack-v1.json").read_text())
    document = (directory / "8d-procedure-v1.md").read_bytes()
    semantic_manifest = dict(manifest)
    declared_digest = semantic_manifest.pop("canonicalDigest")
    semantic_manifest["documents"] = [dict(item) for item in manifest["documents"]]
    for item in semantic_manifest["documents"]:
        item.pop("path")
    canonical_manifest = json.dumps(
        semantic_manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert manifest["knowledgePackVersion"] == "v1"
    assert manifest["provenance"] == "DEMO_CONFIGURATION"
    assert manifest["authority"] == "NON_PRODUCTION_DEMO_CONFIGURATION_ONLY"
    assert manifest["documents"][0]["documentVersion"] == "v1"
    assert (
        declared_digest
        == hashlib.sha256(
            f"demo-knowledge-pack-manifest.v1\n{canonical_manifest}".encode()
        ).hexdigest()
    )
    assert hashlib.sha256(document).hexdigest() == manifest["documents"][0]["sha256"]
    assert len(document) <= MAX_PACK_CONTENT_BYTES
    lowered = document.lower()
    for prohibited in (b"@example.com", b"bearer ", b"api_key=", b"password="):
        assert prohibited not in lowered
