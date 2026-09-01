from agent_console.knowledge_api import (
    get_knowledge_service,
    get_quality_service,
    router,
)
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_quality import KnowledgeQualityService
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
    stale = client.post(
        f"/api/internal/v0.2.2/knowledge/{identity}/validation",
        json={"expectedVersion": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reasonCode"] == "STALE_KNOWLEDGE"
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


def test_private_quality_api_is_scoped_and_classifies_lexical_search():
    app = FastAPI()
    app.include_router(router)
    repository = InMemoryKnowledgeRepository()
    lifecycle = KnowledgeLifecycleService(repository)
    quality = KnowledgeQualityService(repository)
    app.dependency_overrides[get_knowledge_service] = lambda: lifecycle
    app.dependency_overrides[get_quality_service] = lambda: quality
    client = TestClient(app)
    created = client.post(
        "/api/internal/v0.2.2/knowledge",
        json={
            "name": "Chinese quality",
            "source": {
                "sourceId": "source:one",
                "documentId": "document:one",
                "provenance": "human:owner",
                "content": "供应商缺陷必须隔离。",
            },
        },
    )
    assert created.status_code == 201
    result = client.post(
        "/api/internal/v0.2.2/knowledge/operations/search",
        json={"query": "供应商缺陷", "mode": "LEXICAL", "topK": 5},
    )
    assert result.status_code == 200
    assert result.json()["classification"] == "LEXICAL"
    foreign = client.get(
        "/api/internal/v0.2.2/knowledge/operations/dashboard",
        headers={"X-Tenant-ID": "tenant-b"},
    )
    assert foreign.json()["authorizedKnowledgeCount"] == 0
