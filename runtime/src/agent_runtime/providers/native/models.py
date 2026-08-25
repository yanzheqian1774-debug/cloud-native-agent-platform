"""Typed internal values for the Native Runtime Provider candidate.

These values are provider-local implementation details. They are not a public
API, wire schema, CRD, or frozen Runtime Contract.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class DiagnosticReason(StrEnum):
    """Stable provider-local diagnostic reasons."""

    EXACT_COMPATIBILITY_MATCH = "EXACT_COMPATIBILITY_MATCH"
    EXPLICIT_DEGRADED_MODE_ACCEPTED = "EXPLICIT_DEGRADED_MODE_ACCEPTED"
    PLATFORM_EXECUTION_IDENTITY_MISSING = "PLATFORM_EXECUTION_IDENTITY_MISSING"
    RUNTIME_IDENTITY_MISSING = "RUNTIME_IDENTITY_MISSING"
    RUNTIME_VERSION_MISSING = "RUNTIME_VERSION_MISSING"
    RUNTIME_TARGET_UNSUPPORTED = "RUNTIME_TARGET_UNSUPPORTED"
    RUNTIME_VERSION_UNSUPPORTED = "RUNTIME_VERSION_UNSUPPORTED"
    RUNTIME_PROFILE_UNSUPPORTED = "RUNTIME_PROFILE_UNSUPPORTED"
    PROVIDER_PACKAGE_MISMATCH = "PROVIDER_PACKAGE_MISMATCH"
    CORE_VERSION_INCOMPATIBLE = "CORE_VERSION_INCOMPATIBLE"
    IMPLICIT_DEGRADED_MODE_REJECTED = "IMPLICIT_DEGRADED_MODE_REJECTED"
    DEGRADED_MODE_NOT_EVIDENCED = "DEGRADED_MODE_NOT_EVIDENCED"
    BINDING_CONFIGURATION_UNSUPPORTED = "BINDING_CONFIGURATION_UNSUPPORTED"
    BINDING_SECRET_VALUE_PROHIBITED = "BINDING_SECRET_VALUE_PROHIBITED"
    NATIVE_ID_SUBSTITUTION_REJECTED = "NATIVE_ID_SUBSTITUTION_REJECTED"
    NATIVE_INVOCATION_ID_DUPLICATE = "NATIVE_INVOCATION_ID_DUPLICATE"
    INVOCATION_FAILED = "INVOCATION_FAILED"
    INVOCATION_TIMEOUT_AMBIGUOUS = "INVOCATION_TIMEOUT_AMBIGUOUS"
    RESULT_NOT_FOUND = "RESULT_NOT_FOUND"
    OPERATION_NOT_SUPPORTED = "OPERATION_NOT_SUPPORTED"
    CLEANUP_COMPLETED = "CLEANUP_COMPLETED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


class CompatibilityMode(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    DEGRADED = "DEGRADED"
    REJECTED = "REJECTED"


class SupportState(StrEnum):
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_YET_PROVEN = "NOT_YET_PROVEN"


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"


class ReadinessState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class ExecutionState(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProviderPackageIdentity:
    distribution: str
    version: str
    module: str


@dataclass(frozen=True)
class RuntimeTargetIdentity:
    name: str
    exact_version: str | None
    profile: str

    @property
    def target(self) -> str:
        return f"{self.name}:{self.exact_version}:{self.profile}"


@dataclass(frozen=True)
class DegradedModeRequest:
    requested: bool = False
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompatibilityRequest:
    provider_package: ProviderPackageIdentity
    runtime_target: RuntimeTargetIdentity
    core_version: str
    platform_execution_identity: str
    degraded: DegradedModeRequest = field(default_factory=DegradedModeRequest)


@dataclass(frozen=True)
class CompatibilityDecision:
    accepted: bool
    may_invoke: bool
    mode: CompatibilityMode
    reason: DiagnosticReason
    platform_execution_identity: str
    requested_runtime: RuntimeTargetIdentity
    effective_runtime: RuntimeTargetIdentity | None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class DesiredRuntimeBinding:
    runtime_target: RuntimeTargetIdentity
    configuration: Mapping[str, str]


@dataclass(frozen=True)
class EffectiveRuntimeBinding:
    runtime_target: RuntimeTargetIdentity
    configuration: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BindingEvidence:
    desired: DesiredRuntimeBinding
    effective: EffectiveRuntimeBinding
    redacted_desired_configuration: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ProviderExecutionRequest:
    platform_execution_identity: str
    input: str
    compatibility: CompatibilityRequest
    desired_binding: DesiredRuntimeBinding
    claimed_native_invocation_id: str | None = None


@dataclass(frozen=True)
class NativeInvocation:
    output: str
    native_invocation_id: str | None = None


@dataclass(frozen=True)
class ExecutionCorrelation:
    platform_execution_identity: str
    native_invocation_id: str | None


@dataclass(frozen=True)
class ExecutionEvidence:
    state: ExecutionState
    correlation: ExecutionCorrelation
    compatibility: CompatibilityDecision
    binding: BindingEvidence | None
    output: str | None
    reason: DiagnosticReason
    diagnostic: str


@dataclass(frozen=True)
class HealthInformation:
    state: HealthState
    reason: str


@dataclass(frozen=True)
class ReadinessInformation:
    state: ReadinessState
    reason: str


@dataclass(frozen=True)
class RuntimeInformation:
    provider_package: ProviderPackageIdentity
    runtime_target: RuntimeTargetIdentity
    features: tuple[str, ...]
    limitations: tuple[str, ...]
    certification_state: str


@dataclass(frozen=True)
class LifecycleResult:
    operation: str
    state: SupportState
    platform_execution_identity: str
    reason: DiagnosticReason


@dataclass(frozen=True)
class CleanupResult:
    state: SupportState
    platform_execution_identity: str
    reason: DiagnosticReason
