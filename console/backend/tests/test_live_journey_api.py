"""Internal live journey API contract and nondisclosure tests."""

from agent_console.app import (
    app,
    get_live_journey_principal,
    get_live_journey_service,
)
from agent_console.live_journey import LiveJourneyCoordinator, TrustedJourneyPrincipal
from fastapi.testclient import TestClient
from test_live_journey import ExecutionAuthority, seed


def client(*, authorized: bool = True):
    service = LiveJourneyCoordinator(ExecutionAuthority())
    service.register_live(seed())
    app.dependency_overrides[get_live_journey_service] = lambda: service
    app.dependency_overrides[get_live_journey_principal] = lambda: (
        TrustedJourneyPrincipal("human:reviewer", "tenant-a", "quality", authorized)
    )
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_get_returns_strict_equal_sibling_projection():
    response = client().get(
        "/api/internal/preview/v1/live-planning-journeys/journey:supplier-quality-1"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schemaVersion"] == 1
    assert body["product"]["identity"] == body["technical"]["identity"]
    assert body["product"]["revision"] == body["technical"]["revision"]


def test_denial_is_constant_shaped_and_discloses_no_journey_identity():
    response = client(authorized=False).get(
        "/api/internal/preview/v1/live-planning-journeys/journey:supplier-quality-1"
    )
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "schemaVersion": 1,
        "state": "DENIED",
        "reasonCode": "LIVE_JOURNEY_ACCESS_DENIED",
        "message": "Live planning journey is unavailable",
    }
    assert "supplier" not in response.text
    assert "tenant-a" not in response.text


def test_correction_approval_and_rerun_api_are_exact_digest_bound():
    api = client()
    path = "/api/internal/preview/v1/live-planning-journeys/journey:supplier-quality-1"
    current = api.get(path).json()["successor"]
    corrected = api.post(
        f"{path}/corrections",
        json={
            "predecessorRevisionId": current["identity"]["canonicalWorkflowRevisionId"],
            "predecessorDigest": current["identity"]["canonicalDigest"],
            "objective": "Prioritize severe supplier issues first",
            "reasonCode": "CONSTRAINT_CHANGED",
        },
    )
    assert corrected.status_code == 200
    successor = corrected.json()["successor"]
    mismatch = api.post(
        f"{path}/approvals",
        json={
            "candidateDigest": "f" * 64,
            "decision": "APPROVE",
            "reasonCode": "HUMAN_APPROVED",
            "replayIdentity": "api-replay:1",
        },
    )
    assert mismatch.status_code == 409
    approved = api.post(
        f"{path}/approvals",
        json={
            "candidateDigest": successor["identity"]["canonicalDigest"],
            "decision": "APPROVE",
            "reasonCode": "HUMAN_APPROVED",
            "replayIdentity": "api-replay:1",
        },
    ).json()["successor"]
    rerun = api.post(
        f"{path}/reruns",
        json={
            "canonicalWorkflowRevisionId": approved["identity"][
                "canonicalWorkflowRevisionId"
            ],
            "canonicalDigest": approved["identity"]["canonicalDigest"],
        },
    )
    assert rerun.status_code == 200
    assert rerun.json()["successor"]["executionState"] == "SUCCEEDED"


def test_request_extra_fields_are_rejected():
    response = client().post(
        "/api/internal/preview/v1/live-planning-journeys/journey:supplier-quality-1/corrections",
        json={
            "predecessorRevisionId": "revision:x",
            "predecessorDigest": "a" * 64,
            "objective": "change",
            "reasonCode": "CONSTRAINT_CHANGED",
            "rawPrompt": "secret",
        },
    )
    assert response.status_code == 422
    assert "rawPrompt" in response.text
