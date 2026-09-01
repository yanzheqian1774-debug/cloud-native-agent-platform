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
