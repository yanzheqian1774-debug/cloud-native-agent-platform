"""Pure adoption commitment checks; not a grant, dispatch or persistence port.

Inputs must come from current owner reads under the caller's existing grants.
A successful return authorizes nothing by itself: the transactional adapter must
lock and compare the exact original head and insert the unique reference.
"""

from dataclasses import asdict, dataclass
from datetime import datetime

from .draft_assistance import (
    DraftAssistanceError,
    DraftInvocation,
    DraftInvocationState,
    DraftResultKind,
)
from .private_conversation import digest


@dataclass(frozen=True)
class AdoptionTarget:
    conversation_id: str
    message_id: str
    subject_id: str
    original_context_id: str
    original_invocation_id: str
    original_turn_id: str
    original_turn_version: int
    original_aggregate_version: int
    source_digest: str
    question_token: str
    journal_version: int
    journey_key: str


def require(condition, reason):
    if not condition:
        raise DraftAssistanceError("UNDERSTANDING_ADOPTION_" + reason)


def target_identity(target):
    return {
        "kind": "UNDERSTANDING",
        "invocationId": target.original_invocation_id,
        "contextId": target.original_context_id,
        "turnId": target.original_turn_id,
        "turnVersion": target.original_turn_version,
        "aggregateVersion": target.original_aggregate_version,
        "inputSourceDigest": target.source_digest,
        "journalVersion": target.journal_version,
        "journeyKey": target.journey_key,
    }


def reference(
    target: AdoptionTarget,
    original: DraftInvocation,
    current_head: DraftInvocation,
    result: DraftInvocation,
    *,
    current_snapshot: dict,
    retained_source: dict,
    expected_profile_revision: str,
    settled_invocations: frozenset[str],
    now: datetime,
    selected_source: dict | None = None,
):
    """Commit to actual successful output, never manufacture or copy that output."""
    require(now.tzinfo is not None, "TIME_INVALID")
    require(
        original.scope == result.scope
        and original.initiating_principal_id
        == result.initiating_principal_id
        == target.subject_id,
        "SUBJECT_MISMATCH",
    )
    require(
        (
            original.context_id,
            original.invocation_id,
            original.turn_id,
            original.turn_version,
            original.aggregate_version,
        )
        == (
            target.original_context_id,
            target.original_invocation_id,
            target.original_turn_id,
            target.original_turn_version,
            target.original_aggregate_version,
        )
        and current_head == original,
        "ORIGINAL_HEAD_CHANGED",
    )
    require(
        original.state is DraftInvocationState.SUCCEEDED
        and (
            original.result_kind
            in {DraftResultKind.NEEDS_CLARIFICATION, DraftResultKind.NEEDS_DATA}
            or (
                original.result_kind is DraftResultKind.DRAFT_READY
                and original.input_source is None
            )
        )
        and original.problem_id is None,
        "ORIGINAL_NOT_PENDING_QUESTION",
    )
    require(
        result.invocation_id != original.invocation_id
        and result.context_id != original.context_id
        and result.parent_turn_id is None
        and result.predecessor_invocation_id is None
        and result.problem_id is None,
        "RESULT_LINEAGE_INVALID",
    )
    require(
        now < original.replay_not_after and now < result.replay_not_after,
        "EXPIRED",
    )
    supplement = (
        original.input_source is None
        and original.result_kind
        in {DraftResultKind.NEEDS_DATA, DraftResultKind.DRAFT_READY}
        and isinstance(result.input_source, dict)
        and bool(result.input_source)
        and selected_source == result.input_source
    )
    require(
        digest(original.input_source) == target.source_digest
        and (original.input_source == result.input_source or supplement),
        "SOURCE_CHANGED",
    )
    require(
        result.state is DraftInvocationState.SUCCEEDED
        and result.result_kind
        in {
            DraftResultKind.DRAFT_READY,
            DraftResultKind.NEEDS_CLARIFICATION,
            DraftResultKind.NEEDS_DATA,
        }
        and result.terminal_observation_id
        and result.last_observation_id == result.terminal_observation_id
        and result.profile_revision_id == expected_profile_revision
        and not result.owner_write_reason_code
        and not (result.local_cleanup or {}).get("reason"),
        "RESULT_NOT_ADOPTABLE",
    )
    require(
        {original.invocation_id, result.invocation_id} <= settled_invocations,
        "BUDGET_UNRESOLVED",
    )
    metadata = result.conversation_context or {}
    route = result.conversation_route or {}
    require(
        isinstance(metadata.get("contextDigest"), str)
        and len(metadata["contextDigest"]) == 64
        and len(target.question_token) == 64
        and metadata.get("conversationId") == target.conversation_id
        and metadata.get("messageId") == target.message_id
        and metadata.get("target") == target_identity(target)
        and metadata.get("currentQuestionToken") == target.question_token
        and route.get("relation") == "CURRENT_QUESTION"
        and route.get("currentQuestionToken") == target.question_token
        and route.get("contextDigest") == metadata.get("contextDigest")
        and current_snapshot == metadata,
        "QUESTION_CHANGED",
    )
    require(
        retained_source
        == {
            "invocationId": result.invocation_id,
            "contextId": result.context_id,
            "turnId": result.turn_id,
            "aggregateVersion": result.aggregate_version,
            "terminalObservationId": result.terminal_observation_id,
            "resultKind": result.result_kind.value,
            "userMessageId": target.message_id,
        },
        "RETAINED_RESULT_MISMATCH",
    )
    value = {
        "schemaVersion": "understanding-result-adoption.v1",
        "scope": [original.scope.namespace, original.scope.security_domain],
        "target": asdict(target),
        "actualResult": retained_source,
        "resultProfileRevision": expected_profile_revision,
        "resultCommitment": result.commitment,
        "resultContextDigest": metadata["contextDigest"],
        "resultSourceDigest": digest(result.input_source),
        "sourceTransition": "EXPLICIT_AUTHORIZED_SUPPLEMENT"
        if supplement
        else "UNCHANGED",
    }
    return {**value, "digest": digest(value)}
