"""Compatibility policy consumed from the experimental S5-SPIKE-005 manifest."""

from agent_runtime.providers.native.models import (
    CompatibilityDecision,
    CompatibilityMode,
    CompatibilityRequest,
    DiagnosticReason,
    ProviderPackageIdentity,
    RuntimeTargetIdentity,
)

PROVIDER_PACKAGE = ProviderPackageIdentity(
    distribution="cloud-native-agent-platform",
    version="0.1.0",
    module="agent_runtime",
)
MANIFEST_PROVIDER_PACKAGE_ID = "cloud-native-agent-platform.native-runtime"
RUNTIME_TARGET = RuntimeTargetIdentity(
    name="native",
    exact_version="0.1.0+e6a162f",
    profile="managed-kubernetes-deterministic-mock",
)
CORE_EXACT_VERSIONS = frozenset({"0.1.0"})
FEATURES = ("health-readiness-invoke-info", "deterministic-mock-execution")
LIMITATIONS = (
    "No Provider certification",
    "Image digest not published",
    "arm64 not yet proven",
    "semantic recovery not proven",
)
DEGRADED_REQUIRED_EVIDENCE = frozenset(
    {"deterministic mock label", "normalized outcome"}
)


def validate_compatibility(request: CompatibilityRequest) -> CompatibilityDecision:
    """Validate the exact candidate before any binding or invocation side effect."""

    def reject(reason: DiagnosticReason) -> CompatibilityDecision:
        return CompatibilityDecision(
            accepted=False,
            may_invoke=False,
            mode=CompatibilityMode.REJECTED,
            reason=reason,
            platform_execution_identity=request.platform_execution_identity,
            requested_runtime=request.runtime_target,
            effective_runtime=None,
        )

    if not request.platform_execution_identity.strip():
        return reject(DiagnosticReason.PLATFORM_EXECUTION_IDENTITY_MISSING)
    if not request.runtime_target.name.strip():
        return reject(DiagnosticReason.RUNTIME_IDENTITY_MISSING)
    if not request.runtime_target.exact_version:
        return reject(DiagnosticReason.RUNTIME_VERSION_MISSING)
    if request.runtime_target.name != RUNTIME_TARGET.name:
        return reject(DiagnosticReason.RUNTIME_TARGET_UNSUPPORTED)
    if request.runtime_target.exact_version != RUNTIME_TARGET.exact_version:
        return reject(DiagnosticReason.RUNTIME_VERSION_UNSUPPORTED)
    if request.runtime_target.profile != RUNTIME_TARGET.profile:
        return reject(DiagnosticReason.RUNTIME_PROFILE_UNSUPPORTED)
    if request.provider_package != PROVIDER_PACKAGE:
        return reject(DiagnosticReason.PROVIDER_PACKAGE_MISMATCH)
    if request.core_version not in CORE_EXACT_VERSIONS:
        return reject(DiagnosticReason.CORE_VERSION_INCOMPATIBLE)

    degraded = request.degraded
    if degraded.evidence and not degraded.requested:
        return reject(DiagnosticReason.IMPLICIT_DEGRADED_MODE_REJECTED)
    if degraded.requested:
        if not DEGRADED_REQUIRED_EVIDENCE.issubset(degraded.evidence):
            return reject(DiagnosticReason.DEGRADED_MODE_NOT_EVIDENCED)
        return CompatibilityDecision(
            accepted=True,
            may_invoke=True,
            mode=CompatibilityMode.DEGRADED,
            reason=DiagnosticReason.EXPLICIT_DEGRADED_MODE_ACCEPTED,
            platform_execution_identity=request.platform_execution_identity,
            requested_runtime=request.runtime_target,
            effective_runtime=RUNTIME_TARGET,
            limitations=("deterministic mock execution only",),
        )
    return CompatibilityDecision(
        accepted=True,
        may_invoke=True,
        mode=CompatibilityMode.EXACT_MATCH,
        reason=DiagnosticReason.EXACT_COMPATIBILITY_MATCH,
        platform_execution_identity=request.platform_execution_identity,
        requested_runtime=request.runtime_target,
        effective_runtime=RUNTIME_TARGET,
    )
