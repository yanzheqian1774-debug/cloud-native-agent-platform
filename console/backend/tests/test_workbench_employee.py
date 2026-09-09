from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.digital_employee_definition import EmployeeDefinitionError
from agent_console.workbench_employee import EmployeeDefinitionOwnerAdapter
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
