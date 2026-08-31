import httpx
import pytest
from agent_console.knowledge_lifecycle_service import (
    KnowledgeLifecycleFailure,
    KnowledgeLifecycleService,
)
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex
from agent_console.knowledge_repository import InMemoryKnowledgeRepository


def qdrant():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, json={"status": "ok", "result": {}})

    return QdrantKnowledgeIndex(
        "http://qdrant", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def source():
    return {
        "sourceId": "source:one",
        "documentId": "document:one",
        "provenance": "human:owner",
        "content": "Approved procedure.\n\nCitable evidence.",
    }


def published_service(index=None):
    service = KnowledgeLifecycleService(
        InMemoryKnowledgeRepository(), index or qdrant()
    )
    scope = service.scope("tenant-a", "quality")
    value = service.create(scope, "human:owner", "Quality Knowledge", source())[
        "knowledge"
    ]
    value = service.validate(scope, value["knowledgeId"], "human:owner", 1)["knowledge"]
    digest = value["revisions"][-1]["digest"]
    value = service.review(scope, value["knowledgeId"], "human:reviewer", 2, digest)[
        "knowledge"
    ]
    value = service.publish(scope, value["knowledgeId"], "human:publisher", 3, digest)[
        "knowledge"
    ]
    return service, scope, value


def test_exact_digest_publication_and_ingestion_snapshot():
    service, scope, value = published_service()
    result = service.ingest(scope, value["knowledgeId"], "human:operator", 4)[
        "knowledge"
    ]
    assert result["lifecycleState"] == "AVAILABLE" and result["activeIndexSnapshotId"]
    assert result["ingestionJobs"][-1]["highWaterMark"] == 4


def test_successor_preserves_published_revision_and_authorized_retrieval_cites_source():
    service, scope, value = published_service()
    value = service.ingest(scope, value["knowledgeId"], "human", 4)["knowledge"]
    published_id = value["publishedRevisionId"]
    snapshot_id = value["activeIndexSnapshotId"]
    revision = next(
        item for item in value["revisions"] if item["revisionId"] == published_id
    )
    chunk = revision["content"]["documents"][0]["chunks"][0]

    def search(*args, **kwargs):
        return [
            {
                "payload": {
                    "chunkId": chunk["chunkId"],
                    "revisionDigest": revision["digest"],
                }
            }
        ]

    service.qdrant.search = search  # type: ignore[method-assign]
    retrieved = service.retrieve(
        scope,
        value["knowledgeId"],
        "human",
        5,
        "ALLOW",
        "authorization:one",
        "approved procedure",
    )["knowledge"]
    citation = retrieved["retrievals"][-1]["citations"][0]
    assert citation["sourceId"] == "source:one"
    assert retrieved["activeIndexSnapshotId"] == snapshot_id
    successor = service.successor(
        scope,
        value["knowledgeId"],
        "human",
        6,
        "Updated approved procedure.",
    )["knowledge"]
    assert successor["publishedRevisionId"] == published_id
    assert successor["revisions"][-1]["predecessorRevisionId"] == published_id


def test_denied_retrieval_does_not_read_repository():
    service, scope, _ = published_service()
    with pytest.raises(KnowledgeLifecycleFailure, match="KNOWLEDGE_ACCESS_DENIED"):
        service.retrieve(
            scope,
            "knowledge:foreign",
            "human",
            1,
            "DENY",
            "authorization:denied",
            "query",
        )
