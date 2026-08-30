"""Focused Product live-planning journey authority tests."""

from copy import deepcopy

import pytest
from agent_console.live_journey import (
    AuthorizedRerunResult,
    JourneyConflict,
    JourneyDenied,
    LiveJourneyCoordinator,
    LiveJourneySeed,
    TrustedJourneyPrincipal,
)
from agent_console.live_journey_schemas import JourneyCitation, JourneyOutcome
from agent_console.live_journey_stream import (
    InMemoryJourneyEventBroker,
    JourneyStreamScope,
)


class ExecutionAuthority:
    def __init__(self) -> None:
        self.calls = []

    def rerun(self, **request: str) -> str:
        self.calls.append(request)
        return AuthorizedRerunResult(
            platform_execution_identity="platform-execution:successor-2",
            shared_snapshot_id="journey-snapshot:successor-2",
            graph_snapshot_id="graph-snapshot:successor-2",
            evidence_ids=("evidence:successor-2",),
            citations=seed().citations,
            outcome=JourneyOutcome(
                outcomeId="outcome:successor-2",
                classification="SUCCEEDED",
                summary="Two severe issues require containment first.",
                comparableMetric="RISK_WEIGHTED_OPEN_ISSUES",
                comparableValue=2,
            ),
            answer="Prioritize the two severe containment actions.",
        )


def seed(**overrides) -> LiveJourneySeed:
    values = dict(
        journey_id="journey:supplier-quality-1",
        tenant_id="tenant-a",
        security_domain="quality",
        canonical_workflow_revision_id="canonical-workflow-revision:one",
        canonical_digest="a" * 64,
        approval_id="planning-approval:one",
        objective="Find supplier issues likely to miss closure this week",
        task_ids=("task:triage", "task:recommend"),
        shared_snapshot_id="journey-snapshot:one",
        graph_snapshot_id="graph-snapshot:one",
        platform_execution_identity="platform-execution:one",
        placement_decision_id="placement-decision:one",
        evidence_ids=("evidence:one", "evidence:two"),
        citations=(
            JourneyCitation(
                citationId="citation:8d-procedure",
                retrievalEvidenceId="knowledge-evidence:one",
                authorizationDecisionId="knowledge-allow:one",
                knowledgePackId="knowledge-pack:supplier-quality",
                knowledgePackVersion="v1",
                knowledgePackDigest="b" * 64,
                documentId="document:8d",
                documentVersion="v1",
                documentDigest="c" * 64,
                sectionId="section:containment",
                chunkId="chunk:containment-1",
                status="AVAILABLE",
            ),
        ),
        outcome=JourneyOutcome(
            outcomeId="outcome:one",
            classification="SUCCEEDED",
            summary="Three issues require containment first.",
            comparableMetric="RISK_WEIGHTED_OPEN_ISSUES",
            comparableValue=3,
        ),
        answer="Prioritize the three overdue containment actions.",
    )
    values.update(overrides)
    return LiveJourneySeed(**values)


@pytest.fixture
def authority():
    return ExecutionAuthority()


@pytest.fixture
def coordinator(authority):
    service = LiveJourneyCoordinator(authority)
    service.register_live(seed())
    return service


@pytest.fixture
def principal():
    return TrustedJourneyPrincipal("human:reviewer", "tenant-a", "quality", True)


def test_sibling_projections_preserve_backend_identity_and_live_provenance(
    coordinator, principal
):
    response = coordinator.get("journey:supplier-quality-1", principal)
    assert response.provenance == "LIVE_EXECUTION"
    assert response.product.identity == response.technical.identity
    assert response.product.revision == response.technical.revision
    assert response.successor.identity.citationIds == ["citation:8d-procedure"]


def test_correction_requires_new_digest_and_preserves_predecessor(
    coordinator, principal
):
    before = coordinator.get("journey:supplier-quality-1", principal)
    predecessor = deepcopy(before.successor.model_dump())
    corrected = coordinator.correct(
        before.journeyId,
        principal,
        predecessor_revision_id=before.successor.identity.canonicalWorkflowRevisionId,
        predecessor_digest=before.successor.identity.canonicalDigest,
        objective="Prioritize severe supplier issues before overdue medium issues",
        reason_code="CONSTRAINT_CHANGED",
    )
    assert corrected.predecessor is not None
    assert corrected.predecessor.model_dump() == {
        **predecessor,
        "lifecycle": "SUPERSEDED",
    }
    assert (
        corrected.successor.identity.canonicalDigest
        != predecessor["identity"]["canonicalDigest"]
    )
    assert corrected.successor.approvalState == "PENDING"
    assert corrected.successor.identity.platformExecutionIdentity is None
    assert corrected.successor.citations == []


