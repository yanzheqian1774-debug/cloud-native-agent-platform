import json
from pathlib import Path

import pytest
from manifest_candidate import (
    REQUIRED_FIELDS,
    CompatibilityRequest,
    missing_fields,
    validate,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def request(**overrides) -> CompatibilityRequest:
    values = {
        "provider_package_id": "cloud-native-agent-platform.native-runtime",
        "provider_package_version": "0.1.0",
        "core_version": "0.1.0",
        "runtime_exact_version": "0.1.0+e6a162f",
        "platform_execution_identity": "exec-platform-001",
    }
    values.update(overrides)
    return CompatibilityRequest(**values)


@pytest.mark.parametrize(
    "name",
    [
        "native-supported.json",
        "openclaw-exact-target.json",
        "hermes-experimental.json",
        "future-runtime.json",
    ],
)
def test_fixture_manifest_is_complete(name) -> None:
    assert missing_fields(fixture(name)) == set()
    assert REQUIRED_FIELDS


def test_exact_native_match_passes() -> None:
    result = validate(fixture("native-supported.json"), request())
    assert result.accepted and result.may_invoke_runtime
    assert result.mode == "EXACT_MATCH"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"runtime_exact_version": None}, "RUNTIME_EXACT_VERSION_MISSING"),
        ({"runtime_exact_version": "0.1.1"}, "RUNTIME_VERSION_UNSUPPORTED"),
        ({"core_version": "0.2.0"}, "CORE_VERSION_INCOMPATIBLE"),
        ({"provider_package_id": "wrong"}, "PROVIDER_PACKAGE_ID_MISMATCH"),
        ({"provider_package_version": "0.1.1"}, "PROVIDER_PACKAGE_VERSION_MISMATCH"),
    ],
)
def test_unsafe_mismatch_rejected_before_invocation(overrides, reason) -> None:
    result = validate(fixture("native-supported.json"), request(**overrides))
    assert not result.accepted and not result.may_invoke_runtime
    assert result.reason == reason


def test_degraded_mode_requires_explicit_request_and_evidence() -> None:
    result = validate(fixture("native-supported.json"), request(allow_degraded=True))
    assert result.accepted and result.mode == "DEGRADED"
    manifest = fixture("native-supported.json")
    manifest["degraded_mode_policy"]["required_evidence"] = []
    assert (
        validate(manifest, request(allow_degraded=True)).reason
        == "DEGRADED_MODE_NOT_EVIDENCED"
    )


def test_experimental_target_remains_non_invocable() -> None:
    manifest = fixture("hermes-experimental.json")
    result = validate(
        manifest,
        request(
            provider_package_id=manifest["provider_package_id"],
            provider_package_version=manifest["provider_package_version"],
            runtime_exact_version=manifest["runtime_exact_version"],
        ),
    )
    assert result.reason == "EXPERIMENTAL_TARGET_NOT_INVOCABLE"


def test_openclaw_exact_target_does_not_grant_invocation_support() -> None:
    manifest = fixture("openclaw-exact-target.json")
    result = validate(
        manifest,
        request(
            provider_package_id=manifest["provider_package_id"],
            provider_package_version=manifest["provider_package_version"],
            runtime_exact_version=manifest["runtime_exact_version"],
        ),
    )
    assert not result.accepted and not result.may_invoke_runtime
    assert result.reason == "LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED"


def test_platform_identity_is_preserved_on_failure() -> None:
    result = validate(
        fixture("native-supported.json"), request(runtime_exact_version="unsafe")
    )
    assert result.platform_execution_identity == "exec-platform-001"
    assert "native" not in result.platform_execution_identity


def test_openclaw_fallback_is_explicit() -> None:
    manifest = fixture("openclaw-exact-target.json")
    result = validate(
        manifest,
        request(
            provider_package_id=manifest["provider_package_id"],
            provider_package_version=manifest["provider_package_version"],
            runtime_exact_version="untested",
        ),
    )
    assert (
        result.fallback
        == "EXPLICIT_PRE_INVOCATION_FALLBACK_ONLY; DISTINCT_ATTEMPT_IDENTITY; "
        "NO_FALLBACK_AFTER_POSSIBLE_EFFECTS"
    )
    assert not result.may_invoke_runtime


def test_incomplete_manifest_produces_actionable_diagnostic() -> None:
    manifest = fixture("native-supported.json")
    del manifest["runtime_exact_version"]
    assert "runtime_exact_version" in validate(manifest, request()).reason


def test_named_rejection_and_degraded_scenarios_are_machine_readable() -> None:
    scenarios = fixture("rejection-and-degraded-scenarios.json")
    assert set(scenarios) == {
        "openclaw_unsupported_version",
        "missing_version",
        "mismatched_provider_package",
        "incompatible_core",
        "explicit_degraded_mode",
    }
