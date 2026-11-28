"""Narrow real-PG successor coverage; reuse the sealed original sixteen results."""

from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
import test_conversation_message_pages as base_cases
import test_development_administrator as admin_cases
from agent_console import conversation_goal_slots as goals
from agent_console.authority_contracts import AuthorityError
from agent_console.development_administrator import authorized
from agent_console.local_accounts import operate
from agent_console.private_conversation import ConversationError, PrivateConversations
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

database = base_cases.database
service = base_cases.service
ctx, seed = base_cases.ctx, base_cases.seed
login = admin_cases.login


def authority_fixture_generator(routine, dsn):
    """Use the unchanged authority fixture with local globals, never module edits."""
    from types import FunctionType
    from urllib.parse import quote, urlencode

    from psycopg.conninfo import conninfo_to_dict

    info = conninfo_to_dict(dsn)
    extras = {
        k: v
        for k, v in info.items()
        if k not in {"host", "port", "user", "password", "dbname"}
    }
    url = (
        "postgresql://"
        + quote(info["user"], safe="")
        + ":"
        + quote(info.get("password", ""), safe="")
        + "@127.0.0.1:"
        + info["port"]
        + "/postgres"
    )
    if extras:
        url += "?" + urlencode(extras)
    isolated = FunctionType(
        routine.__code__,
        {**routine.__globals__, "URL": url},
        name=routine.__name__,
        argdefs=routine.__defaults__,
        closure=routine.__closure__,
    )
    return isolated()


@pytest.fixture
def setup():
    value = base_cases.history_admin_dsn()
    if not value:
        pytest.skip("explicit isolated history authority PostgreSQL required")
    yield from authority_fixture_generator(admin_cases.setup.__wrapped__, value)


@pytest.fixture(scope="module")
def goal_database(database):
    with psycopg.connect(database, row_factory=dict_row) as c:
        goals.migrate(c)
    return database


def test_real_admin_linearized_for_share_and_revocation(setup):
    repo, generation, sessions, reader = setup
    migrations = Path(__file__).parents[1] / "migrations"
    with repo.connection_scope() as c:
        for name in [
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ]:
            c.execute((migrations / name).read_text())
    records = PrivateConversations(
        repo.pool.conninfo,
        lambda *_: {},
        lambda c, context: authorized(
            reader, context, generation=1, recovery_epoch=1, connection=c
        ),
    )
    _, owner = sessions.authenticate_session(login(sessions).value)
    _, admin = sessions.authenticate_session(login(sessions, "devadmin").value)
    _, other = sessions.authenticate_session(login(sessions, "reviewer324").value)
    identity = records.create(
        owner, {"idempotencyKey": "admin-page-chat", "title": "synthetic owner"}
    )["conversation_id"]
    records.mutate(
        owner,
        identity,
        {
            "idempotencyKey": "request",
            "expectedVersion": 0,
            "content": "saved owner message",
        },
        "message",
    )
    # Reproduce the original clash against the actual authority FOR SHARE reads.
    with (
        pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE") as error,
        records.connect() as c,
    ):
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        records.owned(c, admin, identity)
    assert isinstance(error.value.__cause__, psycopg.errors.ReadOnlySqlTransaction)
    page = records.read_messages(admin, identity)
    assert page["messages"][0]["content"] == "saved owner message"
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        records.read_messages(other, identity)
    operate(
        repo,
        generation.account_by_id("local-account:devadmin"),
        action="DISABLE",
        command_id="disable-admin-page",
        operator_id="operator:test",
        now=datetime.now(UTC),
    )
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        records.read_messages(admin, identity)
    assert (
        records.read_messages(owner, identity)["messages"][0]["content"]
        == "saved owner message"
    )


