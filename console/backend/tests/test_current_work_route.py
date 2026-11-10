"""Actual BFF route/authentication boundary with a controlled owner body."""

from dataclasses import replace

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.workbench_bff import PREFIX, WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_current_work import operations
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_pagination import WorkbenchCursorCodec
from fastapi.testclient import TestClient
from test_workbench_bff import AuthorizerStub, SessionStub, login


def client_for(handler=None):
    sessions, authorizer = SessionStub(), AuthorizerStub()
    operation = operations(WorkbenchCursorCodec(b"c" * 32))[0]
    operation = replace(
        operation, handler=handler or (lambda call: {"query": call.query})
    )
    app = create_workbench_bff(
        sessions,
        authorizer,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        operations=(operation,),
    )
    return TestClient(app, base_url="https://console.example"), authorizer


def test_route_requires_login_and_exact_problem_collection_grant():
    client, authorizer = client_for()
    response = client.get(PREFIX + "/current-work")
    assert response.status_code == 401
    assert not authorizer.calls
    login(client)
    response = client.get(PREFIX + "/current-work?scopeFilter=initiated&pageSize=20")
    assert response.status_code == 200
    assert response.json()["result"]["query"]["scopeFilter"] == "initiated"
    assert authorizer.calls[0][1] == (
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
    )


@pytest.mark.parametrize(
    "query",
    [
        "pageSize=0",
        "pageSize=101",
        "pageSize=1&pageSize=2",
        "scopeFilter=everyone",
        "state=invented",
        "administrator=true",
        "principalId=human:bob",
        "query=" + "x" * 201,
    ],
)
def test_invalid_query_never_reaches_owner(query):
    client, authorizer = client_for()
    login(client)
    response = client.get(PREFIX + "/current-work?" + query)
    assert response.status_code == 422
    assert response.json()["reasonCode"] == "REQUEST_INVALID"
    assert not authorizer.calls


def test_unavailable_authority_returns_failure_instead_of_empty_success():
    def failed(call):
        raise WorkbenchOwnerError("CURRENT_WORK_AUTHORITY_UNAVAILABLE", 503)

    client, _authorizer = client_for(failed)
    login(client)
    response = client.get(PREFIX + "/current-work")
    assert response.status_code == 503
    assert response.json()["reasonCode"] == "CURRENT_WORK_AUTHORITY_UNAVAILABLE"
    assert "result" not in response.json()
