"""Actual prepare, HTTP exchange and SSE parser; controlled socket, no network."""

import io
import json
import socket
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.conversation_relation_context import bind_snapshot, sealed_snapshot
from agent_console.draft_assistance import DraftAssistanceError, ObservationState
from agent_console.draft_assistance_bootstrap import _profile
from agent_console.draft_assistance_policy import V3_CONTEXT_VERSION, policy_for
from agent_console.model_governance import canonical_digest
from agent_console.openai_responses_draft_adapter import (
    OpenAIResponsesDraftTransport,
    ResolvedOpenAICredential,
)
from agent_console.structured_understanding_wire import (
    REVISION,
    VERSION,
    compile_schema,
)
from test_draft_assistance_policy import content
from test_openai_responses_draft_adapter import _completed, _real_runtime_document
from test_structured_understanding_wire import contract, draft


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(
        socket.socket, "connect", lambda *a: pytest.fail("network forbidden")
    )
    policy = policy_for(REVISION, VERSION)
    document = _real_runtime_document(NS(server_port=1), tmp_path / "unused", tmp_path)
    document.update(
        executionClass="REAL_PROVIDER",
        responsesUrl="https://api.openai.com/v1/responses",
        nativeModelId="gpt-6.1-sol",
        maximumInputTokens=65536,
        maximumOutputTokens=8192,
        totalTimeoutSeconds=60,
        connectTimeoutSeconds=5,
        readTimeoutSeconds=55,
        outputSchemaVersion=VERSION,
        policyDigest=policy.digest,
        tls={"caFile": None},
    )
    document["adapter"]["revision"] = REVISION
    document["budget"].update(
        callCap=20,
        totalCostCapMicrousd=1_000_000,
        allowanceId="allowance:original",
        profilePricingRootDigest="a" * 64,
    )
    document.pop("profileDigest")
    document["profileDigest"] = canonical_digest(document)
    profile, _, configuration, budget = _profile(document)
    transport = OpenAIResponsesDraftTransport(configuration)
    envelope = json.loads(content())
    envelope.update(schemaVersion=V3_CONTEXT_VERSION, previousAssistantResponse=None)
    snapshot = sealed_snapshot(
        "conversation",
        "message",
        {"kind": "UNDERSTANDING"},
        {
            "currentQuestion": "Which scope?",
            "currentQuestionType": "UNDERSTANDING",
            "serverUserMessages": [
                {"id": "server-message:original", "text": "Original scope"}
            ],
        },
    )
    with bind_snapshot(snapshot):
        request = transport.prepare(
            invocation_id="one", content=json.dumps(envelope), profile=profile
        )
    value = draft()
    value["currentQuestionToken"] = snapshot["currentQuestionToken"]
    for slot in value["understanding"].values():
        if isinstance(slot, dict):
            slot["sourceRefs"] = ["server-message:original"]
    assert budget["allowanceId"] == "allowance:original"
    assert transport.dispatch_count == 0
    return NS(
        transport=transport,
        profile=profile,
        request=request,
        value=value,
        snapshot=snapshot,
        envelope=envelope,
    )


def exchange(monkeypatch, e, result, *, response=None):
    completed = _completed(result) if response is None else response
    completed["model"] = "gpt-6.1-sol"
    raw = (
        "data: "
        + json.dumps(
            {
                "type": "response.incomplete"
                if completed.get("status") == "incomplete"
                else "response.completed",
                "response": completed,
            }
        )
        + "\n\n"
    ).encode()

    class Response(io.BytesIO):
        status = 200

        def getheader(self, name):
            return (
                "text/event-stream" if name == "content-type" else "controlled-request"
            )

    calls = []

    class Connection:
        sock = NS(settimeout=lambda _: None)

        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def request(self, method, path, **kwargs):
            calls.append((method, path, kwargs["body"]))

        def getresponse(self):
            return Response(raw)

        def close(self):
            pass

    monkeypatch.setattr("http.client.HTTPSConnection", Connection)
    credential = ResolvedOpenAICredential(
        "fake-local-key",
        e.transport.configuration.credential_reference,
        e.transport.configuration.credential_version,
    )
    e.transport._measurement = None
    result = e.transport._dispatch_observation(
        invocation_id="one", request=e.request, credential=credential, profile=e.profile
    )
    assert len(calls) == e.transport.dispatch_count == 1
    assert calls[0][2] == e.request.payload
    return result


def test_full_prepared_schema_sse_and_immutable_prior_policy(prepared, monkeypatch):
    e = prepared
    old = policy_for(
        "v3-relation-adoption-source-answers",
        "conversation-understanding-output.v3-relation-adoption-answers",
    )
    assert (
        old.digest == "e8d08188eb465370ee726dd0c9ec730b614f304f4afb36134a022117d3fc6076"
    )
    sent = json.loads(e.request.payload)
    assert sent["text"]["format"]["schema"] == compile_schema(e.snapshot["input"])
    assert e.request.quote.input_token_upper_bound == len(e.request.payload)
    result = exchange(monkeypatch, e, {"result": e.value})
    assert result.state is ObservationState.SUCCEEDED
    assert result.result_kind.value == "DRAFT_READY"
    assert (
        result.conversation_route["currentQuestionToken"]
        == e.value["currentQuestionToken"]
    )
    assert len(result.understanding) == 5


