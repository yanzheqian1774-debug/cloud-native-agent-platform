"""Bounded static and compatibility validation for S5-IMPL-010 Product View."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from agent_console.graph_projection import ProjectionContext
from agent_console.shared_views import product_view

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "console/frontend/src/product"
FIXTURE = PRODUCT / "fixture.ts"


def source(name: str) -> str:
    path = PRODUCT / name
    assert path.is_file(), f"required Product source absent: {name}"
    return path.read_text(encoding="utf-8")


def run_journey(script: str) -> dict[str, object]:
    module = (PRODUCT / "journey.ts").as_uri()
    completed = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            (
                "import { initialJourney, journeyReducer, applyApprovalDecision } "
                f'from "{module}"; {script}'
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(completed.stdout)


def test_authorized_product_source_structure_exists() -> None:
    expected = {
        "types.ts",
        "fixture.ts",
        "adapter.ts",
        "journey.ts",
        "ProductNavigation.tsx",
        "DigitalEmployeeDirectory.tsx",
        "BusinessJourney.tsx",
        "DraftDiffApproval.tsx",
        "ProductGraph.tsx",
        "OutcomeEvidence.tsx",
        "RuntimeSupport.tsx",
    }
    assert {path.name for path in PRODUCT.iterdir()} == expected


def test_fixture_is_bounded_and_non_authoritative() -> None:
    text = source("fixture.ts")
    assert all(
        label in text
        for label in (
            "DETERMINISTIC",
            "SYNTHETIC",
            "NON_AUTHORITATIVE",
            "TECHNICAL_PREVIEW",
        )
    )
    assert "fetch(" not in text and "localStorage" not in text


def test_shared_product_field_compatibility() -> None:
    fields = set(product_view.__annotations__)
    assert "source" in fields and "return" in fields
    text = source("fixture.ts")
    for concept in (
        "platformExecutionIdentity",
        "planRevision",
        "employees",
        "outcome",
        "citations",
    ):
        assert concept in text


def test_canonical_projection_context_remains_product() -> None:
    assert ProjectionContext.PRODUCT.value == "PRODUCT"
    assert "graphSnapshotId" in source("fixture.ts")
    assert "CANONICAL_GRAPH_SNAPSHOT_REQUIRED" in source("adapter.ts")


def test_platform_execution_identity_is_single_and_stable() -> None:
    text = source("fixture.ts")
    identities = re.findall(r"pei-synthetic-[a-z0-9-]+", text)
    assert set(identities) == {"pei-synthetic-qi-1042-attempt-1"}


@pytest.mark.parametrize(
    "cardinality", ["ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE", "MANY_TO_MANY"]
)
def test_graph_supports_required_cardinalities(cardinality: str) -> None:
    assert cardinality in source("fixture.ts")


def test_fixture_six_aggregate_expansion_order() -> None:
    text = source("fixture.ts")
    block = text[
        text.index('id: "aggregate.fixture-6"') : text.index(
            'id: "aggregate.task-role"'
        )
    ]
    assert [
        block.index(value)
        for value in ('type: "DEPENDS_ON"', 'type: "TRIGGERS"', 'type: "DATA_FLOW"')
    ] == sorted(
        block.index(value)
        for value in ('type: "DEPENDS_ON"', 'type: "TRIGGERS"', 'type: "DATA_FLOW"')
    )
    for field in ("id:", "direction:", "cardinality:", "evidenceIds:"):
        assert block.count(field) >= 3


def test_graph_expansion_is_progressively_disclosed() -> None:
    text = source("ProductGraph.tsx")
    assert "aria-expanded" in text and "<details>" in text
    assert "rawRelations.map" in text


def test_graph_does_not_infer_edges_and_marks_disconnected_nodes() -> None:
    component = source("ProductGraph.tsx")
    css = (ROOT / "console/frontend/src/styles/app.css").read_text(encoding="utf-8")
    assert "connected.has(node.id)" in component
    assert "product.graph.disconnected" in component
    assert 'content: "→"' not in css and 'content: "↓"' not in css


def test_adapter_validates_product_context_edges_and_freezes_fixture() -> None:
    adapter = source("adapter.ts")
    for contract in (
        "PRODUCT_PROJECTION_CONTEXT_REQUIRED",
        "INVALID_CANONICAL_PRODUCT_EDGE",
        "INVALID_RAW_RELATION_EVIDENCE",
        "FIXTURE_6_PRESENTATION_ORDER_REQUIRED",
        "deepFreeze(productFixture)",
    ):
        assert contract in adapter


def test_exact_approval_replay_fails_closed() -> None:
    result = run_journey(
        "const approved=journeyReducer(initialJourney,{type:'APPROVE'});"
        "const replay=applyApprovalDecision(approved,'APPROVED',"
        "approved.decidedAt,approved.approvedFingerprint);"
        "console.log(JSON.stringify({same:replay===approved,error:replay.approvalError}));"
    )
    assert result == {"same": True, "error": None}


def test_changed_approval_decision_fails_closed() -> None:
    result = run_journey(
        "const approved=journeyReducer(initialJourney,{type:'APPROVE'});"
        "const replay=applyApprovalDecision(approved,'REJECTED',"
        "approved.decidedAt,approved.approvedFingerprint);"
        "console.log(JSON.stringify({error:replay.approvalError,execution:replay.execution}));"
    )
    assert result == {
        "error": "APPROVAL_REPLAY_MISMATCH",
        "execution": "NOT_STARTED",
    }


def test_changed_decided_at_fails_closed() -> None:
    result = run_journey(
        "const approved=journeyReducer(initialJourney,{type:'APPROVE'});"
        "const replay=applyApprovalDecision(approved,'APPROVED',"
        "'2026-08-27T08:00:01Z',approved.approvedFingerprint);"
        "console.log(JSON.stringify({error:replay.approvalError,execution:replay.execution}));"
    )
    assert result == {
        "error": "APPROVAL_REPLAY_MISMATCH",
        "execution": "NOT_STARTED",
    }


def test_malformed_approval_fails_closed() -> None:
    result = run_journey(
        "const replay=applyApprovalDecision(initialJourney,null,null,null);"
        "console.log(JSON.stringify({error:replay.approvalError,execution:replay.execution}));"
    )
    assert result == {
        "error": "MALFORMED_APPROVAL_DECISION",
        "execution": "NOT_STARTED",
    }


def test_duplicate_execution_interaction_is_idempotent() -> None:
    result = run_journey(
        "const approved=journeyReducer(initialJourney,{type:'APPROVE'});"
        "const running=journeyReducer(approved,{type:'RUN'});"
        "const duplicate=journeyReducer(running,{type:'RUN'});"
        "console.log(JSON.stringify({same:duplicate===running,count:duplicate.executionPresentationCount,execution:duplicate.execution}));"
    )
    assert result == {"same": True, "count": 1, "execution": "RUNNING"}


def test_corrected_revision_uses_successor_fingerprint() -> None:
    result = run_journey(
        "const corrected=journeyReducer(initialJourney,"
        "{type:'CORRECT',text:'bounded correction'});"
        "const approved=journeyReducer(corrected,{type:'APPROVE'});"
        "const running=journeyReducer(approved,{type:'RUN'});"
        "console.log(JSON.stringify({revision:running.revision,fingerprint:running.approvedFingerprint,execution:running.execution}));"
    )
    assert result == {
        "revision": "plan-revision.synthetic.qi-1042.r2",
        "fingerprint": "sha256:synthetic-plan-r2",
        "execution": "RUNNING",
    }


def test_rejected_revision_cannot_run() -> None:
    result = run_journey(
        "const rejected=journeyReducer(initialJourney,{type:'REJECT'});"
        "const attempted=journeyReducer(rejected,{type:'RUN'});"
        "console.log(JSON.stringify({same:attempted===rejected,approval:attempted.approval,execution:attempted.execution,fingerprint:attempted.approvedFingerprint}));"
    )
    assert result == {
        "same": True,
        "approval": "REJECTED",
        "execution": "NOT_STARTED",
        "fingerprint": "sha256:synthetic-plan-r1",
    }


def test_correction_creates_successor_revision() -> None:
    text = source("journey.ts")
    assert 'revision: "plan-revision.synthetic.qi-1042.r2"' in text
    assert 'diffClassification: "MATERIAL"' in text


def test_deny_requires_zero_provider_effects() -> None:
    assert "DENY_REQUIRES_ZERO_PROVIDER_EFFECTS" in source("adapter.ts")
    outcome = source("OutcomeEvidence.tsx")
    assert "const calls = denied ? 0" in outcome


@pytest.mark.parametrize("state", ["UNKNOWN", "FAILED", "SKIPPED"])
def test_unknown_and_terminal_failure_states_are_explicit(state: str) -> None:
    assert state in source("types.ts") + source("fixture.ts") + source("journey.ts")


def test_runtime_honesty_states_are_exact() -> None:
    text = source("RuntimeSupport.tsx")
    for value in (
        "AVAILABLE",
        "COMPONENT_TESTED_CANDIDATE",
        "NOT_CERTIFIED",
        "CURRENTLY_UNAVAILABLE",
        "NOT_CURRENTLY_CERTIFIABLE",
        "SUPPORT_NOT_GRANTED",
    ):
        assert value in text


def test_product_view_does_not_implement_technical_view() -> None:
    app = (ROOT / "console/frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "TechnicalView" not in app and 'path="/technical"' not in app


def test_catalogs_have_identical_product_keys() -> None:
    text = (ROOT / "console/frontend/src/i18n/messages.ts").read_text(encoding="utf-8")
    en, zh = text.split('"zh-CN":', 1)
    pattern = re.compile(r'"(product\.[^"]+)"\s*:')
    assert set(pattern.findall(en)) == set(pattern.findall(zh))
    assert len(set(pattern.findall(en))) >= 70


def test_locale_switch_lives_outside_journey_state() -> None:
    page = (ROOT / "console/frontend/src/pages/ProductViewPage.tsx").read_text(
        encoding="utf-8"
    )
    provider = (ROOT / "console/frontend/src/i18n/I18nProvider.tsx").read_text(
        encoding="utf-8"
    )
    assert "useReducer(journeyReducer" in page and "useState<Locale>" in provider
    assert "locale" not in source("journey.ts")


def test_product_dates_counts_ordinals_and_percentages_are_locale_aware() -> None:
    product = (
        source("DraftDiffApproval.tsx")
        + source("DigitalEmployeeDirectory.tsx")
        + source("BusinessJourney.tsx")
    )
    assert "Intl.DateTimeFormat(locale" in product
    assert 'timeZone: "UTC"' in product
    assert product.count("Intl.NumberFormat(locale") >= 3


def test_accessibility_and_responsive_contracts() -> None:
    product_sources = "".join(
        path.read_text(encoding="utf-8") for path in PRODUCT.glob("*.tsx")
    )
    css = (ROOT / "console/frontend/src/styles/app.css").read_text(encoding="utf-8")
    for contract in (
        "aria-label",
        "aria-labelledby",
        "aria-current",
        "aria-expanded",
        "aria-pressed",
    ):
        assert contract in product_sources
    assert (
        "@media (max-width: 700px)" in css
        and "min-width: 0" in css
        and ":focus-visible" in css
    )


def test_empty_loading_error_denied_labels_are_present() -> None:
    messages = (ROOT / "console/frontend/src/i18n/messages.ts").read_text(
        encoding="utf-8"
    )
    app = (ROOT / "console/frontend/src/App.tsx").read_text(encoding="utf-8")
    product = source("BusinessJourney.tsx") + source("OutcomeEvidence.tsx")
    assert all(
        value in messages + app + product
        for value in ("EMPTY", "LOADING", "ERROR", "product.state.denied")
    )


def test_no_network_credentials_or_host_paths_in_product_sources() -> None:
    text = "".join(path.read_text(encoding="utf-8") for path in PRODUCT.iterdir())
    assert not re.search(
        r"fetch\(|https?://|/Users/|authorization:|api[_-]?key|password",
        text,
        re.IGNORECASE,
    )
