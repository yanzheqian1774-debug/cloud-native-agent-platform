"""Spike-only semantic recovery evidence harness for Checkpoint C."""

from dataclasses import dataclass
from enum import StrEnum

from generic_caller import GenericCaller, LogicalAgentRequest
from object_model import (
    ExperimentalRuntimeProvider,
    NativeDispatch,
    RuntimeBinding,
    RuntimeRealization,
)


class ConditionValue(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class RecoveryOutcome(StrEnum):
    RECOVERED = "recovered"
    NOT_RECOVERED = "not_recovered"
    RECOVERY_UNKNOWN = "recovery_unknown"


@dataclass(frozen=True)
class RuntimeObservation:
    instance_id: str
    binding_id: str
    realization_id: str | None
    runtime_available: ConditionValue
    infrastructure_available: ConditionValue
    native_evidence: str


@dataclass(frozen=True)
class RecoveryResult:
    instance_id: str
    old_realization_id: str
    new_realization_id: str
    native_restart_succeeded: bool
    semantic_route_verified: bool
    outcome: RecoveryOutcome
    execution_id: str


class ExperimentalRecoveryProvider(ExperimentalRuntimeProvider):
    """Provider performs owned native actions and reports semantic readiness."""

    def __init__(
        self,
        provider_id: str,
        *,
        infrastructure_observable: bool,
    ) -> None:
        super().__init__(provider_id)
        self.infrastructure_observable = infrastructure_observable
        self._runtime_ready: dict[str, bool | None] = {}
        self.native_actions: list[str] = []

    def realize(
        self,
        binding: RuntimeBinding,
        *,
        realization_id: str,
        native_kind: str,
        native_id: str,
    ) -> RuntimeRealization:
        realization = super().realize(
            binding,
            realization_id=realization_id,
            native_kind=native_kind,
            native_id=native_id,
        )
        self._runtime_ready[realization.realization_id] = True
        return realization

    def fail(self, binding: RuntimeBinding, *, evidence: str) -> RuntimeObservation:
        target = self.active(binding)[0]
        self._runtime_ready[target.realization_id] = False
        return self.observe(binding, evidence=evidence)

    def observe(self, binding: RuntimeBinding, *, evidence: str) -> RuntimeObservation:
        active = self.active(binding)
        if not active:
            return RuntimeObservation(
                instance_id=binding.instance_id,
                binding_id=binding.binding_id,
                realization_id=None,
                runtime_available=ConditionValue.FALSE,
                infrastructure_available=self._infrastructure_condition(),
                native_evidence=evidence,
            )
        target = active[0]
        ready = self._runtime_ready.get(target.realization_id)
        runtime_available = (
            ConditionValue.UNKNOWN
            if ready is None
            else ConditionValue.TRUE
            if ready
            else ConditionValue.FALSE
        )
        return RuntimeObservation(
            instance_id=binding.instance_id,
            binding_id=binding.binding_id,
            realization_id=target.realization_id,
            runtime_available=runtime_available,
            infrastructure_available=self._infrastructure_condition(),
            native_evidence=evidence,
        )

    def recover(
        self,
        binding: RuntimeBinding,
        *,
        realization_id: str,
        native_id: str,
        semantically_ready: bool | None,
    ) -> RuntimeRealization:
        self.native_actions.append(f"recreate:{binding.binding_id}")
        replacement = super().replace(
            binding,
            realization_id=realization_id,
            native_kind="GatewaySession",
            native_id=native_id,
        )
        self._runtime_ready[replacement.realization_id] = semantically_ready
        return replacement

    def translate(
        self,
        binding: RuntimeBinding,
        *,
        execution_id: str,
        payload: str,
    ) -> NativeDispatch:
        target = self.active(binding)[0]
        if self._runtime_ready.get(target.realization_id) is not True:
            raise RuntimeError("selected Instance is not semantically reachable")
        return super().translate(binding, execution_id=execution_id, payload=payload)

    def _infrastructure_condition(self) -> ConditionValue:
        if self.infrastructure_observable:
            return ConditionValue.TRUE
        return ConditionValue.NOT_APPLICABLE


class ExperimentalInstanceReconciler:
    """Platform detects divergence; Provider owns runtime-specific recovery."""

    def __init__(self) -> None:
        self.divergences: list[RuntimeObservation] = []

    def detect(self, observation: RuntimeObservation) -> bool:
        divergent = observation.runtime_available is not ConditionValue.TRUE
        if divergent:
            self.divergences.append(observation)
        return divergent

    def verify(
        self,
        *,
        caller: GenericCaller,
        request: LogicalAgentRequest,
        provider: ExperimentalRecoveryProvider,
        binding: RuntimeBinding,
        old_realization_id: str,
        new_realization_id: str,
    ) -> RecoveryResult:
        observation = provider.observe(binding, evidence="post-recreation probe")
        if observation.runtime_available is ConditionValue.UNKNOWN:
            return RecoveryResult(
                binding.instance_id,
                old_realization_id,
                new_realization_id,
                True,
                False,
                RecoveryOutcome.RECOVERY_UNKNOWN,
                request.execution_id,
            )
        try:
            outcome = caller.invoke(request)
        except RuntimeError:
            route_verified = False
        else:
            route_verified = (
                outcome.instance_id == binding.instance_id
                and outcome.execution_id == request.execution_id
            )
        recovered = (
            observation.runtime_available is ConditionValue.TRUE
            and route_verified
            and old_realization_id != new_realization_id
        )
        return RecoveryResult(
            instance_id=binding.instance_id,
            old_realization_id=old_realization_id,
            new_realization_id=new_realization_id,
            native_restart_succeeded=True,
            semantic_route_verified=route_verified,
            outcome=(
                RecoveryOutcome.RECOVERED
                if recovered
                else RecoveryOutcome.NOT_RECOVERED
            ),
            execution_id=request.execution_id,
        )
