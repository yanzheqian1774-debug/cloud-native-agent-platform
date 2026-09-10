from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    InstanceLifecycle,
    InstanceRecord,
)
from agent_console.digital_employee_definition import EmployeeDefinitionError
from agent_console.execution_domain import ExecutionPersistenceError, ScopeIdentity
from agent_console.execution_postgres import (
    AssignmentId,
    DigitalEmployeeInstanceId,
)
from agent_console.workbench_employee import (
    DigitalEmployeeOwnerAdapter,
    EmployeeDefinitionOwnerAdapter,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)


def call(connection=None):
    if connection is None:
        connection = object()
    return AuthorizedOwnerCall(
        operation="READ_EMPLOYEE_REVISION",
        context=TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-a", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        ),
        connection=connection,
        payload={},
        path={
            "employee_definition_id": "employee-definition:quality",
            "revision_id": "employee-revision:v1",
        },
        query={},
        decisions=(),
        authority=SimpleNamespace(),
    )


def test_employee_owner_uses_caller_connection_and_discloses_one_revision() -> None:
    connection = object()

    class Repository:
        def read_revision_for_workbench(
            self, actual_connection, scope, definition_id, revision_id, *, authorized
        ):
            assert actual_connection is connection
            assert (scope.namespace, scope.security_domain) == ("tenant-a", "quality")
            assert (definition_id, revision_id, authorized) == (
                "employee-definition:quality",
                "employee-revision:v1",
                True,
            )
            return {
                "digest": "d" * 64,
                "revision": {
                    "schemaVersion": "digital-employee-composition.v1",
                    "namespace": "tenant-a",
                    "securityDomain": "quality",
                    "definitionId": definition_id,
                    "revisionId": revision_id,
                    "role": "Quality owner",
                    "responsibilities": ["Review quality"],
                    "members": [
                        {
                            "kind": "AGENT",
                            "resource_id": "agent-definition:quality",
                            "revision_id": "agent-revision:v1",
                            "digest": "a" * 64,
                        }
                    ],
                    "predecessorRevisionId": "employee-revision:older",
                },
                "facts": [{"action": "PUBLISH"}],
                "otherRevision": {"revisionId": "employee-revision:v2"},
            }

    result = EmployeeDefinitionOwnerAdapter(Repository())(call(connection))

    assert result == {
        "resourceKind": "DIGITAL_EMPLOYEE_DEFINITION",
        "employeeDefinitionId": "employee-definition:quality",
        "employeeDefinitionRevisionId": "employee-revision:v1",
        "employeeDefinitionDigest": "d" * 64,
        "role": "Quality owner",
        "responsibilities": ["Review quality"],
        "members": [
            {
                "kind": "AGENT",
                "resourceId": "agent-definition:quality",
                "revisionId": "agent-revision:v1",
                "digest": "a" * 64,
            }
        ],
    }
    assert "older" not in repr(result)
    assert "employee-revision:v2" not in repr(result)
    assert "PUBLISH" not in repr(result)


@pytest.mark.parametrize(
    ("reason", "status"),
    (
        ("INVALID_IDENTITY", 422),
        ("EMPLOYEE_NOT_FOUND", 404),
        ("EMPLOYEE_RECORD_CORRUPT", 503),
    ),
)
def test_employee_owner_preserves_bounded_error_semantics(reason, status) -> None:
    class Repository:
        def read_revision_for_workbench(self, *args, **kwargs):
            raise EmployeeDefinitionError(reason)

    with pytest.raises(WorkbenchOwnerError) as raised:
        EmployeeDefinitionOwnerAdapter(Repository())(call())

    expected_reason = (
        "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE"
        if reason == "EMPLOYEE_RECORD_CORRUPT"
        else reason
    )
    assert raised.value.reason_code == expected_reason
    assert raised.value.status_code == status


def digital_call(operation, path, connection=None):
    value = call(connection)
    return AuthorizedOwnerCall(
        operation=operation,
        context=value.context,
        connection=value.connection,
        payload={},
        path=path,
        query={},
        decisions=(),
        authority=SimpleNamespace(),
    )


