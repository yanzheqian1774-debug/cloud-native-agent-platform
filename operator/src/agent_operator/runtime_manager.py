"""Persistence-first Native Runtime Manager with restart-safe reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from agent_core.execution_contract import (
    CommandId,
    CommandResult,
    ExternalCorrelation,
    Generation,
    ObservationId,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeHealth,
    RuntimeInstanceId,
    RuntimeObservation,
    RuntimeObservedStateKind,
    RuntimeReadiness,
    ScopeIdentity,
)
from agent_core.runtime_control import (
    ReconciliationFact,
    RuntimeControlError,
    RuntimeOperation,
    ScopedRuntimeCommand,
    accepts_new_assignment,
    classify_reconciliation,
)
from agent_runtime.providers.native.models import (
    NativeLifecycleObservation,
    NativeLifecycleState,
)

__all__ = [
    "CommandId",
    "CommandResult",
    "Generation",
    "InMemoryRuntimeControlRepository",
    "RuntimeControlError",
    "RuntimeDesiredState",
    "RuntimeDesiredStateKind",
    "RuntimeInstanceId",
    "RuntimeManager",
    "RuntimeOperation",
    "ScopeIdentity",
    "ScopedRuntimeCommand",
    "accepts_new_assignment",
]


class RuntimeControlRepository(Protocol):
    def append_desired(self, command: ScopedRuntimeCommand) -> None: ...
    def desired(
        self, runtime_instance_id: RuntimeInstanceId
    ) -> ScopedRuntimeCommand | None: ...
    def append_fact(self, fact: ReconciliationFact) -> None: ...
    def facts(
        self, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[ReconciliationFact, ...]: ...


class NativeLifecyclePort(Protocol):
    def start_runtime(self, platform_execution_identity: str): ...
    def stop_runtime(self, platform_execution_identity: str): ...
    def replace(self, platform_runtime_identity: str): ...
    def observe_runtime(
        self, platform_runtime_identity: str
    ) -> NativeLifecycleObservation | None: ...


class InMemoryRuntimeControlRepository:
    """Focused conformance adapter; production authority must be PostgreSQL-owned."""

    def __init__(self) -> None:
        self._desired: dict[RuntimeInstanceId, ScopedRuntimeCommand] = {}
        self._facts: dict[RuntimeInstanceId, list[ReconciliationFact]] = {}

    def append_desired(self, command: ScopedRuntimeCommand) -> None:
        runtime_id = command.desired.runtime_instance_id
        existing = self._desired.get(runtime_id)
        if existing is not None:
            if command == existing:
                return
            if (
                command.desired.desired_generation.value
                <= existing.desired.desired_generation.value
            ):
                raise RuntimeControlError("DESIRED_GENERATION_NOT_MONOTONIC")
        self._desired[runtime_id] = command

    def desired(
        self, runtime_instance_id: RuntimeInstanceId
    ) -> ScopedRuntimeCommand | None:
        return self._desired.get(runtime_instance_id)

    def append_fact(self, fact: ReconciliationFact) -> None:
        self._facts.setdefault(fact.command.desired.runtime_instance_id, []).append(
            fact
        )

    def facts(
        self, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[ReconciliationFact, ...]:
        return tuple(self._facts.get(runtime_instance_id, ()))


class RuntimeManager:
    def __init__(
        self,
        *,
        repository: RuntimeControlRepository,
        provider: NativeLifecyclePort,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        freshness: timedelta = timedelta(seconds=30),
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._clock = clock
        self._freshness = freshness

    def request(
        self, command: ScopedRuntimeCommand, *, authorized_scope: ScopeIdentity
    ) -> ReconciliationFact:
        if command.scope != authorized_scope:
            raise RuntimeControlError("COMMAND_SCOPE_MISMATCH")
        # This is intentionally the first mutation/effect: intent before effect.
        self._repository.append_desired(command)
        fact = ReconciliationFact(
            command,
            CommandResult.REQUESTED,
            self._clock(),
            reason_code="DESIRED_PERSISTED",
        )
        self._repository.append_fact(fact)
        return fact

    def reconcile(
        self, runtime_instance_id: RuntimeInstanceId, *, authorized_scope: ScopeIdentity
    ) -> ReconciliationFact:
        command = self._repository.desired(runtime_instance_id)
        if command is None:
            raise RuntimeControlError("DESIRED_COMMAND_NOT_FOUND")
        if command.scope != authorized_scope:
            raise RuntimeControlError("COMMAND_SCOPE_MISMATCH")
        now = self._clock()
        observed = self._provider.observe_runtime(str(runtime_instance_id))
        observation = self._normalize(command, observed, now)
        prior = self._repository.facts(runtime_instance_id)
        replacement_already_issued = any(
            fact.command.desired.command_id == command.desired.command_id
            and fact.result in {CommandResult.APPLIED, CommandResult.OBSERVED}
            for fact in prior
        )
        if (
            observation is not None
            and (
                command.operation is not RuntimeOperation.REPLACE
                or replacement_already_issued
            )
            and classify_reconciliation(command.desired, observation, at=now)
            is CommandResult.OBSERVED
        ):
            return self._append(
                command,
                CommandResult.OBSERVED,
                now,
                observation,
                "EXTERNAL_STATE_OBSERVED",
            )

        if prior and prior[-1].result in {
            CommandResult.UNKNOWN,
            CommandResult.STALE,
            CommandResult.RECOVERY_REQUIRED,
        }:
            return self._append(
                command,
                CommandResult.RECOVERY_REQUIRED,
                now,
                observation,
                "AMBIGUOUS_EFFECT_NOT_REISSUED",
            )
        try:
            if command.operation is RuntimeOperation.START:
                self._provider.start_runtime(str(runtime_instance_id))
            elif command.operation in {RuntimeOperation.STOP, RuntimeOperation.CANCEL}:
                self._provider.stop_runtime(str(runtime_instance_id))
            elif command.operation is RuntimeOperation.REPLACE:
                self._provider.replace(str(runtime_instance_id))
            elif command.operation is not RuntimeOperation.OBSERVE:
                raise RuntimeControlError("OPERATION_NOT_SUPPORTED")
        except Exception:  # provider payload is deliberately not propagated
            return self._append(
                command,
                CommandResult.RECOVERY_REQUIRED,
                now,
                observation,
                "PROVIDER_EFFECT_AMBIGUOUS",
            )
        observed = self._provider.observe_runtime(str(runtime_instance_id))
        observation = self._normalize(command, observed, now)
        result = classify_reconciliation(command.desired, observation, at=now)
        return self._append(
            command, result, now, observation, "EFFECT_APPLIED_AND_OBSERVED"
        )

    def _normalize(
        self,
        command: ScopedRuntimeCommand,
        native: NativeLifecycleObservation | None,
        now: datetime,
    ) -> RuntimeObservation | None:
        if native is None:
            return None
        states = {
            NativeLifecycleState.PENDING: RuntimeObservedStateKind.PENDING,
            NativeLifecycleState.RUNNING: RuntimeObservedStateKind.RUNNING,
            NativeLifecycleState.STOPPED: RuntimeObservedStateKind.STOPPED,
            NativeLifecycleState.TERMINATED: RuntimeObservedStateKind.TERMINATED,
            NativeLifecycleState.FAILED: RuntimeObservedStateKind.FAILED,
            NativeLifecycleState.UNKNOWN: RuntimeObservedStateKind.UNKNOWN,
        }
        state = states[native.state]
        correlation = None
        if native.native_correlation:
            correlation = ExternalCorrelation(
                "native", "runtime", native.native_correlation
            )
        fact_count = len(self._repository.facts(command.desired.runtime_instance_id))
        return RuntimeObservation(
            observation_id=ObservationId(
                f"{command.desired.command_id}-{fact_count + 1}"
            ),
            runtime_instance_id=command.desired.runtime_instance_id,
            observed_generation=command.desired.desired_generation,
            observed_state=state,
            health=RuntimeHealth.HEALTHY
            if state is RuntimeObservedStateKind.RUNNING
            else RuntimeHealth.UNKNOWN,
            readiness=RuntimeReadiness.READY
            if state is RuntimeObservedStateKind.RUNNING
            else RuntimeReadiness.NOT_READY,
            observed_at=now,
            freshness_deadline=now + self._freshness,
            provider_correlation=correlation,
            kubernetes_correlation=None,
            limitation_codes=("NATIVE_PROVIDER_OBSERVATION",),
        )

    def _append(
        self,
        command: ScopedRuntimeCommand,
        result: CommandResult,
        now: datetime,
        observation: RuntimeObservation | None,
        reason: str,
    ) -> ReconciliationFact:
        fact = ReconciliationFact(command, result, now, observation, reason)
        self._repository.append_fact(fact)
        return fact
