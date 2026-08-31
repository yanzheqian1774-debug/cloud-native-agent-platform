import os
import uuid

import httpx
import pytest
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex


def test_qdrant_rest_uses_scope_filter_and_derived_payload():
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        if request.url.path.endswith("/points/query"):
            return httpx.Response(200, json={"status": "ok", "result": {"points": []}})
        return httpx.Response(200, json={"status": "ok", "result": {}})

    subject = QdrantKnowledgeIndex(
        "http://qdrant", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    subject.ensure_collection()
    subject.upsert([{"id": "a" * 64, "vector": [0.0] * 8, "payload": {}}])
    subject.search(
        [0.0] * 8,
        namespace="tenant-a",
        security_domain="quality",
        knowledge_id="knowledge:one",
        snapshot_id="snapshot:one",
    )
    query = requests[-1].read().decode()
    assert "tenant-a" in query and "quality" in query and "snapshot:one" in query


@pytest.mark.skipif(
    not os.environ.get("KNOWLEDGE_TEST_QDRANT_URL"), reason="real Qdrant required"
)
def test_real_qdrant_v115_upsert_query_and_scoped_delete():
    suffix = uuid.uuid4().hex
    subject = QdrantKnowledgeIndex(
        os.environ["KNOWLEDGE_TEST_QDRANT_URL"], collection=f"knowledge_test_{suffix}"
    )
    subject.ensure_collection()
    payload = {
        "namespace": "tenant-a",
        "securityDomain": "quality",
        "knowledgeId": "knowledge:one",
        "snapshotId": "snapshot:one",
    }
    subject.upsert([{"id": str(uuid.uuid4()), "vector": [1.0] * 8, "payload": payload}])
    assert subject.search(
        [1.0] * 8,
        namespace="tenant-a",
        security_domain="quality",
        knowledge_id="knowledge:one",
        snapshot_id="snapshot:one",
    )
    assert (
        subject.search(
            [1.0] * 8,
            namespace="tenant-b",
            security_domain="quality",
            knowledge_id="knowledge:one",
            snapshot_id="snapshot:one",
        )
        == []
    )
    subject.delete_snapshot("tenant-a", "quality", "knowledge:one", "snapshot:one")
