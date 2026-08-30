"""Focused authority, call-count, replay, rerun, and reset tests."""

from __future__ import annotations

import itertools
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.app import _create_supplier_quality_execution_authority
from agent_console.knowledge_authorization import AuthorizationAction
from agent_console.live_journey import (
    LiveJourneyCoordinator,
    TrustedJourneyPrincipal,
)
from agent_console.live_journey_stream import JourneyStreamScope
from agent_console.runtime_placement import TargetState
from agent_console.supplier_quality_demo import (
    NAMESPACE,
    SCENARIO_ID,
    SupplierQualityDemoConflict,
    SupplierQualityDemoFailure,
    SupplierQualityDemoService,
    SupplierQualityDemoUnavailable,
)
from agent_console.supplier_quality_demo_schemas import (
    SupplierQualityDemoResetRequest,
    SupplierQualityDemoStartRequest,
)

ROOT = Path(__file__).parents[3]
PACK = ROOT / "examples/s5-v0.2-supplier-quality"
NOW = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)


@pytest.fixture
def materialized(tmp_path: Path) -> Path:
    target = tmp_path / NAMESPACE
    result = subprocess.run(
        [
            str(PACK / "bootstrap.sh"),
            "--scenario",
            SCENARIO_ID,
            "--namespace",
            NAMESPACE,
            "--target-dir",
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return target


@pytest.fixture
def principal() -> TrustedJourneyPrincipal:
    return TrustedJourneyPrincipal(
        "human:quality-reviewer", "tenant-a", "supplier-quality", True
    )


def service(
    materialized: Path,
    *,
    live: LiveJourneyCoordinator | None = None,
    knowledge_action: AuthorizationAction = AuthorizationAction.ALLOW,
    target_state: TargetState = TargetState.AVAILABLE,
) -> tuple[SupplierQualityDemoService, LiveJourneyCoordinator]:
    issued = itertools.count(1)
    coordinator = live or LiveJourneyCoordinator()
    return (
        SupplierQualityDemoService(
            materialized_root=materialized,
            live_journeys=coordinator,
            clock=lambda: NOW,
            opaque_id=lambda: f"issued-{next(issued)}",
            knowledge_action=knowledge_action,
            target_state=target_state,
            execution_authority_factory=_create_supplier_quality_execution_authority,
        ),
        coordinator,
    )


def start_request(
    replay_identity: str = "supplier-quality-start-1",
    *,
    locale: str = "en",
) -> SupplierQualityDemoStartRequest:
    return SupplierQualityDemoStartRequest(
        scenarioId=SCENARIO_ID,
        replayIdentity=replay_identity,
        locale=locale,
    )


def reset_request(token: str) -> SupplierQualityDemoResetRequest:
    return SupplierQualityDemoResetRequest(
        scenarioId=SCENARIO_ID,
        namespace=NAMESPACE,
        tenantId="tenant-a",
        securityDomain="supplier-quality",
        confirmationToken=token,
    )


def test_exact_three_task_live_composition_and_cross_view_equality(
    materialized: Path, principal: TrustedJourneyPrincipal
) -> None:
    subject, _ = service(materialized)
    response = subject.start(start_request(), principal)

    assert response.live.provenance == "LIVE_EXECUTION"
    assert response.live.state == "LIVE"
    assert response.live.product.identity == response.live.technical.identity
    assert response.live.product.revision == response.live.technical.revision
    assert response.live.successor.planTaskIds == [
        "collect-quality-inputs",
        "analyze-quality-exception",
        "review-quality-plan",
    ]
    assert response.live.successor.answer is not None
    assert "Collected 3 checksum-validated supplier cases" in (
        response.live.successor.answer
    )
    assert response.live.successor.citations
    assert response.live.successor.outcome is not None
    assert response.live.successor.outcome.comparableValue == 3
    assert response.callCounts.model_dump() == {
        "planningGenerator": 1,
        "matchingRequests": 1,
        "knowledgeSourceReads": 1,
        "placementEvaluations": 1,
        "coordinatorExecutions": 3,
        "nativeProviderInvocations": 3,
        "capabilityGatewayInvocations": 0,
        "fixtureExecutions": 0,
    }
    assert len(subject.execution_evidence) == 3
    assert subject.knowledge_evidence_count() == 1
    assert all(item.provider_call_count == 0 for item in subject.execution_evidence)


def test_start_exact_replay_has_no_duplicate_effect_and_conflict_is_closed(
    materialized: Path, principal: TrustedJourneyPrincipal
) -> None:
    subject, _ = service(materialized)
    first = subject.start(start_request(), principal)
    replay = subject.start(start_request(), principal)
    assert replay.replayed is True
    assert replay.journeyId == first.journeyId
    assert replay.live == first.live
    assert subject.counts == first.callCounts
    with pytest.raises(SupplierQualityDemoConflict, match="DEMO_START_REPLAY_MISMATCH"):
        subject.start(start_request(locale="zh-CN"), principal)


def test_authorization_denial_reads_nothing_and_never_executes(
    materialized: Path, principal: TrustedJourneyPrincipal
) -> None:
    subject, live = service(materialized, knowledge_action=AuthorizationAction.DENY)
    with pytest.raises(SupplierQualityDemoUnavailable, match="KNOWLEDGE_ACCESS_DENIED"):
        subject.start(start_request(), principal)
    counts = subject.counts
    assert counts.planningGenerator == 1
    assert counts.matchingRequests == 1
    assert counts.knowledgeSourceReads == 0
    assert counts.placementEvaluations == 0
    assert counts.coordinatorExecutions == 0
    assert counts.nativeProviderInvocations == 0
    assert counts.fixtureExecutions == 0
    assert not live.owns("supplier-quality-journey:issued-2")


def test_unavailable_placement_has_zero_execution_effect(
    materialized: Path, principal: TrustedJourneyPrincipal
) -> None:
    subject, _ = service(materialized, target_state=TargetState.UNAVAILABLE)
    with pytest.raises(
        SupplierQualityDemoUnavailable, match="NATIVE_TARGET_UNAVAILABLE"
    ):
        subject.start(start_request(), principal)
    counts = subject.counts
    assert counts.knowledgeSourceReads == 1
    assert counts.placementEvaluations == 1
    assert counts.coordinatorExecutions == 0
    assert counts.nativeProviderInvocations == 0


def test_root_and_checksum_validation_fail_before_planning_or_scoped_effects(
    materialized: Path, principal: TrustedJourneyPrincipal, tmp_path: Path
) -> None:
    relative, _ = service(Path(NAMESPACE))
    with pytest.raises(SupplierQualityDemoFailure, match="MATERIALIZED_ROOT_INVALID"):
        relative.start(start_request(), principal)
    assert relative.counts.planningGenerator == 0

    (materialized / "data/supplier-quality-cases-v1.json").write_text("{}")
    damaged, _ = service(materialized)
    with pytest.raises(SupplierQualityDemoFailure, match="PACKAGE_CHECKSUM_MISMATCH"):
        damaged.start(start_request(), principal)
    assert damaged.counts.planningGenerator == 0
    assert damaged.counts.knowledgeSourceReads == 0
    assert damaged.counts.coordinatorExecutions == 0
    assert not (tmp_path / "unexpected").exists()


def test_correction_fresh_approval_rerun_and_reset_preserve_history(
    materialized: Path, principal: TrustedJourneyPrincipal
) -> None:
    subject, live = service(materialized)
    started = subject.start(start_request(), principal)
    initial = started.live.successor
    pending = subject.correct(
        started.journeyId,
        principal,
        predecessor_revision_id=initial.identity.canonicalWorkflowRevisionId,
        predecessor_digest=initial.identity.canonicalDigest,
        objective=(
            "Assess governed Package 7 exceptions and escalate overdue containment"
        ),
        reason_code="CONSTRAINT_CHANGED",
    )
    assert pending.successor.approvalState == "PENDING"
    assert pending.successor.identity.platformExecutionIdentity is None
    approved = subject.approve(
        started.journeyId,
        principal,
        candidate_digest=pending.successor.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="supplier-quality-successor-approval",
    )
    assert approved.successor.approvalState == "APPROVED"
    assert approved.successor.executionState == "NOT_REQUESTED"
    completed = subject.rerun(
        started.journeyId,
        principal,
        revision_id=approved.successor.identity.canonicalWorkflowRevisionId,
        digest=approved.successor.identity.canonicalDigest,
    )
    assert completed.successor.executionState == "SUCCEEDED"
    assert (
        completed.successor.identity.platformExecutionIdentity
        != initial.identity.platformExecutionIdentity
    )
    assert len(subject.outcome_history(started.journeyId)) == 2
    assert len(subject.execution_evidence) == 6
    scope = JourneyStreamScope("tenant-a", "supplier-quality", started.journeyId)
    assert live.event_source.scope_counts(scope)[0] == 6

    before_outcomes = subject.outcome_history(started.journeyId)
    before_evidence = subject.execution_evidence
    reset = subject.reset(
        started.journeyId, reset_request(started.resetConfirmationToken), principal
    )
    assert reset.state == "RESET"
    assert subject.owns(started.journeyId) is False
    assert live.event_source.scope_counts(scope) == (0, 0)
    assert subject.outcome_history(started.journeyId) == before_outcomes
    assert subject.execution_evidence == before_evidence
    assert materialized.exists()


def test_reset_requires_exact_token_and_does_not_touch_unrelated_journey(
    materialized: Path, principal: TrustedJourneyPrincipal
) -> None:
    subject, live = service(materialized)
    first = subject.start(start_request("start-one"), principal)
    second = subject.start(start_request("start-two"), principal)
    with pytest.raises(Exception, match="DEMO_RESET_CONFIRMATION_MISMATCH"):
        subject.reset(
            first.journeyId, reset_request("demo-reset:" + "0" * 64), principal
        )
    assert subject.owns(first.journeyId)
    subject.reset(
        first.journeyId, reset_request(first.resetConfirmationToken), principal
    )
    assert live.owns(second.journeyId)
    assert subject.owns(second.journeyId)
