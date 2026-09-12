from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
from agent_console.workbench_workflow import WorkflowOwnerAdapter, workflow_operations


class WorkflowServiceStub:
    def __init__(self) -> None:
        self.calls = []

    @staticmethod
    def scope(namespace, security_domain):
        return namespace, security_domain

    def list_for_workbench(self, connection, scope, *, authorized):
        self.calls.append(("list", connection, scope, authorized))
        return {"items": [], "count": 0}

    def read_revision_for_workbench(
        self, connection, scope, resource_id, revision_id, *, authorized
    ):
        self.calls.append(
            ("read", connection, scope, resource_id, revision_id, authorized)
        )
        return {
            "definition": {"workflowDefinitionId": resource_id},
            "revision": {"revisionId": revision_id},
        }


def call(operation, *, connection):
    return AuthorizedOwnerCall(
        operation=operation,
        context=SimpleNamespace(
            scope=SimpleNamespace(tenant_id="tenant-a", security_domain="quality")
        ),
        connection=connection,
        payload={},
        path={
            "workflow_definition_id": "workflow-definition:one",
            "revision_id": "workflow-revision:one",
        },
        query={},
        decisions=(),
        authority=SimpleNamespace(),
    )


def test_workflow_registry_exposes_only_list_and_exact_revision_read() -> None:
    service = WorkflowServiceStub()
    operations = workflow_operations(service)  # type: ignore[arg-type]

    assert [(item.name, item.method, item.path) for item in operations] == [
        ("LIST_WORKFLOWS", "GET", "/api/workbench/v1/workflows"),
        (
            "READ_WORKFLOW_REVISION",
            "GET",
            "/api/workbench/v1/workflows/{workflow_definition_id}/revisions/{revision_id}",
        ),
    ]
    assert operations[0].grant_builder(None, {}, {}, {}) == (
        ExactGrant("WORKFLOW", "LIST", "workflow:collection"),
    )
    assert operations[1].grant_builder(
        None,
        {
            "workflow_definition_id": "workflow-definition:one",
            "revision_id": "workflow-revision:one",
        },
        {},
        {},
    ) == (
        ExactGrant(
            "WORKFLOW",
            "READ",
            "workflow:workflow-definition:one:workflow-revision:one",
        ),
    )


@pytest.mark.parametrize("operation", ["LIST_WORKFLOWS", "READ_WORKFLOW_REVISION"])
def test_workflow_adapter_reuses_caller_connection_and_trusted_scope(operation) -> None:
    service = WorkflowServiceStub()
    adapter = WorkflowOwnerAdapter(service)  # type: ignore[arg-type]
    connection = object()

    adapter(call(operation, connection=connection))

    actual = service.calls[0]
    assert actual[1] is connection
    assert actual[2] == ("tenant-a", "quality")
    assert actual[-1] is True


def test_owner_query_is_not_invoked_when_authorization_rejects() -> None:
    service = WorkflowServiceStub()
    operation = workflow_operations(service)[1]  # type: ignore[arg-type]

    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        grants = operation.grant_builder(
            None,
            {
                "workflow_definition_id": "workflow-definition:one",
                "revision_id": "workflow-revision:one",
            },
            {},
            {},
        )
        assert grants == (
            ExactGrant(
                "WORKFLOW",
                "READ",
                "workflow:workflow-definition:one:workflow-revision:one",
            ),
        )
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    assert service.calls == []