def test_real_goal_associations_across_pages_and_archival(service, goal_database):
    identity = seed(service, 80)
    with psycopg.connect(goal_database, row_factory=dict_row) as c:
        made = []
        for i in [1, 61]:
            made.append(
                goals.create(
                    c,
                    service,
                    ctx(),
                    identity,
                    goals.CreateGoal(
                        commandId="goal-" + str(i),
                        messageId=f"message-{i:06d}",
                        expectedConversationVersion=80,
                    ),
                )["goalId"]
            )
        goals.attach_message(c, service, ctx(), identity, made[0], "message-000002")
        goals.attach_message(c, service, ctx(), identity, made[1], "message-000062")
    latest = service.read_messages(ctx(), identity, limit=20)
    assert {
        m.get("goalId") for m in latest["messages"] if m["sequence"] in [61, 62]
    } == {made[1]}
    cursor = latest["page"]["nextCursor"]
    old = None
    while cursor:
        old = service.read_messages(ctx(), identity, limit=20, before=cursor)
        cursor = old["page"]["nextCursor"]
    assert {m.get("goalId") for m in old["messages"] if m["sequence"] in [1, 2]} == {
        made[0]
    }
    assert not any(m.get("goalId") == made[1] for m in old["messages"])
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.read_messages(ctx("other"), identity)
    with (
        psycopg.connect(goal_database, row_factory=dict_row) as c,
        pytest.raises(ConversationError, match="NOT_FOUND"),
    ):
        goals.owned(c, service, ctx("other"), identity, made[0])
    with psycopg.connect(goal_database, row_factory=dict_row) as c:
        c.execute(
            "UPDATE private_conversation.conversations SET archived_at=now() "
            "WHERE conversation_id=%s",
            (identity,),
        )
    assert all(
        "goalId" not in m for m in service.read_messages(ctx(), identity)["messages"]
    )
    with (
        psycopg.connect(goal_database, row_factory=dict_row) as c,
        pytest.raises(ConversationError, match="GOAL_NOT_AVAILABLE"),
    ):
        goals.owned(c, service, ctx(), identity, made[0])


def test_latest_2000_with_real_goal_schema_still_limits_facts(service, goal_database):
    source = {"kind": "DRAFT", "invocationId": "synthetic-goal-schema-read"}
    identity = seed(service, 2000, source=source)
    value = service.read_messages(ctx(), identity, limit=20)
    assert len(value["messages"]) == 20 and len(service.reads) == 1
    for query, n in service.trace:
        if (
            "FROM private_conversation.message_facts" in query
            and "intent_id" not in query
        ):
            assert n == 20
        if "FROM conversation_goals.messages" in query:
            assert "message_id=ANY" in query


def test_resume_same_page_after_new_messages_and_current_revocation(
    service, goal_database
):
    source = {"kind": "DRAFT", "invocationId": "synthetic-resume"}
    identity = seed(service, 120, source=source)
    latest = service.read_messages(ctx(), identity, limit=50)
    cursor = latest["page"]["resumeCursor"]
    older = service.read_messages(
        ctx(), identity, limit=50, before=latest["page"]["nextCursor"]
    )
    older_cursor = older["page"]["resumeCursor"]
    with psycopg.connect(goal_database) as c:
        for i in range(121, 182):
            c.execute(
                "INSERT INTO "
                "private_conversation.messages(tenant_id,security_domain,conv"
                "ersation_id,message_id,sequence,author_id,content,dispositio"
                "n,request_key,request_digest) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *service.scope(ctx()),
                    identity,
                    f"new-{i}",
                    i,
                    ctx().principal_id,
                    "new synthetic message",
                    "FOLLOWUP_RECORDED",
                    f"new-{i}",
                    "synthetic",
                ),
            )
    assert (
        service.read_messages(ctx(), identity, limit=50)["messages"][0]["sequence"]
        > 120
    )
    resumed = service.read_messages(ctx(), identity, limit=50, before=cursor)
    assert [m["message_id"] for m in resumed["messages"]] == [
        m["message_id"] for m in latest["messages"]
    ]
    assert [
        m["message_id"]
        for m in service.read_messages(ctx(), identity, limit=50, before=older_cursor)[
            "messages"
        ]
    ] == [m["message_id"] for m in older["messages"]]
    assert resumed["page"]["resumeCursor"] == cursor
    with psycopg.connect(goal_database) as c:
        c.execute(
            "UPDATE test_read_permissions SET allowed=false WHERE subject=%s "
            "AND source=%s",
            (ctx().principal_id, source["invocationId"]),
        )
    restricted = service.read_messages(ctx(), identity, limit=50, before=cursor)
    assert all(
        m["facts"]["readable"] is False for m in restricted["messages"]
    ) and "saved private body" not in str(restricted)
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.read_messages(ctx("other"), identity, before=cursor)


