"""Experimental compatibility-manifest validation for S5-SPIKE-005 only."""

from dataclasses import dataclass
from typing import Any

REQUIRED_FIELDS = frozenset(
    {
        "manifest_format_marker",
        "manifest_schema_version",
        "provider_id",
        "provider_package_id",
        "provider_package_version",
        "provider_implementation_commit",
        "core_compatibility",
        "runtime_name",
        "runtime_exact_version",
        "runtime_tag",
        "runtime_commit_or_digest",
        "runtime_profile",
        "supported_platforms",
        "supported_features",
        "limitations",
        "required_configuration",
        "isolation_requirements",
        "identity_capabilities",
        "lifecycle_capabilities",
        "health_capabilities",
        "recovery_capabilities",
        "cleanup_capabilities",
        "known_failure_modes",
        "mismatch_policy",
        "degraded_mode_policy",
        "fallback_policy",
        "evidence_references",
        "conformance_state",
        "certification_state",
        "deprecation_state",
        "security_notes",
        "license_notes",
        "generated_or_verified_at",
    }
)


@dataclass(frozen=True)
class CompatibilityRequest:
    provider_package_id: str
    provider_package_version: str
    core_version: str
    runtime_exact_version: str | None
    platform_execution_identity: str
    allow_degraded: bool = False


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    mode: str
    reason: str
    platform_execution_identity: str
    may_invoke_runtime: bool
    fallback: str


def missing_fields(manifest: dict[str, Any]) -> set[str]:
    """Return absent required semantic fields without imposing serialization."""

    return REQUIRED_FIELDS - manifest.keys()


def validate(
    manifest: dict[str, Any], request: CompatibilityRequest
) -> ValidationResult:
    """Fail closed before invocation and preserve platform-owned identity."""

    fallback = manifest.get("fallback_policy", {}).get("action", "REJECT")

    def reject(reason: str) -> ValidationResult:
        return ValidationResult(
            False,
            "REJECTED",
            reason,
            request.platform_execution_identity,
            False,
            fallback,
        )

    absent = sorted(missing_fields(manifest))
    if absent:
        return reject(f"MANIFEST_INCOMPLETE: {', '.join(absent)}")
    if not request.runtime_exact_version:
        return reject("RUNTIME_EXACT_VERSION_MISSING")
    if request.provider_package_id != manifest["provider_package_id"]:
        return reject("PROVIDER_PACKAGE_ID_MISMATCH")
    if request.provider_package_version != manifest["provider_package_version"]:
        return reject("PROVIDER_PACKAGE_VERSION_MISMATCH")
    if request.core_version not in manifest["core_compatibility"]["exact_versions"]:
        return reject("CORE_VERSION_INCOMPATIBLE")
    if request.runtime_exact_version != manifest["runtime_exact_version"]:
        return reject("RUNTIME_VERSION_UNSUPPORTED")
    if manifest["conformance_state"] == "EXPERIMENTAL":
        return reject("EXPERIMENTAL_TARGET_NOT_INVOCABLE")
    if manifest["conformance_state"] == "SELECTED_EXACT_VERSION_CANDIDATE":
        return reject("LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED")
    degraded = manifest["degraded_mode_policy"]
    if request.allow_degraded:
        if not degraded.get("allowed") or not degraded.get("required_evidence"):
            return reject("DEGRADED_MODE_NOT_EVIDENCED")
        return ValidationResult(
            True,
            "DEGRADED",
            "EXPLICIT_DEGRADED_MODE_ACCEPTED",
            request.platform_execution_identity,
            True,
            fallback,
        )
    return ValidationResult(
        True,
        "EXACT_MATCH",
        "EXACT_COMPATIBILITY_MATCH",
        request.platform_execution_identity,
        True,
        fallback,
    )
