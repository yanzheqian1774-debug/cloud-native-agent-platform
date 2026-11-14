from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization


def adapter(*, denied_identity=False, unavailable=False):
    calls = []
    connection = NS(execute=lambda sql: calls.append(sql))

    def grants(ctx, probes, **kwargs):
        assert kwargs["require_available"] is True
        assert len(probes) == 1 and probes[0].action == "LIST"
        if unavailable:
            raise AuthorityError("AUTHORIZATION_STATE_UNAVAILABLE")
        return (False,)

    def identity(*args, **kwargs):
        calls.append("identity")
        assert kwargs["connection"] is connection
        if denied_identity:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    value = WorkbenchOwnerAuthorization(
        NS(
            protected_request=lambda: nullcontext(NS(generation=3)),
            readiness=NS(recovery_epoch=1),
        ),
        NS(connection_scope=lambda: nullcontext(connection)),
        NS(has_current_grants=grants, require_current_context=identity),
        clock=lambda: datetime.now(UTC),
    )
    return value, calls


def execute(value, **kwargs):
    return value.execute(
        NS(),
        (),
        operation="LIST_CURRENT_WORK",
        path={},
        payload={},
        query={"state": "all"},
        handler=lambda call: (call.decisions, call.authority.decisions),
        **kwargs,
    )


def test_fixed_directory_current_identity_not_list_decision():
    value, calls = adapter()
    assert execute(value) == ((), {})
    assert "identity" in calls


@pytest.mark.parametrize("failure", ["denied_identity", "unavailable"])
def test_expired_or_unknown_identity_cannot_be_empty_success(failure):
    value, _ = adapter(**{failure: True})
    with pytest.raises(AuthorityError):
        execute(value)


def test_other_empty_grant_operation_remains_forbidden():
    value, _ = adapter()
    with pytest.raises(AuthorityError):
        value.execute(
            NS(),
            (),
            operation="LIST_PROBLEMS",
            path={},
            query={},
            payload={},
            handler=lambda call: pytest.fail("called"),
        )


@pytest.mark.parametrize(
    "field,value",
    [("path", {"id": "x"}), ("payload", {"x": 1}), ("query", {"principalId": "other"})],
)
def test_directory_exception_cannot_be_used_for_arbitrary_commands(field, value):
    auth, _ = adapter()
    args = dict(
        operation="LIST_CURRENT_WORK",
        path={},
        payload={},
        query={},
        handler=lambda call: pytest.fail("called"),
    )
    args[field] = value
    with pytest.raises((AuthorityError, ValueError)):
        auth.execute(NS(), (), **args)
