"""S5-IMPL-011 shared-snapshot and Technical View acceptance tests."""
# ruff: noqa: E501

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1]
SRC = FRONTEND / "src"
SHARED = SRC / "shared"
TECHNICAL = SRC / "technical"


def text(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def run_shared(script: str) -> dict[str, object]:
    fixture = (SHARED / "executionSnapshotFixture.ts").as_uri()
    projections = (SHARED / "projections.ts").as_uri()
    completed = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            (
                f'import {{ sharedExecutionSnapshot }} from "{fixture}";'
                f'import {{ projectProductSnapshot, projectTechnicalSnapshot }} from "{projections}";'
                f"{script}"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(completed.stdout)


def run_module(module: Path, imports: str, script: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "--eval",
            f'import {{ {imports} }} from "{module.as_uri()}";{script}',
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(completed.stdout)


def test_shared_snapshot_has_all_six_exact_classifications() -> None:
    source = text("src/shared/executionSnapshotFixture.ts") + text(
        "src/shared/executionSnapshotTypes.ts"
    )
    for value in (
        "DETERMINISTIC",
        "SYNTHETIC",
        "NON_AUTHORITATIVE",
        "TECHNICAL_PREVIEW",
        "NO_NETWORK",
        "NO_RUNTIME_OR_PROVIDER_INVOCATION",
    ):
        assert value in source


def test_product_and_technical_are_sibling_projections() -> None:
    source = text("src/shared/projections.ts")
    assert "projectProductSnapshot(source: SharedExecutionSnapshot)" in source
    assert "projectTechnicalSnapshot(source: SharedExecutionSnapshot)" in source
    assert "projectTechnicalSnapshot(product" not in source


def test_cross_view_execution_and_snapshot_identity_are_equal() -> None:
    result = run_shared(
        "const p=projectProductSnapshot(sharedExecutionSnapshot);"
        "const t=projectTechnicalSnapshot(sharedExecutionSnapshot);"
        "console.log(JSON.stringify({execution:p.platformExecutionIdentity===t.selectedContext.executionId,snapshot:p.graphSnapshotId===t.selectedContext.graphSnapshotId}));"
    )
    assert result == {"execution": True, "snapshot": True}


def test_stable_revision_work_task_outcome_and_evidence_ids() -> None:
    result = run_shared(
        "const t=projectTechnicalSnapshot(sharedExecutionSnapshot);"
        "console.log(JSON.stringify({revision:t.selectedContext.revisionId,work:t.selectedContext.workId,task:t.selectedContext.taskId,outcome:t.outcome.id,evidence:t.outcome.evidenceIds[1]}));"
    )
    assert result == {
        "revision": "plan-revision.synthetic.qi-1042.r1",
        "work": "work.synthetic.qi-1042",
        "task": "task.synthetic.analyze",
        "outcome": "outcome.synthetic.qi-1042",
        "evidence": "evidence.synthetic.quality.002",
    }


def test_projections_do_not_mutate_frozen_shared_snapshot() -> None:
    result = run_shared(
        "const before=JSON.stringify(sharedExecutionSnapshot);"
        "const p=projectProductSnapshot(sharedExecutionSnapshot);const t=projectTechnicalSnapshot(sharedExecutionSnapshot);"
        "p.nodes.pop();t.nodes.pop();"
        "console.log(JSON.stringify({same:before===JSON.stringify(sharedExecutionSnapshot),frozen:Object.isFrozen(sharedExecutionSnapshot)}));"
    )
    assert result == {"same": True, "frozen": True}


def test_product_filtering_retains_technical_only_shared_nodes() -> None:
    result = run_shared(
        "const p=projectProductSnapshot(sharedExecutionSnapshot);const t=projectTechnicalSnapshot(sharedExecutionSnapshot);"
        "console.log(JSON.stringify({product:p.nodes.some(n=>n.type==='RUNTIME_REALIZATION'),technical:t.nodes.some(n=>n.type==='RUNTIME_REALIZATION'),shared:sharedExecutionSnapshot.nodes.some(n=>n.type==='RUNTIME_REALIZATION')}));"
    )
    assert result == {"product": False, "technical": True, "shared": True}


def test_technical_projection_rejects_product_projection_input() -> None:
    result = run_shared(
        "const p=projectProductSnapshot(sharedExecutionSnapshot);let code=null;try{projectTechnicalSnapshot(p)}catch(error){code=error.message}console.log(JSON.stringify({code}));"
    )
    assert result == {"code": "SHARED_SNAPSHOT_REQUIRED"}


def test_raw_relation_fields_are_preserved_exactly() -> None:
    result = run_shared(
        "const t=projectTechnicalSnapshot(sharedExecutionSnapshot);const r=t.edges.find(e=>e.id==='aggregate.fixture-6').rawRelations;"
        "console.log(JSON.stringify({ids:r.map(x=>x.id),types:r.map(x=>x.type),directions:[...new Set(r.map(x=>x.direction))],cardinalities:r.map(x=>x.cardinality),evidence:r.map(x=>x.evidenceIds[0]),sources:[...new Set(r.map(x=>x.source))],targets:[...new Set(r.map(x=>x.target))]}));"
    )
    assert result["ids"] == [
        "gpr.fixture6.depends",
        "gpr.fixture6.triggers",
        "gpr.fixture6.flow",
    ]
    assert result["types"] == ["DEPENDS_ON", "TRIGGERS", "DATA_FLOW"]
    assert result["directions"] == ["SOURCE_TO_TARGET"]
    assert result["cardinalities"] == ["MANY_TO_ONE", "ONE_TO_MANY", "MANY_TO_MANY"]
    assert len(result["evidence"]) == 3
    assert result["sources"] == ["task.synthetic.analyze"]
    assert result["targets"] == ["task.synthetic.collect"]


def test_components_do_not_infer_relations_or_cardinality() -> None:
    source = "".join(
        path.read_text(encoding="utf-8") for path in TECHNICAL.glob("*.tsx")
    )
    assert "rawRelations.map" in source
    assert not re.search(r"infer|synthesi[sz]e|reverse\(", source, re.IGNORECASE)
    assert "cardinality =" not in source


def test_deny_contract_requires_zero_calls_and_citations() -> None:
    source = text("src/shared/projections.ts") + text("src/technical/adapter.ts")
    assert source.count("DENY_REQUIRES_ZERO_PROVIDER_EFFECTS") >= 2
    result = run_shared(
        "const denied=structuredClone(sharedExecutionSnapshot);denied.authorization.decision='DENY';denied.authorization.providerCallCount=1;denied.citations=[];let code=null;try{projectTechnicalSnapshot(denied)}catch(error){code=error.message}console.log(JSON.stringify({code}));"
    )
    assert result == {"code": "DENY_REQUIRES_ZERO_PROVIDER_EFFECTS"}


def test_unknown_failure_unavailable_and_downstream_are_not_success() -> None:
    source = text("src/shared/executionSnapshotFixture.ts") + text(
        "src/shared/executionSnapshotTypes.ts"
    )
    for state in (
        "UNKNOWN",
        "FAILED",
        "SKIPPED",
        "BLOCKED",
        "UNAVAILABLE",
        "DOWNSTREAM",
    ):
        assert state in source
    assert 'state: "DOWNSTREAM"' in source and "NO_EXACTLY_ONCE_CLAIM" in source


def test_runtime_support_claims_are_exact() -> None:
    source = text("src/shared/executionSnapshotFixture.ts")
    for value in (
        "AVAILABLE",
        "COMPONENT_TESTED_CANDIDATE",
        "NOT_CERTIFIED",
        "EXPERIMENTAL",
        "CURRENTLY_UNAVAILABLE",
        "SUPPORT_NOT_GRANTED",
        "NOT_CURRENTLY_CERTIFIABLE",
    ):
        assert value in source


def test_url_context_allows_only_known_stable_identifiers() -> None:
    source = text("src/shared/urlContext.ts")
    for key in (
        "employeeId",
        "revisionId",
        "workId",
        "workflowId",
        "taskId",
        "executionId",
        "graphSnapshotId",
    ):
        assert key in source
    assert "defaultSelectedExecutionContext" in source
    assert "URLSearchParams" in source


def test_url_context_rejects_partial_duplicate_unknown_and_contradictory_input() -> (
    None
):
    result = run_module(
        SHARED / "urlContext.ts",
        "parseSelectedContext",
        "const snapshot=(await import('"
        + (SHARED / "executionSnapshotFixture.ts").as_uri()
        + "')).sharedExecutionSnapshot;"
        "const base=snapshot.selectedContext;"
        "const full=new URLSearchParams(base);"
        "const duplicate=new URLSearchParams(full);duplicate.append('employeeId',snapshot.employees[1].id);"
        "const contradictory=new URLSearchParams(full);contradictory.set('executionId','pei-unknown');"
        "console.log(JSON.stringify({"
        "partial:parseSelectedContext('?employeeId='+snapshot.employees[1].id,snapshot),"
        "duplicate:parseSelectedContext('?'+duplicate,snapshot),"
        "unknown:parseSelectedContext('?'+full+'&extra=value',snapshot),"
        "contradictory:parseSelectedContext('?'+contradictory,snapshot),"
        "base}));",
    )
    assert result["partial"] == result["base"]
    assert result["duplicate"] == result["base"]
    assert result["unknown"] == result["base"]
    assert result["contradictory"] == result["base"]


def test_history_navigation_cannot_be_overridden_by_stale_local_selection() -> None:
    source = text("src/shared/SelectedExecutionContext.tsx")
    assert "localSelection?.search === location.search" in source
    assert "search: location.search" in source


def test_technical_view_consumes_and_validates_selected_context() -> None:
    page = text("src/pages/TechnicalViewPage.tsx")
    assert "loadTechnicalPreview(selection)" in page
    assert "useSelectedExecution()" in page
    result = run_module(
        TECHNICAL / "adapter.ts",
        "loadTechnicalPreview",
        "const base=loadTechnicalPreview();"
        "const selected={...base.selectedContext,employeeId:'de.synthetic.quality-analysis.v1'};"
        "const accepted=loadTechnicalPreview(selected);"
        "let rejected=null;try{loadTechnicalPreview({...selected,executionId:'pei-unknown'})}catch(error){rejected=error.message}"
        "console.log(JSON.stringify({employeeId:accepted.selectedContext.employeeId,rejected}));",
    )
    assert result == {
        "employeeId": "de.synthetic.quality-analysis.v1",
        "rejected": "CROSS_VIEW_IDENTITY_MISMATCH",
    }


def test_product_technical_navigation_and_route_exist() -> None:
    app = text("src/App.tsx")
    switcher = text("src/shared/ViewSwitcher.tsx")
    assert 'technicalPath = "/technical"' in app and "<TechPage" in app
    assert "/product?${query}" in switcher and "/technical?${query}" in switcher
    assert "serializeSelectedContext(selection)" in switcher


def test_locale_catalogs_have_identical_technical_keys() -> None:
    source = text("src/i18n/messages.ts")
    en, zh = source.split('"zh-CN":', 1)
    pattern = re.compile(r'"((?:technical|nav\.technicalView|nav\.views)[^" ]*)"\s*:')
    assert set(pattern.findall(en)) == set(pattern.findall(zh))
    assert len(set(pattern.findall(en))) >= 45


def test_locale_state_is_separate_from_selected_context() -> None:
    selected = text("src/shared/SelectedExecutionContext.tsx")
    i18n = text("src/i18n/I18nProvider.tsx")
    assert "locale" not in selected and "useState<Locale>" in i18n


def test_accessibility_contracts_are_present() -> None:
    source = "".join(
        path.read_text(encoding="utf-8") for path in TECHNICAL.glob("*.tsx")
    )
    page = text("src/pages/TechnicalViewPage.tsx")
    assert all(
        value in source + page
        for value in (
            "<main",
            "<section",
            "aria-label",
            "aria-labelledby",
            "aria-expanded",
            "aria-current",
            'role="status"',
        )
    )


def test_responsive_reduced_motion_and_focus_styles() -> None:
    css = text("src/styles/app.css")
    assert "@media (max-width: 700px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css and "min-width: 0" in css
    assert ".technical-page" in css and ".technical-node-grid" in css


def test_no_network_storage_secret_or_persistence_side_effects() -> None:
    paths = (
        list(SHARED.glob("*"))
        + list(TECHNICAL.glob("*"))
        + [SRC / "pages" / "TechnicalViewPage.tsx"]
    )
    source = "".join(
        path.read_text(encoding="utf-8") for path in paths if path.is_file()
    )
    assert not re.search(
        r"fetch\(|XMLHttpRequest|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie|https?://|/Users/|bearer |api[_-]?key|password",
        source,
        re.IGNORECASE,
    )


def test_product_wrappers_use_shared_projection_without_copying_fixture() -> None:
    fixture = text("src/product/fixture.ts")
    assert "projectProductSnapshot(sharedExecutionSnapshot)" in fixture
    assert "export const productFixture" in fixture
    assert "employees: [" not in fixture


def test_product_presentation_components_remain_unmodified_by_import_direction() -> (
    None
):
    for name in (
        "BusinessJourney",
        "DigitalEmployeeDirectory",
        "DraftDiffApproval",
        "ProductGraph",
        "OutcomeEvidence",
        "RuntimeSupport",
    ):
        source = text(f"src/product/{name}.tsx")
        assert "../technical" not in source and "projectTechnicalSnapshot" not in source


def test_provider_identifiers_are_correlation_only() -> None:
    fixture = text("src/shared/executionSnapshotFixture.ts")
    panel = text("src/technical/RuntimeProviderPanel.tsx")
    assert "provider-correlation.synthetic.native.001" in fixture
    assert "technical.runtime.correlationOnly" in panel


def test_technical_adapter_freezes_and_validates_projection() -> None:
    source = text("src/technical/adapter.ts")
    for contract in (
        "deepFreeze(view)",
        "CROSS_VIEW_IDENTITY_MISMATCH",
        "TECHNICAL_RELATION_RECONSTRUCTION_REJECTED",
    ):
        assert contract in source


def test_root_shim_is_the_only_standard_discovery_entry() -> None:
    root = FRONTEND.parents[1]
    shim = root / "tests" / "test_s5_impl_011_technical_view.py"
    assert shim.is_file()
    assert FRONTEND not in [
        root / value for value in ("core/tests", "tests", "gateway/tests")
    ]
