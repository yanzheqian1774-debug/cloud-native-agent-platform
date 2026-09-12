from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    BrowserSession,
    CredentialId,
    ExactGrant,
    SessionId,
    SessionSecret,
    TrustedRequestContext,
    VerifiedPrincipal,
)
from agent_console.workbench_bff import (
    PREFIX,
    WorkbenchBffPolicy,
    WorkbenchOperation,
    create_workbench_bff,
)
from agent_console.workbench_bff_schemas import WorkbenchPageQuery
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_employee import (
    digital_employee_operations,
    employee_operations,
)
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
from agent_console.workbench_pagination import WorkbenchCursorCodec
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict


class CreateProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


class SessionStub:
    def __init__(self) -> None:
        self.now = datetime(2029, 1, 1, tzinfo=UTC)
        self.secret = "opaque-session-secret"
        principal = VerifiedPrincipal(
            "human:alice",
            AuthorityScope("tenant-a", "quality"),
            CredentialId("credential-alice"),
            self.now + timedelta(hours=8),
            "policy-1",
        )
        self.session = BrowserSession(
            SessionId("session-one"),
            principal,
            self.now,
            self.now,
            self.now + timedelta(minutes=30),
            self.now + timedelta(hours=8),
            1,
            1,
        )
        self.context = TrustedRequestContext(
            "human:alice",
            principal.scope,
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        self.logged_out = False

    def clock(self) -> datetime:
        return self.now

    def issue_login_nonce(self) -> str:
        return "login-nonce"

    def create_session(self, nonce: str, credential: str) -> SessionSecret:
        if (nonce, credential) != ("login-nonce", "bootstrap-secret"):
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return SessionSecret(
            self.session.session_id, self.secret, self.session.absolute_expires_at
        )

    def authenticate_session(
        self, value: str
    ) -> tuple[BrowserSession, TrustedRequestContext]:
        if value != self.secret or self.logged_out:
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return self.session, self.context

    def issue_csrf(self, _: BrowserSession) -> str:
        return "csrf-token"

    def verify_csrf(self, token: str, _: BrowserSession) -> None:
        if token != "csrf-token":
            raise AuthorityError("CSRF_VALIDATION_FAILED")

    def rotate_session(self, value: str) -> SessionSecret:
        self.authenticate_session(value)
        self.secret = "rotated-session-secret"
        return SessionSecret(
            SessionId("session-two"),
            self.secret,
            self.session.absolute_expires_at,
        )

    def logout(self, value: str, *, actor_id: str) -> None:
        self.authenticate_session(value)
        assert actor_id == "human:alice"
        self.logged_out = True


class AuthorizerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[TrustedRequestContext, tuple[ExactGrant, ...]]] = []
        self.connection = object()

    def execute(self, context, grants, **values):
        self.calls.append((context, tuple(grants)))
        return values["handler"](
            AuthorizedOwnerCall(
                operation=values["operation"],
                context=context,
                connection=self.connection,
                payload=values["payload"],
                path=values["path"],
                query=values["query"],
                decisions=(),
                authority=SimpleNamespace(),
            )
        )


def build_client():
    sessions = SessionStub()
    authorizer = AuthorizerStub()

    def handler(call: AuthorizedOwnerCall):
        assert call.connection is authorizer.connection
        return {"problemId": call.path["problem_id"], "title": call.payload["title"]}

    operation = WorkbenchOperation(
        name="REVISE_PROBLEM",
        method="POST",
        path=f"{PREFIX}/problems/{{problem_id}}/revisions",
        request_model=CreateProblem,
        query_model=None,
        grant_builder=lambda context, path, payload, query: (
            ExactGrant(
                "BUSINESS_PROBLEM",
                "REVISE",
                f"business-problem:{path['problem_id']}",
            ),
        ),
        handler=handler,
        success_status=201,
    )
    app = create_workbench_bff(
        sessions,  # type: ignore[arg-type]
        authorizer,  # type: ignore[arg-type]
        WorkbenchBffPolicy(
            allowed_host="console.example",
            allowed_origin="https://console.example",
        ),
        operations=(operation,),
    )
    return (
        TestClient(app, base_url="https://console.example"),
        sessions,
        authorizer,
    )


