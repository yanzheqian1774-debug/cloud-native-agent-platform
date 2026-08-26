"""Deterministic Harness execution and normalized result arithmetic."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .manifest import select_criteria
from .models import (
    Criterion,
    CriterionManifest,
    CriterionResult,
    Disposition,
    Evidence,
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
)


def _diagnostic(value: object) -> str:
    text = " ".join(str(value).split())
    lowered = text.lower()
    if any(marker in lowered for marker in SENSITIVE_MARKERS):
        return "[REDACTED_SENSITIVE_DIAGNOSTIC]"
    return text[:MAX_DIAGNOSTIC_LENGTH]


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
                diagnostic=_diagnostic(exc or "component assertion failed"),
                evidence=None,
            )
        except Exception as exc:  # normalized diagnostic boundary
            return CriterionResult(
                **base,
                disposition=Disposition.FAIL,
                reason_code=ReasonCode.ADAPTER_ERROR,
                diagnostic=_diagnostic(f"{type(exc).__name__}: {exc}"),
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
        return CriterionResult(
            **base,
            disposition=Disposition.PASS,
            reason_code=ReasonCode.CRITERION_PASSED,
            diagnostic="completed supporting evidence satisfied the criterion",
            evidence=evidence,
        )
