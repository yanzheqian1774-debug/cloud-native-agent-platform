"""Normalized, validated machine-readable Harness records."""

import math
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("evidence observation keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("evidence observations require finite numbers")
    if value is None or isinstance(value, (str, int, float, bool)):
        return deepcopy(value)
    raise TypeError("evidence observations must be JSON-compatible")


PROVENANCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,119}$")
MAX_RESULT_DIAGNOSTIC_LENGTH = 240


class Disposition(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNRUN = "UNRUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceClassification(StrEnum):
    DECLARED_BY_UPSTREAM = "DECLARED_BY_UPSTREAM"
    OBSERVED = "OBSERVED"
    TESTED = "TESTED"
    SUPPORTED_CANDIDATE = "SUPPORTED_CANDIDATE"
    EXPERIMENTAL = "EXPERIMENTAL"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_YET_PROVEN = "NOT_YET_PROVEN"


class ReasonCode(StrEnum):
    CRITERION_PASSED = "CRITERION_PASSED"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    ADAPTER_ERROR = "ADAPTER_ERROR"
    ADAPTER_NOT_REGISTERED = "ADAPTER_NOT_REGISTERED"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    PROFILE_NOT_APPLICABLE = "PROFILE_NOT_APPLICABLE"
    SELECTION_EXCLUDED = "SELECTION_EXCLUDED"


@dataclass(frozen=True, slots=True)
class Criterion:
    criterion_id: str
    criterion_type: str
    target: str
    profile: str
    version: str
    adapter: str
    applicable_profiles: tuple[str, ...]
    evidence_classification: EvidenceClassification


@dataclass(frozen=True, slots=True)
class CriterionManifest:
    schema_version: str
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True, slots=True)
class Evidence:
    criterion_id: str
    classification: EvidenceClassification
    completed: bool
    execution_provenance: str
    observations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.criterion_id or not self.execution_provenance:
            raise ValueError("evidence requires criterion and execution provenance")
        if PROVENANCE_PATTERN.fullmatch(self.execution_provenance) is None:
            raise ValueError("evidence execution provenance is malformed")
        if not isinstance(self.classification, EvidenceClassification):
            raise TypeError("evidence classification must be typed")
        object.__setattr__(self, "observations", _freeze(dict(self.observations)))


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_id: str
    target: str
    profile: str
    version: str
    disposition: Disposition
    evidence_classification: EvidenceClassification
    reason_code: ReasonCode
    diagnostic: str
    evidence: Evidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, Disposition):
            raise TypeError("result disposition must be typed")
        if not isinstance(self.evidence_classification, EvidenceClassification):
            raise TypeError("result evidence classification must be typed")
        if not isinstance(self.reason_code, ReasonCode):
            raise TypeError("result reason code must be typed")
        if not isinstance(self.diagnostic, str):
            raise TypeError("result diagnostic must be a string")
        if len(self.diagnostic) > MAX_RESULT_DIAGNOSTIC_LENGTH:
            raise ValueError("result diagnostic exceeds maximum length")
        if self.evidence is not None:
            if self.evidence.criterion_id != self.criterion_id:
                raise ValueError("evidence belongs to a different criterion")
            if self.evidence.classification is not self.evidence_classification:
                raise ValueError("result and evidence classifications contradict")
        if self.disposition is Disposition.PASS:
            if self.evidence is None or not self.evidence.completed:
                raise ValueError("PASS requires completed supporting evidence")
            if self.evidence_classification not in {
                EvidenceClassification.TESTED,
                EvidenceClassification.SUPPORTED_CANDIDATE,
            }:
                raise ValueError("PASS requires tested candidate evidence authority")
        elif self.evidence is not None and self.evidence.completed:
            raise ValueError("non-PASS result cannot contain completed pass evidence")


@dataclass(frozen=True, slots=True)
class HarnessSummary:
    total: int
    passed: int
    failed: int
    unrun: int
    not_applicable: int

    @classmethod
    def from_results(cls, results: tuple[CriterionResult, ...]) -> "HarnessSummary":
        counts = {disposition: 0 for disposition in Disposition}
        for result in results:
            counts[result.disposition] += 1
        return cls(
            total=len(results),
            passed=counts[Disposition.PASS],
            failed=counts[Disposition.FAIL],
            unrun=counts[Disposition.UNRUN],
            not_applicable=counts[Disposition.NOT_APPLICABLE],
        )

    def __post_init__(self) -> None:
        values = (self.passed, self.failed, self.unrun, self.not_applicable)
        if any(value < 0 for value in (self.total, *values)):
            raise ValueError("summary counts cannot be negative")
        if self.total != sum(values):
            raise ValueError("summary arithmetic does not reconcile")


@dataclass(frozen=True, slots=True)
class HarnessReport:
    profile: str
    results: tuple[CriterionResult, ...]
    summary: HarnessSummary

    def __post_init__(self) -> None:
        results = tuple(self.results)
        if len({result.criterion_id for result in results}) != len(results):
            raise ValueError("report cannot contain duplicate criterion results")
        if self.summary != HarnessSummary.from_results(results):
            raise ValueError("report summary contradicts individual results")
        object.__setattr__(self, "results", results)
