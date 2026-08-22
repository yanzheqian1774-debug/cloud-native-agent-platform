"""Experimental provider-neutral Capability Contract candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


@dataclass(frozen=True)
class CapabilityIdentity:
    capability_id: str
    version: str


@dataclass(frozen=True)
class Capability:
    identity: CapabilityIdentity
    description: str
    input_schema_ref: str
    output_schema_ref: str
    risk_classification_ref: str | None = None


@dataclass(frozen=True)
class CapabilityBinding:
    capability: CapabilityIdentity
    provider_ref: str
    operation: str


@dataclass(frozen=True)
class CapabilityRequest:
    capability: CapabilityIdentity
    operation: str
    input: dict[str, Any]
    execution: ExecutionIdentity


@dataclass(frozen=True)
class ExecutionIdentity:
    """Platform-owned identity created before authorization/provider work."""

    invocation_id: str
    correlation_id: str


@dataclass(frozen=True)
class InvocationHandle:
    provider_ref: str
    native_id: str


class ResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"


class ErrorClass(StrEnum):
    AUTHORIZATION_DENIED = "authorization_denied"
    INPUT_INVALID = "input_invalid"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_PROTOCOL_ERROR = "provider_protocol_error"
    REMOTE_EXECUTION_FAILURE = "remote_execution_failure"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CapabilityResult:
    status: ResultStatus
    invocation_id: str
    correlation_id: str
    output: dict[str, Any] | None = None
    error_class: ErrorClass | None = None
    message: str | None = None
    diagnostic_ref: str | None = None


@dataclass(frozen=True)
class CapabilitySubmission:
    """Accepted work may contain an inline outcome or require observation."""

    execution: ExecutionIdentity
    handle: InvocationHandle
    outcome: CapabilityResult | None = None


class CapabilityProvider(Protocol):
    """Provider boundary permits non-synchronous native interaction models."""

    provider_ref: str

    def submit(self, request: CapabilityRequest) -> CapabilitySubmission: ...

    def observe(self, handle: InvocationHandle) -> CapabilityResult: ...
