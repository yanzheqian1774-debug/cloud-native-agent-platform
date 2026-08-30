"""Repository-level S5-IMPL-037 Package 7 live integration acceptance."""

from __future__ import annotations

import hashlib
import itertools
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from agent_console.app import _create_supplier_quality_execution_authority
from agent_console.intervention_feedback import (
    InterventionFeedbackService,
    TrustedCapturePrincipal,
    TrustedInterventionTarget,
)
from agent_console.intervention_feedback_schemas import (
    InterventionCaptureCommand,
    OutcomeFeedbackCommand,
)
from agent_console.live_journey import (
    LiveJourneyCoordinator,
    TrustedJourneyPrincipal,
)
from agent_console.supplier_quality_demo import (
    NAMESPACE,
    SCENARIO_ID,
    SupplierQualityDemoService,
)
from agent_console.supplier_quality_demo_schemas import (
    SupplierQualityDemoResetRequest,
    SupplierQualityDemoStartRequest,
)

ROOT = Path(__file__).parents[1]
PACK = ROOT / "examples/s5-v0.2-supplier-quality"
NOW = datetime(2026, 8, 30, 2, 0, tzinfo=UTC)


def tree_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def materialize(tmp_path: Path) -> Path:
    target = tmp_path / NAMESPACE
    subprocess.run(
        [
            str(PACK / "bootstrap.sh"),
            "--scenario",
            SCENARIO_ID,
            "--namespace",
            NAMESPACE,
            "--target-dir",
            str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return target


def test_package7_to_live_journey_to_feedback_to_scoped_reset(tmp_path: Path) -> None:
    source_digest = tree_digest(PACK)
    target = materialize(tmp_path)
    issued = itertools.count(1)
    live = LiveJourneyCoordinator()
    service = SupplierQualityDemoService(
        materialized_root=target,
        live_journeys=live,
        clock=lambda: NOW,
        opaque_id=lambda: f"integration-issued-{next(issued)}",
        execution_authority_factory=_create_supplier_quality_execution_authority,
    )
    journey_principal = TrustedJourneyPrincipal(
        "human:integration-reviewer", "tenant-a", "supplier-quality", True
    )
    started = service.start(
        SupplierQualityDemoStartRequest(
            scenarioId=SCENARIO_ID,
            replayIdentity="integration-start",
            locale="en",
        ),
        journey_principal,
    )
    initial = started.live.successor
    pending = service.correct(
        started.journeyId,
        journey_principal,
        predecessor_revision_id=initial.identity.canonicalWorkflowRevisionId,
        predecessor_digest=initial.identity.canonicalDigest,
        objective="Assess Package 7 exceptions and escalate overdue containment",
        reason_code="CONSTRAINT_CHANGED",
    )
    approved = service.approve(
        started.journeyId,
        journey_principal,
        candidate_digest=pending.successor.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="integration-successor-approval",
    )
    completed = service.rerun(
        started.journeyId,
        journey_principal,
        revision_id=approved.successor.identity.canonicalWorkflowRevisionId,
        digest=approved.successor.identity.canonicalDigest,
    )
    predecessor = completed.predecessor
    successor = completed.successor
    assert predecessor is not None
    assert successor.outcome is not None
    assert successor.identity.platformExecutionIdentity is not None
    assert completed.product.identity == completed.technical.identity
    assert completed.product.revision == completed.technical.revision

    target_authority = TrustedInterventionTarget(
        journey_id=started.journeyId,
        tenant_id="tenant-a",
        security_domain="supplier-quality",
        provenance="LIVE_EXECUTION",
        predecessor_revision_id=predecessor.identity.canonicalWorkflowRevisionId,
        predecessor_digest=predecessor.identity.canonicalDigest,
        successor_revision_id=successor.identity.canonicalWorkflowRevisionId,
        successor_digest=successor.identity.canonicalDigest,
        platform_execution_identity=successor.identity.platformExecutionIdentity,
        outcome_id=successor.outcome.outcomeId,
        execution_evidence_ids=tuple(successor.identity.evidenceIds),
    )
    capture_principal = TrustedCapturePrincipal(
        "human:integration-reviewer", "tenant-a", "supplier-quality", True
    )
    capture_ids = itertools.count(1)
    capture = InterventionFeedbackService(
        clock=lambda: NOW,
        id_factory=lambda: f"capture-issued-{next(capture_ids)}",
    )
    evidence_id = successor.identity.evidenceIds[-1]
    capture.capture_intervention(
        capture_principal,
        target_authority,
        InterventionCaptureCommand(
            predecessorRevisionId=target_authority.predecessor_revision_id,
            successorRevisionId=target_authority.successor_revision_id,
            outcomeId=target_authority.outcome_id,
            evidenceId=evidence_id,
            eventKind="CONSTRAINT_CHANGED",
            affectedElementReference="WORKFLOW_OBJECTIVE",
            correctionPatchReference="OBJECTIVE_REPLACEMENT",
            reasonCode="MISSING_CONSTRAINT",
            optimizationUseConsentDecision="DENIED",
        ),
    )
    capture.capture_feedback(
        capture_principal,
        target_authority,
        OutcomeFeedbackCommand(
            outcomeId=target_authority.outcome_id,
            evidenceId=evidence_id,
            assessment="SATISFIED",
            reasonCodes=["CITATION_NOT_USEFUL"],
            supersedesFeedbackId=None,
        ),
    )
    assert capture.preserved_counts(capture_principal, target_authority) == (1, 1)
    outcomes_before = service.outcome_history(started.journeyId)
    evidence_before = service.execution_evidence

    service.reset(
        started.journeyId,
        SupplierQualityDemoResetRequest(
            scenarioId=SCENARIO_ID,
            namespace=NAMESPACE,
            tenantId="tenant-a",
            securityDomain="supplier-quality",
            confirmationToken=started.resetConfirmationToken,
        ),
        journey_principal,
    )
    assert capture.preserved_counts(capture_principal, target_authority) == (1, 1)
    assert service.outcome_history(started.journeyId) == outcomes_before
    assert service.execution_evidence == evidence_before
    assert target.exists()
    assert tree_digest(PACK) == source_digest


def test_live_frontend_mode_is_explicit_and_fixture_free_at_render_boundary() -> None:
    app = (ROOT / "console/frontend/src/App.tsx").read_text()
    product = (ROOT / "console/frontend/src/pages/ProductViewPage.tsx").read_text()
    technical = (ROOT / "console/frontend/src/pages/TechnicalViewPage.tsx").read_text()
    api = (ROOT / "console/frontend/src/api/supplierQualityDemo.ts").read_text()
    assert "VITE_SUPPLIER_QUALITY_DEMO_MODE" in app
    assert "LIVE_EXECUTION" in app
    assert "supplierQualityJourneyId" in product
    assert "supplierQualityJourneyId" in technical
    assert "SYNTHETIC_PREVIEW" not in api
    assert "/api/internal/demo/v1/supplier-quality-journeys" in api
