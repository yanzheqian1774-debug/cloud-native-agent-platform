"""S5-TEST-007 bounded Enhanced Golden Demo acceptance.

This suite consumes the genuine Package 7 start/reset bridge.  It does not seed
``LiveJourneyCoordinator`` and never substitutes synthetic history for live work.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from agent_console.app import (
    _create_supplier_quality_execution_authority,
    app,
    get_live_journey_principal,
    get_live_journey_service,
    get_supplier_quality_demo_service,
)
from agent_console.live_journey import LiveJourneyCoordinator, TrustedJourneyPrincipal
from agent_console.supplier_quality_demo import (
    NAMESPACE,
    SCENARIO_ID,
    SupplierQualityDemoService,
)
from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[1]
PACK = ROOT / "examples/s5-v0.2-supplier-quality"
EXPECTED_CHECKSUM_LINES = 10


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _bootstrap(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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


def test_package7_checksums_bootstrap_and_exact_reset_are_reproducible(
    tmp_path: Path,
) -> None:
    checksum_lines = [
        line
        for line in (PACK / "checksums.sha256").read_text().splitlines()
        if line.strip()
    ]
    assert len(checksum_lines) == EXPECTED_CHECKSUM_LINES
    subprocess.run(
        ["shasum", "-a", "256", "-c", "checksums.sha256"],
        cwd=PACK,
        check=True,
        capture_output=True,
        text=True,
    )
    source_before = _tree_digest(PACK)
    target = tmp_path / NAMESPACE
    _bootstrap(target)
    first = _tree_digest(target)
    _bootstrap(target)
    assert _tree_digest(target) == first
    reset = [
        str(PACK / "reset.sh"),
        "--scenario",
        SCENARIO_ID,
        "--namespace",
        NAMESPACE,
        "--target-dir",
        str(target),
        "--confirm",
        f"{SCENARIO_ID}@{NAMESPACE}",
    ]
    subprocess.run(reset, check=True, capture_output=True, text=True)
    subprocess.run(reset, check=True, capture_output=True, text=True)
    assert not target.exists()
    assert _tree_digest(PACK) == source_before


def test_package7_rejects_implicit_broad_and_incorrect_reset_targets(
    tmp_path: Path,
) -> None:
    rejected = [
        [],
        ["--target-dir", "/"],
        ["--target-dir", "relative/path"],
        ["--target-dir", str(tmp_path / "*")],
        ["--target-dir", str(tmp_path / "wrong-namespace")],
    ]
    for extra in rejected:
        result = subprocess.run(
            [str(PACK / "reset.sh"), *extra], capture_output=True, text=True
        )
        assert result.returncode != 0


def test_genuine_start_contract_proves_live_identity_and_no_fixture_fallback(
    tmp_path: Path,
) -> None:
    target = tmp_path / NAMESPACE
    _bootstrap(target)
    live_authority = LiveJourneyCoordinator()
    issued = itertools.count(1)
    demo = SupplierQualityDemoService(
        materialized_root=target,
        live_journeys=live_authority,
        clock=lambda: datetime(2026, 8, 30, 8, 0, tzinfo=UTC),
        opaque_id=lambda: f"s5-test-007-issued-{next(issued)}",
        execution_authority_factory=_create_supplier_quality_execution_authority,
    )
    principal = TrustedJourneyPrincipal(
        "human:s5-test-007-reviewer", "tenant-a", "supplier-quality", True
    )
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_live_journey_service] = lambda: live_authority
    app.dependency_overrides[get_supplier_quality_demo_service] = lambda: demo
    app.dependency_overrides[get_live_journey_principal] = lambda: principal
    try:
        client = TestClient(app)
        response = client.post(
            "/api/internal/demo/v1/supplier-quality-journeys",
            json={
                "scenarioId": SCENARIO_ID,
                "replayIdentity": "s5-test-007-live-start",
                "locale": "en",
            },
        )
        assert response.status_code == 200, response.text
        started = response.json()
        live = started["live"]
        assert live["provenance"] == "LIVE_EXECUTION"
        assert started["journeyId"] == live["journeyId"]
        assert live["product"]["identity"] == live["technical"]["identity"]
        assert live["product"]["revision"] == live["technical"]["revision"]
        identity = live["product"]["identity"]
        for field in (
            "tenantId",
            "securityDomain",
            "canonicalWorkflowRevisionId",
            "canonicalDigest",
            "approvalId",
            "sharedSnapshotId",
            "graphSnapshotId",
            "platformExecutionIdentity",
            "placementDecisionId",
            "evidenceIds",
            "citationIds",
        ):
            assert identity[field]
        assert "SYNTHETIC_HISTORY" not in json.dumps(live)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_preapproval_denial_is_nondisclosing_and_has_zero_downstream_calls() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/internal/demo/v1/supplier-quality-journeys",
        json={
            "scenarioId": SCENARIO_ID,
            "replayIdentity": "s5-test-007-denied-start",
            "locale": "en",
            "canonicalDigest": "0" * 64,
        },
    )
    assert response.status_code == 422
    body = response.text
    for forbidden in ("citationId", "evidenceId", "sourceTitle", "chunk"):
        assert forbidden not in body


def test_frontend_live_route_is_explicit_bilingual_and_fixture_free() -> None:
    app_source = (ROOT / "console/frontend/src/App.tsx").read_text()
    api_source = (ROOT / "console/frontend/src/api/supplierQualityDemo.ts").read_text()
    messages = (ROOT / "console/frontend/src/i18n/messages.ts").read_text()
    assert "VITE_SUPPLIER_QUALITY_DEMO_MODE" in app_source
    assert "if (supplierQualityLive)" in app_source
    assert (
        "QuestionToOutcomeJourney"
        in (ROOT / "console/frontend/src/pages/ProductViewPage.tsx").read_text()
    )
    assert "SYNTHETIC_PREVIEW" not in api_source
    assert '"supplierQuality.product.title"' in messages
    assert "供应商质量实时旅程" in messages