def test_invalid_resume_mode_and_old_cursor_compatibility(service, goal_database):
    import base64
    import json

    identity = seed(service, 70)
    page = service.read_messages(ctx(), identity, limit=50)
    assert (
        len(
            service.read_messages(ctx(), identity, before=page["page"]["nextCursor"])[
                "messages"
            ]
        )
        == 20
    )
    raw = json.loads(
        base64.urlsafe_b64decode(
            page["page"]["resumeCursor"]
            + "=" * (-len(page["page"]["resumeCursor"]) % 4)
        )
    )
    raw["inclusive"] = 1
    bad = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode()
    with pytest.raises(ConversationError, match="PAGE_INVALID"):
        service.read_messages(ctx(), identity, before=bad)


def test_exact_capability_context_not_absence_on_revocation_or_error(
    service, goal_database
):
    source = {"kind": "CAPABILITY", "invocationId": "synthetic-capability"}
    identity = seed(service, 120)
    with psycopg.connect(goal_database) as c:
        c.execute(
            "INSERT INTO private_conversation.message_facts VALUES(%s,%s,%s,%s,%s,%s)",
            (
                *service.scope(ctx()),
                identity,
                "message-000001",
                "SOURCE",
                Jsonb(
                    {
                        "source": source,
                        "observation": {"state": "PREPARED_NOT_EXECUTED"},
                    }
                ),
            ),
        )
        c.execute(
            "INSERT INTO test_read_permissions VALUES(%s,%s,true)",
            (ctx().principal_id, source["invocationId"]),
        )
    assert all(
        m["message_id"] != "message-000001"
        for m in service.read_messages(ctx(), identity)["messages"]
    )
    context = service.capability_context(ctx(), identity)
    assert (
        context["message"]["message_id"] == "message-000001"
        and context["message"]["facts"]["source"] == source
    )
    with psycopg.connect(goal_database) as c:
        c.execute(
            "UPDATE test_read_permissions SET allowed=false WHERE source=%s",
            (source["invocationId"],),
        )
    hidden = service.capability_context(ctx(), identity)["message"]
    assert (
        hidden is not None
        and hidden["facts"]["readState"] == "ACCESS_RESTRICTED"
        and "saved private body" not in str(hidden)
    )
    service.failed = True
    assert (
        service.capability_context(ctx(), identity)["message"]["facts"]["readState"]
        == "TEMPORARILY_UNAVAILABLE"
    )
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.capability_context(ctx("other"), identity)
    empty = seed(service, 1)
    assert service.capability_context(ctx(), empty)["message"] is None


