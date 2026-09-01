from agent_console.app import app
from agent_console.runtime_profile_api import get_service
from agent_console.runtime_profile_repository import InMemoryRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService
from fastapi.testclient import TestClient


def payload(provider="NATIVE_KUBERNETES"):
    return {
        "name": "Governed runtime",
        "content": {
            "provider": provider,
            "resources": {
                "cpuRequest": "250m",
                "cpuLimit": "500m",
                "memoryRequest": "256Mi",
                "memoryLimit": "1Gi",
            },
            "isolation": "NAMESPACE",
            "stateMode": "STATELESS",
            "sessionAffinity": "NONE",
            "secretReferences": ["secret-ref:model"],
            "openClawPackageRef": None
            if provider == "NATIVE_KUBERNETES"
            else "oci://openclaw@sha256:abc",
        },
    }


def test_private_api_publishes_native_and_declares_openclaw_without_execution():
    service = RuntimeProfileService(InMemoryRuntimeProfileRepository())
    app.dependency_overrides[get_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post(
            "/api/internal/v0.2.2/runtime-profiles", json=payload()
        ).json()["profile"]
        rid = created["runtimeProfileId"]
        validated = client.post(
            f"/api/internal/v0.2.2/runtime-profiles/{rid}/validation",
            json={"expectedVersion": 1},
        ).json()["profile"]
        digest = validated["revisions"][-1]["digest"]
        reviewed = client.post(
            f"/api/internal/v0.2.2/runtime-profiles/{rid}/reviews",
            json={"expectedVersion": 2, "digest": digest, "reason": "bounded"},
        ).json()["profile"]
        published = client.post(
            f"/api/internal/v0.2.2/runtime-profiles/{rid}/publications",
            json={
                "expectedVersion": 3,
                "digest": digest,
                "reviewId": reviewed["reviews"][-1]["reviewId"],
            },
        )
        assert published.json()["technicalProjection"]["executionAuthority"] is False
        assert (
            client.post(
                "/api/internal/v0.2.2/runtime-profiles", json=payload("OPENCLAW")
            ).status_code
            == 201
        )
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_api_rejects_raw_environment_and_secret_values():
    service = RuntimeProfileService(InMemoryRuntimeProfileRepository())
    app.dependency_overrides[get_service] = lambda: service
    try:
        value = payload()
        value["content"]["env"] = {"TOKEN": "secret"}
        assert (
            TestClient(app)
            .post("/api/internal/v0.2.2/runtime-profiles", json=value)
            .status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(get_service, None)
