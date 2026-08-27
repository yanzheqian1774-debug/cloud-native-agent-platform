from agent_console.app import app, get_preview_principal, get_preview_service
from agent_console.preview_service import PreviewService, TrustedPreviewPrincipal
from fastapi.testclient import TestClient
from test_preview_api import EvidenceRepository, WorkflowRepository


def teardown_function():
    app.dependency_overrides.pop(get_preview_principal, None)
    app.dependency_overrides.pop(get_preview_service, None)


def test_authorization_occurs_before_any_evidence_load_and_leaks_nothing() -> None:
    evidence = EvidenceRepository()
    app.dependency_overrides[get_preview_principal] = lambda: TrustedPreviewPrincipal(
        "server-principal", "different-namespace", "domain-a", True
    )
    app.dependency_overrides[get_preview_service] = lambda: PreviewService(
        WorkflowRepository(), evidence
    )
    response = TestClient(app).get(
        "/api/internal/preview/v1/executions/agent-workloads/workflow/task"
    )
    assert response.status_code == 403
    assert evidence.reads == 0
    body = response.json()["detail"]
    assert body == {
        "schemaVersion": 1,
        "state": "DENIED",
        "reasonCode": "PREVIEW_ACCESS_DENIED",
        "message": "Execution preview is unavailable",
    }
    assert not any(
        key in response.text
        for key in ("evidence.native", "highWater", "sharedSnapshot", "graphSnapshot")
    )


def test_arbitrary_client_headers_cannot_create_authority() -> None:
    evidence = EvidenceRepository()
    app.dependency_overrides[get_preview_principal] = lambda: TrustedPreviewPrincipal(
        "", "", "", False
    )
    app.dependency_overrides[get_preview_service] = lambda: PreviewService(
        WorkflowRepository(), evidence
    )
    response = TestClient(app).get(
        "/api/internal/preview/v1/executions/agent-workloads/workflow/task",
        headers={
            "X-Principal": "attacker",
            "X-Namespace": "agent-workloads",
            "X-Security-Domain": "domain-a",
        },
    )
    assert response.status_code == 403
    assert evidence.reads == 0


def test_missing_repository_is_authority_missing_not_success() -> None:
    app.dependency_overrides[get_preview_principal] = lambda: TrustedPreviewPrincipal(
        "server-principal", "agent-workloads", "domain-a", True
    )
    app.dependency_overrides[get_preview_service] = lambda: PreviewService(
        WorkflowRepository(), None
    )
    response = TestClient(app).get(
        "/api/internal/preview/v1/executions/agent-workloads/workflow/task"
    )
    assert response.status_code == 503
    assert response.json()["detail"]["state"] == "AUTHORITY_MISSING"


def test_denied_reference_identity_is_not_serialized() -> None:
    from dataclasses import replace

    from agent_core.execution_evidence import (
        AuthorizationDecision,
        AuthorizedReference,
        ReferenceType,
        ReferenceVisibility,
    )
    from test_preview_api import evidence

    denied = AuthorizedReference(
        "citation-private",
        ReferenceType.CITATION,
        "agent-workloads",
        "domain-a",
        AuthorizationDecision.DENY,
        "REFERENCE_DENIED",
        ReferenceVisibility.BOTH,
        "execution-evidence",
        "native-runtime",
    )
    repository = EvidenceRepository((replace(evidence(), references=(denied,)),))
    browser = TestClient(app)
    app.dependency_overrides[get_preview_principal] = lambda: TrustedPreviewPrincipal(
        "server-principal", "agent-workloads", "domain-a", True
    )
    app.dependency_overrides[get_preview_service] = lambda: PreviewService(
        WorkflowRepository(), repository
    )
    response = browser.get(
        "/api/internal/preview/v1/executions/agent-workloads/workflow/task"
    )
    assert response.status_code == 200
    assert "citation-private" not in response.text
