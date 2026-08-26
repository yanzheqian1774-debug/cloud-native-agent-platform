from dataclasses import replace

import pytest
from conformance_harness.manifest import parse_manifest
from conformance_harness.models import (
    CriterionResult,
    Disposition,
    Evidence,
    EvidenceClassification,
    HarnessReport,
    HarnessSummary,
    ReasonCode,
)
from conformance_harness.runner import (
    MAX_DIAGNOSTIC_LENGTH,
    HarnessRunner,
    normalize_report,
)


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
                    "evidence_classification": "TESTED",
                }
            ],
        }
    )


def test_pass_requires_completed_supporting_evidence() -> None:
    report = HarnessRunner(
        {
            "check": lambda criterion: Evidence(
                criterion.criterion_id,
                EvidenceClassification.TESTED,
                True,
                "unit-test:current-head",
            )
        }
    ).run(manifest(), profile="mvs-native")
    assert report.results[0].disposition is Disposition.PASS
    assert report.results[0].evidence is not None
    assert report.results[0].evidence.completed is True


def test_incomplete_evidence_is_unrun_and_never_pass() -> None:
    report = HarnessRunner(
        {
            "check": lambda criterion: Evidence(
                criterion.criterion_id,
                EvidenceClassification.TESTED,
                False,
                "unit-test:current-head",
            )
        }
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
        {
            "check": lambda criterion: Evidence(
                criterion.criterion_id,
                EvidenceClassification.TESTED,
                True,
                "unit-test:current-head",
            )
        }
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
    assert normalize_report(first) == normalize_report(replay)


def test_result_rejects_contradictory_disposition_and_evidence() -> None:
    evidence = Evidence(
        "TEST-001",
        EvidenceClassification.TESTED,
        True,
        "unit-test:current-head",
    )
    with pytest.raises(ValueError, match="non-PASS"):
        CriterionResult(
            criterion_id="TEST-001",
            target="target",
            profile="profile",
            version="v1",
            disposition=Disposition.UNRUN,
            evidence_classification=EvidenceClassification.TESTED,
            reason_code=ReasonCode.EVIDENCE_INCOMPLETE,
            diagnostic="incomplete",
            evidence=evidence,
        )
    with pytest.raises(ValueError, match="completed supporting evidence"):
        CriterionResult(
            criterion_id="TEST-001",
            target="target",
            profile="profile",
            version="v1",
            disposition=Disposition.PASS,
            evidence_classification=EvidenceClassification.TESTED,
            reason_code=ReasonCode.CRITERION_PASSED,
            diagnostic="pass",
            evidence=None,
        )


def test_upstream_declaration_cannot_be_promoted_to_pass() -> None:
    source = manifest()
    criterion = replace(
        source.criteria[0],
        evidence_classification=EvidenceClassification.DECLARED_BY_UPSTREAM,
    )
    source = replace(source, criteria=(criterion,))
    report = HarnessRunner(
        {
            "check": lambda selected: Evidence(
                selected.criterion_id,
                EvidenceClassification.DECLARED_BY_UPSTREAM,
                True,
                "upstream:declaration-only",
            )
        }
    ).run(source, profile="mvs-native")
    assert report.results[0].disposition is Disposition.FAIL
    assert report.summary.passed == 0


def test_stale_or_ambiguous_evidence_identity_fails_closed() -> None:
    report = HarnessRunner(
        {
            "check": lambda _: Evidence(
                "OTHER-CRITERION",
                EvidenceClassification.TESTED,
                True,
                "ambiguous:unknown-head",
            )
        }
    ).run(manifest(), profile="mvs-native")
    assert report.results[0].disposition is Disposition.FAIL
    assert report.results[0].reason_code is ReasonCode.ADAPTER_ERROR


def test_hostile_exception_serialization_and_host_paths_are_redacted() -> None:
    class HostileValue:
        def __str__(self):
            raise AssertionError("must not stringify hostile object")

    def unserializable(_):
        raise RuntimeError(HostileValue())

    opaque = (
        HarnessRunner({"check": unserializable})
        .run(manifest(), profile="mvs-native")
        .results[0]
    )
    assert opaque.diagnostic == "RuntimeError: [UNSERIALIZABLE_DIAGNOSTIC]"

    def host_path(_):
        raise RuntimeError("failed at /Users/person/private/location.json")

    path_result = (
        HarnessRunner({"check": host_path})
        .run(manifest(), profile="mvs-native")
        .results[0]
    )
    assert "/Users/" not in path_result.diagnostic
    assert "[REDACTED_HOST_PATH]" in path_result.diagnostic


def test_failure_is_isolated_and_does_not_modify_later_result() -> None:
    source = manifest()
    second = replace(source.criteria[0], criterion_id="TEST-002", adapter="succeed")
    combined = replace(source, criteria=(source.criteria[0], second))

    def fail(_):
        raise AssertionError("bounded failure")

    def succeed(criterion):
        return Evidence(
            criterion.criterion_id,
            EvidenceClassification.TESTED,
            True,
            "unit-test:current-head",
        )

    report = HarnessRunner({"check": fail, "succeed": succeed}).run(
        combined, profile="mvs-native"
    )
    assert [result.disposition for result in report.results] == [
        Disposition.FAIL,
        Disposition.PASS,
    ]
    assert report.summary == HarnessSummary(2, 1, 1, 0, 0)


def test_report_rejects_summary_or_duplicate_result_contradictions() -> None:
    report = HarnessRunner(
        {
            "check": lambda criterion: Evidence(
                criterion.criterion_id,
                EvidenceClassification.TESTED,
                True,
                "unit-test:current-head",
            )
        }
    ).run(manifest(), profile="mvs-native")
    with pytest.raises(ValueError, match="summary contradicts"):
        HarnessReport("mvs-native", report.results, HarnessSummary(1, 0, 1, 0, 0))
    with pytest.raises(ValueError, match="duplicate criterion"):
        HarnessReport(
            "mvs-native",
            report.results * 2,
            HarnessSummary.from_results(report.results * 2),
        )


def test_evidence_is_deeply_copied_and_immutable() -> None:
    observations = {"nested": {"items": ["original"]}}
    evidence = Evidence(
        "TEST-001",
        EvidenceClassification.TESTED,
        True,
        "unit-test:current-head",
        observations,
    )
    observations["nested"]["items"][0] = "changed"
    assert evidence.observations["nested"]["items"] == ("original",)
    with pytest.raises(TypeError):
        evidence.observations["new"] = "value"  # type: ignore[index]


@pytest.mark.parametrize("unsupported", [object(), {1: "non-string-key"}, float("nan")])
def test_unsupported_evidence_observations_fail_closed(unsupported) -> None:
    with pytest.raises((TypeError, ValueError)):
        Evidence(
            "TEST-001",
            EvidenceClassification.TESTED,
            True,
            "unit-test:current-head",
            {"value": unsupported},
        )


def test_runner_instances_copy_adapter_registries_and_do_not_share_state() -> None:
    def passed(criterion):
        return Evidence(
            criterion.criterion_id,
            EvidenceClassification.TESTED,
            True,
            "unit-test:current-head",
        )

    registry = {"check": passed}
    first = HarnessRunner(registry)
    registry.clear()
    second = HarnessRunner(registry)
    assert first.run(manifest(), profile="mvs-native").summary.passed == 1
    assert second.run(manifest(), profile="mvs-native").summary.unrun == 1
