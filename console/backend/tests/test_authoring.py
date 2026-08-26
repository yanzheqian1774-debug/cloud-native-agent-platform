"""Tests for the internal Digital Employee authoring lifecycle."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from agent_console.authoring import (
    ApprovalDecision,
    AuthoringBackend,
    AuthoringError,
    AuthoringState,
    deterministic_diff,
)


def values(**overrides):
    result = {
        "definition_id": "definition.customer-insight",
        "display_name": "Mira",
        "role_title": "Customer Insight Specialist",
        "role_description": "Analyzes authorized synthetic complaint evidence.",
        "business_responsibilities": ["Classify themes", "Explain impact"],
        "allowed_capabilities": ["knowledge.synthetic.read"],
        "prohibited_activities": ["Contact customers", "Change records"],
        "runtime_preference": {
            "requested": "NATIVE",
            "evidence_state": "COMPONENT_TESTED_CANDIDATE",
        },
        "knowledge_binding_ref": "knowledge.synthetic.quality.v1",
        "status_code": "DRAFT_CANDIDATE",
        "reason_code": "HUMAN_REVIEW_REQUIRED",
    }
    result.update(overrides)
    return result


NOW = datetime(2026, 8, 26, tzinfo=UTC)


def review(backend: AuthoringBackend, candidate=None):
    draft = backend.create_draft(
        candidate or values(role_title="Senior Customer Insight Specialist"),
        ai_assisted=True,
    )
    return backend.request_review(draft.revision)


def test_draft_and_diff_are_deterministic_and_ai_never_effective() -> None:
    backend = AuthoringBackend(values())
    original = backend.effective
    first = backend.create_draft(
        values(role_title="Senior Specialist"), ai_assisted=True
    )
    second = backend.create_draft(
        values(role_title="Senior Specialist"), ai_assisted=True
    )

    assert first == second
    assert first.state == AuthoringState.DRAFT
    assert first.ai_assisted is True
    assert backend.effective == original
    assert [change.field for change in first.diff] == ["role_title"]
    assert deterministic_diff(original.values, first.values) == first.diff


def test_human_approval_is_required_and_records_complete_decision() -> None:
    backend = AuthoringBackend(values())
    draft = backend.create_draft(values(role_title="Senior Specialist"))
    with pytest.raises(AuthoringError, match="HUMAN_REVIEW_REQUIRED"):
        backend.decide(
            draft.revision,
            actor="human:reviewer",
            decision=ApprovalDecision.APPROVE,
            decided_at=NOW,
            source_revision=draft.source_revision,
        )

    candidate = backend.request_review(draft.revision)
    approved = backend.decide(
        candidate.revision,
        actor="human:reviewer",
        decision=ApprovalDecision.APPROVE,
        decided_at=NOW,
        source_revision=candidate.source_revision,
    )
    assert approved.state == AuthoringState.APPROVED
    assert backend.effective == approved
    assert approved.approval is not None
    assert approved.approval.actor == "human:reviewer"
    assert approved.approval.source_revision == candidate.source_revision


def test_approval_timestamp_must_be_timezone_aware() -> None:
    backend = AuthoringBackend(values())
    candidate = review(backend)
    with pytest.raises(AuthoringError, match="INVALID_APPROVAL_TIMESTAMP"):
        backend.decide(
            candidate.revision,
            actor="human:reviewer",
            decision=ApprovalDecision.APPROVE,
            decided_at=datetime(2026, 8, 26),
            source_revision=candidate.source_revision,
        )


def test_stale_source_revision_and_superseded_revision_fail_closed() -> None:
    backend = AuthoringBackend(values())
    stale = review(backend, values(role_title="Candidate A"))
    current = review(backend, values(role_title="Candidate B"))

    with pytest.raises(AuthoringError, match="STALE_SOURCE_REVISION"):
        backend.decide(
            current.revision,
            actor="human:reviewer",
            decision=ApprovalDecision.APPROVE,
            decided_at=NOW,
            source_revision="wrong",
        )
    backend.decide(
        current.revision,
        actor="human:reviewer",
        decision=ApprovalDecision.APPROVE,
        decided_at=NOW,
        source_revision=current.source_revision,
    )
    with pytest.raises(AuthoringError, match="SUPERSEDED_REVISION"):
        backend.decide(
            stale.revision,
            actor="human:reviewer",
            decision=ApprovalDecision.APPROVE,
            decided_at=NOW,
            source_revision=stale.source_revision,
        )


def test_rejection_preserves_effective_and_same_decision_is_idempotent() -> None:
    backend = AuthoringBackend(values())
    effective = backend.effective
    candidate = review(backend)
    args = {
        "actor": "human:reviewer",
        "decision": ApprovalDecision.REJECT,
        "decided_at": NOW,
        "source_revision": candidate.source_revision,
    }
    rejected = backend.decide(candidate.revision, **args)
    assert rejected.state == AuthoringState.REJECTED
    assert backend.effective == effective
    assert backend.decide(candidate.revision, **args) == rejected
    with pytest.raises(AuthoringError, match="REVISION_ALREADY_DECIDED"):
        backend.decide(
            candidate.revision,
            **{**args, "decision": ApprovalDecision.APPROVE},
        )


def test_input_is_defensively_copied() -> None:
    source = values()
    backend = AuthoringBackend(source)
    candidate = values(role_title="Senior Specialist")
    draft = backend.create_draft(candidate)
    source["business_responsibilities"].append("mutated")
    candidate["business_responsibilities"].append("mutated")
    candidate["runtime_preference"]["requested"] = "HERMES"
    assert "mutated" not in backend.effective.values.business_responsibilities
    assert "mutated" not in draft.values.business_responsibilities
    assert draft.values.runtime_preference.requested == "NATIVE"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda item: item.pop("role_title"), "MALFORMED_OR_AMBIGUOUS_FIELDS"),
        (
            lambda item: item.update({"unknown": "value"}),
            "MALFORMED_OR_AMBIGUOUS_FIELDS",
        ),
        (lambda item: item.update({"display_name": ""}), "INVALID_DISPLAY_NAME"),
        (
            lambda item: item.update({"allowed_capabilities": ["same", "same"]}),
            "AMBIGUOUS_DUPLICATE_VALUE",
        ),
        (
            lambda item: item.update({"role_description": "api_key=must-not-leak"}),
            "SECRET_SHAPED_VALUE_REJECTED",
        ),
        (
            lambda item: item.update({"role_description": "x" * 2_001}),
            "INPUT_LIMIT_EXCEEDED",
        ),
    ],
)
def test_malformed_ambiguous_oversized_and_secret_input_is_redacted(
    mutation, code
) -> None:
    source = deepcopy(values())
    mutation(source)
    with pytest.raises(AuthoringError) as exc_info:
        AuthoringBackend(source)
    assert str(exc_info.value) == code
    assert "must-not-leak" not in str(exc_info.value)
