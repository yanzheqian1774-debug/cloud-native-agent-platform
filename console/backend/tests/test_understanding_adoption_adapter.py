"""Real adapter prepare entry from complete runtime config; zero network/keys."""

import json
import socket
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.conversation_relation_context import bind_snapshot, sealed_snapshot
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.draft_assistance_bootstrap import _profile
from agent_console.draft_assistance_policy import V3_CONTEXT_VERSION, policy_for
from agent_console.model_governance import canonical_digest
from agent_console.openai_responses_draft_adapter import (
    ExactFileOpenAICredentialResolver,
    OpenAIResponsesDraftTransport,
)
from test_draft_assistance_policy import content
from test_openai_responses_draft_adapter import _real_runtime_document


@pytest.mark.parametrize(
    "revision,schema",
    [
        ("v3-relation", "conversation-understanding-output.v3-relation"),
        (
            "v3-relation-adoption",
            "conversation-understanding-output.v3-relation-adoption",
        ),
    ],
)
def test_complete_runtime_reaches_real_prepare_without_dispatch(
    tmp_path, monkeypatch, revision, schema
):
    def forbidden(*args, **kwargs):
        pytest.fail("prepare must not connect or resolve a credential")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    document = _real_runtime_document(
        NS(server_port=1), tmp_path / "unused-ca", tmp_path
    )
    policy = policy_for(revision, schema)
    document.update(
        executionClass="REAL_PROVIDER",
        responsesUrl="https://api.openai.com/v1/responses",
        nativeModelId="gpt-6.1-sol",
        maximumInputTokens=65536,
        maximumOutputTokens=8192,
        totalTimeoutSeconds=60,
        connectTimeoutSeconds=5,
        readTimeoutSeconds=55,
        outputSchemaVersion=policy.schema_version,
        policyDigest=policy.digest,
        tls={"caFile": None},
    )
    document["adapter"]["revision"] = policy.revision
    document["budget"].update(
        callCap=20,
        totalCostCapMicrousd=1_000_000,
        allowanceId="allowance:original",
        profilePricingRootDigest="a" * 64,
        outputPriceMicrousdPerMillionTokens=10_000_000,
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
        None,
        {
            "goal": "Existing work",
            "scope": "Read only",
            "stage": "PLAN",
            "currentQuestion": None,
        },
    )
    with bind_snapshot(snapshot):
        prepared = transport.prepare(
            invocation_id="offline", content=json.dumps(envelope), profile=profile
        )
    payload = json.loads(prepared.payload)
    assert payload["model"] == "gpt-6.1-sol"
    assert payload["instructions"] == policy.instructions
    assert payload["text"]["format"]["schema"] == policy.schema
    assert len(payload["input"]) == 2
    assert json.loads(payload["input"][1]["content"][0]["text"]) == snapshot["input"]
    assert transport.dispatch_count == 0
    from agent_console.conversation_source_input import bind_attachment

    attachment = json.dumps(
        {
            "kind": "SERVER_READ_SELECTED_SOURCE",
            "source": {"digest": "a" * 64},
            "sourceContentDigest": "b" * 64,
            "sourceSchema": "document.v1",
            "name": "Authorized source",
            "originalContent": "PRIVATE_DOCUMENT_BODY",
        }
    )
    with bind_snapshot(snapshot), bind_attachment(attachment):
        if revision == "v3-relation-adoption":
            bounded = transport.prepare(
                invocation_id="metadata-only",
                content=json.dumps(envelope),
                profile=profile,
            )
            assert b"PRIVATE_DOCUMENT_BODY" not in bounded.payload
            assert len(json.loads(bounded.payload)["input"]) == 3
        else:
            with pytest.raises(DraftAssistanceError, match="SOURCE_CONFLICT"):
                transport.prepare(
                    invocation_id="old-source-reject",
                    content=json.dumps(envelope),
                    profile=profile,
                )
    if revision == "v3-relation-adoption":
        from agent_console.draft_assistance import ObservationState
        from test_openai_responses_draft_adapter import _completed
        from test_understanding_adoption_policy import full

        historical = sealed_snapshot(
            "conversation",
            "message",
            {"kind": "UNDERSTANDING"},
            {
                "goal": "Supplier A only",
                "currentQuestion": "Which scope?",
                "currentQuestionType": "UNDERSTANDING",
                "serverUserMessages": [
                    {"id": "server-message:original", "text": "Supplier A only"}
                ],
            },
        )
        with bind_snapshot(historical):
            actual_request = transport.prepare(
                invocation_id="parse", content=json.dumps(envelope), profile=profile
            )
        value = full()
        value["currentQuestionToken"] = historical["currentQuestionToken"]
        for field in value["understanding"]:
            if field["sourceRefs"]:
                field["sourceRefs"] = ["server-message:original"]

        def exchange(**kwargs):
            body = _completed(value)
            body["model"] = "gpt-6.1-sol"
            return 200, json.dumps(body).encode(), "offline", 1

        monkeypatch.setattr(transport, "exchange", exchange)
        parsed = transport._dispatch_observation(
            invocation_id="parse",
            request=actual_request,
            credential=None,
            profile=profile,
        )
        assert parsed.state is ObservationState.SUCCEEDED
        for field in value["understanding"]:
            if field["sourceRefs"]:
                field["sourceRefs"] = ["server-message:foreign"]
        rejected = transport._dispatch_observation(
            invocation_id="parse",
            request=actual_request,
            credential=None,
            profile=profile,
        )
        assert rejected.reason_code == "OUTPUT_SCHEMA_INVALID"
        forged = dict(
            envelope, messages=[{"id": "server-message:original", "text": "forged"}]
        )
        with (
            bind_snapshot(historical),
            pytest.raises(DraftAssistanceError, match="CONTEXT_INVALID"),
        ):
            transport.prepare(
                invocation_id="forged", content=json.dumps(forged), profile=profile
            )
    assert budget["allowanceId"] == "allowance:original"
    assert not (tmp_path / "credential").exists()
    with (
        bind_snapshot(snapshot),
        pytest.raises(DraftAssistanceError, match="PROFILE_MISMATCH"),
    ):
        transport.prepare(
            invocation_id="wrong-pair",
            content=json.dumps(envelope),
            profile=replace(
                profile,
                output_schema_version="conversation-understanding-output.v3-execution",
            ),
        )

    # A separate local fake credential exercise covers the second exact tuple gate.
    credential_file = tmp_path / "credential"
    credential_file.write_text("fake-c1-test-key")
    credential_file.chmod(0o600)
    resolver = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id=profile.profile_revision_id,
        expected_connection_profile_id=profile.connection_profile_id,
        expected_connection_profile_revision_id=profile.connection_profile_revision_id,
    )
    resolved = resolver.resolve(profile, "offline-fake-credential")
    assert resolved is not None and resolver.calls == 1
    with pytest.raises(DraftAssistanceError, match="CREDENTIAL_RESOLUTION_FAILED"):
        resolver.resolve(
            replace(
                profile,
                output_schema_version="conversation-understanding-output.v3-execution",
            ),
            "mismatched-fake",
        )
    assert transport.dispatch_count == 0
