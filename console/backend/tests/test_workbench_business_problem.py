from __future__ import annotations

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.workbench_business_problem import BusinessProblemOwnerAdapter
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall


class Problems:
    def __init__(self) -> None:
        self.connection = None
        self.create_calls = 0

    def list_problems(self, scope, *, authorized, connection):
        assert authorized
        assert (scope.namespace, scope.security_domain) == ("tenant-a", "quality")
        self.connection = connection
        return ()

    def create_problem(self, revision, **values):
        self.create_calls += 1
        assert values["authorized"]
        assert values["receipt_policy_generation"] == 7
        assert values["receipt_recovery_epoch"] == 11
        self.connection = values["connection"]
        return revision

    def get_creator_receipt(self, scope, creator, key, **values):
        assert (scope.namespace, scope.security_domain) == ("tenant-a", "quality")
        assert creator == "human:alice"
        assert key == "create-problem-7"
        assert values["authorized"]
        assert values["connection"] is self.connection
        return SimpleNamespace(receipt_started_at="database-time")


class Authority:
    def __init__(self, *, deny_create: bool = False) -> None:
        self.grants = []
        self.deny_create = deny_create

    def require(self, principal, owner, action, resource):
        self.grants.append((principal.principal_id, owner, action, resource))
        if self.deny_create and action == "CREATE":
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return SimpleNamespace(decision_id="decision-one")


def call(operation, payload, *, authority=None, problems=None):
    connection = object()
    problems = problems or Problems()
    authority = authority or Authority()
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
            policy_generation=7,
            recovery_epoch=11,
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
    ]


def test_create_denial_stops_before_repository_write() -> None:
    authority = Authority(deny_create=True)
    problems = Problems()
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        call(
            "CREATE_PROBLEM",
            {
                "title": "Supplier quality",
                "description": "Reduce escaped defects",
                "ownerId": "business-owner-7",
                "idempotencyKey": "create-problem-denied",
            },
            authority=authority,
            problems=problems,
        )
    assert problems.create_calls == 0
    assert authority.grants == [
        (
            "human:alice",
            "BUSINESS_PROBLEM",
            "CREATE",
            "business-problem:collection",
        )
    ]


def test_explicit_criterion_case_requires_exact_problem_read_before_owner():
    from agent_console.workbench_business_problem import (
        CreateCaseCriterion,
        _criterion_write,
    )

    payload = CreateCaseCriterion.model_validate(
        {
            "problemId": "exact-problem",
            "criterionType": "DETERMINISTIC_BOOLEAN",
            "measurement": {"expected": True},
            "requiredEvidenceKinds": [],
            "evaluatorType": "SYNTHETIC_DELIVERY",
            "evaluatorVersion": "1",
            "idempotencyKey": "new-criterion",
        }
    ).model_dump()
    grants = _criterion_write(None, {}, payload, {})
    assert any(
        g.owner == "BUSINESS_PROBLEM"
        and g.action == "READ"
        and g.exact_resource == "business-problem:exact-problem"
        for g in grants
    )
