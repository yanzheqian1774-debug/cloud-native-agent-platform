"""Experimental runtime-neutral Checkpoint A boundary."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class RuntimeState(StrEnum):
    """Small observational state set; not a production lifecycle."""

    ABSENT = "ABSENT"
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RuntimeRequest:
    input: str
    correlation_id: str


@dataclass(frozen=True)
class RuntimeResult:
    output: str
    correlation_id: str


@dataclass(frozen=True)
class RuntimeHealth:
    state: RuntimeState
    infrastructure_available: bool
    runtime_available: bool
    dependency_available: bool | None
    task_ready: bool | None
    detail: str


class ExperimentalProvider(Protocol):
    """Only operations required by Checkpoint A."""

    def provision(self) -> None: ...

    def invoke(self, request: RuntimeRequest) -> RuntimeResult: ...

    def health(self) -> RuntimeHealth: ...

    def cleanup(self) -> None: ...