@pytest.mark.parametrize(
    "bad", ["null-token", "old-array", "extra-slot", "schema-drift"]
)
def test_invalid_complete_output_fails_once_with_usage(prepared, monkeypatch, bad):
    e = prepared
    if bad == "null-token":
        e.value["currentQuestionToken"] = None
    elif bad == "old-array":
        e.value["understanding"] = [
            {"field": "goal", **e.value["understanding"]["goal"]}
        ] * 5
    elif bad == "extra-slot":
        e.value["understanding"]["goal2"] = e.value["understanding"]["goal"]
    else:
        sent = json.loads(e.request.payload)
        sent["text"]["format"]["schema"] = {}
        e.request = replace(e.request, payload=json.dumps(sent).encode())
    result = exchange(monkeypatch, e, {"result": e.value})
    assert result.reason_code == "OUTPUT_SCHEMA_INVALID"
    assert e.transport._measurement["settleable"] is True


@pytest.mark.parametrize(
    "decision,candidate",
    [("CONFIRM", "p"), ("CHANGE", "q"), ("REJECT", None), ("UNCLEAR", None)],
)
def test_one_typed_answer_uses_original_snapshot_in_sse(
    prepared, monkeypatch, decision, candidate
):
    e = prepared
    meaning = {
        "decision": decision,
        "candidateId": candidate,
        "questionContractDigest": contract()["contractDigest"],
    }
    e.snapshot = sealed_snapshot(
        "conversation",
        "message",
        {"kind": "NATIVE"},
        {
            "currentQuestion": "Scope?",
            "currentQuestionType": "NATIVE",
            "answerContract": contract(),
        },
    )
    with bind_snapshot(e.snapshot):
        e.request = e.transport.prepare(
            invocation_id="one", content=json.dumps(e.envelope), profile=e.profile
        )
    e.value.update(
        kind="CURRENT_QUESTION_ANSWER",
        currentQuestionToken=e.snapshot["currentQuestionToken"],
        title=None,
        description=None,
        understanding=[],
        questionAnswer=meaning,
    )
    # Deliberately put another snapshot in context while decoding the saved request.
    with bind_snapshot(sealed_snapshot("other", "other", None, {})):
        result = exchange(monkeypatch, e, {"result": e.value})
    assert result.state is ObservationState.SUCCEEDED
    assert result.conversation_route["questionAnswer"] == meaning


def test_full_schema_counts_against_original_input_cap(prepared):
    e = prepared
    bounded = OpenAIResponsesDraftTransport(
        replace(
            e.transport.configuration, maximum_input_tokens=len(e.request.payload) - 1
        )
    )
    with (
        bind_snapshot(e.snapshot),
        pytest.raises(DraftAssistanceError, match="INPUT_BOUND"),
    ):
        bounded.prepare(
            invocation_id="one", content=json.dumps(e.envelope), profile=e.profile
        )


@pytest.mark.parametrize("owner", ["UNDERSTANDING", "NATIVE", "PLANNING"])
@pytest.mark.parametrize("source_null", [False, True])
def test_new_wire_keeps_exact_body_boundary(prepared, owner, source_null):
    from agent_console.conversation_source_input import bind_attachment
    from test_understanding_source_body import selected, snapshot

    e = prepared
    source = selected()
    with (
        bind_snapshot(snapshot(source, owner, source_null=source_null)),
        bind_attachment(json.dumps(source)),
    ):
        request = e.transport.prepare(
            invocation_id="body", content=json.dumps(e.envelope), profile=e.profile
        )
    attachment = json.loads(
        json.loads(request.payload)["input"][1]["content"][0]["text"]
    )
    assert ("originalContent" in attachment) == (owner == "UNDERSTANDING")
    if owner == "UNDERSTANDING":
        assert attachment["originalContent"] == source["originalContent"]
    assert attachment["source"] == source["source"]
    assert e.transport.dispatch_count == 0


@pytest.mark.parametrize(
    "status,reason",
    [("refusal", "PROVIDER_REFUSAL"), ("incomplete", "PROVIDER_OUTPUT_TRUNCATED")],
)
def test_new_wire_preserves_provider_failure_without_retry(
    prepared, monkeypatch, status, reason
):
    response = _completed({"result": prepared.value})
    if status == "refusal":
        response["output"] = [
            {"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}
        ]
    else:
        response.update(
            status="incomplete",
            incomplete_details={"reason": "max_output_tokens"},
            output=[],
        )
    if status == "incomplete":
        # Preserve the existing streaming owner's UNKNOWN boundary, not a new
        # completed/settleable result merely because an incomplete event arrived.
        with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
            exchange(monkeypatch, prepared, None, response=response)
        assert prepared.transport.dispatch_count == 1
        assert prepared.transport._measurement is None
    else:
        result = exchange(monkeypatch, prepared, None, response=response)
        assert result.reason_code == reason
        assert result.state is ObservationState.FAILED
        assert prepared.transport._measurement["settleable"] is True
