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


def bound_content():
    value = content()
    value["tasks"][0]["references"] = [
        {
            "kind": "SKILL",
            "resourceId": "skill:one",
            "revisionId": "skill-revision:one",
        }
    ]
    value["tasks"][0]["skillOperationBindings"] = [
        {
            "skillId": "skill:one",
            "skillRevisionId": "skill-revision:one",
            "skillDigest": "a" * 64,
            "operation": "quality.read",
        }
    ]
    return value


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


@pytest.mark.parametrize("replacement", ["omitted", None])
def test_edit_rejects_omitted_or_null_prior_binding_without_writing(replacement):
    repository = InMemoryWorkflowDefinitionRepository()
    service = WorkflowDefinitionService(repository)
    scope = service.scope("tenant-a", "domain-a")
    record = service.create(scope, "human:a", "Flow", bound_content())
    candidate = copy.deepcopy(record["revisions"][-1]["content"])
    candidate["description"] = "unrelated edit"
    if replacement == "omitted":
        candidate["tasks"][0].pop("skillOperationBindings")
    else:
        candidate["tasks"][0]["skillOperationBindings"] = None

    with pytest.raises(
        WorkflowDefinitionFailure,
        match="SKILL_OPERATION_BINDING_PRESERVATION_REQUIRED",
    ):
        service.edit(scope, record["workflowDefinitionId"], "human:a", 1, candidate)

    unchanged = repository.get(scope, record["workflowDefinitionId"])
    assert unchanged["aggregateVersion"] == 1
    assert len(unchanged["revisions"]) == 1


def test_explicit_binding_round_trip_and_historical_omission_compatibility():
    repository = InMemoryWorkflowDefinitionRepository()
    service = WorkflowDefinitionService(repository)
    scope = service.scope("tenant-a", "domain-a")
    bound = service.create(scope, "human:a", "Bound", bound_content())
    candidate = copy.deepcopy(bound["revisions"][-1]["content"])
    candidate["description"] = "unrelated edit"
    edited = service.edit(scope, bound["workflowDefinitionId"], "human:a", 1, candidate)
    assert (
        edited["revisions"][-1]["content"]["tasks"][0]["skillOperationBindings"]
        == bound["revisions"][-1]["content"]["tasks"][0]["skillOperationBindings"]
    )

    historical = service.create(scope, "human:a", "Historical", content())
    original_digest = historical["revisions"][0]["digest"]
    historical_candidate = copy.deepcopy(historical["revisions"][-1]["content"])
    historical_candidate["description"] = "historical compatible edit"
    historical_edited = service.edit(
        scope,
        historical["workflowDefinitionId"],
        "human:a",
        1,
        historical_candidate,
    )
    assert (
        "skillOperationBindings"
        not in historical_edited["revisions"][0]["content"]["tasks"][0]
    )
    assert historical_edited["revisions"][0]["digest"] == original_digest


def test_workbench_list_and_exact_revision_projection_do_not_expand_disclosure():
    repository = InMemoryWorkflowDefinitionRepository()
    service = WorkflowDefinitionService(repository)
    scope = service.scope("tenant-a", "domain-a")
    created = service.create(scope, "human:a", "Flow", content())
    successor_content = copy.deepcopy(created["revisions"][0]["content"])
    successor_content["description"] = "second revision"
    edited = service.edit(
        scope,
        created["workflowDefinitionId"],
        "human:a",
        1,
        successor_content,
    )
    first_revision = created["revisions"][0]

    listed = service.list_for_workbench(object(), scope, authorized=True)
    assert listed["count"] == 1
    assert "revisions" not in listed["items"][0]

    exact = service.read_revision_for_workbench(
        object(),
        scope,
        created["workflowDefinitionId"],
        first_revision["revisionId"],
        authorized=True,
    )
    assert exact["revision"] == first_revision
    assert exact["technicalProjection"]["revisionId"] == first_revision["revisionId"]
    assert edited["revisions"][1]["revisionId"] not in repr(exact)


def test_workbench_exact_revision_missing_is_a_scoped_not_found():
    repository = InMemoryWorkflowDefinitionRepository()
    service = WorkflowDefinitionService(repository)
    scope = service.scope("tenant-a", "domain-a")
    created = service.create(scope, "human:a", "Flow", content())

    with pytest.raises(
        WorkflowDefinitionFailure, match="WORKFLOW_REVISION_NOT_FOUND"
    ) as raised:
        service.read_revision_for_workbench(
            object(),
            scope,
            created["workflowDefinitionId"],
            "workflow-revision:not-authorized-or-missing",
            authorized=True,
        )
    assert raised.value.status == 404
