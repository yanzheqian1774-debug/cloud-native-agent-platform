"""Bounded, secret-free startup state for the IMPL-310 acceptance fixture."""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

STARTUP_STAGES = (
    "DATABASE_CONNECTION",
    "DATABASE_MIGRATION",
    "SAMPLE_PREPARATION",
    "AUTHORIZATION_PREPARATION",
    "TLS_CONFIGURATION",
    "LISTENER_READINESS",
)
EXCEPTION_CATEGORIES = {
    "NONE",
    "CONNECTION_ERROR",
    "DATABASE_ERROR",
    "TIMEOUT_ERROR",
    "FILESYSTEM_ERROR",
    "VALIDATION_ERROR",
    "TLS_ERROR",
    "UNKNOWN",
}
REASON_CODES = {
    "NONE",
    "DATABASE_CONNECTION_FAILED",
    "DATABASE_MIGRATION_FAILED",
    "SAMPLE_PREPARATION_FAILED",
    "AUTHORIZATION_PREPARATION_FAILED",
    "TLS_CONFIGURATION_FAILED",
    "LISTENER_READINESS_FAILED",
    "UNKNOWN",
}
_REASON_BY_STAGE = {stage: f"{stage}_FAILED" for stage in STARTUP_STAGES}


def exception_category(error: BaseException) -> str:
    """Map an exception chain to a fixed category without retaining its text."""
    current: BaseException | None = error
    for _ in range(8):
        if current is None:
            break
        module = type(current).__module__
        name = type(current).__name__
        if isinstance(current, ssl.SSLError):
            return "TLS_ERROR"
        if isinstance(current, TimeoutError):
            return "TIMEOUT_ERROR"
        if isinstance(current, ConnectionError):
            return "CONNECTION_ERROR"
        if module.startswith("psycopg"):
            if name in {"OperationalError", "InterfaceError"}:
                return "CONNECTION_ERROR"
            return "DATABASE_ERROR"
        if isinstance(current, OSError):
            return "FILESYSTEM_ERROR"
        if isinstance(current, ValueError):
            return "VALIDATION_ERROR"
        current = current.__cause__ or current.__context__
    return "UNKNOWN"


@dataclass
class BoundedStartupStatus:
    path: Path
    last_started_stage: str = "NONE"
    last_completed_stage: str = "NONE"
    state: str = "STARTING"
    category: str = "NONE"
    reason_code: str = "NONE"
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def begin(self, stage: str) -> None:
        if stage not in STARTUP_STAGES:
            raise ValueError("STARTUP_STAGE_INVALID")
        with self._lock:
            if self.state in {"FAILED", "READY"}:
                return
            self.last_started_stage = stage
            self._write()

    def complete(self, stage: str) -> None:
        if stage not in STARTUP_STAGES:
            raise ValueError("STARTUP_STAGE_INVALID")
        with self._lock:
            if self.state in {"FAILED", "READY"}:
                return
            if stage != self.last_started_stage:
                raise ValueError("STARTUP_STAGE_ORDER_INVALID")
            self.last_completed_stage = stage
            if stage == STARTUP_STAGES[-1]:
                self.state = "READY"
            self._write()

    def fail(self, error: BaseException) -> None:
        with self._lock:
            if self.state in {"FAILED", "READY"}:
                return
            self.state = "FAILED"
            self.category = exception_category(error)
            self.reason_code = _REASON_BY_STAGE.get(self.last_started_stage, "UNKNOWN")
            self._write()

    def _write(self) -> None:
        document = {
            "schemaVersion": "s5-v023-impl-310-fixture-startup.v1",
            "state": self.state,
            "lastStartedStage": self.last_started_stage,
            "lastCompletedStage": self.last_completed_stage,
            "exceptionCategory": (
                self.category if self.category in EXCEPTION_CATEGORIES else "UNKNOWN"
            ),
            "reasonCode": (
                self.reason_code if self.reason_code in REASON_CODES else "UNKNOWN"
            ),
        }
        temporary = self.path.with_name(f"{self.path.name}.tmp")
        temporary.write_text(json.dumps(document, sort_keys=True) + "\n")
        temporary.replace(self.path)