def test_exact_digest_approval_and_bounded_existing_authority_rerun(
    coordinator, principal, authority
):
    current = coordinator.get("journey:supplier-quality-1", principal).successor
    pending = coordinator.correct(
        "journey:supplier-quality-1",
        principal,
        predecessor_revision_id=current.identity.canonicalWorkflowRevisionId,
        predecessor_digest=current.identity.canonicalDigest,
        objective="Prioritize severe supplier issues first",
        reason_code="CONSTRAINT_CHANGED",
    ).successor
    with pytest.raises(JourneyConflict, match="APPROVAL_DIGEST_MISMATCH"):
        coordinator.approve(
            "journey:supplier-quality-1",
            principal,
            candidate_digest="f" * 64,
            decision="APPROVE",
            reason_code="HUMAN_APPROVED",
            replay_identity="approval-replay:1",
        )
    approved = coordinator.approve(
        "journey:supplier-quality-1",
        principal,
        candidate_digest=pending.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="approval-replay:1",
    ).successor
    rerun = coordinator.rerun(
        "journey:supplier-quality-1",
        principal,
        revision_id=approved.identity.canonicalWorkflowRevisionId,
        digest=approved.identity.canonicalDigest,
    ).successor
    assert len(authority.calls) == 1
    assert authority.calls[0]["tenant_id"] == "tenant-a"
    assert rerun.executionState == "SUCCEEDED"
    assert rerun.identity.platformExecutionIdentity == "platform-execution:successor-2"
    assert rerun.outcome is not None and rerun.outcome.comparableValue == 2


def test_scope_is_fail_closed_and_nondisclosing(coordinator):
    foreign = TrustedJourneyPrincipal("human:foreign", "tenant-b", "quality", True)
    with pytest.raises(JourneyDenied, match=r"^$"):
        coordinator.get("journey:supplier-quality-1", foreign)


def test_absent_and_foreign_scope_are_nondisclosing_equivalents(coordinator):
    principal = TrustedJourneyPrincipal("human:reviewer", "tenant-a", "quality", True)
    foreign = TrustedJourneyPrincipal("human:foreign", "tenant-b", "quality", True)
    failures = []
    for journey_id, actor in (
        ("journey:absent", principal),
        ("journey:supplier-quality-1", foreign),
    ):
        with pytest.raises(JourneyDenied) as captured:
            coordinator.get(journey_id, actor)
        failures.append(
            (
                captured.value.state,
                captured.value.reason_code,
                captured.value.status_code,
                str(captured.value),
            )
        )
    assert (
        failures[0]
        == failures[1]
        == (
            "DENIED",
            "LIVE_JOURNEY_ACCESS_DENIED",
            403,
            "",
        )
    )


def test_registration_emits_backend_identity_without_mutating_journey() -> None:
    broker = InMemoryJourneyEventBroker()
    service = LiveJourneyCoordinator(event_publisher=broker)
    registered = service.register_live(seed())
    scope = JourneyStreamScope("tenant-a", "quality", registered.journeyId)
    subscription = broker.replay_and_subscribe(scope, None)
    assert len(subscription._replay) == 1
    event = subscription._replay[0]
    assert event.eventType == "JOURNEY_REGISTERED"
    assert event.identity == registered.successor.identity
    assert registered.successor.executionState == "SUCCEEDED"
    subscription.close()


@pytest.mark.parametrize(
    "field,value", [("provenance", "SYNTHETIC_PREVIEW"), ("canonical_digest", "bad")]
)
def test_live_registration_rejects_synthetic_or_invalid_authority(field, value):
    with pytest.raises(ValueError):
        LiveJourneyCoordinator().register_live(seed(**{field: value}))


def test_stale_remains_distinct_and_visible(principal):
    service = LiveJourneyCoordinator()
    service.register_live(seed(knowledge_state="STALE"))
    response = service.get("journey:supplier-quality-1", principal)
    assert response.state == "STALE"
    assert response.reasonCode == "LIVE_KNOWLEDGE_STALE"


def test_authoritative_transition_preserves_equal_sibling_projection(principal):
    service = LiveJourneyCoordinator()
    initial = service.register_live(seed())
    current = initial.successor
    successor = current.model_copy(
        update={
            "revision": 2,
            "predecessorRevisionId": current.identity.canonicalWorkflowRevisionId,
            "objective": "Upstream-issued corrected objective",
            "lifecycle": "PENDING_APPROVAL",
            "approvalState": "PENDING",
            "executionState": "NOT_REQUESTED",
            "answer": None,
            "citations": [],
            "outcome": None,
        }
    )
    response = service.register_authoritative_transition(
        initial.journeyId,
        principal,
        predecessor=current,
        successor=successor,
        event_type="CORRECTION_ACCEPTED",
        stage="CORRECTION",
        status="ACCEPTED",
        terminal=False,
        reason_code="UPSTREAM_CORRECTION_ACCEPTED",
        localization_key="liveJourney.event.correctionAccepted",
    )
    assert response.product.identity == response.technical.identity
    assert response.product.revision == response.technical.revision
    assert response.predecessor == current


def test_unregister_removes_only_exact_live_registration_and_stream(principal):
    broker = InMemoryJourneyEventBroker()
    service = LiveJourneyCoordinator(event_publisher=broker)
    first = service.register_live(seed())
    other_seed = seed(journey_id="journey:supplier-quality-2")
    service.register_live(other_seed)
    first_scope = JourneyStreamScope("tenant-a", "quality", first.journeyId)
    other_scope = JourneyStreamScope("tenant-a", "quality", other_seed.journey_id)
    assert broker.scope_counts(first_scope) == (1, 0)
    service.unregister_live(first.journeyId, principal)
    assert broker.scope_counts(first_scope) == (0, 0)
    assert broker.scope_counts(other_scope) == (1, 0)
    assert service.owns(first.journeyId) is False
    assert service.owns(other_seed.journey_id) is True
    with pytest.raises(JourneyDenied):
        service.get(first.journeyId, principal)
