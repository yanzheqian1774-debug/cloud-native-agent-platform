"""Deterministic Harness execution and normalized result arithmetic."""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .manifest import select_criteria
from .models import (
    Criterion,
    CriterionManifest,
    CriterionResult,
    Disposition,
    Evidence,
    EvidenceClassification,
    HarnessReport,
    HarnessSummary,
    ReasonCode,
)

Adapter = Callable[[Criterion], Evidence]
MAX_DIAGNOSTIC_LENGTH = 240
SENSITIVE_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
    "private key",
)
HOST_PATH = re.compile(r"(?:/Users|/home|/private|[A-Za-z]:\\)[^\s:]+")


def _diagnostic(value: str) -> str:
    text = " ".join(value.split())
    lowered = text.lower()
    if any(marker in lowered for marker in SENSITIVE_MARKERS):
        return "[REDACTED_SENSITIVE_DIAGNOSTIC]"
    return HOST_PATH.sub("[REDACTED_HOST_PATH]", text)[:MAX_DIAGNOSTIC_LENGTH]


def _exception_diagnostic(exc: Exception, fallback: str) -> str:
    if not exc.args:
        return _diagnostic(fallback)
    if not all(isinstance(arg, str) for arg in exc.args):
        return _diagnostic(f"{type(exc).__name__}: [UNSERIALIZABLE_DIAGNOSTIC]")
    return _diagnostic(f"{type(exc).__name__}: {'; '.join(exc.args)}")


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def normalize_report(report: HarnessReport) -> bytes:
    """Return stable UTF-8 JSON bytes for deterministic replay comparison."""
    document = {
        "profile": report.profile,
        "results": [
            {
                "criterion_id": result.criterion_id,
                "target": result.target,
                "profile": result.profile,
                "version": result.version,
                "disposition": result.disposition.value,
                "evidence_classification": result.evidence_classification.value,
                "reason_code": result.reason_code.value,
                "diagnostic": result.diagnostic,
                "evidence": (
                    None
                    if result.evidence is None
                    else {
                        "criterion_id": result.evidence.criterion_id,
                        "classification": result.evidence.classification.value,
                        "completed": result.evidence.completed,
                        "execution_provenance": result.evidence.execution_provenance,
                        "observations": _json_value(result.evidence.observations),
                    }
                ),
            }
            for result in report.results
        ],
        "summary": {
            "total": report.summary.total,
            "passed": report.summary.passed,
            "failed": report.summary.failed,
            "unrun": report.summary.unrun,
            "not_applicable": report.summary.not_applicable,
        },
    }
    return json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()


class HarnessRunner:
    def __init__(self, adapters: Mapping[str, Adapter]) -> None:
        self._adapters = dict(adapters)

    def run(
        self,
        manifest: CriterionManifest,
        *,
        profile: str,
        selected_ids: Sequence[str] | None = None,
    ) -> HarnessReport:
        results = tuple(
            self._run_criterion(criterion, profile)
            for criterion in select_criteria(manifest, selected_ids)
        )
        return HarnessReport(profile, results, HarnessSummary.from_results(results))

    def _run_criterion(self, criterion: Criterion, profile: str) -> CriterionResult:
        base: dict[str, Any] = {
            "criterion_id": criterion.criterion_id,
            "target": criterion.target,
            "profile": criterion.profile,
            "version": criterion.version,
            "evidence_classification": criterion.evidence_classification,
        }
        if profile not in criterion.applicable_profiles:
            return CriterionResult(
                **base,
                disposition=Disposition.NOT_APPLICABLE,
                reason_code=ReasonCode.PROFILE_NOT_APPLICABLE,
                diagnostic="criterion does not apply to the selected Harness profile",
                evidence=None,
            )
        adapter = self._adapters.get(criterion.adapter)
        if adapter is None:
            return CriterionResult(
                **base,
                disposition=Disposition.UNRUN,
                reason_code=ReasonCode.ADAPTER_NOT_REGISTERED,
                diagnostic="no adapter is registered for this criterion",
                evidence=None,
            )
        try:
            evidence = adapter(criterion)
            if not isinstance(evidence, Evidence):
                raise TypeError("adapter did not return Evidence")
        except AssertionError as exc:
            return CriterionResult(
                **base,
                disposition=Disposition.FAIL,
                reason_code=ReasonCode.ASSERTION_FAILED,
                diagnostic=_exception_diagnostic(exc, "component assertion failed"),
                evidence=None,
            )
        except Exception as exc:  # normalized diagnostic boundary
            return CriterionResult(
                **base,
                disposition=Disposition.FAIL,
                reason_code=ReasonCode.ADAPTER_ERROR,
                diagnostic=_exception_diagnostic(exc, "adapter failed"),
                evidence=None,
            )
        if evidence.criterion_id != criterion.criterion_id:
            return CriterionResult(
                **base,
                disposition=Disposition.FAIL,
                reason_code=ReasonCode.ADAPTER_ERROR,
                diagnostic="adapter evidence identifies a different criterion",
                evidence=None,
            )
        if evidence.classification is not criterion.evidence_classification:
            return CriterionResult(
                **base,
                disposition=Disposition.FAIL,
                reason_code=ReasonCode.ADAPTER_ERROR,
                diagnostic="adapter evidence classification contradicts the manifest",
                evidence=None,
            )
        if not evidence.completed:
            return CriterionResult(
                **base,
                disposition=Disposition.UNRUN,
                reason_code=ReasonCode.EVIDENCE_INCOMPLETE,
                diagnostic="adapter returned incomplete supporting evidence",
                evidence=evidence,
            )
        if evidence.classification not in {
            EvidenceClassification.TESTED,
            EvidenceClassification.SUPPORTED_CANDIDATE,
        }:
            return CriterionResult(
                **base,
                disposition=Disposition.FAIL,
                reason_code=ReasonCode.ADAPTER_ERROR,
                diagnostic="evidence authority cannot establish PASS",
                evidence=None,
            )
        return CriterionResult(
            **base,
            disposition=Disposition.PASS,
            reason_code=ReasonCode.CRITERION_PASSED,
            diagnostic="completed supporting evidence satisfied the criterion",
            evidence=evidence,
        )
