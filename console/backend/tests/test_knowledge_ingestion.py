import pytest
from agent_console.knowledge_ingestion import deterministic_vector, ingest_text


def test_ingestion_has_stable_identity_digest_and_vector():
    chunks, digest = ingest_text(
        "document:one", "First paragraph.\n\nSecond paragraph."
    )
    assert [item["chunkId"] for item in chunks] == [
        "document:one:chunk:1",
        "document:one:chunk:2",
    ]
    assert len(digest) == 64 and deterministic_vector(
        chunks[0]["content"]
    ) == deterministic_vector(chunks[0]["content"])


def test_ingestion_rejects_empty_content():
    with pytest.raises(ValueError):
        ingest_text("document:one", "   ")