def test_instance_assignment_and_placement_registry_freezes_exact_read_grants() -> None:
    operations = digital_employee_operations(SimpleNamespace())  # type: ignore[arg-type]

    assert [(item.name, item.method, item.path) for item in operations] == [
        (
            "READ_EMPLOYEE_INSTANCE",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}",
        ),
        (
            "READ_EMPLOYEE_ASSIGNMENT",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}/assignments/{{assignment_id}}",
        ),
        (
            "READ_EMPLOYEE_PLACEMENT",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}/assignments/{{assignment_id}}/"
            "placements/{placement_id}",
        ),
    ]
    instance, assignment, placement = operations
    assert tuple(
        instance.grant_builder(
            SessionStub().context,
            {"instance_id": "employee-instance:quality"},
            {},
            {},
        )
    ) == (ExactGrant("INSTANCE", "READ", "instance:employee-instance:quality"),)
    assert tuple(
        assignment.grant_builder(
            SessionStub().context,
            {
                "instance_id": "employee-instance:quality",
                "assignment_id": "employee-assignment:review",
            },
            {},
            {},
        )
    ) == (ExactGrant("ASSIGNMENT", "READ", "assignment:employee-assignment:review"),)
    assert tuple(
        placement.grant_builder(
            SessionStub().context,
            {
                "instance_id": "employee-instance:quality",
                "assignment_id": "employee-assignment:review",
                "placement_id": "placement:quality",
            },
            {},
            {
                "attemptId": "attempt:quality",
                "agentInstanceId": "agent-instance:quality",
            },
        )
    ) == (ExactGrant("PLACEMENT", "READ", "placement:placement:quality"),)


