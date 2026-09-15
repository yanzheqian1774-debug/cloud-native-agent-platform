import pytest
from agent_console.workflow_definition_repository import (
    InMemoryWorkflowDefinitionRepository,
    WorkflowDefinitionConflict,
    WorkflowDefinitionNotFound,
    WorkflowScope,
)


def record(scope: WorkflowScope):
    return {
        "namespace": scope.namespace,
        "securityDomain": scope.security_domain,
        "workflowDefinitionId": "workflow-definition:one",
        "aggregateVersion": 1,
        "reviews": [{"reviewId": "workflow-review:one"}],
        "revisions": [
            {"revisionId": "workflow-revision:one", "state": "PUBLISHED"},
            {"revisionId": "workflow-revision:two", "state": "DRAFT"},
        ],
        "facts": [{"factId": "workflow-fact:create"}],
    }


def test_repository_is_scope_isolated_and_compare_and_set():
    repository = InMemoryWorkflowDefinitionRepository()
    scope = WorkflowScope("tenant-a", "quality")
    other = WorkflowScope("tenant-b", "quality")
    created = repository.create(record(scope))
    assert repository.get(scope, created["workflowDefinitionId"]) == created
    with pytest.raises(WorkflowDefinitionNotFound):
        repository.get(other, created["workflowDefinitionId"])
    changed = {**created, "aggregateVersion": 2}
    repository.replace(
        changed,
        expected_version=1,
        fact={"factId": "workflow-fact:update"},
    )
    with pytest.raises(WorkflowDefinitionConflict):
        repository.replace(
            changed,
            expected_version=1,
            fact={"factId": "workflow-fact:stale"},
        )


def test_repository_returns_defensive_copies():
    repository = InMemoryWorkflowDefinitionRepository()
    scope = WorkflowScope("tenant-a", "quality")
    created = repository.create(record(scope))
    created["aggregateVersion"] = 99
    assert repository.get(scope, "workflow-definition:one")["aggregateVersion"] == 1


def test_caller_owned_workbench_reads_are_authorized_and_minimally_disclosed():
    repository = InMemoryWorkflowDefinitionRepository()
    scope = WorkflowScope("tenant-a", "quality")
    repository.create(record(scope))

    with pytest.raises(WorkflowDefinitionNotFound):
        repository.list_for_workbench(object(), scope, authorized=False)
    with pytest.raises(WorkflowDefinitionNotFound):
        repository.read_revision_for_workbench(
            object(),
            scope,
            "workflow-definition:one",
            "workflow-revision:one",
            authorized=False,
        )

    listed = repository.list_for_workbench(object(), scope, authorized=True)
    assert set(listed[0]).isdisjoint({"facts", "reviews", "revisions"})
    exact = repository.read_revision_for_workbench(
        object(),
        scope,
        "workflow-definition:one",
        "workflow-revision:one",
        authorized=True,
    )
    assert exact["revision"]["revisionId"] == "workflow-revision:one"
    assert set(exact["definition"]).isdisjoint({"facts", "reviews", "revisions"})
    assert "workflow-revision:two" not in repr(exact)