def candidates(service, database):
    identity = seed(service, 120)
    sources = [
        {"kind": "DRAFT", "invocationId": "synthetic-candidate-a-" + identity},
        {"kind": "DRAFT", "invocationId": "synthetic-candidate-b-" + identity},
    ]
    with psycopg.connect(database, row_factory=dict_row) as c:
        goal_ids = []
        for i in [1, 3]:
            goal_ids.append(
                goals.create(
                    c,
                    service,
                    ctx(),
                    identity,
                    goals.CreateGoal(
                        commandId="candidate-goal-" + str(i),
                        messageId=f"message-{i:06d}",
                        expectedConversationVersion=120,
                    ),
                )["goalId"]
            )
        for i, source, user in [(10, sources[0], 1), (80, sources[1], 3)]:
            facts = {
                "source": source,
                "assistantResponse": True,
                "invokedBy": ctx().principal_id,
                "state": "SUCCEEDED",
                "requestKey": f"candidate-{i}",
                "userMessageId": f"message-{user:06d}",
                "response": {"conversationRoute": {"relation": "CURRENT_QUESTION"}},
            }
            c.execute(
                "INSERT INTO private_conversation.message_facts "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    *service.scope(ctx()),
                    identity,
                    f"message-{i:06d}",
                    "SOURCE",
                    Jsonb(facts),
                ),
            )
            c.execute(
                "INSERT INTO test_read_permissions VALUES(%s,%s,true)",
                (ctx().principal_id, source["invocationId"]),
            )
        goals.attach_message(c, service, ctx(), identity, goal_ids[0], "message-000010")
        goals.attach_message(c, service, ctx(), identity, goal_ids[1], "message-000080")
        for i, extra in [
            (90, {"state": "UNKNOWN"}),
            (100, {"invokedBy": "other"}),
            (110, {"response": {"conversationRoute": {"relation": "INDEPENDENT"}}}),
        ]:
            facts = {
                "source": sources[0],
                "assistantResponse": True,
                "invokedBy": ctx().principal_id,
                "state": "SUCCEEDED",
                "requestKey": f"candidate-{i}",
                "userMessageId": "message-000001",
                "response": {"conversationRoute": {"relation": "CURRENT_QUESTION"}},
                **extra,
            }
            c.execute(
                "INSERT INTO private_conversation.message_facts "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    *service.scope(ctx()),
                    identity,
                    f"message-{i:06d}",
                    "SOURCE",
                    Jsonb(facts),
                ),
            )
    service.reads.clear()
    return identity, sources, goal_ids


def test_understanding_candidates_are_bounded_exact_and_goal_bound(
    service, goal_database
):
    identity, sources, goal_ids = candidates(service, goal_database)
    first = service.understanding_successes(ctx(), identity, limit=1)
    assert (
        first["page"]["hasMore"]
        and first["unavailable"] is False
        and len(first["items"]) == 1
    )
    latest = first["items"][0]
    assert (
        latest["message"]["message_id"] == "message-000080"
        and latest["userMessage"]["message_id"] == "message-000003"
    )
    assert latest["message"]["goalId"] == latest["userMessage"]["goalId"] == goal_ids[1]
    second = service.understanding_successes(
        ctx(), identity, limit=1, before=first["page"]["nextCursor"]
    )
    assert (
        second["items"][0]["message"]["goalId"]
        == second["items"][0]["userMessage"]["goalId"]
        == goal_ids[0]
    )
    assert second["page"]["hasMore"] is False
    all_messages = [
        item["message"]["message_id"]
        for page in [first, second]
        for item in page["items"]
    ]
    assert all_messages == ["message-000080", "message-000010"]
    assert service.reads == [sources[1], sources[0]]
    with psycopg.connect(goal_database) as c:
        assert c.execute(
            "SELECT count(*) FROM private_conversation.action_intents WHERE "
            "conversation_id=%s",
            (identity,),
        ).fetchone() == (0,)


def test_understanding_revoked_unavailable_and_wrong_user_do_not_prove_absence(
    service, goal_database
):
    identity, sources, _ = candidates(service, goal_database)
    with psycopg.connect(goal_database) as c:
        c.execute(
            "UPDATE test_read_permissions SET allowed=false WHERE source=%s",
            (sources[1]["invocationId"],),
        )
    value = service.understanding_successes(ctx(), identity)
    assert value["unavailable"] and len(value["items"]) == 2
    blocked = next(
        i for i in value["items"] if i["message"]["message_id"] == "message-000080"
    )
    assert (
        blocked["message"]["facts"]["readable"] is False
        and blocked["userMessage"] is None
    )
    assert "saved private body 80" not in str(value)
    service.failed = True
    assert service.understanding_successes(ctx(), identity)["unavailable"] is True
    with pytest.raises(ConversationError, match="NOT_FOUND"):
        service.understanding_successes(ctx("other"), identity)


