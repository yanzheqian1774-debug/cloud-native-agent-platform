"""Candidate v1 evidence types; experimental and not a frozen contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class TruthValue(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class OutcomeKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RuntimeDescriptor:
    runtime_id: str
    provider_id: str
    version: str
    interaction_modes: tuple[str, ...]
    ownership_modes: tuple[str, ...]
    artifact: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeBinding:
    binding_id: str
    descriptor_id: str
    provider_id: str
    ownership_mode: str
    references: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    name: str
    value: TruthValue
    reason: str
    observed_at_ms: int


@dataclass(frozen=True)
class ExecutionRequest:
    input_text: str
    correlation_id: str


@dataclass(frozen=True)
class ExecutionHandle:
    correlation_id: str
    native_reference: str | None = None


@dataclass(frozen=True)
class ExecutionOutcome:
    kind: OutcomeKind
    correlation_id: str
    output: str | None
    runtime_id: str
    provider_id: str
    latency_ms: int
    usage: dict[str, int] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Submission:
    correlation_id: str
    outcome: ExecutionOutcome | None = None
    handle: ExecutionHandle | None = None

    def __post_init__(self) -> None:
        if (self.outcome is None) == (self.handle is None):
            raise ValueError("submission requires exactly one of outcome or handle")


class RuntimeProvider(Protocol):
    descriptor: RuntimeDescriptor
    binding: RuntimeBinding

    def observe(self) -> tuple[Observation, ...]: ...

    def submit(self, request: ExecutionRequest) -> Submission: ...

    def await_outcome(
        self, handle: ExecutionHandle, timeout_ms: int
    ) -> ExecutionOutcome: ...
