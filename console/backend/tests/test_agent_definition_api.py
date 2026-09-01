from agent_console.agent_definition_repository import InMemoryAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.app import app, get_agent_definition_service
from fastapi.testclient import TestClient


def test_private_api_runs_exact_digest_publication() -> None:
    service = AgentDefinitionService(InMemoryAgentDefinitionRepository())
    app.dependency_overrides[get_agent_definition_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post(
            "/api/internal/v0.2.2/agent-definitions",
            json={
                "name": "Quality Agent",
                "content": {
                    "title": "Supplier Quality Analyst",
                    "duties": ["analyze supplier quality"],
                    "capabilities": ["supplier-quality-analysis"],
                },
            },
        )
        assert created.status_code == 201
        definition = created.json()["definition"]
        definition_id = definition["definitionId"]
        validated = client.post(
            f"/api/internal/v0.2.2/agent-definitions/{definition_id}/validation",
            json={"expectedVersion": 1},
        ).json()["definition"]
        digest = validated["revisions"][-1]["digest"]
        stale = client.post(
            f"/api/internal/v0.2.2/agent-definitions/{definition_id}/validation",
            json={"expectedVersion": 1},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["reasonCode"] == "STALE_AGENT_DEFINITION"
        reviewed = client.post(
            f"/api/internal/v0.2.2/agent-definitions/{definition_id}/reviews",
            json={"expectedVersion": 2, "digest": digest, "reason": "verified"},
        ).json()["definition"]
        published = client.post(
            f"/api/internal/v0.2.2/agent-definitions/{definition_id}/publications",
            json={
                "expectedVersion": 3,
                "digest": digest,
                "reviewId": reviewed["reviews"][-1]["reviewId"],
            },
        )
        assert published.status_code == 200
        body = published.json()
        assert (
            body["technicalProjection"]["publishedRevisionId"]
            == body["definition"]["publishedRevisionId"]
        )
    finally:
        app.dependency_overrides.pop(get_agent_definition_service, None)


def test_private_api_rejects_supplied_unresolved_workflow_reference() -> None:
    service = AgentDefinitionService(InMemoryAgentDefinitionRepository())
    app.dependency_overrides[get_agent_definition_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post(
            "/api/internal/v0.2.2/agent-definitions",
            json={
                "name": "Unresolved workflow Agent",
                "content": {
                    "title": "Analyst",
                    "duties": ["analyze"],
                    "capabilities": ["analysis"],
                    "bindings": {
                        "workflow": {
                            "kind": "workflow-definition",
                            "resourceId": "workflow:1",
                            "revisionId": "workflow-revision:1",
                            "digest": "a" * 64,
                        }
                    },
                },
            },
        ).json()["definition"]
        response = client.post(
            f"/api/internal/v0.2.2/agent-definitions/{created['definitionId']}/validation",
            json={"expectedVersion": 1},
        )
        assert response.status_code == 409
        assert (
            response.json()["detail"]["reasonCode"] == "WORKFLOW_RESOLVER_UNAVAILABLE"
        )
    finally:
        app.dependency_overrides.pop(get_agent_definition_service, None)
