"""Internal v0.2.3 execution-authority contract.

This module contains values and serialization only.  It grants no persistence,
authorization, scheduling, reconciliation, Kubernetes, or provider authority.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self


class ExecutionContractError(ValueError):
    """Fail-closed validation error that does not echo rejected content."""


CONTRACT_VERSION = "v0.2.3-a0"
MAX_ID_BYTES = 200
MAX_SCOPE_BYTES = 128
MAX_VALUE_BYTES = 512
MAX_COLLECTION_ITEMS = 64


def _normalized_text(value: object, *, code: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ExecutionContractError(code)
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized or len(normalized.encode("utf-8")) > maximum:
        raise ExecutionContractError(code)
    return normalized


@dataclass(frozen=True, slots=True)
class _OpaqueId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalized_text(
                self.value, code="INVALID_PRODUCT_ID", maximum=MAX_ID_BYTES
            ),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DigitalEmployeeInstanceId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class AgentInstanceId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class AssignmentId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class WorkflowRunId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class TaskRunId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class AttemptId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeInstanceId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class PlacementId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class PlacementRequestId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class EvidenceId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class OutcomeId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class InterventionId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class CommandId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True)
class ObservationId(_OpaqueId):
    pass


@dataclass(frozen=True, slots=True, order=True)
class Generation:
    value: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.value, int)
            or isinstance(self.value, bool)
            or self.value < 1
        ):
            raise ExecutionContractError("INVALID_GENERATION")

    def successor(self) -> Generation:
        return Generation(self.value + 1)


@dataclass(frozen=True, slots=True)
class ScopeIdentity:
    namespace: str
    security_domain: str

    def __post_init__(self) -> None:
        for name in ("namespace", "security_domain"):
            object.__setattr__(
                self,
                name,
                _normalized_text(
                    getattr(self, name),
                    code="INVALID_SCOPE_IDENTITY",
                    maximum=MAX_SCOPE_BYTES,
                ),
            )


def _require_type(value: object, expected: type, code: str) -> None:
    if type(value) is not expected:
        raise ExecutionContractError(code)


def _timestamp(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ExecutionContractError(code)
    return value.astimezone(UTC)


def _reference(value: object, code: str) -> str:
    return _normalized_text(value, code=code, maximum=MAX_VALUE_BYTES)


def _codes(values: object, code: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or len(values) > MAX_COLLECTION_ITEMS:
        raise ExecutionContractError(code)
    normalized = tuple(_reference(item, code) for item in values)
    if len(set(normalized)) != len(normalized):
        raise ExecutionContractError(code)
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class AssignmentIdentity:
    assignment_id: AssignmentId
    digital_employee_instance_id: DigitalEmployeeInstanceId

    def __post_init__(self) -> None:
        _require_type(self.assignment_id, AssignmentId, "INVALID_ASSIGNMENT_ID")
        _require_type(
            self.digital_employee_instance_id,
            DigitalEmployeeInstanceId,
            "INVALID_DIGITAL_EMPLOYEE_INSTANCE_ID",
        )


@dataclass(frozen=True, slots=True)
class WorkflowRunIdentity:
    workflow_run_id: WorkflowRunId
    assignment_id: AssignmentId
    approved_plan_revision_id: str
    predecessor_workflow_run_id: WorkflowRunId | None = None
    correction_of_workflow_run_id: WorkflowRunId | None = None

    def __post_init__(self) -> None:
        _require_type(self.workflow_run_id, WorkflowRunId, "INVALID_WORKFLOW_RUN_ID")
        _require_type(self.assignment_id, AssignmentId, "INVALID_ASSIGNMENT_ID")
        object.__setattr__(
            self,
            "approved_plan_revision_id",
            _reference(self.approved_plan_revision_id, "INVALID_PLAN_REVISION"),
        )
        for value in (
            self.predecessor_workflow_run_id,
            self.correction_of_workflow_run_id,
        ):
            if value is not None:
                _require_type(value, WorkflowRunId, "INVALID_WORKFLOW_PREDECESSOR")
                if value == self.workflow_run_id:
                    raise ExecutionContractError("WORKFLOW_RUN_CANNOT_SUCCEED_ITSELF")
        if (
            self.correction_of_workflow_run_id is not None
            and self.predecessor_workflow_run_id != self.correction_of_workflow_run_id
        ):
            raise ExecutionContractError("CORRECTION_REQUIRES_PREDECESSOR_RUN")


@dataclass(frozen=True, slots=True)
class TaskRunIdentity:
    task_run_id: TaskRunId
    workflow_run_id: WorkflowRunId

    def __post_init__(self) -> None:
        _require_type(self.task_run_id, TaskRunId, "INVALID_TASK_RUN_ID")
        _require_type(self.workflow_run_id, WorkflowRunId, "INVALID_WORKFLOW_RUN_ID")


@dataclass(frozen=True, slots=True)
class AttemptIdentity:
    attempt_id: AttemptId
    task_run_id: TaskRunId
    predecessor_attempt_id: AttemptId | None = None

    def __post_init__(self) -> None:
        _require_type(self.attempt_id, AttemptId, "INVALID_ATTEMPT_ID")
        _require_type(self.task_run_id, TaskRunId, "INVALID_TASK_RUN_ID")
        if self.predecessor_attempt_id is not None:
            _require_type(
                self.predecessor_attempt_id,
                AttemptId,
                "INVALID_ATTEMPT_PREDECESSOR",
            )
            if self.predecessor_attempt_id == self.attempt_id:
                raise ExecutionContractError("ATTEMPT_CANNOT_RETRY_ITSELF")


@dataclass(frozen=True, slots=True)
class ExecutionIdentityAggregate:
    scope: ScopeIdentity
    assignment: AssignmentIdentity
    workflow_run: WorkflowRunIdentity
    task_run: TaskRunIdentity
    attempt: AttemptIdentity

    def __post_init__(self) -> None:
        _require_type(self.scope, ScopeIdentity, "INVALID_SCOPE_IDENTITY")
        _require_type(self.assignment, AssignmentIdentity, "INVALID_ASSIGNMENT")
        _require_type(self.workflow_run, WorkflowRunIdentity, "INVALID_WORKFLOW_RUN")
        _require_type(self.task_run, TaskRunIdentity, "INVALID_TASK_RUN")
        _require_type(self.attempt, AttemptIdentity, "INVALID_ATTEMPT")
        if self.workflow_run.assignment_id != self.assignment.assignment_id:
            raise ExecutionContractError("WORKFLOW_ASSIGNMENT_MISMATCH")
        if self.task_run.workflow_run_id != self.workflow_run.workflow_run_id:
            raise ExecutionContractError("TASK_WORKFLOW_MISMATCH")
        if self.attempt.task_run_id != self.task_run.task_run_id:
            raise ExecutionContractError("ATTEMPT_TASK_MISMATCH")


def retry_attempt(
    previous: AttemptIdentity, new_attempt_id: AttemptId
) -> AttemptIdentity:
    """Create a new Attempt under the same Task Run."""
    _require_type(previous, AttemptIdentity, "INVALID_ATTEMPT")
    _require_type(new_attempt_id, AttemptId, "INVALID_ATTEMPT_ID")
    if new_attempt_id == previous.attempt_id:
        raise ExecutionContractError("RETRY_REQUIRES_NEW_ATTEMPT")
    return AttemptIdentity(new_attempt_id, previous.task_run_id, previous.attempt_id)


def rerun_workflow(
    previous: WorkflowRunIdentity, new_workflow_run_id: WorkflowRunId
) -> WorkflowRunIdentity:
    """Create a successor Run without reusing the previous Run identity."""
    _require_type(previous, WorkflowRunIdentity, "INVALID_WORKFLOW_RUN")
    return WorkflowRunIdentity(
        new_workflow_run_id,
        previous.assignment_id,
        previous.approved_plan_revision_id,
        predecessor_workflow_run_id=previous.workflow_run_id,
    )


def correct_workflow(
    previous: WorkflowRunIdentity,
    new_workflow_run_id: WorkflowRunId,
    successor_plan_revision_id: str,
) -> WorkflowRunIdentity:
    """Bind a corrected successor Run to a distinct approved plan revision."""
    revision = _reference(successor_plan_revision_id, "INVALID_PLAN_REVISION")
    if revision == previous.approved_plan_revision_id:
        raise ExecutionContractError("CORRECTION_REQUIRES_SUCCESSOR_PLAN_REVISION")
    return WorkflowRunIdentity(
        new_workflow_run_id,
        previous.assignment_id,
        revision,
        predecessor_workflow_run_id=previous.workflow_run_id,
        correction_of_workflow_run_id=previous.workflow_run_id,
    )


class PlacementDecisionKind(StrEnum):
    PLACED = "PLACED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class PlacementRequest:
    request_id: PlacementRequestId
    scope: ScopeIdentity
    workflow_run_id: WorkflowRunId
    task_run_id: TaskRunId
    attempt_id: AttemptId
    agent_instance_id: AgentInstanceId
    agent_revision_id: str
    runtime_profile_revision_id: str
    capability_requirements: tuple[str, ...]
    resource_requirements: tuple[str, ...]
    isolation_requirements: tuple[str, ...]
    state_requirements: tuple[str, ...]
    requested_at: datetime

    def __post_init__(self) -> None:
        for name, expected in (
            ("request_id", PlacementRequestId),
            ("scope", ScopeIdentity),
            ("workflow_run_id", WorkflowRunId),
            ("task_run_id", TaskRunId),
            ("attempt_id", AttemptId),
            ("agent_instance_id", AgentInstanceId),
        ):
            _require_type(getattr(self, name), expected, f"INVALID_{name.upper()}")
        for name in ("agent_revision_id", "runtime_profile_revision_id"):
            object.__setattr__(
                self, name, _reference(getattr(self, name), "INVALID_REVISION")
            )
        for name in (
            "capability_requirements",
            "resource_requirements",
            "isolation_requirements",
            "state_requirements",
        ):
            object.__setattr__(
                self, name, _codes(getattr(self, name), "INVALID_REQUIREMENTS")
            )
        object.__setattr__(
            self, "requested_at", _timestamp(self.requested_at, "INVALID_REQUESTED_AT")
        )

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self)

    @property
    def digest(self) -> str:
        return canonical_digest(self)

    @classmethod
    def from_mapping(cls, source: Mapping[str, object]) -> Self:
        return _from_mapping(cls, source)


@dataclass(frozen=True, slots=True)
class PlacementDecision:
    placement_id: PlacementId
    request_id: PlacementRequestId
    decision: PlacementDecisionKind
    runtime_instance_id: RuntimeInstanceId | None
    policy_version: str
    compatibility_facts: tuple[str, ...]
    limitation_codes: tuple[str, ...]
    decided_at: datetime
    digest: str

    def __post_init__(self) -> None:
        _require_type(self.placement_id, PlacementId, "INVALID_PLACEMENT_ID")
        _require_type(self.request_id, PlacementRequestId, "INVALID_REQUEST_ID")
        if not isinstance(self.decision, PlacementDecisionKind):
            raise ExecutionContractError("INVALID_PLACEMENT_DECISION")
        if self.decision is PlacementDecisionKind.PLACED:
            _require_type(
                self.runtime_instance_id,
                RuntimeInstanceId,
                "PLACED_REQUIRES_RUNTIME_INSTANCE",
            )
        elif self.runtime_instance_id is not None:
            raise ExecutionContractError("REJECTED_PROHIBITS_RUNTIME_INSTANCE")
        object.__setattr__(
            self,
            "policy_version",
            _reference(self.policy_version, "INVALID_POLICY_VERSION"),
        )
        object.__setattr__(
            self,
            "compatibility_facts",
            _codes(self.compatibility_facts, "INVALID_COMPATIBILITY_FACTS"),
        )
        object.__setattr__(
            self,
            "limitation_codes",
            _codes(self.limitation_codes, "INVALID_LIMITATION_CODES"),
        )
        object.__setattr__(
            self, "decided_at", _timestamp(self.decided_at, "INVALID_DECIDED_AT")
        )
        if not isinstance(self.digest, str) or len(self.digest) != 64:
            raise ExecutionContractError("INVALID_DECISION_DIGEST")
        try:
            int(self.digest, 16)
        except ValueError as exc:
            raise ExecutionContractError("INVALID_DECISION_DIGEST") from exc
        if self.digest != self.digest.lower():
            raise ExecutionContractError("INVALID_DECISION_DIGEST")

    @property
    def canonical_payload(self) -> Mapping[str, Any]:
        return _canonical_value(self, excluded={"digest"})

    def verify_digest(self) -> None:
        if self.digest != canonical_digest(self.canonical_payload):
            raise ExecutionContractError("DECISION_DIGEST_MISMATCH")

    @classmethod
    def create(
        cls,
        *,
        placement_id: PlacementId,
        request_id: PlacementRequestId,
        decision: PlacementDecisionKind,
        runtime_instance_id: RuntimeInstanceId | None,
        policy_version: str,
        compatibility_facts: Sequence[str],
        limitation_codes: Sequence[str],
        decided_at: datetime,
    ) -> Self:
        values = {
            "placement_id": placement_id,
            "request_id": request_id,
            "decision": decision,
            "runtime_instance_id": runtime_instance_id,
            "policy_version": _reference(policy_version, "INVALID_POLICY_VERSION"),
            "compatibility_facts": _codes(
                tuple(compatibility_facts), "INVALID_COMPATIBILITY_FACTS"
            ),
            "limitation_codes": _codes(
                tuple(limitation_codes), "INVALID_LIMITATION_CODES"
            ),
            "decided_at": _timestamp(decided_at, "INVALID_DECIDED_AT"),
        }
        digest = canonical_digest(values)
        return cls(**values, digest=digest)

    @classmethod
    def from_mapping(cls, source: Mapping[str, object]) -> Self:
        value = _from_mapping(cls, source)
        value.verify_digest()
        return value


class RuntimeDesiredStateKind(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    OBSERVE = "OBSERVE"


class RuntimeObservedStateKind(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class RuntimeHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class RuntimeReadiness(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class CommandResult(StrEnum):
    REQUESTED = "REQUESTED"
    APPLIED = "APPLIED"
    OBSERVED = "OBSERVED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


AMBIGUOUS_COMMAND_RESULTS = frozenset(
    {CommandResult.UNKNOWN, CommandResult.STALE, CommandResult.RECOVERY_REQUIRED}
)


def may_reissue_command(result: CommandResult) -> bool:
    """Ambiguous effects must be observed or recovered, never blindly reissued."""
    if not isinstance(result, CommandResult):
        raise ExecutionContractError("INVALID_COMMAND_RESULT")
    return result in {CommandResult.REQUESTED, CommandResult.REJECTED}


@dataclass(frozen=True, slots=True)
class RuntimeDesiredState:
    runtime_instance_id: RuntimeInstanceId
    desired_generation: Generation
    desired_state: RuntimeDesiredStateKind
    command_id: CommandId
    requested_by: str
    requested_at: datetime
    deadline: datetime
    reason_classification: str

    def __post_init__(self) -> None:
        _require_type(
            self.runtime_instance_id, RuntimeInstanceId, "INVALID_RUNTIME_INSTANCE_ID"
        )
        _require_type(self.desired_generation, Generation, "INVALID_DESIRED_GENERATION")
        if not isinstance(self.desired_state, RuntimeDesiredStateKind):
            raise ExecutionContractError("INVALID_DESIRED_STATE")
        _require_type(self.command_id, CommandId, "INVALID_COMMAND_ID")
        for name in ("requested_by", "reason_classification"):
            object.__setattr__(
                self, name, _reference(getattr(self, name), f"INVALID_{name.upper()}")
            )
        object.__setattr__(
            self, "requested_at", _timestamp(self.requested_at, "INVALID_REQUESTED_AT")
        )
        object.__setattr__(
            self, "deadline", _timestamp(self.deadline, "INVALID_DEADLINE")
        )
        if self.deadline <= self.requested_at:
            raise ExecutionContractError("DEADLINE_MUST_FOLLOW_REQUEST")

    @classmethod
    def from_mapping(cls, source: Mapping[str, object]) -> Self:
        return _from_mapping(cls, source)


@dataclass(frozen=True, slots=True)
class ExternalCorrelation:
    system: str
    kind: str
    handle: str

    def __post_init__(self) -> None:
        for name in ("system", "kind", "handle"):
            object.__setattr__(
                self,
                name,
                _reference(getattr(self, name), "INVALID_EXTERNAL_CORRELATION"),
            )


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    observation_id: ObservationId
    runtime_instance_id: RuntimeInstanceId
    observed_generation: Generation
    observed_state: RuntimeObservedStateKind
    health: RuntimeHealth
    readiness: RuntimeReadiness
    observed_at: datetime
    freshness_deadline: datetime
    provider_correlation: ExternalCorrelation | None
    kubernetes_correlation: ExternalCorrelation | None
    limitation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_type(self.observation_id, ObservationId, "INVALID_OBSERVATION_ID")
        _require_type(
            self.runtime_instance_id, RuntimeInstanceId, "INVALID_RUNTIME_INSTANCE_ID"
        )
        _require_type(
            self.observed_generation, Generation, "INVALID_OBSERVED_GENERATION"
        )
        for value, expected, code in (
            (self.observed_state, RuntimeObservedStateKind, "INVALID_OBSERVED_STATE"),
            (self.health, RuntimeHealth, "INVALID_RUNTIME_HEALTH"),
            (self.readiness, RuntimeReadiness, "INVALID_RUNTIME_READINESS"),
        ):
            if not isinstance(value, expected):
                raise ExecutionContractError(code)
        for value in (self.provider_correlation, self.kubernetes_correlation):
            if value is not None:
                _require_type(
                    value, ExternalCorrelation, "INVALID_EXTERNAL_CORRELATION"
                )
        object.__setattr__(
            self, "observed_at", _timestamp(self.observed_at, "INVALID_OBSERVED_AT")
        )
        object.__setattr__(
            self,
            "freshness_deadline",
            _timestamp(self.freshness_deadline, "INVALID_FRESHNESS_DEADLINE"),
        )
        if self.freshness_deadline <= self.observed_at:
            raise ExecutionContractError("FRESHNESS_DEADLINE_MUST_FOLLOW_OBSERVATION")
        object.__setattr__(
            self,
            "limitation_codes",
            _codes(self.limitation_codes, "INVALID_LIMITATION_CODES"),
        )

    @classmethod
    def from_mapping(cls, source: Mapping[str, object]) -> Self:
        return _from_mapping(cls, source)


def current_observed_state(
    observation: RuntimeObservation | None, *, at: datetime
) -> RuntimeObservedStateKind:
    """Return UNKNOWN for missing and STALE for expired observations."""
    now = _timestamp(at, "INVALID_CURRENT_TIME")
    if observation is None:
        return RuntimeObservedStateKind.UNKNOWN
    _require_type(observation, RuntimeObservation, "INVALID_OBSERVATION")
    if now > observation.freshness_deadline:
        return RuntimeObservedStateKind.STALE
    return observation.observed_state


def assert_monotonic_generation(previous: Generation, successor: Generation) -> None:
    _require_type(previous, Generation, "INVALID_GENERATION")
    _require_type(successor, Generation, "INVALID_GENERATION")
    if successor.value <= previous.value:
        raise ExecutionContractError("GENERATION_MUST_INCREASE")


def assert_request_replay(
    stored: PlacementRequest, candidate: PlacementRequest
) -> None:
    """Accept exact canonical replay; reject reuse with different bytes."""
    _require_type(stored, PlacementRequest, "INVALID_PLACEMENT_REQUEST")
    _require_type(candidate, PlacementRequest, "INVALID_PLACEMENT_REQUEST")
    if stored.request_id != candidate.request_id:
        raise ExecutionContractError("PLACEMENT_REQUEST_ID_MISMATCH")
    if stored.canonical_bytes != candidate.canonical_bytes:
        raise ExecutionContractError("PLACEMENT_REQUEST_CONFLICT")


def _canonical_value(value: object, *, excluded: set[str] | None = None) -> Any:
    excluded = excluded or set()
    if isinstance(value, _OpaqueId):
        return value.value
    if isinstance(value, Generation):
        return value.value
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return _timestamp(value, "INVALID_TIMESTAMP").isoformat().replace("+00:00", "Z")
    if hasattr(value, "__dataclass_fields__"):
        return {
            field.name: _canonical_value(getattr(value, field.name))
            for field in fields(value)
            if field.name not in excluded
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ExecutionContractError("CANONICAL_MAPPING_KEYS_MUST_BE_STRINGS")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ExecutionContractError("UNSUPPORTED_CANONICAL_VALUE")


def canonical_bytes(value: object) -> bytes:
    envelope = {
        "contract_version": CONTRACT_VERSION,
        "payload": _canonical_value(value),
    }
    return json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _from_mapping(cls: type[Self], source: Mapping[str, object]) -> Self:
    if not isinstance(source, Mapping) or set(source) != {
        field.name for field in fields(cls)
    }:
        raise ExecutionContractError("UNKNOWN_OR_MISSING_CONTRACT_FIELD")
    values = dict(source)
    converters: dict[str, Any] = {
        "request_id": PlacementRequestId,
        "placement_id": PlacementId,
        "scope": lambda value: ScopeIdentity(**value),
        "workflow_run_id": WorkflowRunId,
        "task_run_id": TaskRunId,
        "attempt_id": AttemptId,
        "agent_instance_id": AgentInstanceId,
        "runtime_instance_id": lambda value: (
            None if value is None else RuntimeInstanceId(value)
        ),
        "desired_generation": Generation,
        "observed_generation": Generation,
        "command_id": CommandId,
        "observation_id": ObservationId,
        "decision": PlacementDecisionKind,
        "desired_state": RuntimeDesiredStateKind,
        "observed_state": RuntimeObservedStateKind,
        "health": RuntimeHealth,
        "readiness": RuntimeReadiness,
        "provider_correlation": lambda value: (
            None if value is None else ExternalCorrelation(**value)
        ),
        "kubernetes_correlation": lambda value: (
            None if value is None else ExternalCorrelation(**value)
        ),
    }
    tuple_fields = {
        "capability_requirements",
        "resource_requirements",
        "isolation_requirements",
        "state_requirements",
        "compatibility_facts",
        "limitation_codes",
    }
    datetime_fields = {
        "requested_at",
        "decided_at",
        "deadline",
        "observed_at",
        "freshness_deadline",
    }
    try:
        for name, converter in converters.items():
            if name in values:
                values[name] = converter(values[name])
        for name in tuple_fields & values.keys():
            values[name] = tuple(values[name])  # type: ignore[arg-type]
        for name in datetime_fields & values.keys():
            raw = values[name]
            if not isinstance(raw, str):
                raise TypeError
            values[name] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return cls(**values)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ExecutionContractError):
            raise
        raise ExecutionContractError("INVALID_CONTRACT_VALUE") from exc
