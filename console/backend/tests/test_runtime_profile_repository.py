import pytest
from agent_console.runtime_profile_repository import (
    InMemoryRuntimeProfileRepository,
    RuntimeProfileConflict,
    RuntimeProfileNotFound,
    RuntimeProfileScope,
)


def record(scope: RuntimeProfileScope):
    return {
        "namespace": scope.namespace,
        "securityDomain": scope.security_domain,
        "runtimeProfileId": "runtime-profile:one",
        "aggregateVersion": 1,
        "facts": [{"factId": "runtime-profile-fact:create"}],
    }


def test_repository_is_scope_isolated_and_compare_and_set():
    repository = InMemoryRuntimeProfileRepository()
    scope = RuntimeProfileScope("tenant-a", "quality")
    created = repository.create(record(scope))
    with pytest.raises(RuntimeProfileNotFound):
        repository.get(
            RuntimeProfileScope("tenant-b", "quality"), "runtime-profile:one"
        )
    changed = {**created, "aggregateVersion": 2}
    repository.replace(
        changed,
        expected_version=1,
        fact={"factId": "runtime-profile-fact:update"},
    )
    with pytest.raises(RuntimeProfileConflict):
        repository.replace(
            changed,
            expected_version=1,
            fact={"factId": "runtime-profile-fact:stale"},
        )
