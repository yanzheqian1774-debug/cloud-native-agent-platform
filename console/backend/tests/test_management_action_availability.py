"""Read-only exact action observations, using the real authority port."""

from datetime import UTC, datetime
from types import SimpleNamespace as S

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.workbench_management_actions import employee_projection
from agent_console.workbench_owner_authorization import AuthorizedOwnerAuthority


def test_current_action_reader_keeps_decisions_and_transaction_unchanged():
    observed = []
    connection = object()
    context = S(
        principal_id="person", scope=S(tenant_id="tenant", security_domain="domain")
    )

    def read(ctx, grants, **kwargs):
        observed.append((ctx, grants, kwargs))
        return (False, True)

    adapter = S(
        authorization=S(has_current_grants=read),
        clock=lambda: datetime(2026, 11, 14, tzinfo=UTC),
        controller=S(readiness=S(recovery_epoch=3)),
    )
    authority = AuthorizedOwnerAuthority(adapter, context, connection, 8, ())
    grants = (
        ExactGrant("TEAM", "CREATE", "team:collection"),
        ExactGrant("TEAM", "REVISE", "team:one:aggregate"),
    )
    assert authority.current_action_grants(grants) == (False, True)
    assert authority.decisions == {}
    assert observed == [
        (
            context,
            grants,
            {
                "now": adapter.clock(),
                "generation": 8,
                "recovery_epoch": 3,
                "connection": connection,
                "configure_transaction": False,
                "require_available": True,
            },
        )
    ]


@pytest.mark.parametrize(
    "head,lifecycle,expected",
    [
        ("rev", "DRAFT", {"CREATE", "VALIDATE"}),
        ("rev", "VALIDATED", {"CREATE", "APPROVE"}),
        ("rev", "APPROVED", {"CREATE", "PUBLISH"}),
        ("other", "DRAFT", {"VALIDATE"}),
    ],
)
def test_employee_current_actions_keep_actual_targets_and_lifecycle(
    head, lifecycle, expected
):
    seen = []

    def read(grants):
        seen.extend(grants)
        return tuple(True for _ in grants)

    authority = S(
        current_action_grants=read,
        generation=4,
        adapter=S(
            controller=S(readiness=S(recovery_epoch=1)),
            clock=lambda: datetime(2026, 11, 14, tzinfo=UTC),
        ),
    )
    call = S(
        authority=authority,
        context=S(
            principal_id="person", scope=S(tenant_id="tenant", security_domain="domain")
        ),
    )
    definition = {
        "employeeDefinitionId": "employee:one",
        "employeeDefinitionRevisionId": "rev",
        "employeeDefinitionDigest": "a" * 64,
        "aggregateVersion": 2,
        "lifecycleState": lifecycle,
    }
    value = employee_projection(call, definition, successor_available=head == "rev")
    assert {
        name for name, state in value["actions"].items() if state["lifecycleEligible"]
    } == expected
    assert seen[0] == ExactGrant("EMPLOYEE", "CREATE", "employee:collection")
    assert all(
        grant.exact_resource == "employee:employee:one:aggregate" for grant in seen[1:]
    )
    assert value["authorityGranted"] is False and value["executionStarted"] is False


def test_permission_unavailable_is_not_denied_or_a_missing_readable_resource():
    from agent_console.authority_contracts import AuthorityError
    from agent_console.workbench_management_actions import collection_projection

    def unavailable(grants):
        raise AuthorityError("AUTHORIZATION_STATE_UNAVAILABLE")

    authority = S(
        current_action_grants=unavailable,
        generation=4,
        adapter=S(
            controller=S(readiness=S(recovery_epoch=1)),
            clock=lambda: datetime(2026, 11, 14, tzinfo=UTC),
        ),
    )
    call = S(
        authority=authority,
        context=S(
            principal_id="person", scope=S(tenant_id="tenant", security_domain="domain")
        ),
    )
    value = collection_projection(call, "TEAM")
    assert value["status"] == "UNAVAILABLE" and value["actions"] == {}
    assert value["authorityGranted"] is False


@pytest.mark.parametrize(
    "operation,grants,path,query",
    [
        ("ARBITRARY_OPERATION", (), {}, {}),
        ("READ_TEAM_CAPABILITIES", (), {"subject": "other"}, {}),
        ("READ_TEAM_CAPABILITIES", (), {}, {"target": "other"}),
        (
            "READ_EMPLOYEE_CAPABILITIES",
            (ExactGrant("EMPLOYEE", "CREATE", "employee:collection"),),
            {},
            {},
        ),
    ],
)
def test_observation_exception_is_not_a_general_empty_grant_gateway(
    operation, grants, path, query
):
    from agent_console.authority_contracts import AuthorityError
    from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization

    owner = object.__new__(WorkbenchOwnerAuthorization)
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        owner.execute(
            S(),
            grants,
            operation=operation,
            payload={},
            path=path,
            query=query,
            handler=lambda call: pytest.fail("must not enter handler"),
        )
