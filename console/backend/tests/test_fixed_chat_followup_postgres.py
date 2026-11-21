# ruff: noqa: F401,F811 -- Original isolated fixture dependencies.
"""Exact focus into single-C1 reader, without dispatching any provider."""

import pytest
import test_fixed_chat_bff_postgres as bff
from agent_console.conversation_answer_retention import require_fixed_basis
from agent_console.conversation_relation_reader import reader
from agent_console.fixed_chat_delivery import FixedChatDelivery
from fastapi.testclient import TestClient
from test_fixed_chat_delivery_postgres import automation, case, repository, services


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_focus_is_saved_message_bound_and_read_revocation_hides_basis(
    automation, monkeypatch, tmp_path
):
    monkeypatch.setenv("FIXED_CHAT_FOLLOWUP_ENABLED", "1")
    state = {}
    selected = FixedChatDelivery.selected

    def capture(owner, call, *args):
        state.update(context=call.context, records=owner.records)
        return selected(owner, call, *args)

    monkeypatch.setattr(FixedChatDelivery, "selected", capture)
    post = TestClient.post

    def after_post(client, url, *args, **kwargs):
        response = post(client, url, *args, **kwargs)
        if (
            url.endswith("/read-access")
            and response.status_code == 200
            and response.json()["result"]["state"] == "READ_READY"
            and "focus" not in state
        ):
            result = response.json()["result"]
            body = kwargs["json"]
            headers = kwargs["headers"]
            conversation = result["conversationId"]
            records, ctx = state["records"], state["context"]
            with records.connect() as c:
                from pathlib import Path

                c.execute(
                    (
                        Path(__file__).parents[1]
                        / "migrations/0047_conversation_action_facts.sql"
                    ).read_text()
                )
                version = records.owned(c, ctx, conversation)["version"]
            request = {
                k: body[k]
                for k in (
                    "bindingDigest",
                    "workDigest",
                    "eventId",
                    "receiptDigest",
                    "preparationDigest",
                    "runId",
                )
            }
            request.update(commandId="focus-once", expectedConversationVersion=version)
            focus_url = url[: -len("/read-access")] + "/focus"
            invalid = {**request, "runId": "other-run", "commandId": "wrong-run"}
            assert (
                post(client, focus_url, headers=headers, json=invalid).status_code
                != 200
            )
            focus = post(client, focus_url, headers=headers, json=request)
            assert focus.status_code == 200, focus.text
            focus = focus.json()["result"]
            assert (
                focus["contentComplete"] is False
                and focus["excerptedArtifactCount"] > 0
            )
            state["focus"] = focus
            again = post(client, focus_url, headers=headers, json=request)
            assert (
                again.status_code == 200 and again.json()["result"]["replayed"] is True
            )
            assert again.json()["result"]["focusLinkId"] == focus["focusLinkId"]
            saved = client.get(
                focus_url, headers=headers, params={"commandId": "focus-once"}
            )
            assert (
                saved.status_code == 200
                and saved.json()["result"]["focusDigest"] == focus["focusDigest"]
            )
            message = records.mutate(
                ctx,
                conversation,
                dict(
                    idempotencyKey="followup-user",
                    expectedVersion=focus["conversationVersion"],
                    content="这次检查有哪些遗漏?",
                    focusLinkId=focus["focusLinkId"],
                ),
                "message",
            )
            actions = client.app.state.conversation_actions
            snapshot = reader(client.app, automation.adapter, None, actions)(
                ctx, conversation, message["identity"], None
            )
            assert (
                snapshot["target"] is None and snapshot["currentQuestionToken"] is None
            )
            assert snapshot["input"]["stage"] == "FIXED_CYCLE_OBSERVATION"
            assert snapshot["input"]["currentQuestion"] is None
            assert snapshot["input"]["fixedCycleObservation"]["outputs"]
            basis, _ = client.app.state.fixed_cycle_focus_reader(
                ctx, conversation, message_id=message["identity"]
            )
            require_fixed_basis(actions, ctx, conversation, {"fixedCycleFocus": basis})
            state.update(
                actions=actions,
                conversation=conversation,
                basis=basis,
                client=client,
                headers=headers,
                focus_url=focus_url,
            )
        return response

    monkeypatch.setattr(TestClient, "post", after_post)
    bff.test_actual_bff_mount_initial_receipt_replay_and_revocation(
        automation, monkeypatch, tmp_path
    )
    assert "focus" in state
    from agent_console.authority_contracts import AuthorityError

    with pytest.raises(AuthorityError):
        require_fixed_basis(
            state["actions"],
            state["context"],
            state["conversation"],
            {"fixedCycleFocus": state["basis"]},
        )
    reply = state["client"].get(
        state["focus_url"], headers=state["headers"], params={"commandId": "focus-once"}
    )
    assert reply.status_code != 200
