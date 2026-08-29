"""Internal API tests for authorization-first Package 6A capture and reads."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from agent_console.app import (
    app,
    get_intervention_feedback_service,
    get_live_journey_principal,
    get_live_journey_service,
)
from agent_console.intervention_feedback import (
    InMemoryInterventionFeedbackRepository,
    InterventionFeedbackService,
)
from agent_console.live_journey import (
    AuthorizedRerunResult,
    LiveJourneyCoordinator,
    LiveJourneySeed,
    TrustedJourneyPrincipal,
)
from agent_console.live_journey_schemas import JourneyCitation, JourneyOutcome
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 29, 3, 30, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[3]


class IssuedIds:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"api-issued-{self.count}"


class ExistingExecution:
    def __init__(self) -> None:
        self.calls = 0

    def rerun(self, **_: str) -> AuthorizedRerunResult:
        self.calls += 1
        return AuthorizedRerunResult(
            platform_execution_identity="platform-execution:successor-2",
            shared_snapshot_id="shared-snapshot:successor-2",
            graph_snapshot_id="graph-snapshot:successor-2",
            evidence_ids=("execution-evidence:successor-2",),
            citations=(citation(),),
            outcome=JourneyOutcome(
                outcomeId="outcome:successor-2",
                classification="SUCCEEDED",
                summary="Severe supplier issues are prioritized.",
                comparableMetric="at_risk_closure_count",
                comparableValue=2,
            ),
            answer="Prioritize two severe supplier issues.",
        )


def citation() -> JourneyCitation:
    return JourneyCitation(
        citationId="citation:8d-procedure",
        retrievalEvidenceId="retrieval-evidence:8d-procedure",
        authorizationDecisionId="knowledge-authorization:allow-1",
        knowledgePackId="knowledge-pack:supplier-quality",
        knowledgePackVersion="v1",
        knowledgePackDigest="c" * 64,
        documentId="document:8d-procedure",
        documentVersion="v1",
        documentDigest="d" * 64,
        sectionId="section:containment",
        chunkId="chunk:containment:1",
        status="AVAILABLE",
    )


def trusted_principal(**overrides: object) -> TrustedJourneyPrincipal:
    values: dict[str, object] = {
        "principal_id": "human:reviewer",
        "tenant_id": "tenant-a",
        "security_domain": "supplier-quality",
        "authorized": True,
    }
    values.update(overrides)
    return TrustedJourneyPrincipal(**values)  # type: ignore[arg-type]


def completed_journey() -> tuple[LiveJourneyCoordinator, ExistingExecution]:
    execution = ExistingExecution()
    journey = LiveJourneyCoordinator(execution)
    journey.register_live(
        LiveJourneySeed(
            journey_id="journey:supplier-quality-1",
            tenant_id="tenant-a",
            security_domain="supplier-quality",
            canonical_workflow_revision_id="canonical-workflow-revision:one",
            canonical_digest="a" * 64,
            approval_id="planning-approval:one",
            objective="Identify supplier issues at risk of missing closure.",
            task_ids=("task:collect", "task:analyze"),
            shared_snapshot_id="shared-snapshot:one",
            graph_snapshot_id="graph-snapshot:one",
            platform_execution_identity="platform-execution:one",
            placement_decision_id="placement-decision:native-1",
            evidence_ids=("execution-evidence:one",),
            citations=(citation(),),
            outcome=JourneyOutcome(
                outcomeId="outcome:one",
                classification="SUCCEEDED",
                summary="Three supplier issues are at risk.",
                comparableMetric="at_risk_closure_count",
                comparableValue=3,
            ),
            answer="Three supplier issues need review.",
        )
    )
    principal = trusted_principal()
    current = journey.get("journey:supplier-quality-1", principal).successor
    pending = journey.correct(
        "journey:supplier-quality-1",
        principal,
        predecessor_revision_id=current.identity.canonicalWorkflowRevisionId,
        predecessor_digest=current.identity.canonicalDigest,
        objective="Prioritize severe supplier issues first.",
        reason_code="CONSTRAINT_CHANGED",
    ).successor
    approved = journey.approve(
        "journey:supplier-quality-1",
        principal,
        candidate_digest=pending.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="package-6a-api-setup",
    ).successor
    journey.rerun(
        "journey:supplier-quality-1",
        principal,
        revision_id=approved.identity.canonicalWorkflowRevisionId,
        digest=approved.identity.canonicalDigest,
    )
    return journey, execution


def client(
    repository: object | None = None,
    *,
    principal: TrustedJourneyPrincipal | None = None,
) -> tuple[TestClient, ExistingExecution]:
    journey, execution = completed_journey()
    capture = InterventionFeedbackService(
        repository,  # type: ignore[arg-type]
        clock=lambda: NOW,
        id_factory=IssuedIds(),
    )
    app.dependency_overrides.clear()
    app.dependency_overrides[get_live_journey_service] = lambda: journey
    app.dependency_overrides[get_live_journey_principal] = lambda: (
        principal or trusted_principal()
    )
    app.dependency_overrides[get_intervention_feedback_service] = lambda: capture
    return TestClient(app), execution


def path(suffix: str = "") -> str:
    return (
        "/api/internal/preview/v1/live-planning-journeys/"
        f"journey:supplier-quality-1{suffix}"
    )


def current_identity(api: TestClient) -> dict[str, object]:
    journey = api.get(
        "/api/internal/preview/v1/live-planning-journeys/journey:supplier-quality-1"
    ).json()
    return {
        "predecessorRevisionId": journey["predecessor"]["identity"][
            "canonicalWorkflowRevisionId"
        ],
        "successorRevisionId": journey["successor"]["identity"][
            "canonicalWorkflowRevisionId"
        ],
        "outcomeId": journey["successor"]["outcome"]["outcomeId"],
        "evidenceId": journey["successor"]["identity"]["evidenceIds"][0],
    }


def intervention_body(api: TestClient) -> dict[str, object]:
    return {
        **current_identity(api),
        "eventKind": "CONSTRAINT_CHANGED",
        "affectedElementReference": "CONSTRAINT",
        "correctionPatchReference": "CONSTRAINT_PATCH",
        "reasonCode": "MISSING_CONSTRAINT",
        "optimizationUseConsentDecision": "DENIED",
    }


def test_capture_and_read_return_equal_backend_issued_sibling_identities() -> None:
    api, _ = client()
    empty = api.get(path("/intervention-feedback"))
    assert empty.status_code == 200
    assert empty.json()["product"]["identity"] == empty.json()["technical"]["identity"]
    response = api.post(path("/interventions"), json=intervention_body(api))
    assert response.status_code == 200
    body = response.json()
    assert body["product"]["identity"] == body["technical"]["identity"]
    assert body["product"]["interventions"] == body["technical"]["interventions"]
    record = body["product"]["interventions"][0]
    assert record["interventionEventId"].startswith("intervention-event:api-issued-")
    assert record["recordDigest"] and len(record["recordDigest"]) == 64
    assert record["principalId"] == "human:reviewer"
    assert record["provenance"] == "LIVE_EXECUTION"
    assert record["optimizationUseConsentDecision"] == "DENIED"


def test_api_identical_replay_is_idempotent_and_conflicting_replay_fails() -> None:
    api, _ = client()
    command = intervention_body(api)
    first = api.post(path("/interventions"), json=command).json()["product"][
        "interventions"
    ][0]
    duplicate = api.post(path("/interventions"), json=command).json()["product"][
        "interventions"
    ][0]
    assert duplicate == first
    conflict = api.post(
        path("/interventions"), json={**command, "reasonCode": "WRONG_ORDER"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["reasonCode"] == "INTERVENTION_REPLAY_CONFLICT"


def test_lifecycle_tombstone_and_feedback_supersession_are_append_only() -> None:
    api, _ = client()
    created = api.post(path("/interventions"), json=intervention_body(api)).json()
    event_id = created["product"]["interventions"][0]["interventionEventId"]
    tombstoned = api.post(
        path(f"/interventions/{event_id}/lifecycle"),
        json={"lifecycle": "TOMBSTONED"},
    )
    assert tombstoned.status_code == 200
    assert [
        item["lifecycle"] for item in tombstoned.json()["product"]["interventions"]
    ] == ["RECORDED", "TOMBSTONED"]

    identity = current_identity(api)
    first = api.post(
        path("/outcome-feedback"),
        json={
            "outcomeId": identity["outcomeId"],
            "evidenceId": identity["evidenceId"],
            "assessment": "PARTIALLY_SATISFIED",
            "reasonCodes": ["MISSING_CONSTRAINT"],
            "supersedesFeedbackId": None,
        },
    ).json()["product"]["outcomeFeedback"][0]["record"]
    changed = api.post(
        path("/outcome-feedback"),
        json={
            "outcomeId": identity["outcomeId"],
            "evidenceId": identity["evidenceId"],
            "assessment": "SATISFIED",
            "reasonCodes": ["CITATION_NOT_USEFUL"],
            "supersedesFeedbackId": first["feedbackId"],
        },
    )
    assert changed.status_code == 200
    feedback = changed.json()["product"]["outcomeFeedback"]
    assert [item["lifecycle"] for item in feedback] == ["SUPERSEDED", "RECORDED"]
    assert feedback[1]["record"]["supersedesFeedbackId"] == first["feedbackId"]


def test_malformed_prohibited_and_unknown_fields_return_constant_safe_error() -> None:
    api, _ = client()
    secret = "Bearer this-must-never-be-returned"
    response = api.post(
        path("/interventions"),
        json={**intervention_body(api), "rawPrompt": secret},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "schemaVersion": 1,
        "state": "INVALID",
        "reasonCode": "CAPTURE_COMMAND_INVALID",
        "message": "Intervention and feedback capture is unavailable",
    }
    assert secret not in response.text
    assert "rawPrompt" not in response.text


def test_stale_and_mismatched_identity_references_fail_closed() -> None:
    api, _ = client()
    response = api.post(
        path("/interventions"),
        json={
            **intervention_body(api),
            "successorRevisionId": "canonical-workflow-revision:stale",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["reasonCode"] == (
        "INTERVENTION_TARGET_STALE_OR_MISMATCHED"
    )
    feedback = api.post(
        path("/outcome-feedback"),
        json={
            "outcomeId": "outcome:foreign",
            "evidenceId": "execution-evidence:successor-2",
            "assessment": "UNSATISFIED",
            "reasonCodes": ["WRONG_DATA"],
        },
    )
    assert feedback.status_code == 409
    assert feedback.json()["detail"]["reasonCode"] == (
        "OUTCOME_FEEDBACK_TARGET_STALE_OR_MISMATCHED"
    )


def test_denied_and_cross_domain_reads_are_nondisclosing_and_prequery() -> None:
    class ReadSpyRepository(InMemoryInterventionFeedbackRepository):
        reads = 0

        def interventions(self, **kwargs: str):  # type: ignore[no-untyped-def]
            self.reads += 1
            return super().interventions(**kwargs)

    repository = ReadSpyRepository()
    api, _ = client(repository, principal=trusted_principal(tenant_id="tenant-b"))
    response = api.get(path("/intervention-feedback"))
    assert response.status_code == 403
    assert response.json()["detail"]["reasonCode"] == (
        "INTERVENTION_FEEDBACK_ACCESS_DENIED"
    )
    assert repository.reads == 0
    assert "supplier-quality-1" not in response.text
    assert "tenant-a" not in response.text
    assert "outcome" not in response.text.lower()


def test_capture_repository_failure_is_explicit_and_does_not_rerun_execution() -> None:
    class FailedRepository(InMemoryInterventionFeedbackRepository):
        def append_intervention(self, record):  # type: ignore[no-untyped-def]
            raise OSError("/private/host/path secret")

    api, execution = client(FailedRepository())
    before = execution.calls
    response = api.post(path("/interventions"), json=intervention_body(api))
    assert response.status_code == 503
    assert response.json()["detail"]["reasonCode"] == (
        "INTERVENTION_FEEDBACK_REPOSITORY_UNAVAILABLE"
    )
    assert execution.calls == before
    assert "/private/host/path" not in response.text


def frontend_source(path: str) -> str:
    return (ROOT / "console/frontend/src" / path).read_text(encoding="utf-8")


def test_frontend_submits_only_bounded_commands_and_never_mints_authority() -> None:
    api_source = frontend_source("api/interventionFeedback.ts")
    product = frontend_source("product/InterventionFeedback.tsx")
    for prohibited in (
        "crypto.randomUUID",
        "Math.random",
        "Date.now",
        "recordId:",
        "feedbackId:",
        "recordDigest:",
        "feedbackDigest:",
        "principalId:",
        "decisionTime:",
        "tenantId:",
        "securityDomain:",
        "provenance:",
    ):
        assert prohibited not in product
    assert "JSON.stringify(command)" in api_source
    assert "PRODUCT_TECHNICAL_IDENTITY_MISMATCH" in api_source
    assert "PRODUCT_TECHNICAL_RECORD_MISMATCH" in api_source
    assert '"LIVE_EXECUTION", "SYNTHETIC_PREVIEW"' in api_source


def test_frontend_localizes_labels_with_english_fallback_and_preserves_codes() -> None:
    messages = frontend_source("i18n/messages.ts")
    en, zh = messages.split('"zh-CN":', 1)
    feedback_keys = re.compile(r'"(feedback\.[^"]+)"\s*:')
    assert set(feedback_keys.findall(en)) == set(feedback_keys.findall(zh))
    assert len(set(feedback_keys.findall(en))) >= 30
    translate = frontend_source("i18n/translate.ts")
    presentation = frontend_source("i18n/presentation.ts")
    assert "catalog[DEFAULT_LOCALE][key]" in translate
    assert "preserveTechnicalCode" in presentation
    for code in ("SATISFIED", "PARTIALLY_SATISFIED", "UNSATISFIED"):
        assert code in messages and code in presentation


def test_frontend_product_technical_and_responsive_seams_are_present() -> None:
    product_page = frontend_source("pages/ProductViewPage.tsx")
    technical_page = frontend_source("pages/TechnicalViewPage.tsx")
    css = frontend_source("styles/app.css")
    assert "<InterventionFeedback journeyId={liveJourneyId}" in product_page
    assert "<InterventionFeedbackPanel journeyId={liveJourneyId}" in technical_page
    assert ".feedback-grid" in css
    assert "@media (max-width: 600px)" in css
    assert "grid-template-columns: 1fr" in css
    assert "overflow-wrap: anywhere" in css
