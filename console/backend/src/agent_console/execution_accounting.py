"""Pure, deterministic accounting over already-authorized execution facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent_console.execution_snapshot import SharedExecutionSnapshot, SnapshotState
from agent_console.intervention_feedback_schemas import (
    InterventionEventRecord,
    OutcomeFeedbackRecord,
)
from agent_console.live_journey_schemas import JourneyOutcome


class AccountingError(ValueError):
    """Fail-closed input authority or provenance failure."""


class Availability(StrEnum):
    MEASURED = "MEASURED"
    PARTIAL = "PARTIAL"
    NOT_MEASURABLE = "NOT_MEASURABLE"


class OutcomeChange(StrEnum):
    IMPROVEMENT = "IMPROVEMENT"
    REGRESSION = "REGRESSION"
    NO_CHANGE = "NO_CHANGE"


@dataclass(frozen=True, slots=True)
class ScopedOutcomeComparison:
    """An authorized, directionally comparable predecessor/successor pair."""

    namespace: str
    security_domain: str
    predecessor_execution_identity: str
    successor_execution_identity: str
    predecessor: JourneyOutcome
    successor: JourneyOutcome


@dataclass(frozen=True, slots=True)
class AccountingRate:
    numerator: int
    denominator: int
    value: float | None
    availability: Availability

    def to_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "availability": self.availability.value,
        }


@dataclass(frozen=True, slots=True)
class AccountingReadModel:
    schema_version: int
    namespace: str
    security_domain: str
    source_snapshot_ids: tuple[str, ...]
    evidence_identities: tuple[str, ...]
    outcome_identities: tuple[str, ...]
    source_high_water_mark: int
    execution_count: int
    attempt_count: int
    provider_call_count: int
    success: AccountingRate
    failure: AccountingRate
    denial: AccountingRate
    unknown: AccountingRate
    workflow_identity_coverage: AccountingRate
    task_identity_coverage: AccountingRate
    platform_execution_identity_coverage: AccountingRate
    evidence_completeness: AccountingRate
    limitation_counts: tuple[tuple[str, int], ...]
    intervention_linkage_count: int
    feedback_linkage_count: int
    outcome_change_counts: tuple[tuple[str, int], ...]
    outcome_comparison_availability: Availability
    source_availability: Availability
    token_usage_availability: Availability
    monetary_cost_availability: Availability
    elapsed_latency_availability: Availability

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "scope": {
                "namespace": self.namespace,
                "securityDomain": self.security_domain,
            },
            "sourceSnapshotIds": list(self.source_snapshot_ids),
            "evidenceIdentityProvenance": list(self.evidence_identities),
            "outcomeIdentityProvenance": list(self.outcome_identities),
            "sourceHighWaterMark": self.source_high_water_mark,
            "executionCount": self.execution_count,
            "attemptCount": self.attempt_count,
            "providerCallCount": self.provider_call_count,
            "outcomes": {
                "success": self.success.to_dict(),
                "failure": self.failure.to_dict(),
                "denial": self.denial.to_dict(),
                "unknown": self.unknown.to_dict(),
            },
            "identityCoverage": {
                "workflow": self.workflow_identity_coverage.to_dict(),
                "task": self.task_identity_coverage.to_dict(),
                "platformExecution": (
                    self.platform_execution_identity_coverage.to_dict()
                ),
            },
            "evidenceCompleteness": self.evidence_completeness.to_dict(),
            "limitationCounts": dict(self.limitation_counts),
            "interventionLinkageCount": self.intervention_linkage_count,
            "feedbackLinkageCount": self.feedback_linkage_count,
            "comparableOutcomeChanges": dict(self.outcome_change_counts),
            "outcomeComparisonAvailability": self.outcome_comparison_availability.value,
            "sourceAvailability": self.source_availability.value,
            "unsupportedTelemetry": {
                "tokenUsage": self.token_usage_availability.value,
                "monetaryCost": self.monetary_cost_availability.value,
                "elapsedLatency": self.elapsed_latency_availability.value,
            },
        }


def _rate(numerator: int, denominator: int, partial: bool = False) -> AccountingRate:
    if denominator == 0:
        return AccountingRate(0, 0, None, Availability.NOT_MEASURABLE)
    return AccountingRate(
        numerator,
        denominator,
        numerator / denominator,
        Availability.PARTIAL if partial else Availability.MEASURED,
    )


def _validated_snapshots(
    snapshots: tuple[SharedExecutionSnapshot, ...], namespace: str, domain: str
) -> tuple[SharedExecutionSnapshot, ...]:
    by_id: dict[str, SharedExecutionSnapshot] = {}
    for snapshot in snapshots:
        if not isinstance(snapshot, SharedExecutionSnapshot):
            raise AccountingError("ACCOUNTING_SNAPSHOT_INVALID")
        if snapshot.namespace != namespace or snapshot.security_domain != domain:
            raise AccountingError("ACCOUNTING_SCOPE_DENIED")
        if not snapshot.shared_snapshot_id or not snapshot.platform_execution_identity:
            raise AccountingError("ACCOUNTING_IDENTITY_AMBIGUOUS")
        for evidence in snapshot.evidence:
            if (
                evidence.namespace != namespace
                or evidence.security_domain != domain
                or evidence.platform_execution_identity
                != snapshot.platform_execution_identity
            ):
                raise AccountingError("ACCOUNTING_EVIDENCE_SCOPE_DENIED")
        previous = by_id.setdefault(snapshot.shared_snapshot_id, snapshot)
        if previous != snapshot:
            raise AccountingError("ACCOUNTING_SNAPSHOT_IDENTITY_CONFLICT")
    return tuple(by_id[key] for key in sorted(by_id))


def build_execution_accounting(
    *,
    namespace: str,
    security_domain: str,
    snapshots: tuple[SharedExecutionSnapshot, ...],
    outcome_comparisons: tuple[ScopedOutcomeComparison, ...] = (),
    interventions: tuple[InterventionEventRecord, ...] = (),
    feedback: tuple[OutcomeFeedbackRecord, ...] = (),
) -> AccountingReadModel:
    """Build one scoped read model without I/O or mutation of source facts."""
    if not namespace or not security_domain:
        raise AccountingError("ACCOUNTING_SCOPE_REQUIRED")

    ordered_snapshots = _validated_snapshots(snapshots, namespace, security_domain)
    execution_ids = {item.platform_execution_identity for item in ordered_snapshots}
    evidence_by_id: dict[str, Any] = {}
    for snapshot in ordered_snapshots:
        for item in snapshot.evidence:
            previous = evidence_by_id.setdefault(item.evidence_record_id, item)
            if previous != item:
                raise AccountingError("ACCOUNTING_EVIDENCE_IDENTITY_CONFLICT")

    for item in interventions:
        if item.tenantId != namespace or item.securityDomain != security_domain:
            raise AccountingError("ACCOUNTING_INTERVENTION_SCOPE_DENIED")
        if item.platformExecutionIdentity not in execution_ids:
            raise AccountingError("ACCOUNTING_INTERVENTION_LINKAGE_INVALID")
        if any(
            identity not in evidence_by_id for identity in item.executionEvidenceIds
        ):
            raise AccountingError("ACCOUNTING_INTERVENTION_LINKAGE_INVALID")
    for item in feedback:
        if item.tenantId != namespace or item.securityDomain != security_domain:
            raise AccountingError("ACCOUNTING_FEEDBACK_SCOPE_DENIED")
        if (
            item.platformExecutionIdentity not in execution_ids
            or item.evidenceId not in evidence_by_id
        ):
            raise AccountingError("ACCOUNTING_FEEDBACK_LINKAGE_INVALID")
    for item in outcome_comparisons:
        if item.namespace != namespace or item.security_domain != security_domain:
            raise AccountingError("ACCOUNTING_OUTCOME_SCOPE_DENIED")
        if {
            item.predecessor_execution_identity,
            item.successor_execution_identity,
        } - execution_ids:
            raise AccountingError("ACCOUNTING_OUTCOME_LINKAGE_INVALID")

    evidence = tuple(evidence_by_id[key] for key in sorted(evidence_by_id))
    partial = any(
        item.state in {SnapshotState.PARTIAL, SnapshotState.STALE}
        or item.limitation_codes
        for item in ordered_snapshots
    )
    terminal = tuple(item.terminal_evidence for item in ordered_snapshots)
    denominator = len(terminal)
    classifications = [item.outcome_classification.value for item in terminal]
    attempts = {
        (item.platform_execution_identity, item.attempt_ordinal) for item in evidence
    }
    provider_calls = sum(item.provider_call_count for item in evidence)
    limitations: dict[str, int] = {}
    for snapshot in ordered_snapshots:
        for code in snapshot.limitation_codes:
            limitations[code] = limitations.get(code, 0) + 1
        if snapshot.state is SnapshotState.STALE:
            limitations["SOURCE_STALE"] = limitations.get("SOURCE_STALE", 0) + 1
        elif snapshot.state is SnapshotState.PARTIAL:
            limitations["SOURCE_PARTIAL"] = limitations.get("SOURCE_PARTIAL", 0) + 1

    change_counts = {item.value: 0 for item in OutcomeChange}
    comparable_count = 0
    outcome_ids: set[str] = set()
    for comparison in outcome_comparisons:
        outcome_ids.update(
            (comparison.predecessor.outcomeId, comparison.successor.outcomeId)
        )
        before = comparison.predecessor.comparableValue
        after = comparison.successor.comparableValue
        if (
            before is None
            or after is None
            or comparison.predecessor.comparableMetric
            != comparison.successor.comparableMetric
        ):
            continue
        comparable_count += 1
        change = (
            OutcomeChange.IMPROVEMENT
            if after > before
            else OutcomeChange.REGRESSION
            if after < before
            else OutcomeChange.NO_CHANGE
        )
        change_counts[change.value] += 1
    outcome_ids.update(item.outcomeId for item in interventions)
    outcome_ids.update(item.outcomeId for item in feedback)

    complete_sources = sum(
        item.state is SnapshotState.COMPLETE and not item.limitation_codes
        for item in ordered_snapshots
    )
    source_availability = (
        Availability.NOT_MEASURABLE
        if not ordered_snapshots
        else Availability.PARTIAL
        if partial
        else Availability.MEASURED
    )
    comparison_availability = (
        Availability.NOT_MEASURABLE
        if not outcome_comparisons or comparable_count == 0
        else Availability.PARTIAL
        if comparable_count < len(outcome_comparisons) or partial
        else Availability.MEASURED
    )
    workflow_count = sum(bool(item.workflow.uid) for item in ordered_snapshots)
    task_count = sum(bool(item.tasks) for item in ordered_snapshots)
    execution_identity_count = sum(
        bool(item.platform_execution_identity) for item in ordered_snapshots
    )
    return AccountingReadModel(
        schema_version=1,
        namespace=namespace,
        security_domain=security_domain,
        source_snapshot_ids=tuple(
            item.shared_snapshot_id for item in ordered_snapshots
        ),
        evidence_identities=tuple(sorted(evidence_by_id)),
        outcome_identities=tuple(sorted(outcome_ids)),
        source_high_water_mark=max(
            (item.evidence_high_water_mark for item in ordered_snapshots), default=0
        ),
        execution_count=len(execution_ids),
        attempt_count=len(attempts),
        provider_call_count=provider_calls,
        success=_rate(classifications.count("SUCCEEDED"), denominator, partial),
        failure=_rate(classifications.count("FAILED"), denominator, partial),
        denial=_rate(classifications.count("DENIED"), denominator, partial),
        unknown=_rate(classifications.count("UNKNOWN"), denominator, partial),
        workflow_identity_coverage=_rate(
            workflow_count, len(ordered_snapshots), partial
        ),
        task_identity_coverage=_rate(task_count, len(ordered_snapshots), partial),
        platform_execution_identity_coverage=_rate(
            execution_identity_count, len(ordered_snapshots), partial
        ),
        evidence_completeness=_rate(complete_sources, len(ordered_snapshots), partial),
        limitation_counts=tuple(sorted(limitations.items())),
        intervention_linkage_count=len({item.recordId for item in interventions}),
        feedback_linkage_count=len({item.feedbackId for item in feedback}),
        outcome_change_counts=tuple(sorted(change_counts.items())),
        outcome_comparison_availability=comparison_availability,
        source_availability=source_availability,
        token_usage_availability=Availability.NOT_MEASURABLE,
        monetary_cost_availability=Availability.NOT_MEASURABLE,
        elapsed_latency_availability=Availability.NOT_MEASURABLE,
    )
