"""Real authority transactions must not nest while holding their global lock."""

from datetime import UTC, datetime

import psycopg
import pytest
from agent_console.conversation_actions import ConversationActions
from agent_console.development_administrator import authorized
from agent_console.local_accounts import operate
from agent_console.private_conversation import ConversationError, PrivateConversations
from psycopg.rows import dict_row
from test_development_administrator import MIGRATION, URL, login
from test_development_administrator import setup as setup

pytestmark = pytest.mark.skipif(not URL, reason="exclusive PostgreSQL required")


def test_admin_owner_reads_complete_and_revocation_still_blocks_writes(setup):
    repo, generation, sessions, reader = setup
    with repo.connection_scope() as c:
        for name in [
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ]:
            c.execute((MIGRATION.parent / name).read_text())
    _, admin = sessions.authenticate_session(login(sessions, "devadmin").value)
    _, owner = sessions.authenticate_session(login(sessions).value)
    reads = []

    def owner_read(ctx, target):
        # A separate real owner authorization transaction, with a bounded lock wait.
        with psycopg.connect(
            repo.pool.conninfo,
            row_factory=dict_row,
            options="-c statement_timeout=1500",
        ) as c:
            assert authorized(reader, ctx, generation=1, recovery_epoch=1, connection=c)
        reads.append(target)
        return {"ownerVersion": 6, "state": "SUCCEEDED", "title": "Actual owner read"}

    records = PrivateConversations(
        repo.pool.conninfo,
        owner_read,
        lambda c, ctx: authorized(
            reader, ctx, generation=1, recovery_epoch=1, connection=c
        ),
    )
    actions = ConversationActions(records, owner_read, None)
    identity = records.create(
        owner, {"title": "cross owner", "idempotencyKey": "create"}
    )["conversation_id"]
    message = records.mutate(
        admin,
        identity,
        {"content": "Confirm draft", "expectedVersion": 0, "idempotencyKey": "message"},
        "message",
    )
    source = {
        "kind": "DRAFT",
        "invocationId": "invocation",
        "contextId": "context",
        "turnId": "turn",
        "turnVersion": 1,
    }
    payload = {
        "title": "new goal",
        "description": "new case",
        "ownerId": admin.principal_id,
        "draftInvocationId": "invocation",
        "idempotencyKey": "create-problem",
    }
    body = {
        "idempotencyKey": "intent",
        "expectedVersion": 1,
        "messageId": message["identity"],
        "action": "CREATE_PROBLEM",
        "payload": payload,
        "source": source,
        "expectedOwnerVersion": 6,
        "confirmed": True,
    }
    intent = actions.prepare(admin, identity, body)
    actions.claim(admin, identity, intent["intentId"], "CREATE_PROBLEM", payload)
    version = records.read(admin, identity)["conversation"]["version"]
    actions.source(
        admin,
        identity,
        {"source": source, "expectedVersion": version, "idempotencyKey": "source"},
    )
    version = records.read(admin, identity)["conversation"]["version"]
    target = {
        "problemId": "problem",
        "revisionId": "revision",
        "problemDigest": "a" * 64,
    }
    link = records.mutate(
        admin,
        identity,
        {"target": target, "expectedVersion": version, "idempotencyKey": "link"},
        "link",
    )
    version = records.read(admin, identity)["conversation"]["version"]
    records.mutate(
        admin,
        identity,
        {
            "content": "follow up",
            "focusLinkId": link["identity"],
            "expectedVersion": version,
            "idempotencyKey": "follow",
        },
        "message",
    )
    assert len(reads) >= 5
    version = records.read(admin, identity)["conversation"]["version"]

    def disable_during_owner_read(ctx, target):
        owner_read(ctx, target)
        operate(
            repo,
            generation.account_by_id("local-account:devadmin"),
            action="DISABLE",
            command_id="disable",
            operator_id="operator:test",
            now=datetime.now(UTC),
        )
        return {}

    records.resolve_link = disable_during_owner_read
    with pytest.raises(ConversationError, match="CONVERSATION_NOT_FOUND"):
        records.mutate(
            admin,
            identity,
            {
                "content": "must not save",
                "focusLinkId": link["identity"],
                "expectedVersion": version,
                "idempotencyKey": "denied",
            },
            "message",
        )
    assert records.read(owner, identity)["conversation"]["version"] == version
