"""Minimal generic execution concepts for S5-SPIKE-002 only.

These names are experimental evidence tools, not production Contract vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class EventKind(StrEnum):
    ACCEPTED = "accepted"
    TERMINAL = "terminal"


class OutcomeKind(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    UNKNOWN = "unknown"


class TruthValue(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ExecutionRequest:
    input_text: str


@dataclass(frozen=True)
class ExecutionHandle:
    correlation_id: str


@dataclass(frozen=True)
class ExecutionEvent:
    kind: EventKind
    correlation_id: str
    observed_at_ms: int | None = None
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionOutcome:
    kind: OutcomeKind
    correlation_id: str
    message: str | None = None
    observed_at_ms: int | None = None


@dataclass(frozen=True)
class Observation:
    name: str
    value: TruthValue
    reason: str


class ExperimentalProvider(Protocol):
    def observe(self) -> tuple[Observation, ...]: ...

    def submit(
        self, request: ExecutionRequest
    ) -> tuple[ExecutionHandle, ExecutionEvent]: ...

    def await_outcome(
        self, handle: ExecutionHandle, timeout_ms: int
    ) -> tuple[ExecutionEvent, ExecutionOutcome]: ...
