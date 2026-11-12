"""Actual isolated PostgreSQL and owner routes; provider output is controlled."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    ProviderObservation,
)
from test_conversation_actions import ROOT, create, journey, post, read  # noqa: F401
from test_private_conversation import database  # noqa: F401


def configure(j, unknown=False):
    j.draft.profile = replace(
        j.draft.profile,
        adapter_revision="v3",
        output_schema_version="conversation-understanding-output.v3",
    )
    calls = []

    def dispatch(**kw):
        calls.append(kw["invocation_id"])
        return ProviderObservation(
            "observed:" + kw["invocation_id"],
            ObservationState.UNKNOWN if unknown else ObservationState.SUCCEEDED,
            result_kind=None if unknown else DraftResultKind.DIRECT_ANSWER,
            answer=None if unknown else "这是一条实际服务端返回的受控测试答案。",
        )

    j.transport.dispatch = dispatch
    return calls


def request(
    c, j, content="Please explain the document review process with no execution."
):
    saved = post(
        j,
        "/conversations/" + c + "/messages",
        {
            "idempotencyKey": str(uuid4()),
            "expectedVersion": read(j, c)["conversation"]["version"],
            "content": content,
        },
    )
    return {
        "conversationMessageId": saved["identity"],
        "idempotencyKey": str(uuid4()),
        "conversationId": c,
        "content": "Please explain the document review process with no execution.",
    }


def test_saved_answer_survives_read_and_duplicate_owner_response(journey):  # noqa: F811
    j = journey
    calls = configure(j)
    c = create(j)
    body = request(c, j)
    first = post(j, "/draft-assistance/invocations", body, status=201)
    assert first["conversationDelivery"]["state"] == "SAVED"
    again = post(j, "/draft-assistance/invocations", body, status=201)
    assert (
        again["conversationDelivery"]["messageId"]
        == first["conversationDelivery"]["messageId"]
    )
    assert again["answer"] == first["answer"]
    route = (
        ROOT
        + "/conversations/"
        + c
        + "/understanding-results/"
        + body["conversationMessageId"]
    )
    recovered = j.client.get(route, params={"requestKey": body["idempotencyKey"]})
    assert recovered.status_code == 200
    assert recovered.json()["result"]["answer"] == first["answer"]
    assert (
        j.client.get(route, params={"requestKey": "another-request"}).status_code == 404
    )
    for _ in range(2):
        rows = [m for m in read(j, c)["messages"] if m.get("kind")]
        assert len(rows) == 1 and rows[0]["content"] == first["answer"]
        assert rows[0]["facts"]["assistantResponse"] is True
        assert rows[0]["facts"]["requestKey"] == body["idempotencyKey"]
        assert rows[0]["facts"]["userMessageId"] == body["conversationMessageId"]
        assert rows[0]["facts"]["source"]["invocationId"] == first["invocationId"]
    reopened, _ = j.make()
    assert (
        reopened.get(ROOT + "/conversations/" + c).json()["result"]["messages"][-1][
            "content"
        ]
        == first["answer"]
    )
    assert len(calls) == 1
    j.draft.authorization.can_read = lambda *args: False
    hidden = read(j, c)["messages"][-1]
    assert hidden["facts"] == {"readable": False}
    assert first["answer"] not in hidden["content"]


def test_save_failure_is_not_saved_or_reexecuted(journey, monkeypatch):  # noqa: F811
    j = journey
    calls = configure(j)
    c = create(j)
    body = request(c, j)
    actions = j.app.state.conversation_actions

    def fail(*args, **kw):
        raise RuntimeError("controlled persistence failure")

    monkeypatch.setattr(actions, "insert", fail)
    result = post(j, "/draft-assistance/invocations", body, status=201)
    assert result["conversationDelivery"]["state"] == "SAVE_FAILED"
    assert len(read(j, c)["messages"]) == 1
    monkeypatch.undo()
    retry = post(j, "/draft-assistance/invocations", body, status=201)
    assert retry["conversationDelivery"]["state"] == "CONTENT_UNAVAILABLE"
    recovered = j.client.get(
        ROOT
        + "/conversations/"
        + c
        + "/understanding-results/"
        + body["conversationMessageId"],
        params={"requestKey": body["idempotencyKey"]},
    ).json()["result"]
    assert recovered["conversationDelivery"]["state"] == "CONTENT_UNAVAILABLE"
    assert len(calls) == 1 and len(read(j, c)["messages"]) == 1


def test_unknown_owner_result_does_not_fabricate_or_replay_answer(journey):  # noqa: F811
    j = journey
    calls = configure(j, unknown=True)
    c = create(j)
    body = request(c, j)
    for _ in range(2):
        result = post(j, "/draft-assistance/invocations", body, status=201)
        assert result["conversationDelivery"]["state"] == "NOT_COMPLETED"
    recovered = j.client.get(
        ROOT
        + "/conversations/"
        + c
        + "/understanding-results/"
        + body["conversationMessageId"],
        params={"requestKey": body["idempotencyKey"]},
    ).json()["result"]
    assert recovered["state"] == "OUTCOME_UNKNOWN"
    assert recovered["conversationDelivery"]["state"] == "NOT_COMPLETED"
    assert len(calls) == 1 and len(read(j, c)["messages"]) == 1


def test_foreign_conversation_is_rejected_before_model(journey):  # noqa: F811
    j = journey
    calls = configure(j)
    c = create(j)
    body = request(c, j)
    j.sessions.context = SimpleNamespace(
        principal_id="other", scope=j.sessions.context.scope
    )
    post(j, "/draft-assistance/invocations", body, status=404)
    assert calls == []


def test_client_cannot_submit_an_assistant_answer_or_mix_conversation_bindings(journey):  # noqa: F811
    j = journey
    calls = configure(j)
    c = create(j)
    body = request(c, j)
    post(j, "/draft-assistance/invocations", {**body, "answer": "forged"}, status=422)
    post(
        j,
        "/draft-assistance/invocations",
        body,
        headers={"x-conversation-id": c, "x-conversation-intent": "legacy"},
        status=409,
    )
    assert calls == [] and len(read(j, c)["messages"]) == 1


def test_request_must_match_exact_user_message_not_another_turn(journey):  # noqa: F811
    j = journey
    calls = configure(j)
    c = create(j)
    body = request(c, j)
    for invalid in [
        {**body, "conversationMessageId": "missing"},
        {**body, "content": "a different user goal"},
    ]:
        post(j, "/draft-assistance/invocations", invalid, status=409)
    assert calls == []


def test_followup_context_uses_the_exact_saved_answer_and_rejects_forgery(journey):  # noqa: F811
    import json

    from agent_console.draft_assistance_policy import V3_CONTEXT_VERSION

    j = journey
    calls = configure(j)
    c = create(j)
    first_body = request(c, j)
    first = post(j, "/draft-assistance/invocations", first_body, status=201)
    body = request(c, j, "再详细说一点")
    envelope = {
        "schemaVersion": V3_CONTEXT_VERSION,
        "uiRevision": 2,
        "messages": [
            {"id": "user:1", "text": first_body["content"]},
            {"id": "user:2", "text": "再详细说一点"},
        ],
        "currentDraft": None,
        "previousUnderstanding": [],
        "previousQuestion": None,
        "previousAssistantResponse": {
            "invocationId": first["invocationId"],
            "answer": "a forged answer",
        },
    }
    post(
        j,
        "/draft-assistance/invocations",
        {**body, "content": json.dumps(envelope)},
        status=409,
    )
    assert len(calls) == 1
    envelope["previousAssistantResponse"]["answer"] = first["answer"]
    second = post(
        j,
        "/draft-assistance/invocations",
        {
            **body,
            "content": json.dumps(envelope),
            "parentContextId": first["contextId"],
            "parentTurnId": first["turnId"],
            "expectedParentVersion": first["turnVersion"],
            "predecessorInvocationId": first["invocationId"],
        },
        status=201,
    )
    assert second["conversationDelivery"]["state"] == "SAVED" and len(calls) == 2
    assert second["contextId"] == first["contextId"]
