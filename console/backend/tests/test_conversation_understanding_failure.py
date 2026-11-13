"""Real isolated conversation/draft/source owners; controlled failed provider only."""

# ruff: noqa: F401,F811 -- Shared disposable database/session fixtures.
import json

import pytest
from agent_console.draft_assistance import ObservationState, ProviderObservation
from agent_console.workbench_bff import PREFIX
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted
from test_understanding_adoption_source import select

pytestmark = [
    pytestmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
]


def failed(e):
    select(e)
    routing = e.adoption_client.app.state.understanding_adoption.routing
    original = routing.transport.dispatch
    calls = []

    def dispatch(**kw):
        calls.append(kw["invocation_id"])
        return ProviderObservation(
            "failed:" + kw["invocation_id"],
            ObservationState.FAILED,
            reason_code="OUTPUT_SCHEMA_INVALID",
            input_tokens=10,
            output_tokens=20,
            local_cleanup={"reaped": True},
        )

    routing.transport.dispatch = dispatch
    head = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/head").json()[
        "result"
    ]
    sent = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/messages",
        headers=e.adoption_headers,
        json={
            "content": "生产环境",
            "idempotencyKey": "failed-message",
            "expectedVersion": head["conversation"]["version"],
        },
    )
    assert sent.status_code == 200, sent.text
    message = sent.json()["result"]["identity"]
    response = e.adoption_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.adoption_headers,
        json={
            "content": "生产环境",
            "idempotencyKey": "failed-call",
            "conversationId": e.conv,
            "conversationMessageId": message,
            "conversationRouting": True,
        },
    )
    assert response.status_code in (200, 201), response.text
    assert response.json()["result"]["state"] == "FAILED", response.text
    routing.transport.dispatch = original
    return message, response.json()["result"], calls


def body(e, item):
    return {
        "idempotencyKey": item["successorRequestKey"],
        "conversationRouting": True,
        "conversationId": e.conv,
        "conversationMessageId": item["messageId"],
        "failedRetryOf": item["invocationId"],
        "content": json.dumps(
            {
                "schemaVersion": "conversation-understanding-context.v2",
                "uiRevision": 1,
                "messages": [
                    {"id": "user:" + item["messageId"], "text": item["originalText"]}
                ],
                "currentDraft": None,
                "previousUnderstanding": None,
                "previousQuestion": None,
                "previousAssistantResponse": None,
            }
        ),
    }


def test_real_failure_discovery_and_single_successor(adopted):
    e = adopted
    message, result, calls = failed(e)
    url = PREFIX + f"/conversations/{e.conv}/understanding-failures"
    listing = e.adoption_client.get(url)
    assert listing.status_code == 200, listing.text
    items = listing.json()["result"]["items"]
    assert len(items) == 1, listing.text
    item = items[0]
    assert (
        item["messageId"] == message and item["invocationId"] == result["invocationId"]
    )
    assert item["continuationEligible"], listing.text
    assert len(calls) == 1 and not e.calls
    request = body(e, item)
    for _ in range(2):
        response = e.adoption_client.post(
            PREFIX + "/draft-assistance/invocations",
            headers=e.adoption_headers,
            json=request,
        )
        assert response.status_code in (200, 201), response.text
        assert response.json()["result"]["state"] == "SUCCEEDED", response.text
    adoption = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/understanding-results/{message}/adoption",
        headers=e.adoption_headers,
        json={"requestKey": item["successorRequestKey"]},
    )
    assert adoption.status_code == 200, adoption.text
    assert len(e.calls) == 1
    again = e.adoption_client.get(url)
    assert again.status_code == 200, again.text
    assert again.json()["result"]["items"][0]["successor"] is not None
    assert len(e.calls) == 1


@pytest.mark.parametrize("change", ["key", "text", "message", "conversation"])
def test_retry_rejects_substitution_without_provider(adopted, change):
    e = adopted
    failed(e)
    listing = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-failures"
    )
    item = listing.json()["result"]["items"][0]
    request = body(e, item)
    if change == "key":
        request["idempotencyKey"] = "new-client-key"
    elif change == "text":
        changed = json.loads(request["content"])
        changed["messages"][0]["text"] = "测试环境"
        request["content"] = json.dumps(changed)
    elif change == "message":
        request["conversationMessageId"] = e.message
    else:
        request["conversationId"] = "not-owned-conversation"
    result = e.adoption_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.adoption_headers,
        json=request,
    )
    assert result.status_code in (403, 404, 409), result.text
    assert not e.calls


def test_journal_race_is_rechecked_inside_claim(adopted, monkeypatch):
    import agent_console.conversation_understanding_failure as owner

    e = adopted
    failed(e)
    item = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-failures"
    ).json()["result"]["items"][0]
    original = owner.require_retry_claim

    def raced(connection, candidate):
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.journeys SET version=version+1 "
                "WHERE conversation_id=%s",
                (e.conv,),
            )
        return original(connection, candidate)

    monkeypatch.setattr(owner, "require_retry_claim", raced)
    result = e.adoption_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.adoption_headers,
        json=body(e, item),
    )
    assert result.status_code == 409, result.text
    assert not e.calls


def test_two_explicit_clicks_share_successor_claim(adopted):
    from concurrent.futures import ThreadPoolExecutor

    e = adopted
    failed(e)
    item = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-failures"
    ).json()["result"]["items"][0]
    request = body(e, item)

    def invoke(_):
        return e.adoption_client.post(
            PREFIX + "/draft-assistance/invocations",
            headers=e.adoption_headers,
            json=request,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, range(2)))
    assert all(r.status_code in (200, 201, 503) for r in results), [
        r.text for r in results
    ]
    for response in results:
        if response.status_code == 503:
            assert (
                response.json()["reasonCode"] == "CONVERSATION_FAILED_RETRY_IN_PROGRESS"
            )
    successful = [r for r in results if r.status_code in (200, 201)]
    assert successful
    assert len({r.json()["result"]["invocationId"] for r in successful}) == 1
    read = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-failures"
    )
    assert read.status_code == 200, read.text
    assert (
        read.json()["result"]["items"][0]["successor"]["invocationId"]
        == successful[0].json()["result"]["invocationId"]
    )
    assert len(e.calls) == 1


@pytest.mark.parametrize("boundary", ["unsettled", "not-reaped", "archived"])
def test_failed_retry_requires_current_terminal_eligibility(adopted, boundary):
    from dataclasses import replace

    from agent_console.draft_assistance import DraftScope

    e = adopted
    _, failed_result, _ = failed(e)
    item = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-failures"
    ).json()["result"]["items"][0]
    if boundary == "archived":
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE private_conversation.conversations SET archived_at=now() "
                "WHERE conversation_id=%s",
                (e.conv,),
            )
    else:
        repository = e.draft.repository
        original = repository.get(
            DraftScope.from_context(e.context), failed_result["invocationId"]
        )
        changes = (
            {"settlement_status": "UNSETTLED"}
            if boundary == "unsettled"
            else {"local_cleanup": {"reaped": False}}
        )
        assert repository.compare_and_set(
            original.aggregate_version,
            replace(
                original, aggregate_version=original.aggregate_version + 1, **changes
            ),
        )
    listing = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/understanding-failures"
    )
    if listing.status_code == 200:
        assert not any(
            i["continuationEligible"] for i in listing.json()["result"]["items"]
        )
    else:
        assert listing.status_code in (403, 404, 409)
    response = e.adoption_client.post(
        PREFIX + "/draft-assistance/invocations",
        headers=e.adoption_headers,
        json=body(e, item),
    )
    assert response.status_code in (403, 404, 409), response.text
    assert not e.calls
