"""Bounded exact-version OpenClaw Runtime Provider adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from agent_runtime.providers.openclaw.compatibility import validate_target
from agent_runtime.providers.openclaw.models import (
    EventType,
    ExecutionObservation,
    ExecutionRequest,
    ExecutionState,
    LifecycleState,
    OpenClawError,
    OpenClawTransport,
    ReasonCode,
    RuntimeBinding,
    RuntimeObservation,
    SanitizedEvidence,
    SessionAffinity,
)


class OpenClawRuntimeProvider:
    """Consumes Platform identities and treats all OpenClaw IDs as correlations."""

    def __init__(self, transport: OpenClawTransport) -> None:
        self._transport = transport
        self._bindings: dict[str, RuntimeBinding] = {}
        self._terminal: dict[str, ExecutionObservation] = {}
        self._ambiguous: set[str] = set()

    def preflight(self) -> ReasonCode:
        return validate_target(self._transport.preflight())

    def start(self, binding: RuntimeBinding, *, at: datetime) -> RuntimeObservation:
        self._require_exact_target()
        previous = self._bindings.get(binding.runtime_instance_id)
        if previous is not None and binding.generation < previous.generation:
            raise OpenClawError(ReasonCode.OBSERVATION_STALE.value)
        if previous is not None and binding.generation == previous.generation:
            if previous != binding:
                raise OpenClawError(ReasonCode.OBSERVATION_CONFLICTING.value)
            return self.observe_runtime(binding, at=at)
        observed = self._transport.start(binding)
        self._validate_runtime_observation(binding, observed, at=at)
        self._bindings[binding.runtime_instance_id] = binding
        return observed

    def observe_runtime(
        self, binding: RuntimeBinding, *, at: datetime
    ) -> RuntimeObservation:
        observations = self._transport.observe_runtime(binding)
        if not observations:
            raise OpenClawError(ReasonCode.OBSERVATION_MISSING.value)
        if len(observations) != 1:
            raise OpenClawError(ReasonCode.OBSERVATION_CONFLICTING.value)
        observed = observations[0]
        self._validate_runtime_observation(binding, observed, at=at)
        return observed

    def execute(
        self, binding: RuntimeBinding, request: ExecutionRequest, *, at: datetime
    ) -> ExecutionObservation:
        runtime = self.observe_runtime(binding, at=at)
        if runtime.state is not LifecycleState.RUNNING:
            raise OpenClawError(ReasonCode.OBSERVATION_UNKNOWN.value)
        if runtime.readiness.value != "READY":
            raise OpenClawError(ReasonCode.OBSERVATION_UNKNOWN.value)
        self._validate_execution_identity(binding, request)
        existing = self._terminal.get(request.idempotency_key)
        if existing is not None:
            return existing
        if request.idempotency_key in self._ambiguous:
            raise OpenClawError(ReasonCode.PROVIDER_EFFECT_AMBIGUOUS.value)
        try:
            observed = self._transport.execute(request)
        except Exception:
            self._ambiguous.add(request.idempotency_key)
            raise OpenClawError(ReasonCode.PROVIDER_EFFECT_AMBIGUOUS.value) from None
        self._validate_execution_observation(request, observed)
        if observed.state in {ExecutionState.SUCCEEDED, ExecutionState.FAILED}:
            self._terminal[request.idempotency_key] = observed
        return observed

    def observe_execution(self, request: ExecutionRequest) -> ExecutionObservation:
        observations = self._transport.observe_execution(request)
        if not observations:
            raise OpenClawError(ReasonCode.OBSERVATION_MISSING.value)
        if len(observations) != 1:
            raise OpenClawError(ReasonCode.OBSERVATION_CONFLICTING.value)
        observed = observations[0]
        self._validate_execution_observation(request, observed)
        return observed

    def stop(self, binding: RuntimeBinding, *, at: datetime) -> RuntimeObservation:
        self._require_registered(binding)
        try:
            observed = self._transport.stop(binding)
        except Exception:
            raise OpenClawError(ReasonCode.PROVIDER_EFFECT_AMBIGUOUS.value) from None
        self._validate_runtime_observation(binding, observed, at=at)
        if observed.state not in {LifecycleState.STOPPED, LifecycleState.TERMINATED}:
            raise OpenClawError(ReasonCode.OBSERVATION_UNKNOWN.value)
        return observed

    def replace(self, binding: RuntimeBinding, *, at: datetime) -> RuntimeObservation:
        previous = self._bindings.get(binding.runtime_instance_id)
        if previous is None:
            raise OpenClawError(ReasonCode.OBSERVATION_MISSING.value)
        if binding.generation != previous.generation + 1:
            raise OpenClawError(ReasonCode.OBSERVATION_CONFLICTING.value)
        if (
            binding.namespace,
            binding.security_domain,
            binding.placement_id,
            binding.mode,
            binding.session_affinity,
            binding.session_reference,
        ) != (
            previous.namespace,
            previous.security_domain,
            previous.placement_id,
            previous.mode,
            previous.session_affinity,
            previous.session_reference,
        ):
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)
        old = self.observe_runtime(previous, at=at)
        observed = self._transport.replace(binding)
        self._validate_runtime_observation(binding, observed, at=at)
        if observed.correlation.gateway_id == old.correlation.gateway_id:
            raise OpenClawError(ReasonCode.OBSERVATION_CONFLICTING.value)
        self._bindings[binding.runtime_instance_id] = binding
        return observed

    def evidence(
        self,
        event_type: EventType,
        reason: ReasonCode,
        binding: RuntimeBinding,
        request: ExecutionRequest,
        observation: ExecutionObservation,
        *,
        recorded_at: datetime,
    ) -> SanitizedEvidence:
        self._validate_execution_identity(binding, request)
        self._validate_execution_observation(request, observation)
        correlation = observation.correlation
        digest = sha256(
            "\0".join(
                value or ""
                for value in (
                    correlation.gateway_id,
                    correlation.run_id,
                    correlation.session_id,
                )
            ).encode()
        ).hexdigest()
        return SanitizedEvidence(
            event_type=event_type,
            reason=reason,
            linkage=request.linkage,
            runtime_instance_id=binding.runtime_instance_id,
            generation=binding.generation,
            provider_correlation_digest=digest,
            recorded_at=recorded_at.astimezone(UTC),
        )

    def _require_exact_target(self) -> None:
        reason = self.preflight()
        if reason is not ReasonCode.EXACT_VERSION_READY:
            raise OpenClawError(reason.value)

    def _require_registered(self, binding: RuntimeBinding) -> RuntimeBinding:
        existing = self._bindings.get(binding.runtime_instance_id)
        if existing is None:
            raise OpenClawError(ReasonCode.OBSERVATION_MISSING.value)
        if existing != binding:
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)
        return existing

    @staticmethod
    def _validate_runtime_observation(
        binding: RuntimeBinding, observed: RuntimeObservation, *, at: datetime
    ) -> None:
        if observed.runtime_instance_id != binding.runtime_instance_id:
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)
        if observed.generation != binding.generation:
            raise OpenClawError(ReasonCode.OBSERVATION_CONFLICTING.value)
        if at.astimezone(UTC) > observed.freshness_deadline:
            raise OpenClawError(ReasonCode.OBSERVATION_STALE.value)
        if observed.state is LifecycleState.UNKNOWN:
            raise OpenClawError(ReasonCode.OBSERVATION_UNKNOWN.value)

    @staticmethod
    def _validate_execution_identity(
        binding: RuntimeBinding, request: ExecutionRequest
    ) -> None:
        if request.linkage.runtime_instance_id != binding.runtime_instance_id:
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)
        if request.linkage.placement_id != binding.placement_id:
            raise OpenClawError(ReasonCode.PLACEMENT_REQUIRED.value)
        if binding.session_affinity is SessionAffinity.REQUIRED:
            if request.session_reference != binding.session_reference:
                raise OpenClawError(ReasonCode.SESSION_AFFINITY_REQUIRED.value)
        elif request.session_reference is not None:
            raise OpenClawError(ReasonCode.SESSION_AFFINITY_PROHIBITED.value)

    @staticmethod
    def _validate_execution_observation(
        request: ExecutionRequest, observed: ExecutionObservation
    ) -> None:
        if observed.linkage != request.linkage:
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)
        if observed.correlation.run_id in {
            request.linkage.workflow_run_id,
            request.linkage.task_run_id,
            request.linkage.attempt_id,
            request.linkage.runtime_instance_id,
        }:
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)
