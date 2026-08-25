"""Bounded internal Native Runtime Provider candidate."""

from collections.abc import Callable
from hashlib import sha256

from agent_runtime.providers.native.binding import (
    BindingTranslationError,
    translate_binding,
)
from agent_runtime.providers.native.compatibility import (
    FEATURES,
    LIMITATIONS,
    PROVIDER_PACKAGE,
    RUNTIME_TARGET,
    validate_compatibility,
)
from agent_runtime.providers.native.models import (
    BindingEvidence,
    CleanupResult,
    CompatibilityDecision,
    DiagnosticReason,
    ExecutionCorrelation,
    ExecutionEvidence,
    ExecutionState,
    HealthInformation,
    HealthState,
    LifecycleResult,
    NativeInvocation,
    ProviderExecutionRequest,
    ReadinessInformation,
    ReadinessState,
    RuntimeInformation,
    SupportState,
)


class NativeInvocationFailure(RuntimeError):
    """A native invocation is known to have failed without a result."""


class NativeInvocationAmbiguousTimeout(TimeoutError):
    """Invocation outcome is unknown because effects may have occurred."""


def deterministic_mock_invoker(
    platform_execution_identity: str,
    input_text: str,
    configuration: tuple[tuple[str, str], ...],
) -> NativeInvocation:
    """Execute the bounded deterministic Golden Path."""

    correlation = sha256(
        f"{platform_execution_identity}\0{input_text}\0{configuration}".encode()
    ).hexdigest()[:24]
    return NativeInvocation(
        output=f"mock response: {input_text}",
        native_invocation_id=f"native-{correlation}",
    )


class NativeRuntimeProvider:
    """Native candidate; intentionally independent of Stable Core and HTTP DTOs."""

    def __init__(
        self,
        invoker: Callable[
            [str, str, tuple[tuple[str, str], ...]], NativeInvocation
        ] = deterministic_mock_invoker,
    ) -> None:
        self._invoker = invoker
        self._results: dict[str, ExecutionEvidence] = {}
        self._native_ids: set[str] = set()

    def health(self) -> HealthInformation:
        return HealthInformation(HealthState.HEALTHY, "NATIVE_PROVIDER_HEALTHY")

    def readiness(self) -> ReadinessInformation:
        return ReadinessInformation(ReadinessState.READY, "EXACT_TARGET_READY")

    def runtime_information(self) -> RuntimeInformation:
        return RuntimeInformation(
            provider_package=PROVIDER_PACKAGE,
            runtime_target=RUNTIME_TARGET,
            features=FEATURES,
            limitations=LIMITATIONS,
            certification_state="NOT_CERTIFIED",
        )

    def invoke(self, request: ProviderExecutionRequest) -> ExecutionEvidence:
        decision = validate_compatibility(request.compatibility)
        correlation = ExecutionCorrelation(request.platform_execution_identity, None)
        if request.platform_execution_identity != decision.platform_execution_identity:
            return self._failure(
                correlation,
                decision,
                DiagnosticReason.NATIVE_ID_SUBSTITUTION_REJECTED,
            )
        if request.claimed_native_invocation_id is not None:
            return self._failure(
                correlation,
                decision,
                DiagnosticReason.NATIVE_ID_SUBSTITUTION_REJECTED,
            )
        if not decision.may_invoke:
            return self._failure(correlation, decision, decision.reason)
        try:
            binding = translate_binding(request.desired_binding)
        except BindingTranslationError as exc:
            return self._failure(correlation, decision, exc.reason)
        try:
            invocation = self._invoker(
                request.platform_execution_identity,
                request.input,
                binding.effective.configuration,
            )
        except NativeInvocationAmbiguousTimeout:
            return self._failure(
                correlation,
                decision,
                DiagnosticReason.INVOCATION_TIMEOUT_AMBIGUOUS,
                state=ExecutionState.UNKNOWN,
                binding=binding,
            )
        except NativeInvocationFailure:
            return self._failure(
                correlation,
                decision,
                DiagnosticReason.INVOCATION_FAILED,
                binding=binding,
            )
        native_id = invocation.native_invocation_id
        if native_id == request.platform_execution_identity:
            return self._failure(
                correlation,
                decision,
                DiagnosticReason.NATIVE_ID_SUBSTITUTION_REJECTED,
                binding=binding,
            )
        if native_id is not None and native_id in self._native_ids:
            return self._failure(
                ExecutionCorrelation(request.platform_execution_identity, native_id),
                decision,
                DiagnosticReason.NATIVE_INVOCATION_ID_DUPLICATE,
                binding=binding,
            )
        if native_id is not None:
            self._native_ids.add(native_id)
        evidence = ExecutionEvidence(
            state=ExecutionState.SUCCEEDED,
            correlation=ExecutionCorrelation(
                request.platform_execution_identity, native_id
            ),
            compatibility=decision,
            binding=binding,
            output=invocation.output,
            reason=decision.reason,
            diagnostic=f"native invocation normalized: {decision.reason.value}",
        )
        self._results[request.platform_execution_identity] = evidence
        return evidence

    def observe(self, platform_execution_identity: str) -> ExecutionEvidence | None:
        return self._results.get(platform_execution_identity)

    def start(self, platform_execution_identity: str) -> LifecycleResult:
        return LifecycleResult(
            operation="start",
            state=SupportState.NOT_YET_PROVEN,
            platform_execution_identity=platform_execution_identity,
            reason=DiagnosticReason.OPERATION_NOT_SUPPORTED,
        )

    def stop(self, platform_execution_identity: str) -> LifecycleResult:
        return LifecycleResult(
            operation="stop",
            state=SupportState.NOT_YET_PROVEN,
            platform_execution_identity=platform_execution_identity,
            reason=DiagnosticReason.OPERATION_NOT_SUPPORTED,
        )

    def cleanup(self, platform_execution_identity: str) -> CleanupResult:
        evidence = self._results.pop(platform_execution_identity, None)
        if evidence is None:
            return CleanupResult(
                state=SupportState.NOT_SUPPORTED,
                platform_execution_identity=platform_execution_identity,
                reason=DiagnosticReason.CLEANUP_FAILED,
            )
        native_id = evidence.correlation.native_invocation_id
        if native_id is not None:
            self._native_ids.discard(native_id)
        return CleanupResult(
            state=SupportState.SUPPORTED,
            platform_execution_identity=platform_execution_identity,
            reason=DiagnosticReason.CLEANUP_COMPLETED,
        )

    @staticmethod
    def _failure(
        correlation: ExecutionCorrelation,
        decision: CompatibilityDecision,
        reason: DiagnosticReason,
        *,
        state: ExecutionState = ExecutionState.FAILED,
        binding: BindingEvidence | None = None,
    ) -> ExecutionEvidence:
        return ExecutionEvidence(
            state=state,
            correlation=correlation,
            compatibility=decision,
            binding=binding,
            output=None,
            reason=reason,
            diagnostic=reason.value,
        )
