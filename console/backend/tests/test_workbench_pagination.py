import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_pagination import WorkbenchCursorCodec


def context(tenant: str = "tenant-a") -> TrustedRequestContext:
    return TrustedRequestContext(
        "human:alice",
        AuthorityScope(tenant, "quality"),
        "session-one",
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )


def test_cursor_is_signed_and_bound_to_route_scope_query_and_key_shape() -> None:
    codec = WorkbenchCursorCodec(b"k" * 32)
    cursor = codec.mint(
        route="EMPLOYEE_LIST",
        context=context(),
        page_size=50,
        last_key=("employee-definition:one", "employee-revision:one"),
    )

    assert codec.resolve(
        cursor,
        route="EMPLOYEE_LIST",
        context=context(),
        page_size=50,
        key_size=2,
    ) == ("employee-definition:one", "employee-revision:one")

    for values in (
        {"token": cursor[:-1] + ("0" if cursor[-1] != "0" else "1")},
        {"route": "AGENT_LIST"},
        {"context": context("tenant-b")},
        {"page_size": 51},
        {"key_size": 1},
    ):
        with pytest.raises(WorkbenchOwnerError, match="REQUEST_INVALID"):
            codec.resolve(
                values.get("token", cursor),
                route=values.get("route", "EMPLOYEE_LIST"),
                context=values.get("context", context()),
                page_size=values.get("page_size", 50),
                key_size=values.get("key_size", 2),
            )