def login(client: TestClient) -> None:
    response = client.post(
        f"{PREFIX}/session",
        headers={
            "origin": "https://console.example",
            "content-type": "application/x-www-form-urlencoded",
        },
        content="loginNonce=login-nonce&bootstrapCredential=bootstrap-secret",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/workbench"
    assert "Secure" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert response.headers["referrer-policy"] == "no-referrer"


def test_session_and_bound_operation_use_only_server_context() -> None:
    client, _, authorizer = build_client()
    login_form = client.get(f"{PREFIX}/login")
    assert "login-nonce" in login_form.text
    assert login_form.headers["referrer-policy"] == "same-origin"
    assert client.get("/healthz").headers["referrer-policy"] == "no-referrer"
    login(client)

    session = client.get(f"{PREFIX}/session")
    assert session.status_code == 200
    assert session.json()["principal"] == {
        "principalId": "human:alice",
        "tenantId": "tenant-a",
        "securityDomain": "quality",
    }
    response = client.post(
        f"{PREFIX}/problems/problem-1/revisions",
        headers={
            "origin": "https://console.example",
            "x-csrf-token": "csrf-token",
        },
        json={"title": "Supplier escapes"},
    )
    assert response.status_code == 201
    assert response.json()["result"] == {
        "problemId": "problem-1",
        "title": "Supplier escapes",
    }
    context, grants = authorizer.calls[0]
    assert context.principal_id == "human:alice"
    assert grants == (
        ExactGrant("BUSINESS_PROBLEM", "REVISE", "business-problem:problem-1"),
    )


@pytest.mark.parametrize("origin", ["https://foreign.example", "null", None])
def test_login_rejects_cross_origin_null_or_missing_origin(origin) -> None:
    client, _, _ = build_client()
    headers = {"content-type": "application/x-www-form-urlencoded"}
    if origin is not None:
        headers["origin"] = origin

    response = client.post(
        f"{PREFIX}/session",
        headers=headers,
        content="loginNonce=login-nonce&bootstrapCredential=bootstrap-secret",
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert response.json()["reasonCode"] == "CSRF_VALIDATION_FAILED"
    assert response.headers["referrer-policy"] == "no-referrer"
    login(client)


@pytest.mark.parametrize(
    ("nonce", "credential"),
    [
        ("invalid-nonce", "bootstrap-secret"),
        ("login-nonce", "invalid-credential"),
    ],
)
def test_login_preserves_invalid_nonce_and_credential_semantics(
    nonce: str, credential: str
) -> None:
    client, _, _ = build_client()

    response = client.post(
        f"{PREFIX}/session",
        headers={
            "origin": "https://console.example",
            "content-type": "application/x-www-form-urlencoded",
        },
        content=f"loginNonce={nonce}&bootstrapCredential={credential}",
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert response.json()["reasonCode"] == "AUTHENTICATION_REQUIRED"
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({"host": "other.example"}, "WORKBENCH_HOST_REJECTED"),
        ({"authorization": "Bearer forged"}, "UNTRUSTED_IDENTITY_HEADER"),
        ({"x-principal-id": "human:mallory"}, "UNTRUSTED_IDENTITY_HEADER"),
    ],
)
def test_browser_boundary_rejects_host_and_identity_headers(headers, reason) -> None:
    client, _, _ = build_client()
    response = client.get(f"{PREFIX}/login", headers=headers)
    assert response.status_code == 400
    assert response.json()["reasonCode"] == reason
    assert set(response.json()) == {"reasonCode", "requestId"}


def test_unsafe_boundary_and_strict_schema_fail_before_owner() -> None:
    client, _, authorizer = build_client()
    login(client)
    foreign = client.post(
        f"{PREFIX}/problems/problem-1/revisions",
        headers={"origin": "https://foreign.example", "x-csrf-token": "csrf-token"},
        json={"title": "hidden"},
    )
    assert foreign.status_code == 403
    assert foreign.json()["reasonCode"] == "CSRF_VALIDATION_FAILED"

    extra = client.post(
        f"{PREFIX}/problems/problem-1/revisions",
        headers={
            "origin": "https://console.example",
            "x-csrf-token": "csrf-token",
        },
        json={"title": "hidden", "principalId": "human:mallory"},
    )
    assert extra.status_code == 422
    assert extra.json()["reasonCode"] == "REQUEST_INVALID"
    assert authorizer.calls == []


def test_duplicate_query_parameters_fail_before_owner() -> None:
    sessions = SessionStub()
    authorizer = AuthorizerStub()
    operation = WorkbenchOperation(
        name="LIST_THINGS",
        method="GET",
        path=f"{PREFIX}/things",
        request_model=None,
        query_model=WorkbenchPageQuery,
        grant_builder=lambda context, path, payload, query: (
            ExactGrant("EMPLOYEE", "LIST", "employee:collection"),
        ),
        handler=lambda call: {"items": []},
    )
    client = TestClient(
        create_workbench_bff(
            sessions,  # type: ignore[arg-type]
            authorizer,  # type: ignore[arg-type]
            WorkbenchBffPolicy("console.example", "https://console.example"),
            operations=(operation,),
        ),
        base_url="https://console.example",
    )
    login(client)

    response = client.get(f"{PREFIX}/things?pageSize=10&pageSize=20")

    assert response.status_code == 422
    assert response.json()["reasonCode"] == "REQUEST_INVALID"
    assert authorizer.calls == []


def test_route_set_is_closed_and_rotation_invalidates_predecessor_cookie() -> None:
    client, sessions, _ = build_client()
    login(client)
    old_secret = sessions.secret
    rotated = client.post(
        f"{PREFIX}/session/rotate",
        headers={
            "origin": "https://console.example",
            "x-csrf-token": "csrf-token",
        },
    )
    assert rotated.status_code == 204
    assert sessions.secret != old_secret
    assert client.get("/api/internal/v0.2.3/business-problems").status_code == 404
    assert client.post(f"{PREFIX}/problems/problem-1/revisions").status_code == 403


def test_duplicate_operation_registry_is_rejected() -> None:
    _, sessions, authorizer = build_client()
    operation = WorkbenchOperation(
        name="READ_PROBLEM",
        method="GET",
        path=f"{PREFIX}/problems/{{problem_id}}",
        request_model=None,
        query_model=None,
        grant_builder=lambda context, path, payload, query: (),
        handler=lambda call: {},
    )
    with pytest.raises(AuthorityError, match="WORKBENCH_OPERATION_INVALID"):
        create_workbench_bff(
            sessions,  # type: ignore[arg-type]
            authorizer,  # type: ignore[arg-type]
            WorkbenchBffPolicy("console.example", "https://console.example"),
            operations=(operation, operation),
        )


def test_business_problem_registry_freezes_routes_and_exact_resource_builders() -> None:
    operations = business_problem_operations(SimpleNamespace())  # type: ignore[arg-type]
    assert len(operations) == 13
    assert len({(item.method, item.path) for item in operations}) == 13
    assert all(item.path.startswith(f"{PREFIX}/") for item in operations)

    read = next(item for item in operations if item.name == "READ_PROBLEM")
    assert tuple(
        read.grant_builder(SessionStub().context, {"problem_id": "problem-7"}, {}, {})
    ) == (ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-7"),)
    plan = next(item for item in operations if item.name == "READ_PLAN")
    assert tuple(
        plan.grant_builder(
            SessionStub().context,
            {"plan_id": "plan-9"},
            {},
            {"version": 3},
        )
    ) == (ExactGrant("PLAN", "READ", "plan:plan-9:3"),)


def test_employee_registry_exposes_list_and_exact_revision_read() -> None:
    operations = employee_operations(  # type: ignore[arg-type]
        SimpleNamespace(), WorkbenchCursorCodec(b"k" * 32)
    )

    assert [(item.name, item.method, item.path) for item in operations] == [
        ("LIST_EMPLOYEES", "GET", f"{PREFIX}/employees"),
        (
            "READ_EMPLOYEE_REVISION",
            "GET",
            f"{PREFIX}/employees/{{employee_definition_id}}/revisions/{{revision_id}}",
        ),
    ]
    listing, operation = operations
    assert tuple(
        listing.grant_builder(SessionStub().context, {}, {}, {"pageSize": 50})
    ) == (ExactGrant("EMPLOYEE", "LIST", "employee:collection"),)
    assert tuple(
        operation.grant_builder(
            SessionStub().context,
            {
                "employee_definition_id": "employee-definition:quality",
                "revision_id": "employee-revision:v1",
            },
            {},
            {},
        )
    ) == (
        ExactGrant(
            "EMPLOYEE",
            "READ",
            "employee:employee-definition:quality:employee-revision:v1",
        ),
    )
