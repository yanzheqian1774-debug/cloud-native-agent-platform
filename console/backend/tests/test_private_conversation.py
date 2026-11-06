"""Isolated PostgreSQL contracts; never connects to the acceptance database."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from agent_console.private_conversation import ConversationError, PrivateConversations
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from test_workbench_bff import SessionStub


@pytest.fixture(scope="module")
def database():
    value = os.environ.get("PRIVATE_CONVERSATION_TEST_DATABASE_URL")
    if not value:
        pytest.skip("explicit isolated PostgreSQL required")
    info = conninfo_to_dict(value)
    assert info.get("port") == "64335" and info.get("host") == "127.0.0.1"
    name = "conversation_test_" + uuid4().hex
    with psycopg.connect(value, autocommit=True) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(value, dbname=name)
    with psycopg.connect(dsn) as c:
        c.execute(
            (
                Path(__file__).parents[1] / "migrations/0046_private_conversation.sql"
            ).read_text()
        )
        c.execute(
            (
                Path(__file__).parents[1]
                / "migrations/0047_conversation_action_facts.sql"
            ).read_text()
        )
    yield dsn
    with psycopg.connect(value, autocommit=True) as c:
        c.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def ctx(user="a", tenant="tenant", domain="domain"):
    return SimpleNamespace(
        principal_id=user,
        scope=SimpleNamespace(tenant_id=tenant, security_domain=domain),
    )


@pytest.fixture
def service(database):
    def resolve(context, target):
        if target.get("problemId") != "allowed":
            raise ConversationError("DENIED", 403)
        return {"title": "Authorized existing work"}

    return PrivateConversations(database, resolve)


def new(service):
    return service.create(ctx(), {"idempotencyKey": str(uuid4()), "title": "Private"})[
        "conversation_id"
    ]


def test_create_replay_and_payload_collision(service):
    body = {"idempotencyKey": str(uuid4()), "title": "One"}
    with ThreadPoolExecutor(2) as pool:
        values = list(pool.map(lambda _: service.create(ctx(), body), range(2)))
    assert values[0] == values[1]
    with pytest.raises(ConversationError, match="IDEMPOTENCY"):
        service.create(ctx(), {**body, "title": "Other"})


@pytest.mark.parametrize("other", [ctx("b"), ctx(tenant="other"), ctx(domain="other")])
def test_private_scope_read_and_write(service, other):
    identity = new(service)
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.read(other, identity)
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.mutate(
            other,
            identity,
            {"idempotencyKey": "x", "content": "x", "expectedVersion": 0},
            "message",
        )
    assert identity not in [x["conversation_id"] for x in service.list(other)["items"]]


def test_append_cas_duplicate_and_restart(service, database):
    identity = new(service)
    body = {
        "idempotencyKey": "message",
        "expectedVersion": 0,
        "content": "原工作继续核对",
    }
    with ThreadPoolExecutor(2) as pool:
        values = list(
            pool.map(
                lambda _: service.mutate(ctx(), identity, body, "message"), range(2)
            )
        )
    assert values[0]["identity"] == values[1]["identity"]
    assert len(service.read(ctx(), identity)["messages"]) == 1
    with pytest.raises(ConversationError, match="VERSION_CONFLICT"):
        service.mutate(ctx(), identity, {**body, "idempotencyKey": "second"}, "message")
    fresh = PrivateConversations(database, service.resolve_link)
    assert fresh.read(ctx(), identity)["messages"][0]["content"] == body["content"]
    with pytest.raises(ConversationError, match="IDEMPOTENCY"):
        service.mutate(ctx(), identity, {**body, "content": "different"}, "message")


def test_links_revocation_and_no_implicit_work_creation(service):
    identity = new(service)
    link = {
        "idempotencyKey": "link",
        "expectedVersion": 0,
        "target": {"problemId": "allowed"},
    }
    receipt = service.mutate(ctx(), identity, link, "link")
    message = {
        "idempotencyKey": "m",
        "expectedVersion": 1,
        "content": "继续核对",
        "focusLinkId": receipt["identity"],
    }
    service.mutate(ctx(), identity, message, "message")
    data = service.read(ctx(), identity)
    assert data["messages"][0]["disposition"] == "FOLLOWUP_RECORDED"
    service.resolve_link = lambda *_: (_ for _ in ()).throw(
        ConversationError("DENIED", 403)
    )
    assert service.read(ctx(), identity)["links"] == [
        {"link_id": receipt["identity"], "readable": False}
    ]
    with pytest.raises(ConversationError, match="DENIED"):
        service.mutate(
            ctx(),
            identity,
            {**message, "idempotencyKey": "n", "expectedVersion": 2},
            "message",
        )
    assert service.read(ctx(), identity)["conversation"]["version"] == 2


def test_foreign_link_and_ambiguity(service):
    identity = new(service)
    with pytest.raises(ConversationError, match="DENIED"):
        service.mutate(
            ctx(),
            identity,
            {
                "idempotencyKey": "bad",
                "expectedVersion": 0,
                "target": {"problemId": "foreign"},
            },
            "link",
        )
    assert service.read(ctx(), identity)["conversation"]["version"] == 0
    service.mutate(
        ctx(),
        identity,
        {
            "idempotencyKey": "ok",
            "expectedVersion": 0,
            "target": {"problemId": "allowed"},
        },
        "link",
    )
    service.mutate(
        ctx(),
        identity,
        {"idempotencyKey": "m", "expectedVersion": 1, "content": "它的情况怎么样"},
        "message",
    )
    assert service.read(ctx(), identity)["messages"][0]["disposition"] == "CLARIFY_WORK"
    service.mutate(
        ctx(),
        identity,
        {
            "idempotencyKey": "n",
            "expectedVersion": 2,
            "content": "我想分析另一季度的销售",
        },
        "message",
    )
    assert (
        service.read(ctx(), identity)["messages"][1]["disposition"] == "NEW_GOAL_REVIEW"
    )


def test_bff_flag_session_csrf_and_real_storage(database):
    sessions = SessionStub()
    app = create_workbench_bff(
        sessions,
        object(),
        WorkbenchBffPolicy("testserver", "https://testserver"),
        conversation_database_url=database,
    )
    client = TestClient(app, base_url="https://testserver")
    assert client.get("/api/workbench/v1/conversations").status_code == 401
    client.cookies.set("__Host-workbench_session", sessions.secret)
    # Use the actual configured cookie name from the boundary.
    from agent_console.workbench_bff import SESSION_COOKIE

    client.cookies.set(SESSION_COOKIE, sessions.secret)
    body = {"idempotencyKey": str(uuid4()), "title": "BFF"}
    path = "/api/workbench/v1/conversations"
    assert (
        client.post(
            path, json=body, headers={"origin": "https://testserver"}
        ).status_code
        == 403
    )
    headers = {"origin": "https://testserver", "x-csrf-token": "csrf-token"}
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    identity = response.json()["result"]["conversation_id"]
    assert client.get(path + "/" + identity).status_code == 200
    sessions.logged_out = True
    assert client.get(path + "/" + identity).status_code == 401
    sessions.logged_out = False
    disabled = TestClient(
        create_workbench_bff(
            sessions, object(), WorkbenchBffPolicy("testserver", "https://testserver")
        ),
        base_url="https://testserver",
    )
    disabled.cookies.set(SESSION_COOKIE, sessions.secret)
    assert disabled.get(path + "/capabilities").json()["result"]["enabled"] is False
    assert disabled.post(path, json=body, headers=headers).status_code == 404


def test_distinct_concurrent_writes_cas(service):
    identity = new(service)

    def append(key):
        try:
            service.mutate(
                ctx(),
                identity,
                {"idempotencyKey": key, "expectedVersion": 0, "content": key},
                "message",
            )
            return "saved"
        except ConversationError as exc:
            return exc.reason

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(append, ["left", "right"]))
    assert sorted(results) == ["CONVERSATION_VERSION_CONFLICT", "saved"]
    assert len(service.read(ctx(), identity)["messages"]) == 1


def test_bff_exact_work_bridge_and_revocation(database):
    from agent_console.authority_contracts import AuthorityError
    from agent_console.workbench_bff import SESSION_COOKIE, WorkbenchOperation

    class Reader:
        allowed = True

        def execute(self, context, grants, *, operation, **kwargs):
            assert operation in {"READ_PROBLEM", "READ_PREPARED_EXECUTION"}
            if not self.allowed:
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            if operation == "READ_PROBLEM":
                return {
                    "revisions": [
                        {"revision_id": "r", "digest": "a" * 64, "title": "Existing"}
                    ]
                }
            return {
                "digest": "b" * 64,
                "preparation": {
                    "semantics": {
                        "target": {
                            "problem": {
                                "resource_id": "p",
                                "revision_id": "r",
                                "digest": "a" * 64,
                            }
                        }
                    }
                },
            }

    reader = Reader()
    ops = tuple(
        WorkbenchOperation(name, "GET", path, None, None, lambda *_: (), lambda _: None)
        for name, path in [
            ("READ_PROBLEM", "/api/workbench/v1/probe-p"),
            ("READ_PREPARED_EXECUTION", "/api/workbench/v1/probe-e"),
        ]
    )
    sessions = SessionStub()
    client = TestClient(
        create_workbench_bff(
            sessions,
            reader,
            WorkbenchBffPolicy("testserver", "https://testserver"),
            operations=ops,
            conversation_database_url=database,
        ),
        base_url="https://testserver",
    )
    client.cookies.set(SESSION_COOKIE, sessions.secret)
    headers = {"origin": "https://testserver", "x-csrf-token": "csrf-token"}
    root = "/api/workbench/v1/conversations"
    identity = client.post(
        root, json={"title": "Bridge", "idempotencyKey": str(uuid4())}, headers=headers
    ).json()["result"]["conversation_id"]
    path = root + "/" + identity
    body = {
        "idempotencyKey": "x",
        "expectedVersion": 0,
        "target": {
            "problemId": "other",
            "revisionId": "r",
            "problemDigest": "a" * 64,
            "executionDigest": "b" * 64,
        },
    }
    assert client.post(path + "/links", json=body, headers=headers).status_code == 409
    assert client.get(path).json()["result"]["conversation"]["version"] == 0
    body["target"]["problemId"] = "p"
    response = client.post(path + "/links", json=body, headers=headers)
    assert response.status_code == 200, response.text
    link = response.json()["result"]["identity"]
    reader.allowed = False
    assert client.get(path).json()["result"]["links"] == [
        {"link_id": link, "readable": False}
    ]
    response = client.post(
        path + "/messages",
        headers=headers,
        json={
            "idempotencyKey": "m",
            "expectedVersion": 1,
            "content": "followup",
            "focusLinkId": link,
        },
    )
    assert response.status_code in (403, 404)
    assert client.get(path).json()["result"]["messages"] == []


def test_additive_migration_replay_and_verify_retains_records(database, service):
    import subprocess
    import sys

    identity = new(service)
    root = Path(__file__).resolve().parents[3]
    command = [
        sys.executable,
        str(root / "scripts/acceptance/private_conversation_migrate.py"),
    ]
    env = {**os.environ, "CONVERSATION_DATABASE_URL": database}
    for options in (["--apply"], ["--apply"], []):
        result = subprocess.run(
            command + options, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
    assert service.read(ctx(), identity)["conversation"]["conversation_id"] == identity
