"""Feature-local OpenClaw adapter over the exact provider-local implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agent_runtime.providers.openclaw import OpenClawRuntimeProvider
from agent_runtime.providers.openclaw.models import (
    HealthState,
    LifecycleState,
    OpenClawError,
    ReadinessState,
    RuntimeMode,
    SessionAffinity,
)

from agent_operator.execution_coordinator import InternalExecutionEnvelope
from agent_operator.openclaw_runtime_driver import (
    PlacementDecision,
    PlacementRequest,
    translate_openclaw_placement,
)
from agent_operator.runtime_manager import (
    CommandResult,
    ExternalCorrelation,
    ObservationId,
    ReconciliationFact,
    RuntimeHealth,
    RuntimeObservation,
    RuntimeObservedStateKind,
    RuntimeOperation,
    RuntimeReadiness,
    ScopedRuntimeCommand,
)
from agent_operator.runtime_provider_factory import RuntimeProviderKind


class OpenClawRuntimeAdapterError(ValueError):
    """Sanitized assembly-boundary rejection."""


@dataclass(frozen=True, slots=True)
class OpenClawRuntimeAssembly:
    envelope: InternalExecutionEnvelope
    placement_request: PlacementRequest
    placement_decision: PlacementDecision
    command: ScopedRuntimeCommand
    mode: RuntimeMode
    session_affinity: SessionAffinity
    observed_at: datetime
    session_reference: str | None = None


class OpenClawRuntimeApplicationAdapter:
    provider_kind = RuntimeProviderKind.OPENCLAW

    def __init__(self, provider: OpenClawRuntimeProvider) -> None:
        self._provider = provider
        self._observed_commands: set[str] = set()

    def apply(self, value: OpenClawRuntimeAssembly) -> ReconciliationFact:
        command = value.command
        placement = translate_openclaw_placement(
            value.placement_request,
            value.placement_decision,
            authorized_scope=command.scope,
            workflow_run_id=str(value.placement_request.workflow_run_id),
            task_run_id=str(value.placement_request.task_run_id),
            attempt_id=str(value.placement_request.attempt_id),
            agent_instance_id=str(value.placement_request.agent_instance_id),
            generation=command.desired.desired_generation,
            mode=value.mode,
            session_affinity=value.session_affinity,
            session_reference=value.session_reference,
        )
        if (
            value.envelope.selected_instance_id.value
            != placement.linkage.agent_instance_id
        ):
            raise OpenClawRuntimeAdapterError("AGENT_INSTANCE_IDENTITY_MISMATCH")
        if (
            command.desired.runtime_instance_id.value
            != placement.binding.runtime_instance_id
        ):
            raise OpenClawRuntimeAdapterError("RUNTIME_INSTANCE_IDENTITY_MISMATCH")
        if command.placement_reference != placement.binding.placement_id:
            raise OpenClawRuntimeAdapterError("PLACEMENT_IDENTITY_MISMATCH")
        command_key = str(command.desired.command_id)
        try:
            if command_key in self._observed_commands:
                observed = self._provider.observe_runtime(
                    placement.binding, at=value.observed_at
                )
            elif command.operation is RuntimeOperation.START:
                try:
                    observed = self._provider.observe_runtime(
                        placement.binding, at=value.observed_at
                    )
                except OpenClawError as exc:
                    if str(exc) != "OBSERVATION_MISSING":
                        raise
                    observed = self._provider.start(
                        placement.binding, at=value.observed_at
                    )
            elif command.operation in {RuntimeOperation.STOP, RuntimeOperation.CANCEL}:
                observed = self._provider.stop(placement.binding, at=value.observed_at)
            elif command.operation is RuntimeOperation.REPLACE:
                observed = self._provider.replace(
                    placement.binding, at=value.observed_at
                )
            elif command.operation is RuntimeOperation.OBSERVE:
                observed = self._provider.observe_runtime(
                    placement.binding, at=value.observed_at
                )
            else:  # pragma: no cover - enum is closed
                raise OpenClawRuntimeAdapterError("OPERATION_NOT_SUPPORTED")
        except OpenClawError as exc:
            code = str(exc)
            result = (
                CommandResult.STALE
                if code == "OBSERVATION_STALE"
                else CommandResult.UNKNOWN
                if code in {"OBSERVATION_MISSING", "OBSERVATION_UNKNOWN"}
                else CommandResult.RECOVERY_REQUIRED
            )
            return ReconciliationFact(
                command, result, value.observed_at, reason_code=code
            )
        except Exception:
            return ReconciliationFact(
                command,
                CommandResult.RECOVERY_REQUIRED,
                value.observed_at,
                reason_code="PROVIDER_EFFECT_AMBIGUOUS",
            )
        normalized = _normalize(command, observed)
        self._observed_commands.add(command_key)
        return ReconciliationFact(
            command,
            CommandResult.OBSERVED,
            value.observed_at,
            normalized,
            "EXTERNAL_STATE_OBSERVED",
        )


def _normalize(command: ScopedRuntimeCommand, observed) -> RuntimeObservation:
    states = {
        LifecycleState.PENDING: RuntimeObservedStateKind.PENDING,
        LifecycleState.RUNNING: RuntimeObservedStateKind.RUNNING,
        LifecycleState.STOPPED: RuntimeObservedStateKind.STOPPED,
        LifecycleState.TERMINATED: RuntimeObservedStateKind.TERMINATED,
        LifecycleState.FAILED: RuntimeObservedStateKind.FAILED,
        LifecycleState.UNKNOWN: RuntimeObservedStateKind.UNKNOWN,
    }
    health = {
        HealthState.HEALTHY: RuntimeHealth.HEALTHY,
        HealthState.DEGRADED: RuntimeHealth.DEGRADED,
        HealthState.UNHEALTHY: RuntimeHealth.UNHEALTHY,
        HealthState.UNKNOWN: RuntimeHealth.UNKNOWN,
    }
    readiness = {
        ReadinessState.READY: RuntimeReadiness.READY,
        ReadinessState.NOT_READY: RuntimeReadiness.NOT_READY,
        ReadinessState.UNKNOWN: RuntimeReadiness.UNKNOWN,
    }
    return RuntimeObservation(
        ObservationId(f"{command.desired.command_id}-openclaw"),
        command.desired.runtime_instance_id,
        command.desired.desired_generation,
        states[observed.state],
        health[observed.health],
        readiness[observed.readiness],
        observed.observed_at,
        observed.freshness_deadline,
        ExternalCorrelation("openclaw", "gateway", observed.correlation.gateway_id),
        None,
        ("OPENCLAW_CORRELATION_OPAQUE",),
    )