def test_instance_owner_uses_caller_connection_and_minimal_projection() -> None:
    connection = object()
    scope = ScopeIdentity("tenant-a", "quality")
    instance = InstanceRecord(
        scope,
        DigitalEmployeeInstanceId("instance:quality"),
        7,
        DefinitionReference(
            "employee-definition:quality",
            "employee-revision:v1",
            "d" * 64,
            True,
            True,
            "DIGITAL_EMPLOYEE_DEFINITION_V1",
        ),
        "human:owner",
        "organization:quality",
        InstanceLifecycle.ENABLED,
        "workspace:private",
        "model:private",
        ("policy:private",),
        datetime(2029, 1, 1, tzinfo=UTC),
        datetime(2029, 1, 2, tzinfo=UTC),
    )

    class Repository:
        def read_instance_for_workbench(
            self, actual_connection, actual_scope, instance_id, *, authorized
        ):
            assert actual_connection is connection
            assert actual_scope == scope
            assert instance_id == instance.instance_id
            assert authorized is True
            return instance

    result = DigitalEmployeeOwnerAdapter(Repository())(
        digital_call(
            "READ_EMPLOYEE_INSTANCE",
            {"instance_id": "instance:quality"},
            connection,
        )
    )

    assert result["instanceId"] == "instance:quality"
    assert result["employeeDefinition"]["employeeDefinitionRevisionId"] == (
        "employee-revision:v1"
    )
    assert result["ownerId"] == "human:owner"
    assert result["organizationId"] == "organization:quality"
    assert result["lifecycle"] == "ENABLED"
    assert result["execution"]["reasonCode"] == "EXECUTION_NOT_ASSEMBLED"
    assert result["health"]["reasonCode"] == "HEALTH_NOT_ASSEMBLED"
    assert "workspace:private" not in repr(result)
    assert "model:private" not in repr(result)
    assert "policy:private" not in repr(result)
    assert "version" not in repr(result).lower()


def test_assignment_owner_checks_parent_and_uses_minimal_projection() -> None:
    connection = object()
    scope = ScopeIdentity("tenant-a", "quality")
    assignment = AssignmentRecord(
        scope,
        AssignmentId("assignment:review"),
        DigitalEmployeeInstanceId("instance:quality"),
        "human:reviewer",
        "Quality reviewer",
        AssignmentLifecycle.ACTIVE,
        datetime(2029, 1, 1, tzinfo=UTC),
        None,
        4,
        "command:private",
    )

    class Repository:
        def read_assignment_for_workbench(
            self,
            actual_connection,
            actual_scope,
            instance_id,
            assignment_id,
            *,
            authorized,
        ):
            assert actual_connection is connection
            assert actual_scope == scope
            assert instance_id == assignment.instance_id
            assert assignment_id == assignment.assignment_id
            assert authorized is True
            return assignment

    result = DigitalEmployeeOwnerAdapter(Repository())(
        digital_call(
            "READ_EMPLOYEE_ASSIGNMENT",
            {
                "instance_id": "instance:quality",
                "assignment_id": "assignment:review",
            },
            connection,
        )
    )

    assert result["assignmentId"] == "assignment:review"
    assert result["instanceId"] == "instance:quality"
    assert result["assigneeId"] == "human:reviewer"
    assert result["businessRole"] == "Quality reviewer"
    assert result["binding"]["reasonCode"] == "WORKFLOW_BINDING_NOT_ASSEMBLED"
    assert "command:private" not in repr(result)
    assert "version" not in repr(result).lower()


@pytest.mark.parametrize(
    ("operation", "reason"),
    (
        ("READ_EMPLOYEE_INSTANCE", "INSTANCE_NOT_FOUND"),
        ("READ_EMPLOYEE_ASSIGNMENT", "ASSIGNMENT_NOT_FOUND"),
    ),
)
def test_digital_employee_missing_is_hidden(operation, reason) -> None:
    class Repository:
        def read_instance_for_workbench(self, *args, **kwargs):
            return None

        def read_assignment_for_workbench(self, *args, **kwargs):
            return None

    path = {
        "instance_id": "instance:quality",
        "assignment_id": "assignment:review",
    }
    with pytest.raises(WorkbenchOwnerError) as raised:
        DigitalEmployeeOwnerAdapter(Repository())(digital_call(operation, path))

    assert raised.value.reason_code == reason
    assert raised.value.status_code == 404


def test_digital_employee_storage_error_is_fail_closed() -> None:
    class Repository:
        def read_instance_for_workbench(self, *args, **kwargs):
            raise ExecutionPersistenceError("EXECUTION_STORAGE_UNAVAILABLE")

    with pytest.raises(WorkbenchOwnerError) as raised:
        DigitalEmployeeOwnerAdapter(Repository())(
            digital_call("READ_EMPLOYEE_INSTANCE", {"instance_id": "instance:quality"})
        )

    assert raised.value.reason_code == "EXECUTION_STORAGE_UNAVAILABLE"
    assert raised.value.status_code == 503
