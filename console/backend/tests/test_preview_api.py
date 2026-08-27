from agent_console.app import (
    app,
    get_preview_principal,
    get_preview_service,
)
from agent_console.preview_service import PreviewService, TrustedPreviewPrincipal
from agent_core.execution_evidence import (
    AppendDisposition,
    AppendResult,
    AuthorizationDecision,
    EvidenceEventType,
    ExecutionEvidenceRecord,
    OutcomeClassification,
)
from fastapi.testclient import TestClient


class WorkflowRepository:
    def __init__(self):
        self.workflow = {
            "metadata": {
                "name": "workflow",
                "uid": "workflow-uid",
                "resourceVersion": "10",
            }
        }
        self.tasks = [
            {
                "metadata": {
                    "name": "task",
                    "uid": "task-uid",
                    "resourceVersion": "20",
                },
                "spec": {},
                "status": {"phase": "Succeeded"},
            }
        ]

    def get_workflow(self, namespace, name):
        return self.workflow

    def list_workflow_tasks(self, namespace, workflow_name):
        return self.tasks


def evidence():
    return ExecutionEvidenceRecord(
        evidence_record_id="evidence.native.pei-001.1.1",
        namespace="agent-workloads",
        security_domain="domain-a",
        platform_execution_identity="pei-001",
        workflow_identity="workflow-uid",
        task_identity="task",
        attempt_ordinal=1,
        event_ordinal=1,
        event_type=EvidenceEventType.EXECUTION_OUTCOME,
        occurred_at="2026-08-27T08:00:00Z",
        runtime_classification="NATIVE",
        selected_instance_identity="instance-001",
        capability_identity="lookup",
        authorization_decision=AuthorizationDecision.ALLOW,
        reason_code="TASK_RUNTIME_SUCCEEDED",
        provider_correlation_id="provider-001",
        provider_call_count=1,
        outcome_classification=OutcomeClassification.SUCCEEDED,
        evidence_references=("evidence-ref",),
        citation_references=("citation-ref",),
        storage_sequence=1,
        recorded_at="2026-08-27T08:00:01Z",
    )


class EvidenceRepository:
    def __init__(self):
        self.reads = 0

    def append(self, value):
        return AppendResult(AppendDisposition.APPENDED, value)

    def high_water_mark(self, scope):
        self.reads += 1
        return 1

    def read_task(self, scope, task_identity, *, through_high_water_mark):
        self.reads += 1
        return (evidence(),)

    def read_execution(self, *args, **kwargs):
        raise AssertionError


def authorized():
    return TrustedPreviewPrincipal(
        "server-principal", "agent-workloads", "domain-a", True
    )


def client(repository=None):
    evidence_repository = repository or EvidenceRepository()
    app.dependency_overrides[get_preview_principal] = authorized
    app.dependency_overrides[get_preview_service] = lambda: PreviewService(
        WorkflowRepository(), evidence_repository
    )
    return TestClient(app), evidence_repository


def teardown_function():
    app.dependency_overrides.pop(get_preview_principal, None)
    app.dependency_overrides.pop(get_preview_service, None)


def test_versioned_preview_returns_shared_snapshot_and_etag() -> None:
    browser, _ = client()
    response = browser.get(
        "/api/internal/preview/v1/executions/agent-workloads/workflow/task"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == 1
    assert payload["state"] == "COMPLETE"
    assert response.headers["etag"] == f'"{payload["sharedSnapshotId"]}"'
    assert (
        payload["snapshot"]["product"]["sharedSnapshotId"]
        == payload["snapshot"]["technical"]["sharedSnapshotId"]
    )


def test_conditional_request_returns_304() -> None:
    browser, _ = client()
    url = "/api/internal/preview/v1/executions/agent-workloads/workflow/task"
    first = browser.get(url)
    second = browser.get(url, headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304
    assert second.content == b""


def test_authorized_not_found_is_bounded() -> None:
    browser, _ = client()
    response = browser.get(
        "/api/internal/preview/v1/executions/agent-workloads/workflow/missing"
    )
    assert response.status_code == 404
    assert response.json()["detail"]["state"] == "NOT_FOUND"
    assert "trace" not in response.text.lower()
