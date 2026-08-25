from copy import deepcopy

import pytest
from agent_runtime.providers.native.binding import (
    BindingTranslationError,
    translate_binding,
)
from agent_runtime.providers.native.compatibility import (
    DEGRADED_REQUIRED_EVIDENCE,
    PROVIDER_PACKAGE,
    RUNTIME_TARGET,
    validate_compatibility,
)
from agent_runtime.providers.native.models import (
    CompatibilityMode,
    CompatibilityRequest,
    DegradedModeRequest,
    DesiredRuntimeBinding,
    DiagnosticReason,
    ExecutionState,
    HealthState,
    NativeInvocation,
    ProviderExecutionRequest,
    ProviderPackageIdentity,
    ReadinessState,
    RuntimeTargetIdentity,
    SupportState,
)
from agent_runtime.providers.native.provider import (
    NativeInvocationAmbiguousTimeout,
    NativeInvocationFailure,
    NativeRuntimeProvider,
)


def compatibility(**overrides) -> CompatibilityRequest:
    values = {
        "provider_package": PROVIDER_PACKAGE,
        "runtime_target": RUNTIME_TARGET,
        "core_version": "0.1.0",
        "platform_execution_identity": "platform-exec-001",
    }
    values.update(overrides)
    return CompatibilityRequest(**values)


def desired(**configuration) -> DesiredRuntimeBinding:
    values = {"AGENT_NAME": "researcher", "MODEL_PROVIDER": "mock"}
    values.update(configuration)
    return DesiredRuntimeBinding(RUNTIME_TARGET, values)


def execution(**overrides) -> ProviderExecutionRequest:
    values = {
        "platform_execution_identity": "platform-exec-001",
        "input": "hello",
        "compatibility": compatibility(),
        "desired_binding": desired(),
    }
    values.update(overrides)
    return ProviderExecutionRequest(**values)


def test_exact_provider_and_runtime_identity() -> None:
    assert (
        ProviderPackageIdentity("cloud-native-agent-platform", "0.1.0", "agent_runtime")
        == PROVIDER_PACKAGE
    )
    assert RUNTIME_TARGET.target == (
        "native:0.1.0+e6a162f:managed-kubernetes-deterministic-mock"
    )


@pytest.mark.parametrize(
    ("compatibility_request", "reason"),
    [
        (
            compatibility(
                provider_package=ProviderPackageIdentity(
                    "foreign-package", "0.1.0", "agent_runtime"
                )
            ),
            DiagnosticReason.PROVIDER_PACKAGE_MISMATCH,
        ),
        (
            compatibility(
                runtime_target=RuntimeTargetIdentity(
                    "", "0.1.0+e6a162f", RUNTIME_TARGET.profile
                )
            ),
            DiagnosticReason.RUNTIME_IDENTITY_MISSING,
        ),
        (
            compatibility(
                runtime_target=RuntimeTargetIdentity(
                    "native", None, RUNTIME_TARGET.profile
                )
            ),
            DiagnosticReason.RUNTIME_VERSION_MISSING,
        ),
        (
            compatibility(
                runtime_target=RuntimeTargetIdentity(
                    "native", "0.1.1", RUNTIME_TARGET.profile
                )
            ),
            DiagnosticReason.RUNTIME_VERSION_UNSUPPORTED,
        ),
        (
            compatibility(
                runtime_target=RuntimeTargetIdentity(
                    "native", RUNTIME_TARGET.exact_version, "foreign-profile"
                )
            ),
            DiagnosticReason.RUNTIME_PROFILE_UNSUPPORTED,
        ),
        (
            compatibility(core_version="0.2.0"),
            DiagnosticReason.CORE_VERSION_INCOMPATIBLE,
        ),
        (
            compatibility(platform_execution_identity=""),
            DiagnosticReason.PLATFORM_EXECUTION_IDENTITY_MISSING,
        ),
        (
            compatibility(
                runtime_target=RuntimeTargetIdentity(
                    "openclaw", "2026.7.1-2", "external"
                )
            ),
            DiagnosticReason.RUNTIME_TARGET_UNSUPPORTED,
        ),
        (
            compatibility(
                runtime_target=RuntimeTargetIdentity("hermes", "0.20.4", "experimental")
            ),
            DiagnosticReason.RUNTIME_TARGET_UNSUPPORTED,
        ),
    ],
)
def test_compatibility_rejects_before_invocation(compatibility_request, reason) -> None:
    decision = validate_compatibility(compatibility_request)
    assert not decision.accepted
    assert not decision.may_invoke
    assert decision.reason == reason
    assert (
        decision.platform_execution_identity
        == compatibility_request.platform_execution_identity
    )
    assert decision.effective_runtime is None


