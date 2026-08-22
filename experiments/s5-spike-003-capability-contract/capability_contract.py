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
    correlation_id: str


@dataclass(frozen=True)
class InvocationHandle:
    provider_ref: str
    native_id: str


class ResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True)
class CapabilityResult:
    status: ResultStatus
    correlation_id: str
    output: dict[str, Any] | None = None
    error_code: str | None = None
    message: str | None = None


class CapabilityProvider(Protocol):
    """Provider boundary permits non-synchronous native interaction models."""

    provider_ref: str

    def start(self, request: CapabilityRequest) -> InvocationHandle: ...

    def result(self, handle: InvocationHandle) -> CapabilityResult: ...
