import copy

import pytest
from agent_console.workflow_definition_repository import (
    InMemoryWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import (
    WorkflowDefinitionFailure,
    WorkflowDefinitionService,
)


def content(tasks=None):
    return {
        "description": "governed flow",
        "tasks": tasks
        or [
            {
                "taskId": "collect",
                "name": "Collect",
                "dependsOn": [],
                "inputs": [],
                "outputs": ["facts"],
                "capabilityRequirements": ["research"],
                "references": [],
                "retryLimit": 1,
                "timeoutSeconds": 30,
                "failurePolicy": "FAIL_WORKFLOW",
            }
        ],
        "inputs": [],
        "outputs": ["facts"],
        "runtimeProfile": {
            "kind": "RUNTIME_PROFILE",
            "resourceId": "runtime-profile:1",
            "revisionId": "runtime-profile-revision:1",
        },
    }


def test_stable_dag_and_exact_digest_lifecycle():
    service = WorkflowDefinitionService(
        InMemoryWorkflowDefinitionRepository(), lambda _scope, _ref: True
    )
    scope = service.scope("tenant-a", "domain-a")
    record = service.create(
        scope,
        "human:a",
        "Flow",
        content(
            [
                {"taskId": "b", "name": "B", "dependsOn": ["a"]},
                {"taskId": "a", "name": "A", "dependsOn": []},
            ]
        ),
    )
    assert service.project(record)["productProjection"]["orderedTaskIds"] == ["a", "b"]
    record = service.validate(scope, record["workflowDefinitionId"], "human:a", 1)
    draft = record["revisions"][-1]
    record = service.review(
        scope,
        record["workflowDefinitionId"],
        "human:a",
        2,
        draft["digest"],
        "APPROVE",
        "reviewed",
    )
    review = record["reviews"][-1]
    record = service.publish(
        scope,
        record["workflowDefinitionId"],
        "human:a",
        3,
        draft["digest"],
        review["reviewId"],
    )
    assert record["lifecycleState"] == "PUBLISHED"
    assert (
        service.successor(scope, record["workflowDefinitionId"], "human:a", 4)[
            "revisions"
        ][-1]["predecessorRevisionId"]
        == draft["revisionId"]
    )


def test_cycle_and_unsafe_runtime_fields_are_rejected():
    service = WorkflowDefinitionService(InMemoryWorkflowDefinitionRepository())
    scope = service.scope("tenant-a", "domain-a")
    with pytest.raises(WorkflowDefinitionFailure, match="WORKFLOW_CYCLE_DETECTED"):
        service.create(
            scope,
            "human:a",
            "Flow",
            content(
                [
                    {"taskId": "a", "name": "A", "dependsOn": ["b"]},
                    {"taskId": "b", "name": "B", "dependsOn": ["a"]},
                ]
            ),
        )
    unsafe = content()
    unsafe["tasks"][0]["podYaml"] = "kind: Pod"
    with pytest.raises(
        WorkflowDefinitionFailure, match="UNSAFE_RUNTIME_FIELD_FORBIDDEN"
    ):
        service.create(scope, "human:a", "Flow", unsafe)


def test_validation_requires_resolved_exact_revision():
    service = WorkflowDefinitionService(
        InMemoryWorkflowDefinitionRepository(), lambda _scope, _ref: False
    )
    scope = service.scope("tenant-a", "domain-a")
    record = service.create(scope, "human:a", "Flow", content())
    with pytest.raises(WorkflowDefinitionFailure, match="EXACT_REFERENCE_NOT_FOUND"):
        service.validate(scope, record["workflowDefinitionId"], "human:a", 1)


def test_skill_operation_binding_is_added_only_by_successor_revision():
    service = WorkflowDefinitionService(
        InMemoryWorkflowDefinitionRepository(), lambda _scope, _ref: True
    )
    scope = service.scope("tenant-a", "domain-a")
    record = service.create(scope, "human:a", "Flow", content())
    record = service.validate(scope, record["workflowDefinitionId"], "human:a", 1)
    published = record["revisions"][-1]
    record = service.review(
        scope,
        record["workflowDefinitionId"],
        "human:a",
        2,
        published["digest"],
        "APPROVE",
        "reviewed",
    )
    record = service.publish(
        scope,
        record["workflowDefinitionId"],
        "human:a",
        3,
        published["digest"],
        record["reviews"][-1]["reviewId"],
    )
    original_content = record["revisions"][0]["content"]
    original_digest = record["revisions"][0]["digest"]
    record = service.successor(scope, record["workflowDefinitionId"], "human:a", 4)
    successor_content = copy.deepcopy(record["revisions"][-1]["content"])
    successor_content["tasks"][0]["references"] = [
        {
            "kind": "SKILL",
            "resourceId": "skill:one",
            "revisionId": "skill-revision:one",
        }
    ]
    successor_content["tasks"][0]["skillOperationBindings"] = [
        {
            "skillId": "skill:one",
            "skillRevisionId": "skill-revision:one",
            "skillDigest": "a" * 64,
            "operation": "quality.read",
        }
    ]
    record = service.edit(
        scope,
        record["workflowDefinitionId"],
        "human:a",
        5,
        successor_content,
    )
    bound = record["revisions"][-1]
    assert "skillOperationBindings" not in original_content["tasks"][0]
    assert record["revisions"][0]["digest"] == original_digest
    assert bound["predecessorRevisionId"] == record["revisions"][-2]["revisionId"]
    assert bound["digest"] != original_digest
    service.validate(scope, record["workflowDefinitionId"], "human:a", 6)


@pytest.mark.parametrize(
    ("bindings", "reason"),
    (
        ([], "SKILL_OPERATION_BINDING_REQUIRED"),
        (
            [
                {
                    "skillId": "skill:one",
                    "skillRevisionId": "skill-revision:one",
                    "skillDigest": "a" * 64,
                    "operation": "quality.read",
                }
            ]
            * 2,
            "DUPLICATE_SKILL_OPERATION_BINDING",
        ),
        (
            [
                {
                    "skillId": "skill:missing",
                    "skillRevisionId": "skill-revision:missing",
                    "skillDigest": "a" * 64,
                    "operation": "quality.read",
                }
            ],
            "SKILL_OPERATION_REFERENCE_REQUIRED",
        ),
    ),
)
def test_invalid_skill_operation_bindings_fail_closed(bindings, reason):
    service = WorkflowDefinitionService(InMemoryWorkflowDefinitionRepository())
    scope = service.scope("tenant-a", "domain-a")
    value = content()
    value["tasks"][0]["skillOperationBindings"] = bindings
    with pytest.raises(WorkflowDefinitionFailure, match=reason):
        service.create(scope, "human:a", "Flow", value)
