"""Typed Attempt Resource Use facts, measurements, and deterministic snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from agent_core.execution_contract import ScopeIdentity


class ResourceUseError(ValueError):
    reason_code = "RESOURCE_USE_INVALID"


class ResourceUseConflict(ResourceUseError):
    reason_code = "RESOURCE_USE_CONFLICT"


class ResourceKind(StrEnum):
    SKILL = "SKILL"
    MCP = "MCP"
    KNOWLEDGE = "KNOWLEDGE"
    WORKFLOW = "WORKFLOW"
    RUNTIME = "RUNTIME"
    DIGITAL_EMPLOYEE = "DIGITAL_EMPLOYEE"


class ResourceUseFactKind(StrEnum):
    CONFIGURED = "CONFIGURED"
    BOUND = "BOUND"
    SELECTED = "SELECTED"
    REQUESTED = "REQUESTED"
    DISPATCH_RECORDED = "DISPATCH_RECORDED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLATION_CONFIRMED = "CANCELLATION_CONFIRMED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    NOT_EXECUTED = "NOT_EXECUTED"
    NO_RESULT = "NO_RESULT"
    MEASUREMENT_RECORDED = "MEASUREMENT_RECORDED"
    MEASUREMENT_NOT_COLLECTED = "MEASUREMENT_NOT_COLLECTED"
    MEASUREMENT_NOT_MEASURABLE = "MEASUREMENT_NOT_MEASURABLE"


class EffectiveUseState(StrEnum):
    CONFIGURED = "CONFIGURED"
    BOUND = "BOUND"
    SELECTED = "SELECTED"
    REQUESTED = "REQUESTED"
    DISPATCH_RECORDED = "DISPATCH_RECORDED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLATION_CONFIRMED = "CANCELLATION_CONFIRMED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    NOT_EXECUTED = "NOT_EXECUTED"
    NO_RESULT = "NO_RESULT"
    CONFLICTED = "CONFLICTED"


class MeasurementAvailability(StrEnum):
    MEASURED = "MEASURED"
    NOT_COLLECTED = "NOT_COLLECTED"
    NOT_MEASURABLE = "NOT_MEASURABLE"
    ESTIMATED = "ESTIMATED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"


CORE_METRICS = frozenset(
    {
        "duration",
        "request_count",
        "invocation_count",
        "retrieval_count",
        "citation_count",
        "attempt_count",
    }
)
REDUCER_VERSION = "resource-use-reducer.v1"


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def stable_id(kind: str, *parts: str) -> str:
    if not parts or any(not item or not isinstance(item, str) for item in parts):
        raise ResourceUseError("RESOURCE_USE_IDENTITY_INVALID")
    return f"{kind}:{hashlib.sha256(chr(0).join(parts).encode()).hexdigest()}"


def canonical_record(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return canonical_record(asdict(value))
    if isinstance(value, dict):
        return {key: canonical_record(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical_record(item) for item in value]
    return value


def _required(value: str, code: str) -> None:
    if not isinstance(value, str) or not value or len(value.encode()) > 500:
        raise ResourceUseError(code)


@dataclass(frozen=True, slots=True)
class ResourceUseBinding:
    scope: ScopeIdentity
    resource_use_id: str
    attempt_id: str
    resource_kind: ResourceKind
    slot_key: str
    occurrence_ordinal: int
    resource_id: str
    resource_revision_id: str
    resource_digest: str
    binding_id: str
    binding_digest: str
    plan_id: str
    plan_version: int
    plan_digest: str
    workflow_run_id: str
    task_run_id: str
    digital_employee_definition_id: str
    digital_employee_definition_revision_id: str
    digital_employee_definition_digest: str
    digital_employee_instance_id: str
    agent_instance_id: str | None
    runtime_instance_id: str | None
    executor_id: str | None
    executor_revision: str | None
    provider_id: str | None
    provider_revision: str | None
    authorization_decision_id: str
    predecessor_attempt_id: str | None = None
    predecessor_workflow_run_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise ResourceUseError("RESOURCE_USE_SCOPE_REQUIRED")
        for field in (
            "resource_use_id",
            "attempt_id",
            "slot_key",
            "resource_id",
            "resource_revision_id",
            "resource_digest",
            "binding_id",
            "binding_digest",
            "plan_id",
            "plan_digest",
            "workflow_run_id",
            "task_run_id",
            "digital_employee_definition_id",
            "digital_employee_definition_revision_id",
            "digital_employee_definition_digest",
            "digital_employee_instance_id",
            "authorization_decision_id",
        ):
            _required(getattr(self, field), f"RESOURCE_USE_{field.upper()}_REQUIRED")
        if not isinstance(self.resource_kind, ResourceKind):
            raise ResourceUseError("RESOURCE_USE_KIND_INVALID")
        if self.occurrence_ordinal != 1:
            raise ResourceUseError("RESOURCE_USE_MANAGED_SLOT_CARDINALITY")
        if isinstance(self.plan_version, bool) or self.plan_version < 1:
            raise ResourceUseError("RESOURCE_USE_PLAN_VERSION_INVALID")
        expected = stable_id(
            "resource-use",
            self.scope.namespace,
            self.scope.security_domain,
            self.attempt_id,
            self.resource_kind.value,
            self.slot_key,
            str(self.occurrence_ordinal),
        )
        if self.resource_use_id != expected:
            raise ResourceUseError("RESOURCE_USE_IDENTITY_MISMATCH")

    @property
    def payload_digest(self) -> str:
        return canonical_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class ResourceUseFact:
    fact_id: str
    resource_use_id: str
    kind: ResourceUseFactKind
    source_owner: str
    source_observation_id: str
    source_digest: str
    observed_at: datetime
    recorded_at: datetime
    evidence_references: tuple[str, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    supersedes_fact_id: str | None = None

    def __post_init__(self) -> None:
        for value, code in (
            (self.fact_id, "RESOURCE_USE_FACT_ID_REQUIRED"),
            (self.resource_use_id, "RESOURCE_USE_ID_REQUIRED"),
            (self.source_owner, "RESOURCE_USE_SOURCE_OWNER_REQUIRED"),
            (self.source_observation_id, "RESOURCE_USE_SOURCE_OBSERVATION_REQUIRED"),
            (self.source_digest, "RESOURCE_USE_SOURCE_DIGEST_REQUIRED"),
        ):
            _required(value, code)
        if not isinstance(self.kind, ResourceUseFactKind):
            raise ResourceUseError("RESOURCE_USE_FACT_KIND_INVALID")
        if self.observed_at.tzinfo is None or self.recorded_at.tzinfo is None:
            raise ResourceUseError("RESOURCE_USE_TIMESTAMP_REQUIRED")


@dataclass(frozen=True, slots=True)
class ResourceMeasurement:
    measurement_id: str
    resource_use_id: str
    metric: str
    value: int | float | None
    unit: str
    availability: MeasurementAvailability
    source_identity: str
    source_digest: str
    window_started_at: datetime
    window_ended_at: datetime
    observed_at: datetime
    authority_level: str
    confidence: str
    limitations: tuple[str, ...]
    precision: str
    aggregation_eligible: bool
    redaction_profile: str
    evidence_references: tuple[str, ...]
    superseded_measurement_id: str | None = None

    def __post_init__(self) -> None:
        for value, code in (
            (self.measurement_id, "MEASUREMENT_ID_REQUIRED"),
            (self.resource_use_id, "RESOURCE_USE_ID_REQUIRED"),
            (self.metric, "MEASUREMENT_METRIC_REQUIRED"),
            (self.unit, "MEASUREMENT_UNIT_REQUIRED"),
            (self.source_identity, "MEASUREMENT_SOURCE_REQUIRED"),
            (self.source_digest, "MEASUREMENT_SOURCE_DIGEST_REQUIRED"),
            (self.authority_level, "MEASUREMENT_AUTHORITY_REQUIRED"),
            (self.confidence, "MEASUREMENT_CONFIDENCE_REQUIRED"),
            (self.precision, "MEASUREMENT_PRECISION_REQUIRED"),
            (self.redaction_profile, "MEASUREMENT_REDACTION_REQUIRED"),
        ):
            _required(value, code)
        if not isinstance(self.availability, MeasurementAvailability):
            raise ResourceUseError("MEASUREMENT_AVAILABILITY_INVALID")
        if self.metric not in CORE_METRICS:
            raise ResourceUseError("MEASUREMENT_METRIC_INVALID")
        if self.availability is MeasurementAvailability.MEASURED:
            if self.value is None or isinstance(self.value, bool) or self.value < 0:
                raise ResourceUseError("MEASURED_VALUE_REQUIRED")
        elif self.value is not None:
            raise ResourceUseError("UNAVAILABLE_MEASUREMENT_MUST_BE_NULL")
        if self.window_started_at > self.window_ended_at:
            raise ResourceUseError("MEASUREMENT_WINDOW_INVALID")
        if any(
            value.tzinfo is None
            for value in (
                self.window_started_at,
                self.window_ended_at,
                self.observed_at,
            )
        ):
            raise ResourceUseError("MEASUREMENT_TIMESTAMP_REQUIRED")


@dataclass(frozen=True, slots=True)
class ResourceUseSnapshot:
    snapshot_id: str
    digest: str
    resource_use_id: str
    high_water: int
    reducer_version: str
    effective_state: EffectiveUseState
    fact_ids: tuple[str, ...]
    measurement_ids: tuple[str, ...]
    evidence_references: tuple[str, ...]
    limitation_codes: tuple[str, ...]
    conflicts: tuple[str, ...]
    created_at: datetime


_STATE_FACTS = {
    kind: EffectiveUseState(kind.value)
    for kind in ResourceUseFactKind
    if kind.value in EffectiveUseState._value2member_map_
}
_TERMINAL = {
    EffectiveUseState.SUCCEEDED,
    EffectiveUseState.FAILED,
    EffectiveUseState.CANCELLATION_CONFIRMED,
    EffectiveUseState.OUTCOME_UNKNOWN,
    EffectiveUseState.REJECTED,
    EffectiveUseState.UNAVAILABLE,
    EffectiveUseState.NOT_EXECUTED,
    EffectiveUseState.NO_RESULT,
}

_STATE_RANK = {
    EffectiveUseState.CONFIGURED: 0,
    EffectiveUseState.BOUND: 1,
    EffectiveUseState.SELECTED: 2,
    EffectiveUseState.REQUESTED: 3,
    EffectiveUseState.DISPATCH_RECORDED: 4,
    EffectiveUseState.ACCEPTED: 5,
    EffectiveUseState.RUNNING: 6,
    EffectiveUseState.CANCELLATION_REQUESTED: 7,
}


def reduce_resource_use(
    resource_use_id: str,
    facts: tuple[ResourceUseFact, ...],
    measurements: tuple[ResourceMeasurement, ...],
    *,
    high_water: int,
    created_at: datetime | None = None,
) -> ResourceUseSnapshot:
    if high_water < 1 or high_water > len(facts):
        raise ResourceUseError("RESOURCE_USE_HIGH_WATER_INVALID")
    selected = facts[:high_water]
    if any(fact.resource_use_id != resource_use_id for fact in selected) or any(
        item.resource_use_id != resource_use_id for item in measurements
    ):
        raise ResourceUseError("RESOURCE_USE_SCOPE_MISMATCH")
    states = [_STATE_FACTS[item.kind] for item in selected if item.kind in _STATE_FACTS]
    if not states:
        raise ResourceUseError("RESOURCE_USE_STATE_FACT_REQUIRED")
    terminal = {item for item in states if item in _TERMINAL}
    conflicts: list[str] = []
    if len(terminal) > 1:
        conflicts.append("CONFLICTING_TERMINAL_FACTS")
    seen_sources: dict[tuple[str, str], str] = {}
    for item in selected:
        source = (item.source_owner, item.source_observation_id)
        prior = seen_sources.setdefault(source, item.source_digest)
        if prior != item.source_digest:
            conflicts.append("CONFLICTING_SOURCE_OBSERVATION")
    prior_state: EffectiveUseState | None = None
    for state in states:
        if prior_state in _TERMINAL and state != prior_state:
            conflicts.append("STATE_AFTER_TERMINAL")
        elif (
            prior_state in _STATE_RANK
            and state in _STATE_RANK
            and _STATE_RANK[state] < _STATE_RANK[prior_state]
        ):
            conflicts.append("ILLEGAL_STATE_REGRESSION")
        prior_state = state
    conflicts = list(dict.fromkeys(conflicts))
    effective = EffectiveUseState.CONFLICTED if conflicts else states[-1]
    evidence = tuple(
        dict.fromkeys(ref for fact in selected for ref in fact.evidence_references)
    )
    limitations = tuple(
        dict.fromkeys(code for fact in selected for code in fact.limitation_codes)
    )
    payload = {
        "resourceUseId": resource_use_id,
        "highWater": high_water,
        "reducerVersion": REDUCER_VERSION,
        "effectiveState": effective.value,
        "factIds": [item.fact_id for item in selected],
        "measurementIds": [item.measurement_id for item in measurements],
        "evidenceReferences": evidence,
        "limitationCodes": limitations,
        "conflicts": conflicts,
    }
    digest = canonical_digest(payload)
    snapshot_id = stable_id(
        "resource-use-snapshot", resource_use_id, str(high_water), digest
    )
    return ResourceUseSnapshot(
        snapshot_id,
        digest,
        resource_use_id,
        high_water,
        REDUCER_VERSION,
        effective,
        tuple(payload["factIds"]),
        tuple(payload["measurementIds"]),
        evidence,
        limitations,
        tuple(conflicts),
        created_at or datetime.now(UTC),
    )
