from agent_console.knowledge_api import get_knowledge_service, router
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_repository import InMemoryKnowledgeRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_standalone_private_api_runs_exact_digest_lifecycle():
    app = FastAPI()
    app.include_router(router)
    service = KnowledgeLifecycleService(InMemoryKnowledgeRepository())
    app.dependency_overrides[get_knowledge_service] = lambda: service
    client = TestClient(app)
    created = client.post(
        "/api/internal/v0.2.2/knowledge",
        json={
            "name": "Quality Knowledge",
            "source": {
                "sourceId": "source:one",
                "documentId": "document:one",
                "provenance": "human:owner",
                "content": "Approved procedure.",
            },
        },
    )
    assert created.status_code == 201
    value = created.json()["knowledge"]
    identity = value["knowledgeId"]
    validated = client.post(
        f"/api/internal/v0.2.2/knowledge/{identity}/validation",
        json={"expectedVersion": 1},
    ).json()["knowledge"]
    digest = validated["revisions"][-1]["digest"]
    assert (
        client.post(
            f"/api/internal/v0.2.2/knowledge/{identity}/reviews",
            json={"expectedVersion": 2, "digest": digest},
        ).status_code
        == 200
    )
    published = client.post(
        f"/api/internal/v0.2.2/knowledge/{identity}/publications",
        json={"expectedVersion": 3, "digest": digest},
    )
    assert (
        published.json()["technicalProjection"]["publishedRevisionId"]
        == published.json()["knowledge"]["publishedRevisionId"]
    )
