"""Feature-local Native application adapter over the durable Runtime Manager."""

from __future__ import annotations

from dataclasses import dataclass

from agent_operator.execution_coordinator import InternalExecutionEnvelope
from agent_operator.runtime_identity_translation import (
    PlacementDecision,
    PlacementRequest,
    translate_native_identity,
)
from agent_operator.runtime_manager import (
    ReconciliationFact,
    RuntimeManager,
    ScopedRuntimeCommand,
)
from agent_operator.runtime_provider_factory import RuntimeProviderKind


class NativeRuntimeAdapterError(ValueError):
    """Sanitized assembly-boundary rejection."""


@dataclass(frozen=True, slots=True)
class NativeRuntimeAssembly:
    envelope: InternalExecutionEnvelope
    placement_request: PlacementRequest
    placement_decision: PlacementDecision
    command: ScopedRuntimeCommand


class NativeRuntimeApplicationAdapter:
    provider_kind = RuntimeProviderKind.NATIVE

    def __init__(self, manager: RuntimeManager) -> None:
        self._manager = manager

    def apply(self, value: NativeRuntimeAssembly) -> ReconciliationFact:
        identity = translate_native_identity(
            value.placement_request,
            value.placement_decision,
            authorized_scope=value.command.scope,
        )
        if value.envelope.selected_instance_id.value != identity.agent_instance_id:
            raise NativeRuntimeAdapterError("AGENT_INSTANCE_IDENTITY_MISMATCH")
        if value.command.desired.runtime_instance_id != identity.runtime_instance_id:
            raise NativeRuntimeAdapterError("RUNTIME_INSTANCE_IDENTITY_MISMATCH")
        if value.command.placement_reference != identity.placement_id:
            raise NativeRuntimeAdapterError("PLACEMENT_IDENTITY_MISMATCH")
        self._manager.request(value.command, authorized_scope=identity.scope)
        return self._manager.reconcile(
            identity.runtime_instance_id, authorized_scope=identity.scope
        )
