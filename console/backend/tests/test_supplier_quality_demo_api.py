"""FastAPI contract tests for the exact Package 7 initiation/reset bridge."""

from __future__ import annotations

import itertools
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.app import (
    _create_supplier_quality_execution_authority,
    app,
    get_live_journey_principal,
    get_live_journey_service,
    get_supplier_quality_demo_service,
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
from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[3]
PACK = ROOT / "examples/s5-v0.2-supplier-quality"
NOW = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)


@pytest.fixture
def api(tmp_path: Path):
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
    issued = itertools.count(1)
    live = LiveJourneyCoordinator()
    demo = SupplierQualityDemoService(
        materialized_root=target,
        live_journeys=live,
        clock=lambda: NOW,
        opaque_id=lambda: f"api-issued-{next(issued)}",
        execution_authority_factory=_create_supplier_quality_execution_authority,
    )
    principal = TrustedJourneyPrincipal(
        "human:api-reviewer", "tenant-a", "supplier-quality", True
    )
    app.dependency_overrides[get_live_journey_service] = lambda: live
    app.dependency_overrides[get_supplier_quality_demo_service] = lambda: demo
    app.dependency_overrides[get_live_journey_principal] = lambda: principal
    try:
        yield TestClient(app), demo, live
    finally:
        app.dependency_overrides.clear()


def start(client: TestClient, replay: str = "api-start"):
    return client.post(
        "/api/internal/demo/v1/supplier-quality-journeys",
        json={
            "scenarioId": SCENARIO_ID,
            "replayIdentity": replay,
            "locale": "en",
        },
    )


def test_start_get_and_exact_replay_share_one_backend_identity(api) -> None:
    client, demo, _ = api
    first = start(client)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["live"]["provenance"] == "LIVE_EXECUTION"
    assert payload["journeyId"] == payload["live"]["journeyId"]
    assert (
        payload["live"]["product"]["identity"]
        == payload["live"]["technical"]["identity"]
    )
    assert (
        payload["live"]["product"]["revision"]
        == payload["live"]["technical"]["revision"]
    )
    fetched = client.get(
        "/api/internal/preview/v1/live-planning-journeys/" + payload["journeyId"]
    )
    assert fetched.status_code == 200
    assert fetched.json() == payload["live"]

    replay = start(client)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["journeyId"] == payload["journeyId"]
    assert demo.counts.model_dump() == payload["callCounts"]


def test_malformed_conflicting_and_denied_requests_fail_truthfully(api) -> None:
    client, _, _ = api
    assert (
        client.post(
            "/api/internal/demo/v1/supplier-quality-journeys",
            json={"scenarioId": SCENARIO_ID, "replayIdentity": "bad", "extra": True},
        ).status_code
        == 422
    )
    assert start(client, "conflict").status_code == 200
    conflict = client.post(
        "/api/internal/demo/v1/supplier-quality-journeys",
        json={
            "scenarioId": SCENARIO_ID,
            "replayIdentity": "conflict",
            "locale": "zh-CN",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["reasonCode"] == "DEMO_START_REPLAY_MISMATCH"

    app.dependency_overrides[get_live_journey_principal] = lambda: (
        TrustedJourneyPrincipal("", "tenant-a", "supplier-quality", False)
    )
    denied = start(client, "denied")
    assert denied.status_code == 403
    assert denied.json()["detail"]["state"] == "DENIED"


def test_correction_approval_rerun_sse_and_scoped_reset(api) -> None:
    client, demo, live = api
    started = start(client, "full-flow").json()
    journey_id = started["journeyId"]
    initial = started["live"]["successor"]
    corrected = client.post(
        f"/api/internal/preview/v1/live-planning-journeys/{journey_id}/corrections",
        json={
            "predecessorRevisionId": initial["identity"]["canonicalWorkflowRevisionId"],
            "predecessorDigest": initial["identity"]["canonicalDigest"],
            "objective": (
                "Assess governed Package 7 exceptions and escalate containment"
            ),
            "reasonCode": "CONSTRAINT_CHANGED",
        },
    )
    assert corrected.status_code == 200, corrected.text
    pending = corrected.json()["successor"]
    approved = client.post(
        f"/api/internal/preview/v1/live-planning-journeys/{journey_id}/approvals",
        json={
            "candidateDigest": pending["identity"]["canonicalDigest"],
            "decision": "APPROVE",
            "reasonCode": "HUMAN_APPROVED",
            "replayIdentity": "api-successor-approval",
        },
    )
    assert approved.status_code == 200, approved.text
    successor = approved.json()["successor"]
    rerun = client.post(
        f"/api/internal/preview/v1/live-planning-journeys/{journey_id}/reruns",
        json={
            "canonicalWorkflowRevisionId": successor["identity"][
                "canonicalWorkflowRevisionId"
            ],
            "canonicalDigest": successor["identity"]["canonicalDigest"],
        },
    )
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["successor"]["executionState"] == "SUCCEEDED"
    assert len(demo.outcome_history(journey_id)) == 2
    assert len(demo.execution_evidence) == 6

    scope_identity = rerun.json()["successor"]["identity"]
    scope = (
        scope_identity["tenantId"],
        scope_identity["securityDomain"],
        journey_id,
    )
    assert live.event_source._buffers[scope].terminal is True
    assert [
        event["eventType"]
        for event in (
            __import__("json").loads(line[6:])
            for line in client.get(
                f"/api/internal/preview/v1/live-planning-journeys/{journey_id}/events"
            ).text.splitlines()
            if line.startswith("data: ")
        )
    ] == [
        "JOURNEY_REGISTERED",
        "CORRECTION_ACCEPTED",
        "APPROVAL_RECORDED",
        "EXECUTION_AUTHORIZED",
        "EXECUTION_STARTED",
        "EXECUTION_SUCCEEDED",
    ]

    wrong = client.request(
        "DELETE",
        f"/api/internal/demo/v1/supplier-quality-journeys/{journey_id}",
        json={
            "scenarioId": SCENARIO_ID,
            "namespace": NAMESPACE,
            "tenantId": "tenant-a",
            "securityDomain": "supplier-quality",
            "confirmationToken": "demo-reset:" + "0" * 64,
        },
    )
    assert wrong.status_code == 403
    reset = client.request(
        "DELETE",
        f"/api/internal/demo/v1/supplier-quality-journeys/{journey_id}",
        json={
            "scenarioId": SCENARIO_ID,
            "namespace": NAMESPACE,
            "tenantId": "tenant-a",
            "securityDomain": "supplier-quality",
            "confirmationToken": started["resetConfirmationToken"],
        },
    )
    assert reset.status_code == 200
    assert reset.json()["state"] == "RESET"
    assert demo.outcome_history(journey_id)
    assert demo.execution_evidence
