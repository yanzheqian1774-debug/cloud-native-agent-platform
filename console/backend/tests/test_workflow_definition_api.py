import pytest
from agent_console import runtime_profile_api, workflow_definition_api
from agent_console.agent_binding_validation import (
    BindingValidationFailure,
    validate_bindings,
)
from agent_console.agent_definition_repository import DefinitionScope
from agent_console.app import app
from agent_console.runtime_profile_repository import InMemoryRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService
from agent_console.workflow_definition_api import get_service
from agent_console.workflow_definition_repository import (
    InMemoryWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService
from fastapi.testclient import TestClient


class WorkbenchResolver:
    def resolve(self, scope, kind, resource_id):
        resolver = {
            "workflow": workflow_definition_api.binding_resolver,
            "runtime-profile": runtime_profile_api.binding_resolver,
        }.get(kind)
        return None if resolver is None else resolver.resolve(scope, kind, resource_id)


def payload():
    return {
        "name": "Supplier response workflow",
        "content": {
            "description": "Governed response",
            "tasks": [
                {
                    "taskId": "analyze",
                    "name": "Analyze",
                    "dependsOn": [],
                    "inputs": ["quality-records"],
                    "outputs": ["analysis"],
                    "capabilityRequirements": ["supplier-quality-analysis"],
                    "references": [],
                    "retryLimit": 1,
                    "timeoutSeconds": 300,
                    "failurePolicy": "FAIL_WORKFLOW",
                }
            ],
            "inputs": ["quality-records"],
            "outputs": ["analysis"],
            "runtimeProfile": {
                "kind": "RUNTIME_PROFILE",
                "resourceId": "runtime-profile:native",
                "revisionId": "runtime-profile-revision:one",
            },
        },
    }


def test_private_api_exact_digest_publication_and_comparison():
    service = WorkflowDefinitionService(
        InMemoryWorkflowDefinitionRepository(), lambda _scope, _reference: True
    )
    app.dependency_overrides[get_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post(
            "/api/internal/v0.2.2/workflow-definitions", json=payload()
        )
        assert created.status_code == 201
        definition = created.json()["definition"]
        resource_id = definition["workflowDefinitionId"]
        validated = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/validation",
            json={"expectedVersion": 1},
        ).json()["definition"]
        digest = validated["revisions"][-1]["digest"]
        conflict = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/reviews",
            json={"expectedVersion": 2, "digest": "sha256:wrong", "reason": "checked"},
        )
        assert conflict.status_code == 409
        reviewed = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/reviews",
            json={"expectedVersion": 2, "digest": digest, "reason": "checked"},
        ).json()["definition"]
        published = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/publications",
            json={
                "expectedVersion": 3,
                "digest": digest,
                "reviewId": reviewed["reviews"][-1]["reviewId"],
            },
        ).json()["definition"]
        successor = client.post(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/successors",
            json={"expectedVersion": 4},
        ).json()["definition"]
        comparison = client.get(
            f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/comparison",
            params={
                "leftRevisionId": published["publishedRevisionId"],
                "rightRevisionId": successor["currentDraftRevisionId"],
            },
        )
        assert comparison.status_code == 200
        assert comparison.json()["digestChanged"] is True
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_api_strictly_rejects_pod_yaml():
    service = WorkflowDefinitionService(InMemoryWorkflowDefinitionRepository())
    app.dependency_overrides[get_service] = lambda: service
    try:
        value = payload()
        value["content"]["tasks"][0]["podYaml"] = "kind: Pod"
        assert (
            TestClient(app)
            .post("/api/internal/v0.2.2/workflow-definitions", json=value)
            .status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_agent_binding_resolver_is_scoped_digest_exact_and_fail_closed(monkeypatch):
    workflow_repository = InMemoryWorkflowDefinitionRepository()
    workflow_service = WorkflowDefinitionService(
        workflow_repository, lambda _scope, _reference: True
    )
    workflow_scope = workflow_service.scope("tenant-a", "domain-a")
    record = workflow_service.create(
        workflow_scope, "human:a", "Flow", payload()["content"]
    )
    record = workflow_service.validate(
        workflow_scope, record["workflowDefinitionId"], "human:a", 1
    )
    revision = record["revisions"][-1]
    record = workflow_service.review(
        workflow_scope,
        record["workflowDefinitionId"],
        "human:a",
        2,
        revision["digest"],
        "APPROVE",
        "exact",
    )
    record = workflow_service.publish(
        workflow_scope,
        record["workflowDefinitionId"],
        "human:a",
        3,
        revision["digest"],
        record["reviews"][-1]["reviewId"],
    )

    runtime_service = RuntimeProfileService(InMemoryRuntimeProfileRepository())
    runtime_scope = runtime_service.scope("tenant-a", "domain-a")
    profile = runtime_service.create(
        runtime_scope,
        "human:a",
        "Runtime",
        {
            "provider": "NATIVE_KUBERNETES",
            "resources": {
                "cpuRequest": "250m",
                "cpuLimit": "500m",
                "memoryRequest": "256Mi",
                "memoryLimit": "1Gi",
            },
            "isolation": "NAMESPACE",
            "stateMode": "STATELESS",
            "sessionAffinity": "NONE",
            "secretReferences": [],
            "openClawPackageRef": None,
        },
    )
    profile = runtime_service.validate(
        runtime_scope, profile["runtimeProfileId"], "human:a", 1
    )
    runtime_revision = profile["revisions"][-1]
    profile = runtime_service.review(
        runtime_scope,
        profile["runtimeProfileId"],
        "human:a",
        2,
        runtime_revision["digest"],
        "APPROVE",
        "exact",
    )
    runtime_service.publish(
        runtime_scope,
        profile["runtimeProfileId"],
        "human:a",
        3,
        runtime_revision["digest"],
        profile["reviews"][-1]["reviewId"],
    )

    monkeypatch.setattr(workflow_definition_api, "_service", workflow_service)
    monkeypatch.setattr(runtime_profile_api, "_service", runtime_service)
    scope = DefinitionScope("tenant-a", "domain-a")
    bindings = {
        "workflow": {
            "resourceId": record["workflowDefinitionId"],
            "revisionId": revision["revisionId"],
            "digest": revision["digest"].removeprefix("sha256:"),
        },
        "runtimeProfile": {
            "resourceId": profile["runtimeProfileId"],
            "revisionId": runtime_revision["revisionId"],
            "digest": runtime_revision["digest"].removeprefix("sha256:"),
        },
    }
    verified = validate_bindings(scope, bindings, WorkbenchResolver())
    assert [item["kind"] for item in verified] == ["workflow", "runtime-profile"]

    for changed, reason in (
        ({"digest": "0" * 64}, "BOUND_RESOURCE_DIGEST_MISMATCH"),
        (
            {"revisionId": "workflow-revision:wrong"},
            "BOUND_REVISION_NOT_CURRENT_PUBLISHED",
        ),
    ):
        invalid = {**bindings, "workflow": {**bindings["workflow"], **changed}}
        with pytest.raises(BindingValidationFailure, match=reason):
            validate_bindings(scope, invalid, WorkbenchResolver())
    with pytest.raises(BindingValidationFailure, match="SUPPLIED_REFERENCE_UNRESOLVED"):
        validate_bindings(
            DefinitionScope("tenant-b", "domain-a"), bindings, WorkbenchResolver()
        )

    key = ("tenant-a", "domain-a", record["workflowDefinitionId"])
    for field, value, reason in (
        ("enabled", False, "BOUND_RESOURCE_DISABLED"),
        ("lifecycleState", "DEPRECATED", "BOUND_RESOURCE_DEPRECATED"),
        ("compatible", False, "BOUND_RESOURCE_INCOMPATIBLE"),
    ):
        stored = workflow_repository._records[key]
        previous = stored.get(field)
        stored[field] = value
        with pytest.raises(BindingValidationFailure, match=reason):
            validate_bindings(scope, bindings, WorkbenchResolver())
        if previous is None:
            stored.pop(field)
        else:
            stored[field] = previous
