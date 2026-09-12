from types import SimpleNamespace

import pytest
from agent_console.agent_definition_repository import (
    AgentDefinitionNotFound,
    AgentDefinitionRepositoryError,
)
from agent_console.agent_definition_service import agent_revision_digest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.workbench_agent import (
    AgentDefinitionListOwnerAdapter,
    AgentDefinitionOwnerAdapter,
    agent_operations,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec


def record() -> dict:
    value = {
        "definitionId": "agent-definition:quality",
        "name": "Quality agent",
        "namespace": "tenant-a",
        "securityDomain": "quality",
        "publishedRevisionId": "agent-revision:v1",
        "enabled": True,
        "archived": False,
        "revisions": [
            {
                "revisionId": "agent-revision:v1",
                "predecessorRevisionId": None,
                "state": "PUBLISHED",
                "content": {
                    "title": "Quality analyst",
                    "duties": ["Review quality"],
                    "data": ["private"],
                    "knowledge": ["private"],
                    "skills": ["private"],
                    "capabilities": ["quality.review"],
                    "runtimes": ["private"],
                    "businessPurpose": "Prevent defects",
                    "bindings": {"private": True},
                },
                "createdAt": "2029-01-01T00:00:00Z",
            }
        ],
        "relationships": ["private"],
        "facts": ["private"],
    }
    value["revisions"][0]["digest"] = agent_revision_digest(
        value, value["revisions"][0]
    )
    return value


def call(connection=None) -> AuthorizedOwnerCall:
    return AuthorizedOwnerCall(
        operation="READ_AGENT_REVISION",
        context=TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-a", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        ),
        connection=object() if connection is None else connection,
        payload={},
        path={
            "definition_id": "agent-definition:quality",
            "revision_id": "agent-revision:v1",
        },
        query={},
        decisions=(),
        authority=SimpleNamespace(),
    )


def test_agent_owner_uses_caller_connection_and_discloses_one_revision() -> None:
    connection = object()
    stored = record()

    class Repository:
        def read_revision_for_workbench(
            self, actual_connection, scope, definition_id, revision_id, *, authorized
        ):
            assert actual_connection is connection
            assert (scope.namespace, scope.security_domain) == ("tenant-a", "quality")
            assert (definition_id, revision_id, authorized) == (
                "agent-definition:quality",
                "agent-revision:v1",
                True,
            )
            return {"record": stored, "revision": stored["revisions"][0]}

    result = AgentDefinitionOwnerAdapter(Repository())(call(connection))

    assert result == {
        "definitionId": "agent-definition:quality",
        "revisionId": "agent-revision:v1",
        "digest": stored["revisions"][0]["digest"],
        "name": "Quality agent",
        "role": {
            "title": "Quality analyst",
            "duties": ["Review quality"],
            "businessPurpose": "Prevent defects",
            "capabilities": ["quality.review"],
        },
    }
    assert "private" not in repr(result)


def test_agent_operation_builds_only_the_exact_read_grant() -> None:
    operation = next(
        item
        for item in agent_operations(SimpleNamespace(), WorkbenchCursorCodec(b"k" * 32))
        if item.name == "READ_AGENT_REVISION"
    )
    grant = operation.grant_builder(call().context, call().path, {}, {})[0]

    assert (grant.owner, grant.action, grant.exact_resource) == (
        "AGENT",
        "READ",
        "agent:agent-definition:quality:agent-revision:v1",
    )


def test_agent_list_uses_formal_published_pointer_and_signed_keyset_cursor() -> None:
    first = record()
    draft = {
        **first["revisions"][0],
        "revisionId": "agent-revision:v2",
        "predecessorRevisionId": "agent-revision:v1",
        "state": "DRAFT",
    }
    draft["digest"] = agent_revision_digest(first, draft)
    first["revisions"].insert(0, draft)
    second = record()
    second["definitionId"] = "agent-definition:zeta"
    second["name"] = "Zeta agent"
    second["revisions"][0]["digest"] = agent_revision_digest(
        second, second["revisions"][0]
    )
    connection = object()

    class Repository:
        def list_published_for_workbench(
            self,
            actual_connection,
            scope,
            *,
            after_definition_id,
            limit,
            authorized,
        ):
            assert actual_connection is connection
            assert (scope.namespace, scope.security_domain) == ("tenant-a", "quality")
            assert after_definition_id is None
            assert (limit, authorized) == (2, True)
            return [first, second]

    codec = WorkbenchCursorCodec(b"k" * 32)
    value = call(connection)
    list_call = AuthorizedOwnerCall(
        operation="LIST_AGENTS",
        context=value.context,
        connection=connection,
        payload={},
        path={},
        query={"pageSize": 1},
        decisions=(),
        authority=SimpleNamespace(),
    )
    result = AgentDefinitionListOwnerAdapter(Repository(), codec)(list_call)

    assert result["items"] == [
        {
            "definitionId": "agent-definition:quality",
            "name": "Quality agent",
            "revisionId": "agent-revision:v1",
            "digest": first["revisions"][1]["digest"],
            "title": "Quality analyst",
            "enabled": True,
            "archived": False,
        }
    ]
    assert "agent-revision:v2" not in repr(result)
    assert codec.resolve(
        result["nextCursor"],
        route="AGENT_LIST",
        context=value.context,
        page_size=1,
        key_size=1,
    ) == ("agent-definition:quality",)


@pytest.mark.parametrize(
    ("failure", "reason", "status"),
    (
        (
            AgentDefinitionNotFound("AGENT_DEFINITION_NOT_FOUND"),
            "AGENT_NOT_FOUND",
            404,
        ),
        (
            AgentDefinitionRepositoryError("AGENT_DEFINITION_RECORD_CORRUPT"),
            "AGENT_DEFINITION_STORAGE_UNAVAILABLE",
            503,
        ),
    ),
)
def test_agent_owner_preserves_bounded_error_semantics(failure, reason, status) -> None:
    class Repository:
        def read_revision_for_workbench(self, *args, **kwargs):
            raise failure

    with pytest.raises(WorkbenchOwnerError) as raised:
        AgentDefinitionOwnerAdapter(Repository())(call())

    assert raised.value.reason_code == reason
    assert raised.value.status_code == status
