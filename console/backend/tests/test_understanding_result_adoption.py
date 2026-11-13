"""Pure reference contract tests; no owner grants or real provider acceptance."""

import copy
from dataclasses import replace
from datetime import timedelta

import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftInvocationState,
    DraftResultKind,
)
from agent_console.private_conversation import digest
from agent_console.understanding_result_adoption import (
    AdoptionTarget,
    reference,
    target_identity,
)
from test_draft_assistance import NOW, build, context


@pytest.fixture
def case():
    service, *_ = build()
    original = service.begin(context(), key="question", content="scope?").invocation
    result = service.begin(
        context(),
        key="answer",
        content="Check the currently authorized production document.",
    ).invocation
    source = {"source": {"resource_id": "one", "digest": "a" * 64}}
    original = replace(original, input_source=source)
    target = AdoptionTarget(
        "conversation",
        "message",
        original.initiating_principal_id,
        original.context_id,
        original.invocation_id,
        original.turn_id,
        original.turn_version,
        original.aggregate_version,
        digest(source),
        "b" * 64,
        7,
        "work",
    )
    metadata = {
        "conversationId": target.conversation_id,
        "messageId": target.message_id,
        "target": target_identity(target),
        "contextDigest": "c" * 64,
        "currentQuestionToken": target.question_token,
    }
    result = replace(
        result,
        input_source=copy.deepcopy(source),
        conversation_context=metadata,
        conversation_route={
            "relation": "CURRENT_QUESTION",
            "currentQuestionToken": target.question_token,
            "contextDigest": metadata["contextDigest"],
        },
    )
    receipt = {
        "invocationId": result.invocation_id,
        "contextId": result.context_id,
        "turnId": result.turn_id,
        "aggregateVersion": result.aggregate_version,
        "terminalObservationId": result.terminal_observation_id,
        "resultKind": result.result_kind.value,
        "userMessageId": target.message_id,
    }
    return dict(
        target=target,
        original=original,
        current_head=original,
        result=result,
        current_snapshot=copy.deepcopy(metadata),
        retained_source=receipt,
        expected_profile_revision=result.profile_revision_id,
        settled_invocations=frozenset((original.invocation_id, result.invocation_id)),
        now=NOW,
    )


def test_adoption_references_real_result_without_rewriting_or_dispatch(case):
    before = copy.deepcopy(case)
    first = reference(**case)
    assert reference(**case) == first
    assert case == before
    assert first["actualResult"]["invocationId"] == case["result"].invocation_id
    assert "description" not in first and "answer" not in first
    assert first["target"]["original_invocation_id"] == case["original"].invocation_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("initiating_principal_id", "someone-else"),
        ("state", DraftInvocationState.OUTCOME_UNKNOWN),
        ("result_kind", DraftResultKind.DIRECT_ANSWER),
        ("terminal_observation_id", None),
        ("profile_revision_id", "different-profile"),
        ("input_source", None),
        ("owner_write_reason_code", "SAVE_FAILED"),
        ("local_cleanup", {"reason": "CLEANUP_FAILURE"}),
        ("parent_turn_id", "borrowed-turn"),
        ("problem_id", "already-created"),
        ("replay_not_after", NOW - timedelta(seconds=1)),
    ],
)
def test_unadoptable_real_result_is_rejected(case, field, value):
    case["result"] = replace(case["result"], **{field: value})
    with pytest.raises(DraftAssistanceError):
        reference(**case)


@pytest.mark.parametrize("field", ["turn_id", "invocation_id", "aggregate_version"])
def test_changed_original_head_is_not_silently_retargeted(case, field):
    value = 999 if field == "aggregate_version" else "different"
    case["current_head"] = replace(case["current_head"], **{field: value})
    with pytest.raises(DraftAssistanceError, match="ORIGINAL_HEAD_CHANGED"):
        reference(**case)


@pytest.mark.parametrize(
    "field", ["conversationId", "messageId", "currentQuestionToken"]
)
def test_cross_conversation_message_or_question_cannot_be_adopted(case, field):
    changed = copy.deepcopy(case["result"].conversation_context)
    changed[field] = "another"
    case["result"] = replace(case["result"], conversation_context=changed)
    with pytest.raises(DraftAssistanceError, match="QUESTION_CHANGED"):
        reference(**case)