def test_exact_compatibility_candidate_is_accepted() -> None:
    decision = validate_compatibility(compatibility())
    assert decision.accepted and decision.may_invoke
    assert decision.mode == CompatibilityMode.EXACT_MATCH
    assert decision.requested_runtime == RUNTIME_TARGET
    assert decision.effective_runtime == RUNTIME_TARGET


def test_implicit_degraded_mode_is_rejected() -> None:
    decision = validate_compatibility(
        compatibility(degraded=DegradedModeRequest(evidence=("normalized outcome",)))
    )
    assert decision.reason == DiagnosticReason.IMPLICIT_DEGRADED_MODE_REJECTED


def test_explicit_degraded_mode_requires_and_records_evidence() -> None:
    denied = validate_compatibility(
        compatibility(degraded=DegradedModeRequest(requested=True))
    )
    assert denied.reason == DiagnosticReason.DEGRADED_MODE_NOT_EVIDENCED
    accepted = validate_compatibility(
        compatibility(
            degraded=DegradedModeRequest(
                requested=True, evidence=tuple(DEGRADED_REQUIRED_EVIDENCE)
            )
        )
    )
    assert accepted.mode == CompatibilityMode.DEGRADED
    assert accepted.limitations == ("deterministic mock execution only",)


def test_binding_translation_is_deterministic_distinct_and_non_mutating() -> None:
    source = {"MODEL_PROVIDER": "mock", "AGENT_NAME": "researcher"}
    original = deepcopy(source)
    binding = DesiredRuntimeBinding(RUNTIME_TARGET, source)
    first = translate_binding(binding)
    second = translate_binding(binding)
    assert first == second
    assert source == original
    assert first.desired == binding
    assert first.desired is not binding
    assert first.effective.runtime_target == RUNTIME_TARGET
    assert first.effective.configuration == (
        ("AGENT_NAME", "researcher"),
        ("AGENT_NAMESPACE", "unknown"),
        ("MODEL_NAME", "mock-model"),
        ("MODEL_PROVIDER", "mock"),
    )


@pytest.mark.parametrize(
    ("configuration", "reason"),
    [
        ({"UNSUPPORTED": "value"}, DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED),
        (
            {"MODEL_PROVIDER": "openai-compatible"},
            DiagnosticReason.BINDING_CONFIGURATION_UNSUPPORTED,
        ),
        (
            {"MODEL_API_KEY": "do-not-record"},
            DiagnosticReason.BINDING_SECRET_VALUE_PROHIBITED,
        ),
        (
            {"access_token": "do-not-record"},
            DiagnosticReason.BINDING_SECRET_VALUE_PROHIBITED,
        ),
    ],
)
def test_binding_rejects_unsupported_or_secret_configuration(
    configuration, reason
) -> None:
    with pytest.raises(BindingTranslationError) as exc:
        translate_binding(DesiredRuntimeBinding(RUNTIME_TARGET, configuration))
    assert exc.value.reason == reason
    assert "do-not-record" not in str(exc.value)


def test_health_readiness_and_runtime_information_are_normalized() -> None:
    provider = NativeRuntimeProvider()
    assert provider.health().state == HealthState.HEALTHY
    assert provider.readiness().state == ReadinessState.READY
    info = provider.runtime_information()
    assert info.provider_package == PROVIDER_PACKAGE
    assert info.runtime_target == RUNTIME_TARGET
    assert info.certification_state == "NOT_CERTIFIED"


