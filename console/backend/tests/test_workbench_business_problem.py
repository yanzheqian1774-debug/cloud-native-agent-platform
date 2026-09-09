from __future__ import annotations

from types import SimpleNamespace

from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.workbench_business_problem import BusinessProblemOwnerAdapter
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall


class Problems:
    def __init__(self) -> None:
        self.connection = None

    def list_problems(self, scope, *, authorized, connection):
        assert authorized
        assert (scope.namespace, scope.security_domain) == ("tenant-a", "quality")
        self.connection = connection
        return ()

    def create_problem(self, revision, **values):
        assert values["authorized"]
        self.connection = values["connection"]
        return revision


class Authority:
    def __init__(self) -> None:
        self.grants = []

    def require(self, principal, owner, action, resource):
        self.grants.append((principal.principal_id, owner, action, resource))
        return SimpleNamespace(decision_id="decision-one")


def call(operation, payload):
    connection = object()
    problems = Problems()
    authority = Authority()
    application = SimpleNamespace(
        uow=SimpleNamespace(problems=problems, control=object()),
        workflows=object(),
        employees=object(),
        instances=object(),
    )
    result = BusinessProblemOwnerAdapter(application)(
        AuthorizedOwnerCall(
            operation=operation,
            context=TrustedRequestContext(
                "human:alice",
                AuthorityScope("tenant-a", "quality"),
                "session-one",
                AuthenticationSource.BROWSER_SESSION,
                "policy-1",
            ),
            connection=connection,
            payload=payload,
            path={},
            query={},
            decisions=(),
            authority=authority,  # type: ignore[arg-type]
        )
    )
    return result, problems, authority, connection


def test_list_uses_trusted_context_and_caller_owned_connection() -> None:
    result, problems, authority, connection = call("LIST_PROBLEMS", {})
    assert result == {"problems": []}
    assert problems.connection is connection
    assert authority.grants == [
        (
            "human:alice",
            "BUSINESS_PROBLEM",
            "LIST",
            "business-problem:collection",
        )
    ]


def test_create_keeps_owner_identity_and_write_on_caller_connection() -> None:
    result, problems, authority, connection = call(
        "CREATE_PROBLEM",
        {
            "title": "Supplier quality",
            "description": "Reduce escaped defects",
            "ownerId": "business-owner-7",
            "idempotencyKey": "create-problem-7",
        },
    )
    assert problems.connection is connection
    assert result["revision"]["created_by"] == "human:alice"
    assert result["revision"]["owner_id"] == "business-owner-7"
    assert [item[1:] for item in authority.grants] == [
        ("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        ("BUSINESS_PROBLEM", "READ", "business-problem:collection"),
    ]