def test_unrelated_or_ambiguous_result_cannot_consume_question(case):
    for relation in ("INDEPENDENT", "AMBIGUOUS", "CURRENT_WORK"):
        route = {**case["result"].conversation_route, "relation": relation}
        candidate = {
            **case,
            "result": replace(case["result"], conversation_route=route),
        }
        with pytest.raises(DraftAssistanceError, match="QUESTION_CHANGED"):
            reference(**candidate)


def test_unresolved_budget_or_lost_retention_blocks_adoption(case):
    with pytest.raises(DraftAssistanceError, match="BUDGET_UNRESOLVED"):
        reference(**{**case, "settled_invocations": frozenset()})
    with pytest.raises(DraftAssistanceError, match="RETAINED_RESULT_MISMATCH"):
        reference(**{**case, "retained_source": {}})


def saved_facts(case):
    result, target = case["result"], case["target"]
    return {
        "assistantResponse": True,
        "state": "SUCCEEDED",
        "invokedBy": target.subject_id,
        "requestKey": "request",
        "userMessageId": target.message_id,
        "source": {
            "kind": "DRAFT",
            "invocationId": result.invocation_id,
            "contextId": result.context_id,
            "turnId": result.turn_id,
            "turnVersion": result.turn_version,
        },
        "response": {
            "resultKind": result.result_kind.value,
            "conversationRoute": result.conversation_route,
            "inputSource": result.input_source,
        },
    }


def test_adoption_evidence_uses_exact_persisted_reply_and_target(case):
    from agent_console.understanding_adoption_evidence import (
        retained_evidence,
        target_from_result,
    )

    assert target_from_result(case["result"]) == case["target"]
    assert (
        retained_evidence(case["result"], case["target"], saved_facts(case), "request")
        == case["retained_source"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("invokedBy", "other"),
        ("userMessageId", "other-message"),
        ("requestKey", "other-request"),
        ("assistantResponse", "true"),
        ("state", "OUTCOME_UNKNOWN"),
        ("source", {}),
        ("response", {"resultKind": "DIRECT_ANSWER"}),
    ],
)
def test_adoption_evidence_rejects_unrelated_saved_facts(case, field, value):
    from agent_console.understanding_adoption_evidence import retained_evidence

    facts = saved_facts(case)
    facts[field] = value
    with pytest.raises(DraftAssistanceError, match="RETAINED_RESULT_MISMATCH"):
        retained_evidence(case["result"], case["target"], facts, "request")


def test_adoption_target_rejects_boolean_version_or_extra_client_field(case):
    from agent_console.understanding_adoption_evidence import target_from_result

    for change in ({"journalVersion": True}, {"arbitraryOwner": "accepted"}):
        metadata = copy.deepcopy(case["result"].conversation_context)
        metadata["target"].update(change)
        with pytest.raises(DraftAssistanceError, match="TARGET_INVALID"):
            target_from_result(replace(case["result"], conversation_context=metadata))


def test_explicit_source_supplement_only_accepts_needs_data_and_current_owner_source(
    case,
):
    source = case["result"].input_source
    case["original"] = replace(
        case["original"], input_source=None, result_kind=DraftResultKind.NEEDS_DATA
    )
    case["current_head"] = case["original"]
    case["target"] = replace(case["target"], source_digest=digest(None))
    metadata = {
        **case["result"].conversation_context,
        "target": target_identity(case["target"]),
    }
    case["result"] = replace(case["result"], conversation_context=metadata)
    case["current_snapshot"] = metadata
    with pytest.raises(DraftAssistanceError, match="SOURCE_CHANGED"):
        reference(**case)
    assert (
        reference(**case, selected_source=source)["sourceTransition"]
        == "EXPLICIT_AUTHORIZED_SUPPLEMENT"
    )
    with pytest.raises(DraftAssistanceError, match="SOURCE_CHANGED"):
        reference(**case, selected_source={"source": "other"})
    case["original"] = replace(
        case["original"], result_kind=DraftResultKind.NEEDS_CLARIFICATION
    )
    case["current_head"] = case["original"]
    with pytest.raises(DraftAssistanceError, match="SOURCE_CHANGED"):
        reference(**case, selected_source=source)
