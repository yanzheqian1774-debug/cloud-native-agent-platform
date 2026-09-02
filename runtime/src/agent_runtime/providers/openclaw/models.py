"""Provider-local OpenClaw values; not a public Runtime Contract or wire API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol


class OpenClawError(ValueError):
    """Fail-closed error whose message never contains provider payloads."""


class RuntimeMode(StrEnum):
    STATELESS = "STATELESS"
    STATEFUL = "STATEFUL"


class SessionAffinity(StrEnum):
    NONE = "NONE"
    REQUIRED = "REQUIRED"


class LifecycleState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ExecutionState(StrEnum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ReadinessState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class ReasonCode(StrEnum):
    EXACT_VERSION_READY = "EXACT_VERSION_READY"
    VERSION_UNSUPPORTED = "VERSION_UNSUPPORTED"
    PACKAGE_INTEGRITY_MISMATCH = "PACKAGE_INTEGRITY_MISMATCH"
    PLACEMENT_REQUIRED = "PLACEMENT_REQUIRED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    SESSION_AFFINITY_REQUIRED = "SESSION_AFFINITY_REQUIRED"
    SESSION_AFFINITY_PROHIBITED = "SESSION_AFFINITY_PROHIBITED"
    OBSERVATION_MISSING = "OBSERVATION_MISSING"
    OBSERVATION_STALE = "OBSERVATION_STALE"
    OBSERVATION_CONFLICTING = "OBSERVATION_CONFLICTING"
    OBSERVATION_UNKNOWN = "OBSERVATION_UNKNOWN"
    PROVIDER_EFFECT_AMBIGUOUS = "PROVIDER_EFFECT_AMBIGUOUS"
    PROVIDER_OBSERVED = "PROVIDER_OBSERVED"
    EXECUTION_ACCEPTED = "EXECUTION_ACCEPTED"
    EXECUTION_RUNNING = "EXECUTION_RUNNING"
    EXECUTION_TERMINAL = "EXECUTION_TERMINAL"
    GRACEFUL_STOPPED = "GRACEFUL_STOPPED"
    REPLACEMENT_BOUNDED = "REPLACEMENT_BOUNDED"


class EventType(StrEnum):
    RUNTIME_STARTED = "RUNTIME_STARTED"
    RUNTIME_STOPPED = "RUNTIME_STOPPED"
    RUNTIME_REPLACED = "RUNTIME_REPLACED"
    EXECUTION_ACCEPTED = "EXECUTION_ACCEPTED"
    EXECUTION_RUNNING = "EXECUTION_RUNNING"
    EXECUTION_TERMINAL = "EXECUTION_TERMINAL"


def _text(value: object, code: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise OpenClawError(code)
    normalized = value.strip()
    if not normalized or len(normalized.encode()) > maximum:
        raise OpenClawError(code)
    return normalized


def _aware(value: datetime, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise OpenClawError(code)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ExactTarget:
    version: str
    tag_commit: str
    package_integrity: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _text(self.version, "INVALID_VERSION"))
        object.__setattr__(
            self, "tag_commit", _text(self.tag_commit, "INVALID_TAG_COMMIT")
        )
        object.__setattr__(
            self,
            "package_integrity",
            _text(self.package_integrity, "INVALID_PACKAGE_INTEGRITY", maximum=512),
        )


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    namespace: str
    security_domain: str
    runtime_instance_id: str
    placement_id: str
    generation: int
    mode: RuntimeMode
    session_affinity: SessionAffinity
    session_reference: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "namespace",
            "security_domain",
            "runtime_instance_id",
            "placement_id",
        ):
            object.__setattr__(
                self, field, _text(getattr(self, field), "INVALID_BINDING")
            )
        if not isinstance(self.generation, int) or isinstance(self.generation, bool):
            raise OpenClawError("INVALID_GENERATION")
        if self.generation < 1:
            raise OpenClawError("INVALID_GENERATION")
        if not isinstance(self.mode, RuntimeMode) or not isinstance(
            self.session_affinity, SessionAffinity
        ):
            raise OpenClawError("INVALID_RUNTIME_FACTS")
        if self.session_reference is not None:
            object.__setattr__(
                self,
                "session_reference",
                _text(self.session_reference, "INVALID_SESSION_REFERENCE"),
            )
        if (
            self.session_affinity is SessionAffinity.REQUIRED
            and not self.session_reference
        ):
            raise OpenClawError(ReasonCode.SESSION_AFFINITY_REQUIRED.value)
        if self.session_affinity is SessionAffinity.NONE and self.session_reference:
            raise OpenClawError(ReasonCode.SESSION_AFFINITY_PROHIBITED.value)


@dataclass(frozen=True, slots=True)
class ExecutionLinkage:
    workflow_run_id: str
    task_run_id: str
    attempt_id: str
    agent_instance_id: str
    runtime_instance_id: str
    placement_id: str

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            object.__setattr__(
                self, field, _text(getattr(self, field), "INVALID_LINKAGE")
            )


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    linkage: ExecutionLinkage
    input_reference: str
    idempotency_key: str
    session_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.linkage, ExecutionLinkage):
            raise OpenClawError("INVALID_LINKAGE")
        object.__setattr__(
            self,
            "input_reference",
            _text(self.input_reference, "INVALID_INPUT_REFERENCE"),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            _text(self.idempotency_key, "INVALID_IDEMPOTENCY_KEY"),
        )
        if self.session_reference is not None:
            object.__setattr__(
                self,
                "session_reference",
                _text(self.session_reference, "INVALID_SESSION_REFERENCE"),
            )


@dataclass(frozen=True, slots=True)
class ProviderCorrelation:
    gateway_id: str
    run_id: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        for field in ("gateway_id", "run_id", "session_id"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _text(value, "INVALID_CORRELATION"))


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    runtime_instance_id: str
    generation: int
    state: LifecycleState
    health: HealthState
    readiness: ReadinessState
    observed_at: datetime
    freshness_deadline: datetime
    correlation: ProviderCorrelation

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "runtime_instance_id",
            _text(self.runtime_instance_id, "INVALID_RUNTIME_IDENTITY"),
        )
        if not isinstance(self.generation, int) or self.generation < 1:
            raise OpenClawError("INVALID_GENERATION")
        if not isinstance(self.state, LifecycleState):
            raise OpenClawError("INVALID_LIFECYCLE_STATE")
        if not isinstance(self.health, HealthState) or not isinstance(
            self.readiness, ReadinessState
        ):
            raise OpenClawError("INVALID_STATUS_FACT")
        object.__setattr__(
            self, "observed_at", _aware(self.observed_at, "INVALID_TIME")
        )
        object.__setattr__(
            self,
            "freshness_deadline",
            _aware(self.freshness_deadline, "INVALID_TIME"),
        )
        if self.freshness_deadline <= self.observed_at:
            raise OpenClawError("INVALID_FRESHNESS")
        if not isinstance(self.correlation, ProviderCorrelation):
            raise OpenClawError("INVALID_CORRELATION")


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    linkage: ExecutionLinkage
    state: ExecutionState
    observed_at: datetime
    correlation: ProviderCorrelation
    reason: ReasonCode
    result_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.linkage, ExecutionLinkage):
            raise OpenClawError("INVALID_LINKAGE")
        if not isinstance(self.state, ExecutionState) or not isinstance(
            self.reason, ReasonCode
        ):
            raise OpenClawError("INVALID_EXECUTION_OBSERVATION")
        object.__setattr__(
            self, "observed_at", _aware(self.observed_at, "INVALID_TIME")
        )
        if self.result_reference is not None:
            object.__setattr__(
                self,
                "result_reference",
                _text(self.result_reference, "INVALID_RESULT_REFERENCE"),
            )


@dataclass(frozen=True, slots=True)
class SanitizedEvidence:
    event_type: EventType
    reason: ReasonCode
    linkage: ExecutionLinkage
    runtime_instance_id: str
    generation: int
    provider_correlation_digest: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType) or not isinstance(
            self.reason, ReasonCode
        ):
            raise OpenClawError("INVALID_EVIDENCE")
        if not isinstance(self.linkage, ExecutionLinkage):
            raise OpenClawError("INVALID_EVIDENCE")
        object.__setattr__(
            self,
            "runtime_instance_id",
            _text(self.runtime_instance_id, "INVALID_RUNTIME_IDENTITY"),
        )
        if not isinstance(self.generation, int) or self.generation < 1:
            raise OpenClawError("INVALID_GENERATION")
        if (
            not isinstance(self.provider_correlation_digest, str)
            or len(self.provider_correlation_digest) != 64
        ):
            raise OpenClawError("INVALID_CORRELATION_DIGEST")
        object.__setattr__(
            self, "recorded_at", _aware(self.recorded_at, "INVALID_TIME")
        )


class OpenClawTransport(Protocol):
    """Fixed operations only: no command, YAML, environment, log, or Secret API."""

    def preflight(self) -> ExactTarget: ...
    def start(self, binding: RuntimeBinding) -> RuntimeObservation: ...
    def observe_runtime(
        self, binding: RuntimeBinding
    ) -> tuple[RuntimeObservation, ...]: ...
    def execute(self, request: ExecutionRequest) -> ExecutionObservation: ...
    def observe_execution(
        self, request: ExecutionRequest
    ) -> tuple[ExecutionObservation, ...]: ...
    def stop(self, binding: RuntimeBinding) -> RuntimeObservation: ...
    def replace(self, binding: RuntimeBinding) -> RuntimeObservation: ...
