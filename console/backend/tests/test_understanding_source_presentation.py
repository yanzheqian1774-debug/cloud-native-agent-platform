from types import SimpleNamespace

import pytest
from agent_console.draft_assistance import DraftInvocationState
from agent_console.private_conversation import digest
from agent_console.understanding_source_presentation import (
    current_source_capability,
    source_input_observation,
)


def response(revision="v3-relation-adoption"):
    source = {
        "source": {"resource_id": "source", "revision_id": "1", "digest": "a" * 64},
        "sourceContentDigest": "b" * 64,
        "sourceSchema": "document-review-source.v1",
        "name": "Test",
    }
    snapshot = SimpleNamespace(
        adapter_id="openai-responses-draft",
        profile_revision_id="profile",
        snapshot_id="snapshot",
        adapter_revision=revision,
    )
    value = SimpleNamespace(
        input_source=source,
        state=DraftInvocationState.SUCCEEDED,
        snapshot=snapshot,
        profile_revision_id="profile",
        snapshot_candidate_id="snapshot",
        terminal_observation_id="terminal",
        last_observation_id="terminal",
        conversation_context={
            "target": {"kind": "UNDERSTANDING", "inputSourceDigest": digest(source)},
            "contextDigest": "context",
        },
        conversation_route={"relation": "CURRENT_QUESTION", "contextDigest": "context"},
        invocation_id="old",
        aggregate_version=12,
    )
    return SimpleNamespace(invocation=value, synthetic=False)


def test_old_input_contract_independent_of_current_capability():
    result = response()
    observed = source_input_observation(result)
    assert observed["state"] == "METADATA_ONLY"
    assert observed["invocationId"] == "old"
    assert observed["aggregateVersion"] == 12
    assert observed["source"] == result.invocation.input_source
    current = SimpleNamespace(
        profile=SimpleNamespace(
            adapter_id="openai-responses-draft",
            adapter_revision="v3-relation-adoption-source",
        )
    )
    assert current_source_capability(current, True) == "BODY_SUPPORTED"
    assert source_input_observation(result) == observed
    assert current_source_capability(current, False) == "UNAVAILABLE"
    assert current_source_capability(None, False) == "UNAVAILABLE"


def test_successor_context_does_not_claim_business_completeness():
    result = response("v3-relation-adoption-source")
    result.invocation.conversation_context["sourceInputBranch"] = {
        "currentQuestionType": "UNDERSTANDING",
        "hasCurrentQuestion": True,
    }
    observed = source_input_observation(result)
    assert observed["state"] == "BODY_CONTEXT"
    assert "complete" not in observed


@pytest.mark.parametrize(
    "change",
    [
        "synthetic",
        "profile",
        "snapshot",
        "source",
        "owner",
        "route",
        "terminal",
        "state",
        "unknown_adapter",
        "wrong_adapter_id",
    ],
)
def test_unproven_input_never_classified(change):
    result = response()
    value = result.invocation
    if change == "synthetic":
        result.synthetic = True
    elif change == "profile":
        value.snapshot.profile_revision_id = "other"
    elif change == "snapshot":
        value.snapshot.snapshot_id = "other"
    elif change == "source":
        value.conversation_context["target"]["inputSourceDigest"] = "wrong"
    elif change == "owner":
        value.conversation_context["target"]["kind"] = "NATIVE"
    elif change == "route":
        value.conversation_route["contextDigest"] = "other"
    elif change == "terminal":
        value.last_observation_id = "different"
    elif change == "state":
        value.state = DraftInvocationState.OUTCOME_UNKNOWN
    elif change == "wrong_adapter_id":
        value.snapshot.adapter_id = "other"
    else:
        value.snapshot.adapter_revision = "future"
    assert source_input_observation(result)["state"] == "UNVERIFIED"


@pytest.mark.parametrize(
    "current",
    [
        None,
        {},
        {"currentQuestionType": "UNDERSTANDING", "hasCurrentQuestion": False},
        {"currentQuestionType": "NATIVE", "hasCurrentQuestion": True},
    ],
)
def test_source_adapter_without_exact_body_branch_is_unverified(current):
    result = response("v3-relation-adoption-source")
    if current is not None:
        result.invocation.conversation_context["sourceInputBranch"] = current
    assert source_input_observation(result)["state"] == "UNVERIFIED"


def test_branch_evidence_is_noncontent_and_legacy_comparison_stays_exact():
    from agent_console.conversation_relation_context import (
        bind_snapshot,
        current_metadata,
        metadata_for_snapshot,
        sealed_snapshot,
    )

    snapshot = sealed_snapshot(
        "conversation",
        "message",
        {"kind": "UNDERSTANDING"},
        {
            "currentQuestionType": "UNDERSTANDING",
            "currentQuestion": "Private question text",
        },
    )
    legacy = metadata_for_snapshot(snapshot, include_source_branch=False)
    with bind_snapshot(snapshot):
        recorded = current_metadata()
    assert recorded["sourceInputBranch"] == {
        "currentQuestionType": "UNDERSTANDING",
        "hasCurrentQuestion": True,
    }
    assert "Private question text" not in str(recorded)
    assert {k: v for k, v in recorded.items() if k != "sourceInputBranch"} == legacy
    changed = {**snapshot, "input": {**snapshot["input"], "currentQuestion": ""}}
    assert metadata_for_snapshot(changed) != recorded
    assert metadata_for_snapshot(changed, include_source_branch=False) == legacy
    assert "sourceInputBranch" not in legacy
