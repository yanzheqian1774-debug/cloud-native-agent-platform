"""Immutable domain values for the internal v0.2 Core prototype.

These types are intentionally independent of Kubernetes, HTTP, and runtime-
provider implementations. Their serialization is internal and not frozen.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import NewType
from uuid import uuid4

from .errors import (
    InvalidBindingError,
    InvalidDomainValueError,
    InvalidNativeEvidenceError,
)

OpaqueIdGenerator = Callable[[], str]
ConfigurationScalar = str | int | float | bool | None


def _required(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDomainValueError(f"{field_name} must be a non-empty string")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _redacted_configuration(
    value: Mapping[str, ConfigurationScalar],
) -> Mapping[str, ConfigurationScalar]:
    blocked_fragments = ("secret", "token", "password", "credential", "api_key")
    result: dict[str, ConfigurationScalar] = {}
    for key, item in value.items():
        _required(key, "configuration key")
        if any(fragment in key.casefold() for fragment in blocked_fragments):
            raise InvalidBindingError("configuration contains a secret-shaped key")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise InvalidBindingError("configuration values must be JSON scalars")
        result[key] = item
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class AgentDefinitionRef:
    namespace: str
    name: str

    def __post_init__(self) -> None:
        _required(self.namespace, "definition namespace")
        _required(self.name, "definition name")


@dataclass(frozen=True, slots=True)
class AgentInstanceId:
    value: str

    def __post_init__(self) -> None:
        _required(self.value, "instance ID")

    def __str__(self) -> str:
        return f"AgentInstanceId({self.value[:8]}...)"


@dataclass(frozen=True, slots=True)
class PlatformExecutionIdentity:
    value: str

    def __post_init__(self) -> None:
        _required(self.value, "execution identity")

    def __str__(self) -> str:
        return f"PlatformExecutionIdentity({self.value[:8]}...)"


@dataclass(frozen=True, slots=True)
class NativeCorrelationId:
    value: str

    def __post_init__(self) -> None:
        _required(self.value, "native correlation ID")


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    binding_id: str
    provider_ref: str
    mode: str
    package_ref: str | None = None
    configuration: Mapping[str, ConfigurationScalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.binding_id, "binding ID")
        _required(self.provider_ref, "provider reference")
        _required(self.mode, "binding mode")
        if self.package_ref is not None:
            _required(self.package_ref, "package reference")
        object.__setattr__(
            self, "configuration", _redacted_configuration(self.configuration)
        )


@dataclass(frozen=True, slots=True)
class DesiredRuntimeBinding:
    value: RuntimeBinding

    def __post_init__(self) -> None:
        if not isinstance(self.value, RuntimeBinding):
            raise InvalidBindingError("desired Runtime Binding has an invalid value")


@dataclass(frozen=True, slots=True)
class EffectiveRuntimeBinding:
    value: RuntimeBinding
    resolved_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, RuntimeBinding):
            raise InvalidBindingError("effective Runtime Binding has an invalid value")
        if not isinstance(self.resolved_at, datetime):
            raise InvalidBindingError("resolved_at must be a datetime")


@dataclass(frozen=True, slots=True)
class NativeRealizationEvidence:
    system: str
    kind: str
    correlation_id: NativeCorrelationId
    observed_at: datetime
    active: bool = True

    def __post_init__(self) -> None:
        _required(self.system, "native evidence system")
        _required(self.kind, "native evidence kind")
        if not isinstance(self.correlation_id, NativeCorrelationId):
            raise InvalidNativeEvidenceError(
                "native evidence requires a native correlation ID"
            )
        if not isinstance(self.observed_at, datetime):
            raise InvalidNativeEvidenceError("observed_at must be a datetime")


@dataclass(frozen=True, slots=True)
class SelectedInstanceEvidence:
    definition_ref: AgentDefinitionRef
    instance_id: AgentInstanceId
    authority: str
    reason: str | None = None
    selected_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.definition_ref, AgentDefinitionRef):
            raise InvalidDomainValueError("selection requires a Definition reference")
        if not isinstance(self.instance_id, AgentInstanceId):
            raise InvalidDomainValueError("selection requires an Instance ID")
        _required(self.authority, "selection authority")
        if self.reason is not None:
            _required(self.reason, "selection reason")


@dataclass(frozen=True, slots=True)
class AgentDefinitionProjection:
    """Definition-facing compatibility input; never an Instance identity."""

    definition_ref: AgentDefinitionRef
    desired_runtime_binding: DesiredRuntimeBinding
    compatibility_mode: str = "LEGACY_AGENT_V1ALPHA1"
    source_uid: str | None = None
    source_generation: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.definition_ref, AgentDefinitionRef):
            raise InvalidDomainValueError("projection requires a Definition reference")
        if not isinstance(self.desired_runtime_binding, DesiredRuntimeBinding):
            raise InvalidBindingError("projection requires a desired Runtime Binding")
        _required(self.compatibility_mode, "compatibility mode")
        if self.source_uid is not None:
            _required(self.source_uid, "source UID")
        if self.source_generation is not None and self.source_generation < 0:
            raise InvalidDomainValueError("source generation cannot be negative")


@dataclass(frozen=True, slots=True)
class ExecutionIdentityRecord:
    execution_id: PlatformExecutionIdentity
    root_execution_id: PlatformExecutionIdentity
    parent_execution_id: PlatformExecutionIdentity | None
    attempt: int
    native_correlations: tuple[NativeCorrelationId, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, PlatformExecutionIdentity):
            raise InvalidDomainValueError(
                "execution record requires a Platform execution ID"
            )
        if not isinstance(self.root_execution_id, PlatformExecutionIdentity):
            raise InvalidDomainValueError(
                "root execution ID must be a Platform execution ID"
            )
        if self.parent_execution_id is not None and not isinstance(
            self.parent_execution_id, PlatformExecutionIdentity
        ):
            raise InvalidDomainValueError(
                "parent execution ID must be a Platform execution ID"
            )
        if self.attempt < 1:
            raise InvalidDomainValueError("execution attempt must be positive")
        if not all(
            isinstance(item, NativeCorrelationId) for item in self.native_correlations
        ):
            raise InvalidNativeEvidenceError(
                "execution correlations must contain native correlation IDs"
            )
        if not isinstance(self.created_at, datetime):
            raise InvalidDomainValueError("execution created_at must be a datetime")


class AgentInstanceLifecycle(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True, slots=True)
class AgentInstance:
    instance_id: AgentInstanceId
    definition_ref: AgentDefinitionRef
    lifecycle: AgentInstanceLifecycle
    desired_runtime_binding: DesiredRuntimeBinding
    effective_runtime_binding: EffectiveRuntimeBinding | None = None
    realizations: tuple[NativeRealizationEvidence, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, AgentInstanceId):
            raise InvalidDomainValueError("Agent Instance requires an Instance ID")
        if not isinstance(self.definition_ref, AgentDefinitionRef):
            raise InvalidDomainValueError(
                "Agent Instance requires a Definition reference"
            )
        if not isinstance(self.lifecycle, AgentInstanceLifecycle):
            raise InvalidDomainValueError("Agent Instance requires a lifecycle value")
        if not isinstance(self.desired_runtime_binding, DesiredRuntimeBinding):
            raise InvalidBindingError(
                "Agent Instance requires a desired Runtime Binding"
            )
        if self.effective_runtime_binding is not None and not isinstance(
            self.effective_runtime_binding, EffectiveRuntimeBinding
        ):
            raise InvalidBindingError(
                "effective Runtime Binding has the wrong ownership type"
            )
        if not all(
            isinstance(item, NativeRealizationEvidence) for item in self.realizations
        ):
            raise InvalidNativeEvidenceError(
                "realizations must contain native evidence"
            )

    def with_realization(
        self, evidence: NativeRealizationEvidence, *, updated_at: datetime
    ) -> AgentInstance:
        return replace(
            self, realizations=(*self.realizations, evidence), updated_at=updated_at
        )

    def with_effective_binding(
        self, binding: EffectiveRuntimeBinding, *, updated_at: datetime
    ) -> AgentInstance:
        return replace(self, effective_runtime_binding=binding, updated_at=updated_at)


def mint_agent_instance_id(
    generator: OpaqueIdGenerator | None = None,
) -> AgentInstanceId:
    """Mint an opaque Platform-owned Instance ID."""
    return AgentInstanceId((generator or (lambda: str(uuid4())))())


def mint_platform_execution_identity(
    generator: OpaqueIdGenerator | None = None,
) -> PlatformExecutionIdentity:
    """Mint an opaque Platform-owned execution identity."""
    return PlatformExecutionIdentity((generator or (lambda: str(uuid4())))())


# Documents that external Task targets remain Definition-facing without making
# this internal projection a public Task DTO.
DefinitionFacingTaskTarget = NewType("DefinitionFacingTaskTarget", AgentDefinitionRef)
