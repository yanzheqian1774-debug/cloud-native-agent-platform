"""Internal Native Runtime reconciliation policy built on the v0.2.3 contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from agent_core.execution_contract import (
    CommandResult,
    ExecutionContractError,
    Generation,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeObservation,
    RuntimeObservedStateKind,
    ScopeIdentity,
    current_observed_state,
)


class RuntimeControlError(ValueError):
    """Fail-closed runtime-control error containing no rejected payload."""


class RuntimeOperation(StrEnum):
    START = "START"
    STOP = "STOP"
    CANCEL = "CANCEL"
    REPLACE = "REPLACE"
    OBSERVE = "OBSERVE"


@dataclass(frozen=True, slots=True)
class ScopedRuntimeCommand:
    scope: ScopeIdentity
    desired: RuntimeDesiredState
    operation: RuntimeOperation
    authorization_reference: str
    placement_reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise RuntimeControlError("INVALID_SCOPE")
        if not isinstance(self.desired, RuntimeDesiredState):
            raise RuntimeControlError("INVALID_DESIRED_STATE")
        if not isinstance(self.operation, RuntimeOperation):
            raise RuntimeControlError("INVALID_OPERATION")
        expected = {
            RuntimeOperation.START: RuntimeDesiredStateKind.RUNNING,
            RuntimeOperation.STOP: RuntimeDesiredStateKind.STOPPED,
            RuntimeOperation.CANCEL: RuntimeDesiredStateKind.CANCELLED,
            RuntimeOperation.REPLACE: RuntimeDesiredStateKind.REPLACED,
            RuntimeOperation.OBSERVE: RuntimeDesiredStateKind.OBSERVE,
        }[self.operation]
        if self.desired.desired_state is not expected:
            raise RuntimeControlError("OPERATION_DESIRED_STATE_MISMATCH")
        for value in (self.authorization_reference, self.placement_reference):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeControlError("AUTHORITY_REFERENCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ReconciliationFact:
    command: ScopedRuntimeCommand
    result: CommandResult
    recorded_at: datetime
    observation: RuntimeObservation | None = None
    reason_code: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.result, CommandResult):
            raise RuntimeControlError("INVALID_COMMAND_RESULT")
        if self.recorded_at.tzinfo is None:
            raise RuntimeControlError("RECORDED_AT_MUST_BE_AWARE")
        object.__setattr__(self, "recorded_at", self.recorded_at.astimezone(UTC))
        if self.observation is not None:
            if (
                self.observation.runtime_instance_id
                != self.command.desired.runtime_instance_id
            ):
                raise RuntimeControlError("OBSERVATION_RUNTIME_MISMATCH")
            if (
                self.observation.observed_generation
                != self.command.desired.desired_generation
            ):
                raise RuntimeControlError("OBSERVATION_GENERATION_MISMATCH")


def next_desired_generation(previous: RuntimeDesiredState | None) -> Generation:
    """Mint only a generation; Product Runtime identity is always supplied."""
    return (
        Generation(1) if previous is None else previous.desired_generation.successor()
    )


def observation_matches_desired(
    desired: RuntimeDesiredState, observation: RuntimeObservation, *, at: datetime
) -> bool:
    if observation.runtime_instance_id != desired.runtime_instance_id:
        return False
    if observation.observed_generation != desired.desired_generation:
        return False
    state = current_observed_state(observation, at=at)
    expected = {
        RuntimeDesiredStateKind.RUNNING: {RuntimeObservedStateKind.RUNNING},
        RuntimeDesiredStateKind.STOPPED: {
            RuntimeObservedStateKind.STOPPED,
            RuntimeObservedStateKind.TERMINATED,
        },
        RuntimeDesiredStateKind.CANCELLED: {RuntimeObservedStateKind.TERMINATED},
        RuntimeDesiredStateKind.REPLACED: {
            RuntimeObservedStateKind.PENDING,
            RuntimeObservedStateKind.RUNNING,
        },
        RuntimeDesiredStateKind.OBSERVE: set(RuntimeObservedStateKind)
        - {RuntimeObservedStateKind.STALE},
    }[desired.desired_state]
    return state in expected


def classify_reconciliation(
    desired: RuntimeDesiredState,
    observation: RuntimeObservation | None,
    *,
    at: datetime,
    effect_was_ambiguous: bool = False,
) -> CommandResult:
    """Normalize convergence without claiming success from stale state."""
    if effect_was_ambiguous:
        return CommandResult.RECOVERY_REQUIRED
    state = current_observed_state(observation, at=at)
    if state is RuntimeObservedStateKind.UNKNOWN:
        return CommandResult.UNKNOWN
    if state is RuntimeObservedStateKind.STALE:
        return CommandResult.STALE
    if observation is None:  # defensive narrowing
        raise ExecutionContractError("OBSERVATION_REQUIRED")
    return (
        CommandResult.OBSERVED
        if observation_matches_desired(desired, observation, at=at)
        else CommandResult.APPLIED
    )


def accepts_new_assignment(
    desired: RuntimeDesiredState,
    observation: RuntimeObservation | None,
    *,
    at: datetime,
) -> bool:
    """Fail closed during stop/cancel/replace and unless current state is ready."""
    if desired.desired_state is not RuntimeDesiredStateKind.RUNNING:
        return False
    if (
        observation is None
        or current_observed_state(observation, at=at)
        is not RuntimeObservedStateKind.RUNNING
    ):
        return False
    return observation.readiness.name == "READY"
