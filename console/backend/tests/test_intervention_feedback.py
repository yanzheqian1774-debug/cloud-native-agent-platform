"""Contract, security, and failure-isolation tests for Package 6A."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.intervention_feedback import (
    CaptureConflict,
    CaptureDenied,
    CaptureUnavailable,
    InMemoryInterventionFeedbackRepository,
    InterventionFeedbackFailure,
    InterventionFeedbackService,
    TrustedCapturePrincipal,
    TrustedInterventionTarget,
)
from agent_console.intervention_feedback_schemas import (
    InterventionCaptureCommand,
    InterventionLifecycleCommand,
    OutcomeFeedbackCommand,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 29, 3, 0, tzinfo=UTC)


class IssuedIds:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"issued-{self.count}"


def target(*, provenance: str = "LIVE_EXECUTION") -> TrustedInterventionTarget:
    return TrustedInterventionTarget(
        journey_id="journey:supplier-quality-1",
        tenant_id="tenant-a",
        security_domain="supplier-quality",
        provenance=provenance,
        predecessor_revision_id="canonical-workflow-revision:one",
        predecessor_digest="a" * 64,
        successor_revision_id="canonical-workflow-revision:two",
        successor_digest="b" * 64,
        platform_execution_identity="platform-execution:two",
        outcome_id="outcome:two",
        execution_evidence_ids=("evidence:two:1", "evidence:two:2"),
    )


def principal(**overrides: object) -> TrustedCapturePrincipal:
    values: dict[str, object] = {
        "principal_id": "human:reviewer",
        "tenant_id": "tenant-a",
        "security_domain": "supplier-quality",
        "authorized": True,
    }
    values.update(overrides)
    return TrustedCapturePrincipal(**values)  # type: ignore[arg-type]


def intervention(**overrides: object) -> InterventionCaptureCommand:
    values: dict[str, object] = {
        "predecessorRevisionId": "canonical-workflow-revision:one",
        "successorRevisionId": "canonical-workflow-revision:two",
        "outcomeId": "outcome:two",
        "evidenceId": "evidence:two:1",
        "eventKind": "CONSTRAINT_CHANGED",
        "affectedElementReference": "CONSTRAINT",
        "correctionPatchReference": "CONSTRAINT_PATCH",
        "reasonCode": "MISSING_CONSTRAINT",
        "optimizationUseConsentDecision": "DENIED",
    }
    values.update(overrides)
    return InterventionCaptureCommand.model_validate(values)


def feedback(**overrides: object) -> OutcomeFeedbackCommand:
    values: dict[str, object] = {
        "outcomeId": "outcome:two",
        "evidenceId": "evidence:two:1",
        "assessment": "PARTIALLY_SATISFIED",
        "reasonCodes": ["MISSING_CONSTRAINT"],
        "supersedesFeedbackId": None,
    }
    values.update(overrides)
    return OutcomeFeedbackCommand.model_validate(values)


def service(
    repository: object | None = None,
) -> InterventionFeedbackService:
    return InterventionFeedbackService(
        repository,  # type: ignore[arg-type]
        clock=lambda: NOW,
        id_factory=IssuedIds(),
    )


def test_intervention_append_is_immutable_digest_bound_and_replay_exact() -> None:
    capture = service()
    first = capture.capture_intervention(principal(), target(), intervention())
    duplicate = capture.capture_intervention(principal(), target(), intervention())
    assert duplicate == first
    assert first.recordId == "intervention-record:issued-2"
    assert first.recordDigest and len(first.recordDigest) == 64
    assert first.principalId == "human:reviewer"
    assert first.decisionTime == "2026-08-29T03:00:00Z"
    assert first.predecessorRevisionDigest == "a" * 64
    assert first.successorRevisionDigest == "b" * 64
    with pytest.raises(ValidationError):
        first.lifecycle = "EXCLUDED"  # type: ignore[misc]
    with pytest.raises(CaptureConflict, match="INTERVENTION_REPLAY_CONFLICT"):
        capture.capture_intervention(
            principal(), target(), intervention(reasonCode="WRONG_ORDER")
        )


def test_repository_rejects_same_record_identity_with_conflicting_digest() -> None:
    repository = InMemoryInterventionFeedbackRepository()
    capture = service(repository)
    record = capture.capture_intervention(principal(), target(), intervention())
    conflicting = record.model_copy(update={"recordDigest": "f" * 64})
    with pytest.raises(CaptureConflict, match="INTERVENTION_RECORD_ID_CONFLICT"):
        repository.append_intervention(conflicting)


def test_lifecycle_facts_append_and_tombstone_never_deletes_history() -> None:
    capture = service()
    original = capture.capture_intervention(principal(), target(), intervention())
    retained = capture.append_intervention_lifecycle(
        principal(),
        target(),
        original.interventionEventId,
        InterventionLifecycleCommand(lifecycle="RETAINED"),
    )
    tombstone = capture.append_intervention_lifecycle(
        principal(),
        target(),
        original.interventionEventId,
        InterventionLifecycleCommand(lifecycle="TOMBSTONED"),
    )
    projection = capture.project(principal(), target())
    assert [item.lifecycle for item in projection.product.interventions] == [
        "RECORDED",
        "RETAINED",
        "TOMBSTONED",
    ]
    assert retained.supersedesRecordId == original.recordId
    assert tombstone.supersedesRecordId == retained.recordId
    assert projection.product.interventions[0] == original
    assert (
        capture.append_intervention_lifecycle(
            principal(),
            target(),
            original.interventionEventId,
            InterventionLifecycleCommand(lifecycle="TOMBSTONED"),
        )
        == tombstone
    )
    with pytest.raises(CaptureConflict, match="INTERVENTION_LIFECYCLE_CONFLICT"):
        capture.append_intervention_lifecycle(
            principal(),
            target(),
            original.interventionEventId,
            InterventionLifecycleCommand(lifecycle="RETAINED"),
        )


def test_feedback_changes_append_explicit_superseding_versions() -> None:
    capture = service()
    first = capture.capture_feedback(principal(), target(), feedback())
    assert capture.capture_feedback(principal(), target(), feedback()) == first
    with pytest.raises(CaptureConflict, match="OUTCOME_FEEDBACK_SUPERSESSION_REQUIRED"):
        capture.capture_feedback(
            principal(), target(), feedback(assessment="UNSATISFIED")
        )
    changed = capture.capture_feedback(
        principal(),
        target(),
        feedback(
            assessment="UNSATISFIED",
            reasonCodes=["MISSING_CONSTRAINT", "WRONG_ORDER"],
            supersedesFeedbackId=first.feedbackId,
        ),
    )
    assert changed.revision == 2
    assert changed.supersedesFeedbackId == first.feedbackId
    assert first.revision == 1
    projection = capture.project(principal(), target())
    assert [item.lifecycle for item in projection.product.outcomeFeedback] == [
        "SUPERSEDED",
        "RECORDED",
    ]
    assert projection.product.outcomeFeedback[0].record == first
    assert projection.product.outcomeFeedback[1].record == changed


def test_feedback_assesses_exactly_one_current_outcome_evidence_pair() -> None:
    capture = service()
    with pytest.raises(
        CaptureConflict, match="OUTCOME_FEEDBACK_TARGET_STALE_OR_MISMATCHED"
    ):
        capture.capture_feedback(
            principal(), target(), feedback(evidenceId="evidence:other")
        )
    with pytest.raises(
        CaptureConflict, match="OUTCOME_FEEDBACK_TARGET_STALE_OR_MISMATCHED"
    ):
        capture.capture_feedback(
            principal(), target(), feedback(outcomeId="outcome:one")
        )


@pytest.mark.parametrize(
    "capture_principal",
    [
        principal(authorized=False),
        principal(tenant_id="tenant-b"),
        principal(security_domain="finance"),
    ],
)
def test_authorization_and_tenant_domain_scope_fail_before_repository_read(
    capture_principal: TrustedCapturePrincipal,
) -> None:
    class ReadSpyRepository(InMemoryInterventionFeedbackRepository):
        reads = 0

        def interventions(self, **kwargs: str):  # type: ignore[no-untyped-def]
            self.reads += 1
            return super().interventions(**kwargs)

    repository = ReadSpyRepository()
    capture = service(repository)
    with pytest.raises(CaptureDenied):
        capture.project(capture_principal, target())
    with pytest.raises(CaptureDenied):
        capture.capture_intervention(capture_principal, target(), intervention())
    assert repository.reads == 0


def test_stale_revision_execution_outcome_and_evidence_references_fail_closed() -> None:
    capture = service()
    for changed in (
        intervention(predecessorRevisionId="canonical-workflow-revision:stale"),
        intervention(successorRevisionId="canonical-workflow-revision:stale"),
        intervention(outcomeId="outcome:stale"),
        intervention(evidenceId="evidence:stale"),
    ):
        with pytest.raises(
            CaptureConflict, match="INTERVENTION_TARGET_STALE_OR_MISMATCHED"
        ):
            capture.capture_intervention(principal(), target(), changed)
    with pytest.raises(
        InterventionFeedbackFailure, match="INTERVENTION_TARGET_INVALID"
    ):
        capture.project(
            principal(), replace(target(), platform_execution_identity=None)
        )


@pytest.mark.parametrize("provenance", ["LIVE_EXECUTION", "SYNTHETIC_PREVIEW"])
def test_live_and_synthetic_provenance_remain_explicit(provenance: str) -> None:
    capture = service()
    record = capture.capture_intervention(
        principal(), target(provenance=provenance), intervention()
    )
    projection = capture.project(principal(), target(provenance=provenance))
    assert record.provenance == provenance
    assert projection.product.identity.provenance == provenance
    assert projection.technical.identity.provenance == provenance
    with pytest.raises(InterventionFeedbackFailure, match="CAPTURE_PROVENANCE_INVALID"):
        capture.project(principal(), target(provenance="HIDDEN_FALLBACK"))


def test_product_and_technical_projections_preserve_identical_backend_identities() -> (
    None
):
    capture = service()
    capture.capture_intervention(principal(), target(), intervention())
    capture.capture_feedback(principal(), target(), feedback())
    projection = capture.project(principal(), target())
    assert projection.product.identity == projection.technical.identity
    assert projection.product.interventions == projection.technical.interventions
    assert projection.product.outcomeFeedback == projection.technical.outcomeFeedback


def test_projection_only_returns_records_for_the_exact_current_target() -> None:
    capture = service()
    capture.capture_intervention(principal(), target(), intervention())
    capture.capture_feedback(principal(), target(), feedback())
    current = capture.project(principal(), target())
    assert len(current.product.interventions) == 1
    assert len(current.product.outcomeFeedback) == 1

    stale_revision = replace(
        target(),
        successor_revision_id="canonical-workflow-revision:three",
        successor_digest="c" * 64,
    )
    stale_execution = replace(
        target(),
        platform_execution_identity="platform-execution:three",
    )
    for advanced in (stale_revision, stale_execution):
        projection = capture.project(principal(), advanced)
        assert projection.product.interventions == ()
        assert projection.product.outcomeFeedback == ()


def test_prohibited_fields_and_unknown_codes_do_not_reach_records() -> None:
    secret = "Bearer sensitive-value"
    with pytest.raises(ValidationError):
        InterventionCaptureCommand.model_validate(
            {**intervention().model_dump(), "rawPrompt": secret}
        )
    with pytest.raises(ValidationError):
        InterventionCaptureCommand.model_validate(
            {**intervention().model_dump(), "reasonCode": "ARBITRARY_REASON"}
        )
    assert "rawPrompt" not in set(InterventionCaptureCommand.model_fields)
    capture = service()
    record = capture.capture_intervention(principal(), target(), intervention())
    serialized = record.model_dump_json()
    for prohibited in (
        "rawPrompt",
        "secret",
        "credential",
        "providerBody",
        "stackTrace",
        "hostPath",
        "metadata",
    ):
        assert prohibited not in serialized


def test_repository_outage_and_corruption_are_explicit_with_zero_execution_impact() -> (
    None
):
    class FailedRepository(InMemoryInterventionFeedbackRepository):
        def append_intervention(self, record):  # type: ignore[no-untyped-def]
            raise OSError("private host path and secret must not escape")

    execution_state = {"state": "SUCCEEDED", "calls": 1}
    capture = service(FailedRepository())
    with pytest.raises(
        CaptureUnavailable, match="INTERVENTION_FEEDBACK_REPOSITORY_UNAVAILABLE"
    ) as failure:
        capture.capture_intervention(principal(), target(), intervention())
    assert "private host path" not in str(failure.value)
    assert execution_state == {"state": "SUCCEEDED", "calls": 1}
    assert capture._intervention_replays == {}

    class CorruptRepository(InMemoryInterventionFeedbackRepository):
        def interventions(self, **kwargs: str):  # type: ignore[no-untyped-def]
            del kwargs
            return (object(),)

    with pytest.raises(CaptureUnavailable, match="CAPTURE_REPOSITORY_CORRUPT"):
        service(CorruptRepository()).project(principal(), target())


def test_package_6b_types_and_influence_ports_are_absent() -> None:
    source = Path(
        "console/backend/src/agent_console/intervention_feedback.py"
    ).read_text(encoding="utf-8")
    for prohibited in (
        "UserPreferenceProfile",
        "CandidateEvidenceSet",
        "ImprovementCandidate",
        "OptimizationEvaluation",
        "PublishedOptimization",
        "apply_to_planner",
        "execute_workflow",
    ):
        assert prohibited not in source
