"""Spike-only Agent Instance object model; not a production contract."""

from dataclasses import dataclass, field
from enum import StrEnum


class DesiredLifecycle(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True)
class AgentDefinition:
    definition_id: str
    version: str


@dataclass(frozen=True)
class AgentInstance:
    instance_id: str
    definition_id: str
    definition_version: str
    desired_lifecycle: DesiredLifecycle
    runtime_binding_id: str


@dataclass(frozen=True)
class RuntimeBinding:
    binding_id: str
    instance_id: str
    provider_id: str
    provider_config: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeRealization:
    realization_id: str
    binding_id: str
    native_kind: str
    native_id: str
    revision: int


class ExperimentalRuntimeProvider:
    """Provider-owned mapping from bindings to native realizations."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        self._realizations: dict[str, list[RuntimeRealization]] = {}

    def realize(
        self,
        binding: RuntimeBinding,
        *,
        realization_id: str,
        native_kind: str,
        native_id: str,
    ) -> RuntimeRealization:
        if binding.provider_id != self.provider_id:
            raise ValueError("binding belongs to a different provider")
        history = self._realizations.setdefault(binding.binding_id, [])
        realization = RuntimeRealization(
            realization_id=realization_id,
            binding_id=binding.binding_id,
            native_kind=native_kind,
            native_id=native_id,
            revision=len(history) + 1,
        )
        history.append(realization)
        return realization

    def active(self, binding: RuntimeBinding) -> tuple[RuntimeRealization, ...]:
        return tuple(self._realizations.get(binding.binding_id, ()))

    def replace(
        self,
        binding: RuntimeBinding,
        *,
        realization_id: str,
        native_kind: str,
        native_id: str,
    ) -> RuntimeRealization:
        self._realizations[binding.binding_id] = []
        return self.realize(
            binding,
            realization_id=realization_id,
            native_kind=native_kind,
            native_id=native_id,
        )
