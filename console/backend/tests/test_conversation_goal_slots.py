# ruff: noqa: F401, F811, E501 -- Dedicated random planning database fixture.
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from agent_console import conversation_goal_slots as goals
from agent_console.private_conversation import ConversationError, PrivateConversations
from psycopg.types.json import Jsonb
from test_plan_suggestion_v2 import repository


def test_two_goal_journals_cas_and_replay_do_not_rewrite_legacy(
    repository, monkeypatch
):
    migrations = Path(__file__).parents[1] / "migrations"
    records = PrivateConversations(repository.pool.conninfo, lambda *args: None)
    ctx = N(
        principal_id="human:goal-test",
        scope=N(tenant_id="tenant", security_domain="domain"),
    )
    with records.connect() as c:
        for name in (
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ):
            c.execute((migrations / name).read_text())
        goals.migrate(c)
        c.execute(
            "CREATE TABLE private_conversation.journeys(tenant_id text,security_domain text,conversation_id text,version bigint,state jsonb,PRIMARY KEY(tenant_id,security_domain,conversation_id))"
        )
    chat = records.create(ctx, {"idempotencyKey": "chat", "title": "two goals"})[
        "conversation_id"
    ]
    legacy = {"phase": "PLAN", "key": "fixed-original", "problem": {"id": "unchanged"}}
    with records.connect() as c:
        c.execute(
            "INSERT INTO private_conversation.journeys VALUES(%s,%s,%s,7,%s)",
            (*records.scope(ctx), chat, Jsonb(legacy)),
        )
    made = []
    for i in range(2):
        version = records.head(ctx, chat)["conversation"]["version"]
        message = records.mutate(
            ctx,
            chat,
            dict(
                idempotencyKey=f"message{i}",
                expectedVersion=version,
                content=f"Independent goal {i}",
                focusLinkId=None,
            ),
            "message",
        )["identity"]
        body = goals.CreateGoal(
            commandId=f"goal{i}",
            messageId=message,
            expectedConversationVersion=version + 1,
        )
        with records.connect() as c:
            item = goals.create(c, records, ctx, chat, body)
            assert goals.create(c, records, ctx, chat, body) == {
                **item,
                "replayed": True,
            }
            assert goals.message_goal(c, records, ctx, chat, message) == item["goalId"]
            assert goals.read(c, records, ctx, chat, item["goalId"]) == {
                "version": 0,
                "state": None,
            }
            goals.save(
                c,
                records,
                ctx,
                chat,
                item["goalId"],
                0,
                {"phase": "UNDERSTAND", "key": f"new{i}"},
            )
        with (
            pytest.raises(
                ConversationError, match="CONVERSATION_GOAL_MESSAGE_ALREADY_USED"
            ),
            records.connect() as c,
        ):
            goals.create(
                c,
                records,
                ctx,
                chat,
                body.model_copy(update={"commandId": f"different{i}"}),
            )
        made.append(item)
    assert made[0]["goalId"] != made[1]["goalId"]
    with records.connect() as c:
        assert c.execute(
            "SELECT version,state FROM private_conversation.journeys WHERE conversation_id=%s",
            (chat,),
        ).fetchone() == {"version": 7, "state": legacy}
        assert (
            goals.read(c, records, ctx, chat, made[0]["goalId"])["state"]["key"]
            == "new0"
        )
        assert (
            goals.read(c, records, ctx, chat, made[1]["goalId"])["state"]["key"]
            == "new1"
        )
    with (
        pytest.raises(ConversationError, match="JOURNEY_VERSION_CONFLICT"),
        records.connect() as c,
    ):
        goals.save(c, records, ctx, chat, made[0]["goalId"], 0, {"phase": "overwrite"})
    foreign = N(principal_id="human:other", scope=ctx.scope)
    with pytest.raises(ConversationError), records.connect() as c:
        goals.read(c, records, foreign, chat, made[0]["goalId"])

    # Claim-time scope is server bound, never supplied in a model payload.
    from agent_console.conversation_experience_admission import _binding
    from agent_console.conversation_goal_selection import require_claim_binding

    def new_message(key, **extras):
        return records.mutate(
            ctx,
            chat,
            dict(
                idempotencyKey=key,
                expectedVersion=records.head(ctx, chat)["conversation"]["version"],
                content=key,
                focusLinkId=None,
                **extras,
            ),
            "message",
        )["identity"]

    monkeypatch.setenv("CONVERSATION_GOAL_SLOTS_ENABLED", "1")
    child = new_message("goal-child", goalId=made[0]["goalId"])
    with records.connect() as c:
        assert goals.message_goal(c, records, ctx, chat, child) == made[0]["goalId"]
    with (
        pytest.raises(ConversationError, match="BINDING_CHANGED"),
        records.connect() as c,
    ):
        require_claim_binding(
            c,
            N(
                conversation_context=dict(
                    conversationId=chat, messageId=child, goalId=made[1]["goalId"]
                ),
                scope=N(namespace="tenant", security_domain="domain"),
                initiating_principal_id=ctx.principal_id,
                invocation_id="wrong-goal",
                predecessor_invocation_id=None,
            ),
        )
    with records.connect() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM conversation_goals.claimed_messages"
            ).fetchone()["n"]
            == 0
        )
    unassigned = new_message("claimed-original")
    token = _binding.set((chat, unassigned, "same-request", False))
    try:
        with records.connect() as c:
            require_claim_binding(
                c,
                N(
                    conversation_context=None,
                    scope=N(namespace="tenant", security_domain="domain"),
                    initiating_principal_id=ctx.principal_id,
                    invocation_id="original-invocation",
                    predecessor_invocation_id=None,
                ),
            )
    finally:
        _binding.reset(token)
    with (
        pytest.raises(ConversationError, match="MESSAGE_ALREADY_USED"),
        records.connect() as c,
    ):
        goals.create(
            c,
            records,
            ctx,
            chat,
            goals.CreateGoal(
                commandId="late-goal",
                messageId=unassigned,
                expectedConversationVersion=records.head(ctx, chat)["conversation"][
                    "version"
                ],
            ),
        )
    monkeypatch.delenv("CONVERSATION_GOAL_SLOTS_ENABLED")
    with pytest.raises(ConversationError, match="GOALS_DISABLED"):
        new_message("disabled", goalId=made[0]["goalId"])
    with records.connect() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM private_conversation.messages WHERE request_key='disabled'"
            ).fetchone()["n"]
            == 0
        )
    with (
        pytest.raises(ConversationError, match="SCHEMA_INVALID"),
        records.connect() as c,
    ):
        c.execute(
            "ALTER TABLE conversation_goals.messages DISABLE TRIGGER immutable_goal_message"
        )
        goals.require_schema(c)

    with (
        pytest.raises(ConversationError, match="SCHEMA_INVALID"),
        records.connect() as c,
    ):
        constraint = c.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid='conversation_goals.messages'::regclass "
            "AND contype='f' AND confrelid='conversation_goals.slots'::regclass"
        ).fetchone()["conname"]
        from psycopg import sql

        c.execute(
            sql.SQL(
                "ALTER TABLE conversation_goals.messages DROP CONSTRAINT {}"
            ).format(sql.Identifier(constraint))
        )
        goals.require_schema(c)
    # Both failed schema mutations roll back, preserving the immutable identities.
    with records.connect() as c:
        goals.require_schema(c)
