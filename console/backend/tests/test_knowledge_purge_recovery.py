import httpx
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex
from test_knowledge_lifecycle_service import published_service


def test_partial_purge_is_resumable_and_recovery_required():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(404)
        if request.url.path.endswith("/points/delete"):
            return httpx.Response(503)
        return httpx.Response(200, json={"status": "ok", "result": {}})

    index = QdrantKnowledgeIndex(
        "http://qdrant", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    service, scope, value = published_service(index)
    value = service.ingest(scope, value["knowledgeId"], "human", 4)["knowledge"]
    result = service.purge(
        scope,
        value["knowledgeId"],
        "human:compliance",
        5,
        "authorization:one",
        "PROHIBITED_CONTENT",
    )["knowledge"]
    assert (
        result["purge"]["status"] == "RECOVERY_REQUIRED"
        and result["lifecycleState"] == "RECOVERY_REQUIRED"
    )
