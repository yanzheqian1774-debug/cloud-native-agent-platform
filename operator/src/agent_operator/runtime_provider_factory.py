"""Explicit runtime-provider selection and inert Track-270 registration data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class RuntimeProviderFactoryError(ValueError):
    """Stable fail-closed configuration error."""


class RuntimeProviderKind(StrEnum):
    NATIVE = "native"
    OPENCLAW = "openclaw"


@dataclass(frozen=True, slots=True)
class RuntimeProviderRegistration:
    provider: RuntimeProviderKind
    adapter_type: str
    provider_package: str
    runtime_target: str
    exact_version: str
    registration_version: str = "v0.2.3-a0"


REGISTRATIONS = (
    RuntimeProviderRegistration(
        RuntimeProviderKind.NATIVE,
        "agent_operator.native_runtime_adapter.NativeRuntimeApplicationAdapter",
        "cloud-native-agent-platform.native-runtime",
        "native",
        "0.1.0+e6a162f",
    ),
    RuntimeProviderRegistration(
        RuntimeProviderKind.OPENCLAW,
        "agent_operator.openclaw_runtime_adapter.OpenClawRuntimeApplicationAdapter",
        "openclaw",
        "openclaw",
        "2026.7.1-2",
    ),
)


class RuntimeApplicationAdapter(Protocol):
    provider_kind: RuntimeProviderKind


class RuntimeProviderFactory:
    """Resolve exactly one explicitly configured runtime provider."""

    def __init__(
        self,
        *,
        native: RuntimeApplicationAdapter | None = None,
        openclaw: RuntimeApplicationAdapter | None = None,
    ) -> None:
        self._adapters = {
            RuntimeProviderKind.NATIVE: native,
            RuntimeProviderKind.OPENCLAW: openclaw,
        }

    def create(self, configured: tuple[str, ...]) -> RuntimeApplicationAdapter:
        if not configured:
            raise RuntimeProviderFactoryError("RUNTIME_PROVIDER_MISSING")
        if len(configured) != 1:
            raise RuntimeProviderFactoryError("RUNTIME_PROVIDER_AMBIGUOUS")
        try:
            kind = RuntimeProviderKind(configured[0])
        except (TypeError, ValueError):
            raise RuntimeProviderFactoryError("RUNTIME_PROVIDER_UNKNOWN") from None
        adapter = self._adapters[kind]
        if adapter is None:
            raise RuntimeProviderFactoryError("RUNTIME_PROVIDER_NOT_REGISTERED")
        if adapter.provider_kind is not kind:
            raise RuntimeProviderFactoryError("RUNTIME_PROVIDER_REGISTRATION_CONFLICT")
        return adapter

    @staticmethod
    def registrations() -> tuple[RuntimeProviderRegistration, ...]:
        return REGISTRATIONS
