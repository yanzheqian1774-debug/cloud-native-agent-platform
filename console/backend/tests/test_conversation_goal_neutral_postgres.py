# ruff: noqa: F401,F811,E501 -- Reuse isolated formal fixed-cycle owner dependencies.
"""Real retained BOUND/provenance reader; controlled original BIND fixture.

This does not claim a real model invocation or live business acceptance.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
import test_fixed_chat_delivery_postgres as original
from agent_console import conversation_goal_slots as goals
from agent_console.conversation_relation_reader import reader
from agent_console.fixed_chat_delivery import FixedChatDelivery
from test_fixed_chat_delivery_postgres import automation, case, repository, services


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_bound_without_readable_cycle_has_neutral_original_reader(
    automation, monkeypatch, tmp_path
):
    monkeypatch.setenv("CONVERSATION_GOAL_SLOTS_ENABLED", "1")
    monkeypatch.setenv("CONVERSATION_GOAL_NATURAL_ENABLED", "1")
    original_read = FixedChatDelivery.read
    seen = []

    def inspect(owner, call, conversation, *args, **kwargs):
        if not seen:
            records, ctx = owner.records, call.context
            with records.connect() as c:
                c.execute(
                    (
                        Path(__file__).parents[1]
                        / "migrations/0047_conversation_action_facts.sql"
                    ).read_text()
                )
                goals.migrate(c)
                before = c.execute(
                    "SELECT record,digest FROM fixed_work_sources.bindings WHERE conversation_id=%s",
                    (conversation,),
                ).fetchone()
            version = records.head(ctx, conversation)["conversation"]["version"]
            message = records.mutate(
                ctx,
                conversation,
                dict(
                    content="你好",
                    idempotencyKey="neutral-greeting",
                    expectedVersion=version,
                ),
                "message",
            )["identity"]
            actual = reader(
                SimpleNamespace(state=SimpleNamespace()),
                None,
                None,
                SimpleNamespace(records=records),
            )
            snapshot = actual(ctx, conversation, message, None)
            assert (
                snapshot["target"] is None and snapshot["currentQuestionToken"] is None
            )
            assert snapshot["input"]["stage"] == "FIXED_WORK_BACKGROUND"
            assert snapshot["input"]["naturalGoalIntentVersion"] == "v1"
            assert snapshot["neutralBinding"]["bindingDigest"] == before["digest"]
            assert "fixedCycleObservation" not in snapshot["input"]
            with records.connect() as c:
                assert (
                    c.execute(
                        "SELECT record,digest FROM fixed_work_sources.bindings WHERE conversation_id=%s",
                        (conversation,),
                    ).fetchone()
                    == before
                )
                assert (
                    c.execute(
                        "SELECT count(*) n FROM conversation_goals.slots"
                    ).fetchone()["n"]
                    == 0
                )
                assert (
                    c.execute(
                        "SELECT count(*) n FROM conversation_goals.result_adoptions"
                    ).fetchone()["n"]
                    == 0
                )
            seen.append(snapshot)
        return original_read(owner, call, conversation, *args, **kwargs)

    monkeypatch.setattr(FixedChatDelivery, "read", inspect)
    original.test_bound_committed_event_is_read_in_original_chat_without_human_model_lease(
        automation, monkeypatch, tmp_path
    )
    assert len(seen) == 1
