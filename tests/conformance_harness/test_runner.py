from dataclasses import replace

from conformance_harness.manifest import parse_manifest
from conformance_harness.models import (
    Disposition,
    Evidence,
    EvidenceClassification,
    ReasonCode,
)
from conformance_harness.runner import MAX_DIAGNOSTIC_LENGTH, HarnessRunner


def manifest(*, profiles=("mvs-native",), adapter="check"):
    return parse_manifest(
        {
            "schema_version": "s5-test-005/v1",
            "criteria": [
                {
                    "id": "TEST-001",
                    "type": "component",
                    "target": "Exact Component",
                    "profile": "exact-profile",
                    "version": "v1",
                    "adapter": adapter,
                    "applicable_profiles": list(profiles),
                }
            ],
        }
    )


def test_pass_requires_completed_supporting_evidence() -> None:
    report = HarnessRunner(
        {"check": lambda _: Evidence(EvidenceClassification.TESTED, True)}
    ).run(manifest(), profile="mvs-native")
    assert report.results[0].disposition is Disposition.PASS
    assert report.results[0].evidence is not None
    assert report.results[0].evidence.completed is True


def test_incomplete_evidence_is_unrun_and_never_pass() -> None:
    report = HarnessRunner(
        {"check": lambda _: Evidence(EvidenceClassification.NOT_YET_PROVEN, False)}
    ).run(manifest(), profile="mvs-native")
    assert report.results[0].disposition is Disposition.UNRUN
    assert report.results[0].reason_code is ReasonCode.EVIDENCE_INCOMPLETE
    assert report.summary.passed == 0


def test_missing_adapter_is_explicit_unrun() -> None:
    report = HarnessRunner({}).run(manifest(adapter="missing"), profile="mvs-native")
    assert report.results[0].disposition is Disposition.UNRUN
    assert report.results[0].reason_code is ReasonCode.ADAPTER_NOT_REGISTERED


def test_applicability_is_explicit_and_not_counted_as_pass() -> None:
    report = HarnessRunner({}).run(manifest(profiles=("other",)), profile="mvs-native")
    assert report.results[0].disposition is Disposition.NOT_APPLICABLE
    assert report.summary.not_applicable == 1
    assert report.summary.passed == 0


def test_assertion_failure_preserves_bounded_reason_evidence() -> None:
    def fail(_):
        raise AssertionError("x" * 500)

    result = (
        HarnessRunner({"check": fail}).run(manifest(), profile="mvs-native").results[0]
    )
    assert result.disposition is Disposition.FAIL
    assert result.reason_code is ReasonCode.ASSERTION_FAILED
    assert len(result.diagnostic) == MAX_DIAGNOSTIC_LENGTH


def test_credential_like_diagnostics_are_redacted() -> None:
    def fail(_):
        raise RuntimeError("password field present")

    result = (
        HarnessRunner({"check": fail}).run(manifest(), profile="mvs-native").results[0]
    )
    assert result.diagnostic == "[REDACTED_SENSITIVE_DIAGNOSTIC]"


def test_summary_arithmetic_reconciles_and_runs_are_stable() -> None:
    source = manifest()
    second = replace(
        source, criteria=(replace(source.criteria[0], criterion_id="TEST-002"),)
    )
    combined = replace(source, criteria=source.criteria + second.criteria)
    runner = HarnessRunner(
        {"check": lambda _: Evidence(EvidenceClassification.TESTED, True)}
    )
    first = runner.run(combined, profile="mvs-native")
    replay = runner.run(combined, profile="mvs-native")
    assert first == replay
    assert first.summary.total == sum(
        (
            first.summary.passed,
            first.summary.failed,
            first.summary.unrun,
            first.summary.not_applicable,
        )
    )