def test_understanding_missing_or_foreign_user_stays_unavailable(
    service, goal_database
):
    identity, _, _ = candidates(service, goal_database)
    with psycopg.connect(goal_database) as c:
        c.execute(
            "UPDATE private_conversation.message_facts SET "
            "facts=jsonb_set(facts,'{userMessageId}','\"foreign-only-message\"'"
            ") "
            "WHERE conversation_id=%s AND message_id='message-000080'",
            (identity,),
        )
    result = service.understanding_successes(ctx(), identity, limit=1)
    assert result["unavailable"] and result["items"][0]["userMessage"] is None


def test_new_read_routes_preserve_http_auth_and_empty_shapes(goal_database):
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
        conversation_database_url=goal_database,
    )
    client = TestClient(app, base_url="https://testserver")
    prefix = "/api/workbench/v1/conversations"
    for suffix in ["capability-context", "understanding-successes"]:
        assert client.get(prefix + "/missing/" + suffix).status_code == 401
    client.cookies.set(SESSION_COOKIE, sessions.secret)
    assert (
        client.get(prefix + "/capabilities").json()["result"]["historyMessagePaging"]
        is True
    )
    response = client.post(
        prefix,
        json={"idempotencyKey": "successor-http", "title": "HTTP"},
        headers={"origin": "https://testserver", "x-csrf-token": "csrf-token"},
    )
    identity = response.json()["result"]["conversation_id"]
    assert (
        client.get(prefix + "/" + identity + "/capability-context").json()["result"][
            "message"
        ]
        is None
    )
    result = client.get(prefix + "/" + identity + "/understanding-successes").json()[
        "result"
    ]
    assert result["items"] == [] and result["unavailable"] is False
    page = client.get(prefix + "/" + identity + "/messages").json()["result"]["page"]
    assert page == {"hasMore": False, "nextCursor": None, "resumeCursor": None}


def test_understanding_empty_request_keys_are_not_candidates(service, goal_database):
    identity, _, _ = candidates(service, goal_database)
    with psycopg.connect(goal_database) as c:
        c.execute(
            (
                "UPDATE private_conversation.message_facts SET "
                "facts=jsonb_set(facts,'{requestKey}','\"\"') WHERE "
                "conversation_id=%s AND message_id='message-000080'"
            ),
            (identity,),
        )
    result = service.understanding_successes(ctx(), identity)
    assert [item["message"]["message_id"] for item in result["items"]] == [
        "message-000010"
    ]


@pytest.mark.parametrize("port", ["53447", "53428"])
@pytest.mark.parametrize(
    "key", ["HISTORY_PAGE_TEST_ADMIN_DSN", "AUTHORITY_I1_TEST_DATABASE_URL"]
)
def test_history_dsn_accepts_only_explicit_approved_server_without_connecting(
    port, key
):
    from psycopg.conninfo import conninfo_to_dict

    value = base_cases.history_admin_dsn(
        {key: f"postgresql://postgres:synthetic@127.0.0.1:{port}/postgres"}
    )
    parsed = conninfo_to_dict(value)
    assert (parsed["host"], parsed["hostaddr"], parsed["port"], parsed["dbname"]) == (
        "127.0.0.1",
        "127.0.0.1",
        port,
        "postgres",
    )


