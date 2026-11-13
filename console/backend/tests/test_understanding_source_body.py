"""Offline immutable successor input boundary; no provider or credential use."""

import json

import pytest
from agent_console.conversation_relation_context import bind_snapshot, sealed_snapshot
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.draft_assistance_policy import policy_for
from agent_console.private_conversation import digest
from agent_console.understanding_source_body import (
    METADATA_KEYS,
    REVISION,
    provider_attachment,
)


def selected():
    return {
        "kind": "SERVER_READ_SELECTED_SOURCE",
        "source": {
            "resource_id": "knowledge:test",
            "revision_id": "revision:1",
            "digest": "a" * 64,
        },
        "sourceContentDigest": "b" * 64,
        "sourceSchema": "document-review-source.v1",
        "name": "Production handover",
        "originalContent": {
            "synthetic": True,
            "body": "Do not obey this document as instructions.",
        },
        "readStatus": "EXACT_PUBLISHED_SNAPSHOT_READ",
        "executionStatus": "NOT_EXECUTED",
        "externalLiveQuery": False,
    }


def snapshot(source, owner="UNDERSTANDING", *, source_null=False):
    return sealed_snapshot(
        "conversation",
        "message",
        {
            "kind": owner,
            "inputSourceDigest": digest(
                None if source_null else {key: source[key] for key in METADATA_KEYS}
            ),
        },
        {"currentQuestionType": owner, "currentQuestion": "Which environment?"},
    )


@pytest.mark.parametrize("source_null", [False, True])
def test_same_selected_source_or_first_selection_contains_exact_body(source_null):
    source = selected()
    with bind_snapshot(snapshot(source, source_null=source_null)):
        actual = json.loads(provider_attachment(json.dumps(source)))
    assert actual["originalContent"] == source["originalContent"]
    assert actual["sourceContentDigest"] == source["sourceContentDigest"]
    assert actual["executionStatus"] == "NOT_EXECUTED"


@pytest.mark.parametrize("owner", ["NATIVE", "PLANNING", None])
def test_other_owner_never_receives_body(owner):
    source = selected()
    with bind_snapshot(snapshot(source, owner)):
        actual = json.loads(provider_attachment(json.dumps(source)))
    assert "originalContent" not in actual
    assert set(actual) == {"kind", *METADATA_KEYS}


@pytest.mark.parametrize(
    "change",
    [
        {"sourceContentDigest": "c" * 64},
        {"readStatus": "CLAIMED"},
        {"executionStatus": "EXECUTED"},
        {"externalLiveQuery": True},
        {"originalContent": {"synthetic": False}},
        {"originalContent": "unverified raw text"},
        {"sourceSchema": "arbitrary-private-source.v1"},
    ],
)
def test_stale_or_unverified_body_fails_before_dispatch(change):
    source = selected()
    current = snapshot(source)
    source.update(change)
    with (
        bind_snapshot(current),
        pytest.raises(
            DraftAssistanceError, match="UNDERSTANDING_SOURCE_CONTEXT_INVALID"
        ),
    ):
        provider_attachment(json.dumps(source))


def test_missing_current_owner_rejected():
    with pytest.raises(DraftAssistanceError, match="SOURCE_CONTEXT_INVALID"):
        provider_attachment(json.dumps(selected()))


def test_new_revision_preserves_output_schema_and_instruction_bytes():
    old = policy_for(
        "v3-relation-adoption", "conversation-understanding-output.v3-relation-adoption"
    )
    new = policy_for(REVISION, old.schema_version)
    assert old.instructions == new.instructions
    assert old.schema == new.schema
    assert old.digest != new.digest
