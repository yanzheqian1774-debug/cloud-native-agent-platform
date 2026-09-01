from agent_console.app import app
from agent_console.skill_mcp_api import get_skill_mcp_service
from agent_console.skill_mcp_repository import InMemorySkillMcpRepository
from agent_console.skill_mcp_service import SkillMcpService
from fastapi.testclient import TestClient


def test_private_workbench_api_creates_and_validates() -> None:
    service = SkillMcpService(InMemorySkillMcpRepository())
    app.dependency_overrides[get_skill_mcp_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post(
            "/api/internal/v0.2.2/resources/skill",
            json={
                "name": "Quality",
                "content": {
                    "description": "Quality",
                    "capabilities": ["quality.lookup"],
                    "instructions": "Inspect quality",
                },
            },
        )
        assert created.status_code == 201
        resource = created.json()["resource"]
        validated = client.post(
            f"/api/internal/v0.2.2/resources/skill/{resource['resourceId']}/validation",
            json={"expectedVersion": 1},
        )
        assert (
            validated.status_code == 200
            and validated.json()["productProjection"]["state"] == "VALIDATED"
        )
        stale = client.post(
            f"/api/internal/v0.2.2/resources/skill/{resource['resourceId']}/validation",
            json={"expectedVersion": 1},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["reasonCode"] == "STALE_RESOURCE"
        manifest = client.get(
            f"/api/internal/v0.2.2/resources/skill/{resource['resourceId']}/manifest"
        )
        assert manifest.status_code == 200
        assert manifest.json()["credentialMaterial"] == "NOT_INCLUDED"
        imported = client.post(
            "/api/internal/v0.2.2/resources/skill/manifest-import",
            json={**manifest.json(), "name": "Imported Quality"},
        )
        assert imported.status_code == 201
        cloned = client.post(
            f"/api/internal/v0.2.2/resources/skill/{resource['resourceId']}/clones",
            json={
                "revisionId": resource["revisions"][0]["revisionId"],
                "name": "Cloned Quality",
            },
        )
        assert cloned.status_code == 201
        assert cloned.json()["resource"]["relationships"][0]["type"] == (
            "CLONED_FROM_TEMPLATE"
        )
    finally:
        app.dependency_overrides.pop(get_skill_mcp_service, None)
