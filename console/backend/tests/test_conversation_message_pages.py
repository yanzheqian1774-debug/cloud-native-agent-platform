"""Real isolated PG, synthetic owner permissions; never a live platform/model."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from agent_console.private_conversation import ConversationError, PrivateConversations
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def ctx(user="reader", tenant="test-tenant", domain="test-domain"):
    return SimpleNamespace(
        principal_id=user,
        scope=SimpleNamespace(tenant_id=tenant, security_domain=domain),
    )


def history_admin_dsn(environment=None):
    """Select only explicit approved loopback PostgreSQL admin endpoints."""
    values = os.environ if environment is None else environment
    sources = [
        values.get(name)
        for name in ("HISTORY_PAGE_TEST_ADMIN_DSN", "AUTHORITY_I1_TEST_DATABASE_URL")
        if values.get(name)
    ]
    if not sources:
        return None
    identities = []
    for source in sources:
        try:
            info = conninfo_to_dict(source)
        except psycopg.Error:
            raise ValueError("ISOLATED_HISTORY_ADMIN_DSN_INVALID") from None
        if (
            info.get("host") != "127.0.0.1"
            or info.get("port") not in {"53447", "53428"}
            or info.get("dbname", "postgres") != "postgres"
            or info.get("user") != "postgres"
            or info.get("hostaddr", "127.0.0.1") != "127.0.0.1"
            or any(key in info for key in ("service", "passfile"))
        ):
            raise ValueError("ISOLATED_HISTORY_ADMIN_DSN_INVALID")
        identities.append(
            (info["host"], info["port"], info["user"], info.get("dbname", "postgres"))
        )
    if len(set(identities)) != 1:
        raise ValueError("ISOLATED_HISTORY_ADMIN_DSN_CONFLICT")
    return make_conninfo(sources[0], hostaddr="127.0.0.1", dbname="postgres")


@pytest.fixture(scope="module")
def database():
    admin = history_admin_dsn()
    if not admin:
        pytest.skip("explicit isolated history PostgreSQL required")
    name = "history_page_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin, dbname=name)
    with psycopg.connect(dsn) as c:
        for migration in [
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ]:
            c.execute(
                (Path(__file__).parents[1] / "migrations" / migration).read_text()
            )
        c.execute(
            "CREATE TABLE test_read_permissions(subject text, source text, "
            "allowed bool, PRIMARY KEY(subject,source))"
        )
    yield dsn
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


class Rows:
    def __init__(self, cursor, trace, query):
        self.cursor, self.trace, self.query = cursor, trace, query

    def fetchall(self):
        rows = self.cursor.fetchall()
        self.trace.append((self.query, len(rows)))
        return rows

    def fetchone(self):
        row = self.cursor.fetchone()
        self.trace.append((self.query, int(row is not None)))
        return row


class Connection:
    def __init__(self, c, trace):
        self.c, self.trace = c, trace

    def execute(self, q, args=None):
        return Rows(self.c.execute(q, args), self.trace, str(q))

    def pipeline(self):
        return self.c.pipeline()


@pytest.fixture
def service(database):
    s = PrivateConversations(database, lambda *_: {"title": "synthetic work"})
    s.trace = []
    s.acquisitions = 0
    s.active = 0
    s.reads = []
    s.failed = False

    @contextmanager
    def connection():
        s.acquisitions += 1
        s.active += 1
        try:
            with psycopg.connect(database, row_factory=dict_row) as c:
                yield Connection(c, s.trace)
        finally:
            s.active -= 1

    s.connect = connection

    def source_read(context, source):
        assert s.active == 0, "authorization must not hold a conversation connection"
        s.reads.append(source)
        if s.failed:
            raise ConversationError("SYNTHETIC_OUTAGE", 503)
        with psycopg.connect(database) as c:
            row = c.execute(
                "SELECT allowed FROM test_read_permissions WHERE subject=%s "
                "AND source=%s",
                (context.principal_id, source["invocationId"]),
            ).fetchone()
        if not row or not row[0]:
            raise ConversationError("SOURCE_DENIED", 403)

    s.facts_reader = SimpleNamespace(source_read=source_read)
    return s


def seed(service, n, *, source=None, authorization=None, user=None):
    context = user or ctx()
    identity = service.create(
        context, {"idempotencyKey": uuid4().hex, "title": "Synthetic history"}
    )["conversation_id"]
    with psycopg.connect(service.database_url) as c:
        for i in range(1, n + 1):
            mid = f"message-{i:06d}"
            c.execute(
                "INSERT INTO "
                "private_conversation.messages(tenant_id,security_domain,conv"
                "ersation_id,message_id,sequence,author_id,content,dispositio"
                "n,request_key,request_digest) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *service.scope(context),
                    identity,
                    mid,
                    i,
                    context.principal_id,
                    f"saved private body {i}",
                    "FOLLOWUP_RECORDED",
                    mid,
                    "test",
                ),
            )
            if source:
                facts = {
                    "source": source,
                    "authorizationSource": authorization or source,
                }
                c.execute(
                    "INSERT INTO private_conversation.message_facts "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (*service.scope(context), identity, mid, "SOURCE", Jsonb(facts)),
                )
        c.execute(
            "UPDATE private_conversation.conversations SET version=%s WHERE "
            "tenant_id=%s AND security_domain=%s AND conversation_id=%s",
            (n, *service.scope(context), identity),
        )
        for ref in [source, authorization]:
            if ref:
                c.execute(
                    "INSERT INTO test_read_permissions VALUES(%s,%s,true) ON "
                    "CONFLICT(subject,source) DO UPDATE SET allowed=true",
                    (context.principal_id, ref["invocationId"]),
                )
    service.trace.clear()
    service.acquisitions = 0
    service.reads.clear()
    return identity


@pytest.mark.parametrize("length", [0, 3, 2000])
def test_latest_page_and_scoped_facts(service, length):
    ref = {"kind": "DRAFT", "invocationId": uuid4().hex}
    identity = seed(service, length, source=ref)
    result = service.read_messages(ctx(), identity, limit=20)
    assert [m["sequence"] for m in result["messages"]] == list(
        range(max(1, length - 19), length + 1)
    )
    assert set(result) == {"conversation", "messages", "page"} and result["page"][
        "hasMore"
    ] == (length > 20)
    assert service.acquisitions == 1 and len(service.reads) == int(length > 0)
    for query, count in service.trace:
        if "message_facts" in query or "action_intents" in query:
            assert "message_id=ANY" in query and count <= 20
    if length == 2000:
        print(
            "PAGED_SQL_EVIDENCE",
            json.dumps(
                {
                    "length": length,
                    "pageRows": len(result["messages"]),
                    "connections": service.acquisitions,
                    "ownerSourceReads": len(service.reads),
                    "fetchedRows": [
                        (q.split("FROM ")[-1].split(" WHERE")[0], n)
                        for q, n in service.trace
                    ],
                }
            ),
        )


def test_cursor_stability_with_new_messages_and_legacy_read(service):
    identity = seed(service, 125)
    first = service.read_messages(ctx(), identity, limit=17)
    cursor = first["page"]["nextCursor"]
    service.mutate(
        ctx(),
        identity,
        {
            "idempotencyKey": "concurrent-append",
            "expectedVersion": 125,
            "content": "new after first page",
        },
        "message",
    )
    pages = [first]
    while cursor:
        current = service.read_messages(ctx(), identity, limit=17, before=cursor)
        pages.append(current)
        cursor = current["page"]["nextCursor"]
    sequences = [m["sequence"] for p in pages for m in p["messages"]]
    assert sorted(sequences) == list(range(1, 126)) and len(set(sequences)) == 125
    assert (
        service.read_messages(ctx(), identity, limit=17)["messages"][-1]["sequence"]
        == 126
    )
    legacy = service.read(ctx(), identity)
    assert len(legacy["messages"]) == 126 and set(legacy) == {
        "conversation",
        "messages",
        "links",
    }


@pytest.mark.parametrize(
    "other", [ctx("other"), ctx(tenant="other"), ctx(domain="other")]
)
def test_current_ownership_checked_on_every_page(service, other):
    identity = seed(service, 5)
    cursor = service.read_messages(ctx(), identity, limit=2)["page"]["nextCursor"]
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.read_messages(other, identity, before=cursor)


@pytest.mark.parametrize("value", ["", "not-a-cursor", "a" * 4097])
def test_invalid_cursor(service, value):
    identity = seed(service, 2)
    with pytest.raises(ConversationError, match="PAGE_INVALID"):
        service.read_messages(ctx(), identity, before=value)


def test_cursor_cannot_cross_conversation(service):
    one = seed(service, 3)
    two = seed(service, 3)
    cursor = service.read_messages(ctx(), one, limit=1)["page"]["nextCursor"]
    with pytest.raises(ConversationError, match="PAGE_INVALID"):
        service.read_messages(ctx(), two, before=cursor)


def test_reauthorization_revocation_and_error_never_leak_saved_body(service, database):
    source = {"kind": "DRAFT", "invocationId": uuid4().hex}
    auth = {"kind": "DRAFT", "invocationId": uuid4().hex}
    identity = seed(service, 8, source=source, authorization=auth)
    service.read_messages(ctx(), identity)
    assert service.reads == [source, auth]
    service.reads.clear()
    with psycopg.connect(database) as c:
        c.execute(
            "UPDATE test_read_permissions SET allowed=false WHERE subject=%s "
            "AND source=%s",
            (ctx().principal_id, auth["invocationId"]),
        )
    denied = service.read_messages(ctx(), identity)
    assert service.reads == [source, auth] and all(
        m["facts"]["readState"] == "ACCESS_RESTRICTED" for m in denied["messages"]
    )
    assert "saved private body" not in str(denied) and auth["invocationId"] not in str(
        denied
    )
    service.failed = True
    service.reads.clear()
    outage = service.read_messages(ctx(), identity)
    assert service.reads == [source] and all(
        m["facts"]["readState"] == "TEMPORARILY_UNAVAILABLE" for m in outage["messages"]
    )
    assert "saved private body" not in str(outage)
    service.failed = False
    with psycopg.connect(database) as c:
        c.execute(
            "UPDATE test_read_permissions SET allowed=true WHERE subject=%s",
            (ctx().principal_id,),
        )
    restored = service.read_messages(ctx(), identity)
    assert restored["messages"][0]["content"].startswith("saved private body")


def test_archived_history_and_work_links_independent(service, database):
    ref = {"kind": "DRAFT", "invocationId": uuid4().hex}
    identity = seed(service, 9, source=ref)
    with psycopg.connect(database) as c:
        c.execute(
            "UPDATE private_conversation.conversations SET archived_at=now() "
            "WHERE conversation_id=%s",
            (identity,),
        )
    assert len(service.read_messages(ctx(), identity, limit=3)["messages"]) == 3
    service.reads.clear()
    links = service.work_links(ctx(), identity)
    assert links["links"] == [] and not service.reads


def test_http_authentication_and_original_read_contract(database, monkeypatch):
    from agent_console.workbench_bff import (
        SESSION_COOKIE,
        WorkbenchBffPolicy,
        create_workbench_bff,
    )
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    sessions = SessionStub()
    app = create_workbench_bff(
        sessions,
        object(),
        WorkbenchBffPolicy("testserver", "https://testserver"),
        conversation_database_url=database,
    )
    client = TestClient(app, base_url="https://testserver")
    path = "/api/workbench/v1/conversations"
    assert client.get(path + "/unknown/messages").status_code == 401
    client.cookies.set(SESSION_COOKIE, sessions.secret)
    result = client.post(
        path,
        json={"idempotencyKey": uuid4().hex, "title": "HTTP"},
        headers={"origin": "https://testserver", "x-csrf-token": "csrf-token"},
    )
    assert result.status_code == 200
    identity = result.json()["result"]["conversation_id"]
    page = client.get(path + "/" + identity + "/messages?limit=1")
    assert page.status_code == 200 and page.json()["result"]["page"] == {
        "hasMore": False,
        "nextCursor": None,
        "resumeCursor": None,
    }
    assert client.get(path + "/" + identity + "/messages?limit=101").status_code == 422
    assert set(client.get(path + "/" + identity).json()["result"]) == {
        "conversation",
        "messages",
        "links",
    }
    assert client.get(path + "/" + identity + "/work-links").status_code == 200
    sessions.context = ctx("wrong", tenant="tenant-a", domain="quality")
    assert client.get(path + "/" + identity + "/messages").status_code == 404
    sessions.context = SessionStub().context

    def unavailable_connection(_):
        raise psycopg.OperationalError("synthetic-private-storage-error")

    monkeypatch.setattr(PrivateConversations, "connect", unavailable_connection)
    unavailable = client.get(path + "/" + identity + "/messages")
    assert unavailable.status_code == 503
    assert "synthetic-private-storage-error" not in unavailable.text
    assert "saved private body" not in unavailable.text


@pytest.mark.parametrize("claimed", [False, True])
def test_current_page_intent_uses_exact_fact_reference_not_original_request_message(
    service, database, claimed
):
    identity = seed(service, 2)
    with psycopg.connect(database) as c:
        c.execute(
            (
                "INSERT INTO private_conversation.message_facts "
                "VALUES(%s,%s,%s,%s,%s,%s)"
            ),
            (
                *service.scope(ctx()),
                identity,
                "message-000002",
                "ACTION_INTENT",
                Jsonb({"intentId": "synthetic-intent"}),
            ),
        )
        c.execute(
            (
                "INSERT INTO "
                "private_conversation.action_intents(tenant_id,security_domai"
                "n,conversation_id,intent_id,message_id,confirmed_by,action,p"
                "ayload,payload_digest,owner_request_key,expected_owner_versi"
                "on,request_key,request_digest,claimed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s "
                "THEN now() ELSE NULL END)"
            ),
            (
                *service.scope(ctx()),
                identity,
                "synthetic-intent",
                "message-000001",
                ctx().principal_id,
                "PREPARE",
                Jsonb({}),
                "synthetic",
                "owner-key-" + identity,
                1,
                "intent-key",
                "synthetic",
                claimed,
            ),
        )
    current = service.read_messages(ctx(), identity, limit=1)
    assert current["messages"][0]["facts"]["attemptState"] == (
        "UNKNOWN" if claimed else "NOT_SUBMITTED"
    )
    with psycopg.connect(database) as c:
        assert c.execute(
            (
                "SELECT claimed_at IS NOT NULL,owner_ref FROM "
                "private_conversation.action_intents WHERE "
                "conversation_id=%s"
            ),
            (identity,),
        ).fetchone() == (claimed, None)