def test_deterministic_invocation_preserves_platform_identity() -> None:
    provider = NativeRuntimeProvider()
    first = provider.invoke(execution())
    second = NativeRuntimeProvider().invoke(execution())
    assert first.state == ExecutionState.SUCCEEDED
    assert first.output == "mock response: hello"
    assert first.correlation.platform_execution_identity == "platform-exec-001"
    assert (
        first.correlation.native_invocation_id
        == second.correlation.native_invocation_id
    )
    assert first.correlation.native_invocation_id != "platform-exec-001"
    assert provider.observe("platform-exec-001") == first


def test_compatibility_rejection_happens_before_invocation() -> None:
    calls = []

    def invoker(*args):
        calls.append(args)
        return NativeInvocation("unexpected")

    provider = NativeRuntimeProvider(invoker)
    rejected = provider.invoke(
        execution(
            compatibility=compatibility(
                runtime_target=RuntimeTargetIdentity(
                    "openclaw", "2026.7.1-2", "external"
                )
            )
        )
    )
    assert rejected.reason == DiagnosticReason.RUNTIME_TARGET_UNSUPPORTED
    assert calls == []


def test_foreign_or_native_identity_substitution_is_rejected() -> None:
    provider = NativeRuntimeProvider()
    foreign = provider.invoke(
        execution(
            platform_execution_identity="foreign",
            compatibility=compatibility(
                platform_execution_identity="platform-exec-001"
            ),
        )
    )
    claimed = provider.invoke(execution(claimed_native_invocation_id="native-1"))
    asserting_platform_as_native = NativeRuntimeProvider(
        lambda *_: NativeInvocation("output", "platform-exec-001")
    ).invoke(execution())
    assert foreign.reason == DiagnosticReason.NATIVE_ID_SUBSTITUTION_REJECTED
    assert claimed.reason == DiagnosticReason.NATIVE_ID_SUBSTITUTION_REJECTED
    assert (
        asserting_platform_as_native.reason
        == DiagnosticReason.NATIVE_ID_SUBSTITUTION_REJECTED
    )


def test_duplicate_native_invocation_id_is_rejected() -> None:
    provider = NativeRuntimeProvider(lambda *_: NativeInvocation("output", "native-1"))
    assert provider.invoke(execution()).state == ExecutionState.SUCCEEDED
    duplicate = provider.invoke(
        execution(
            platform_execution_identity="platform-exec-002",
            compatibility=compatibility(
                platform_execution_identity="platform-exec-002"
            ),
        )
    )
    assert duplicate.reason == DiagnosticReason.NATIVE_INVOCATION_ID_DUPLICATE
    assert duplicate.correlation.platform_execution_identity == "platform-exec-002"


@pytest.mark.parametrize(
    ("error", "state", "reason"),
    [
        (
            NativeInvocationFailure("failed"),
            ExecutionState.FAILED,
            DiagnosticReason.INVOCATION_FAILED,
        ),
        (
            NativeInvocationAmbiguousTimeout("unknown"),
            ExecutionState.UNKNOWN,
            DiagnosticReason.INVOCATION_TIMEOUT_AMBIGUOUS,
        ),
    ],
)
def test_invocation_failure_and_transport_ambiguity_are_normalized(
    error, state, reason
) -> None:
    def invoker(*_):
        raise error

    evidence = NativeRuntimeProvider(invoker).invoke(execution())
    assert evidence.state == state
    assert evidence.reason == reason
    assert evidence.correlation.platform_execution_identity == "platform-exec-001"


def test_lifecycle_fails_closed_and_cleanup_is_bounded() -> None:
    provider = NativeRuntimeProvider()
    assert provider.start("platform-exec-001").state == SupportState.NOT_YET_PROVEN
    assert provider.stop("platform-exec-001").state == SupportState.NOT_YET_PROVEN
    missing = provider.cleanup("platform-exec-001")
    assert missing.state == SupportState.NOT_SUPPORTED
    provider.invoke(execution())
    completed = provider.cleanup("platform-exec-001")
    assert completed.state == SupportState.SUPPORTED
    assert provider.observe("platform-exec-001") is None
