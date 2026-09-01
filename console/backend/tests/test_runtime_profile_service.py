import pytest
from agent_console.runtime_profile_repository import InMemoryRuntimeProfileRepository
from agent_console.runtime_profile_service import (
    RuntimeProfileFailure,
    RuntimeProfileService,
)


def native():
    return {
        "provider": "NATIVE_KUBERNETES",
        "resources": {
            "cpuRequest": "250m",
            "cpuLimit": "500m",
            "memoryRequest": "256Mi",
            "memoryLimit": "1Gi",
        },
        "isolation": "NAMESPACE",
        "stateMode": "STATELESS",
        "sessionAffinity": "NONE",
        "secretReferences": ["secret-ref:model-provider"],
        "openClawPackageRef": None,
    }


def test_native_profile_governance_and_projections():
    service = RuntimeProfileService(InMemoryRuntimeProfileRepository())
    scope = service.scope("tenant-a", "domain-a")
    record = service.create(scope, "human:a", "Native", native())
    record = service.validate(scope, record["runtimeProfileId"], "human:a", 1)
    revision = record["revisions"][-1]
    record = service.review(
        scope,
        record["runtimeProfileId"],
        "human:a",
        2,
        revision["digest"],
        "APPROVE",
        "safe limits",
    )
    review = record["reviews"][-1]
    record = service.publish(
        scope,
        record["runtimeProfileId"],
        "human:a",
        3,
        revision["digest"],
        review["reviewId"],
    )
    projected = service.project(record)
    assert projected["productProjection"]["provider"] == "NATIVE_KUBERNETES"
    assert projected["technicalProjection"]["executionAuthority"] is False


def test_openclaw_is_bounded_declaration_only():
    service = RuntimeProfileService(InMemoryRuntimeProfileRepository())
    scope = service.scope("tenant-a", "domain-a")
    value = native()
    value.update(
        provider="OPENCLAW",
        openClawPackageRef="oci://registry/openclaw@sha256:abc",
        sessionAffinity="REQUIRED",
    )
    assert (
        service.create(scope, "human:a", "OpenClaw", value)["revisions"][0]["content"][
            "provider"
        ]
        == "OPENCLAW"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {
            "resources": {
                "cpuRequest": "900m",
                "cpuLimit": "500m",
                "memoryRequest": "1Gi",
                "memoryLimit": "1Gi",
            }
        },
        {"secretReferences": ["plaintext-token"]},
        {"podYaml": "kind: Pod"},
        {"exec": "sh"},
    ],
)
def test_unsafe_or_unbounded_configuration_is_rejected(mutation):
    service = RuntimeProfileService(InMemoryRuntimeProfileRepository())
    value = native()
    value.update(mutation)
    with pytest.raises(RuntimeProfileFailure):
        service.create(
            service.scope("tenant-a", "domain-a"), "human:a", "Unsafe", value
        )
