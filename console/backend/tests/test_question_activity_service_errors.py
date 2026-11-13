"""Real BFF status boundary; service failure is never browser logout."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.question_activity_input import (
    QuestionActivityInput,
    QuestionActivityRequest,
)
from agent_console.workbench_bff import (
    PREFIX,
    WorkbenchBffPolicy,
    WorkbenchOperation,
    create_workbench_bff,
)
from fastapi.testclient import TestClient
from psycopg import OperationalError
from test_workbench_bff import AuthorizerStub, SessionStub, login


def client_for(failure):
    calls = []

    def authenticate(context):
        calls.append(context)
        raise failure

    automation = SimpleNamespace(authenticate=authenticate)
    sessions, authorizer = SessionStub(), AuthorizerStub()
    operation = WorkbenchOperation(
        "PREPARE_QUESTION_ACTIVITY_INPUT",
        "POST",
        PREFIX + "/question-activity-input",
        QuestionActivityRequest,
        None,
        lambda *args: (
            ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        ),
        QuestionActivityInput(automation),
    )
    app = create_workbench_bff(
        sessions,
        authorizer,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        operations=(operation,),
    )
    return (
        TestClient(app, base_url="https://console.example"),
        sessions,
        authorizer,
        calls,
    )


def post(client):
    return client.post(
        PREFIX + "/question-activity-input",
        headers={"origin": "https://console.example", "x-csrf-token": "csrf-token"},
        json={
            "question": "Check the confirmed document",
            "idempotencyKey": "same-input",
        },
    )


@pytest.mark.parametrize(
    "failure,status,code",
    [
        (
            AuthorityError("AUTHENTICATION_REQUIRED"),
            503,
            "QUESTION_INPUT_SERVICE_UNAVAILABLE",
        ),
        (
            AuthorityError("AUTHORIZATION_NOT_FOUND"),
            503,
            "QUESTION_INPUT_SERVICE_UNAVAILABLE",
        ),
        (
            AuthorityError("RESOURCE_POLICY_SCOPE_DENIED"),
            403,
            "QUESTION_INPUT_SERVICE_ACCESS_DENIED",
        ),
        (
            OperationalError("private storage host"),
            503,
            "QUESTION_INPUT_SERVICE_UNAVAILABLE",
        ),
        (OSError("private credential path"), 503, "QUESTION_INPUT_SERVICE_UNAVAILABLE"),
    ],
)
def test_backend_auth_failure_preserves_live_browser_session(failure, status, code):
    client, sessions, authorizer, calls = client_for(failure)
    login(client)
    response = post(client)
    assert response.status_code == status
    assert response.json()["reasonCode"] == code
    assert "private" not in response.text
    assert not sessions.logged_out
    assert client.get(PREFIX + "/session").status_code == 200
    assert len(calls) == 1
    assert len(authorizer.calls) == 1
    assert authorizer.calls[0][1] == (
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
    )


def test_actual_expired_browser_still_returns_401_without_service_call():
    client, sessions, authorizer, calls = client_for(
        AuthorityError("AUTHENTICATION_REQUIRED")
    )
    login(client)
    sessions.logged_out = True
    assert post(client).status_code == 401
    assert calls == [] and authorizer.calls == []


def test_entry_permission_denial_is_not_relabelled_as_service_authentication():
    client, sessions, authorizer, calls = client_for(
        AuthorityError("AUTHENTICATION_REQUIRED")
    )
    login(client)

    def denied(*args, **kwargs):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    authorizer.execute = denied
    response = post(client)
    assert response.status_code == 404  # Existing minimum-disclosure entry boundary.
    assert response.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
    assert calls == [] and not sessions.logged_out
