"""Tests for the internal Digital Employee authoring lifecycle."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from agent_console.authoring import (
    ApprovalDecision,
    AuthoringBackend,
    AuthoringError,
    AuthoringState,
    ChangeType,
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
    assert first.diff[0].change_type == ChangeType.REPLACE
    assert deterministic_diff(original.values, first.values) == first.diff


def test_diff_classifies_add_remove_replace_and_omits_unchanged_values() -> None:
    backend = AuthoringBackend(values(knowledge_binding_ref=None))
    added = backend.create_draft(
        values(
            knowledge_binding_ref="knowledge.synthetic.quality.v1",
            role_title="Senior Specialist",
        )
    )
    assert [(item.field, item.change_type) for item in added.diff] == [
        ("role_title", ChangeType.REPLACE),
        ("knowledge_binding_ref", ChangeType.ADD),
    ]
    approved = backend.decide(
        backend.request_review(added.revision).revision,
        actor="human:reviewer",
        decision=ApprovalDecision.APPROVE,
        decided_at=NOW,
        source_revision=added.source_revision,
    )
    removed = backend.create_draft(
        values(knowledge_binding_ref=None, role_title=approved.values.role_title)
    )
    assert [(item.field, item.change_type) for item in removed.diff] == [
        ("knowledge_binding_ref", ChangeType.REMOVE)
    ]


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


def test_rejection_exact_replay_is_idempotent_and_conflicts_fail_closed() -> None:
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
    stored_approval = rejected.approval
    assert rejected.state == AuthoringState.REJECTED
    assert backend.effective == effective
    assert backend.decide(candidate.revision, **args) == rejected

    conflicts = (
        {**args, "decided_at": datetime(2026, 8, 27, tzinfo=UTC)},
        {**args, "actor": "human:other-reviewer"},
        {**args, "decision": ApprovalDecision.APPROVE},
    )
    for conflicting_args in conflicts:
        original_args = conflicting_args.copy()
        for _ in range(2):
            with pytest.raises(AuthoringError) as exc_info:
                backend.decide(candidate.revision, **conflicting_args)
            assert str(exc_info.value) == "REVISION_ALREADY_DECIDED"
            assert "human:" not in str(exc_info.value)
            assert "2026" not in str(exc_info.value)
            assert backend.effective == effective
            assert backend._get(candidate.revision) == rejected
            assert backend._get(candidate.revision).approval == stored_approval
            assert conflicting_args == original_args


def test_approval_exact_replay_is_idempotent_and_rejection_fails_closed() -> None:
    backend = AuthoringBackend(values())
    candidate = review(backend)
    args = {
        "actor": "human:reviewer",
        "decision": ApprovalDecision.APPROVE,
        "decided_at": NOW,
        "source_revision": candidate.source_revision,
    }
    approved = backend.decide(candidate.revision, **args)
    assert backend.decide(candidate.revision, **args) == approved

    with pytest.raises(AuthoringError) as exc_info:
        backend.decide(
            candidate.revision,
            **{**args, "decision": ApprovalDecision.REJECT},
        )
    assert str(exc_info.value) == "REVISION_ALREADY_DECIDED"
    assert backend.effective == approved
    assert backend._get(candidate.revision) == approved


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
        (
            lambda item: item.update({"role_description": object()}),
            "MALFORMED_INPUT",
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


def test_cyclic_input_and_missing_source_revision_fail_closed() -> None:
    cyclic = values()
    cyclic["runtime_preference"]["requested"] = cyclic
    with pytest.raises(AuthoringError, match="MALFORMED_INPUT"):
        AuthoringBackend(cyclic)

    backend = AuthoringBackend(values())
    candidate = review(backend)
    with pytest.raises(AuthoringError, match="SOURCE_REVISION_REQUIRED"):
        backend.decide(
            candidate.revision,
            actor="human:reviewer",
            decision=ApprovalDecision.APPROVE,
            decided_at=NOW,
            source_revision="",
        )
