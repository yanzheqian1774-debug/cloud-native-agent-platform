"""Normalized, machine-readable Harness records."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


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


@dataclass(frozen=True, slots=True)
class CriterionManifest:
    schema_version: str
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True, slots=True)
class Evidence:
    classification: EvidenceClassification
    completed: bool
    observations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        copied = deepcopy(dict(self.observations))
        object.__setattr__(self, "observations", MappingProxyType(copied))


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_id: str
    target: str
    profile: str
    version: str
    disposition: Disposition
    reason_code: ReasonCode
    diagnostic: str
    evidence: Evidence | None


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


@dataclass(frozen=True, slots=True)
class HarnessReport:
    profile: str
    results: tuple[CriterionResult, ...]
    summary: HarnessSummary
