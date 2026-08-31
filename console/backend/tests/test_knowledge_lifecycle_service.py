import httpx
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
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
