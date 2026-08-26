from pathlib import Path

from conformance_harness.adapters import ADAPTERS
from conformance_harness.manifest import load_manifest
from conformance_harness.models import Disposition, EvidenceClassification
from conformance_harness.runner import HarnessRunner

FIXTURES = Path(__file__).parents[2] / "conformance_harness" / "fixtures"


def test_component_adapters_produce_stable_bounded_mvs_results() -> None:
    manifest = load_manifest(FIXTURES / "criteria.json")
    runner = HarnessRunner(ADAPTERS)
    first = runner.run(manifest, profile="mvs-native")
    second = runner.run(manifest, profile="mvs-native")
    assert first == second
    assert first.summary.total == 6
    assert first.summary.passed == 5
    assert first.summary.failed == 0
    assert first.summary.unrun == 0
    assert first.summary.not_applicable == 1
    assert [result.disposition for result in first.results].count(Disposition.PASS) == 5
    workflow = next(
        result
        for result in first.results
        if result.criterion_id == "E-WORKFLOW-OPTIONAL-001"
    )
    assert workflow.disposition is Disposition.NOT_APPLICABLE
    assert workflow.evidence_classification is EvidenceClassification.NOT_YET_PROVEN
    assert workflow.evidence is None


def test_every_pass_names_exact_target_profile_and_version() -> None:
    report = HarnessRunner(ADAPTERS).run(
        load_manifest(FIXTURES / "criteria.json"), profile="mvs-native"
    )
    for result in report.results:
        if result.disposition is Disposition.PASS:
            assert result.target
            assert result.profile
            assert result.version