def test_history_dsn_equivalent_sources_and_local_authority_globals():
    source = "postgresql://postgres:synthetic@127.0.0.1:53428/postgres"
    dsn = base_cases.history_admin_dsn(
        {
            "HISTORY_PAGE_TEST_ADMIN_DSN": source,
            "AUTHORITY_I1_TEST_DATABASE_URL": (
                "host=127.0.0.1 port=53428 "
                "user=postgres "
                "password=synthetic "
                "dbname=postgres"
            ),
        }
    )

    def probe():
        yield globals().get("URL")

    before = probe.__globals__.get("URL")
    result = next(authority_fixture_generator(probe, dsn))
    from psycopg.conninfo import conninfo_to_dict

    assert conninfo_to_dict(result)["port"] == "53428"
    assert probe.__globals__.get("URL") == before
    assert base_cases.history_admin_dsn({}) is None


@pytest.mark.parametrize(
    "bad",
    [
        "host=127.0.0.1 port=64330 user=postgres dbname=postgres",
        "host=127.0.0.1 port=64335 user=postgres dbname=postgres",
        "host=127.0.0.1 port=5432 user=postgres dbname=postgres",
        "host=localhost port=53428 user=postgres dbname=postgres",
        "host=192.0.2.1 port=53428 user=postgres dbname=postgres",
        "host=127.0.0.1 hostaddr=192.0.2.1 port=53428 user=postgres dbname=postgres",
        "host=127.0.0.1 port=53428 user=postgres dbname=business",
        "host=127.0.0.1 port=53428 user=ordinary dbname=postgres",
        "host=127.0.0.1 port=53428 user=postgres dbname=postgres "
        "passfile=/tmp/not-read",
        "not a PostgreSQL DSN",
    ],
)
def test_history_dsn_rejects_unsafe_entries_without_connecting(bad):
    with pytest.raises(ValueError, match="ISOLATED_HISTORY_ADMIN_DSN_INVALID"):
        base_cases.history_admin_dsn({"AUTHORITY_I1_TEST_DATABASE_URL": bad})


def test_history_dsn_different_servers_are_rejected_without_connecting():
    with pytest.raises(ValueError, match="ISOLATED_HISTORY_ADMIN_DSN_CONFLICT"):
        base_cases.history_admin_dsn(
            {
                "HISTORY_PAGE_TEST_ADMIN_DSN": (
                    "host=127.0.0.1 port=53447 user=postgres dbname=postgres"
                ),
                "AUTHORITY_I1_TEST_DATABASE_URL": (
                    "host=127.0.0.1 port=53428 user=postgres dbname=postgres"
                ),
            }
        )


def test_history_dsn_standard_fixture_entry_creates_only_uuid_database(monkeypatch):
    import re
    from contextlib import contextmanager

    from psycopg.conninfo import conninfo_to_dict

    monkeypatch.delenv("HISTORY_PAGE_TEST_ADMIN_DSN", raising=False)
    monkeypatch.setenv(
        "AUTHORITY_I1_TEST_DATABASE_URL",
        "postgresql://postgres:synthetic@127.0.0.1:53428/postgres",
    )
    opened, queries = [], []

    class NoNetworkConnection:
        def execute(self, query):
            queries.append(str(query))

    @contextmanager
    def no_network_connect(dsn, **options):
        opened.append((conninfo_to_dict(dsn), options))
        yield NoNetworkConnection()

    monkeypatch.setattr(base_cases.psycopg, "connect", no_network_connect)
    generator = base_cases.database.__wrapped__()
    selected = next(generator)
    info = conninfo_to_dict(selected)
    assert info["port"] == "53428" and re.fullmatch(
        "history_page_[a-f0-9]{32}", info["dbname"]
    )
    with pytest.raises(StopIteration):
        next(generator)
    assert [v["dbname"] for v, _ in opened] == ["postgres", info["dbname"], "postgres"]
    assert all(v["host"] == "127.0.0.1" and v["port"] == "53428" for v, _ in opened)
    assert "CREATE DATABASE" in queries[0] and "DROP DATABASE" in queries[-1]
    assert info["dbname"] in queries[0] and info["dbname"] in queries[-1]
