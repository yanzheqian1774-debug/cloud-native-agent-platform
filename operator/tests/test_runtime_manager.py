from datetime import UTC, datetime, timedelta

import pytest
from agent_operator.runtime_manager import (
    CommandId,
    CommandResult,
    Generation,
    InMemoryRuntimeControlRepository,
    RuntimeControlError,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeInstanceId,
    RuntimeManager,
    RuntimeOperation,
    ScopedRuntimeCommand,
    ScopeIdentity,
    accepts_new_assignment,
)
from agent_runtime.providers.native import NativeRuntimeProvider
from agent_runtime.providers.native.models import (
    DiagnosticReason,
    NativeLifecycleObservation,
    NativeLifecycleState,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)
SCOPE = ScopeIdentity("tenant-a", "domain-a")


class Driver:
    def __init__(self):
        self.values = {}
        self.sequence = 0

    def start(self, identity):
        self.sequence += 1
        value = NativeLifecycleObservation(
            identity,
            NativeLifecycleState.RUNNING,
            f"native-runtime-{self.sequence}",
            DiagnosticReason.LIFECYCLE_APPLIED,
        )
        self.values[identity] = value
        return value

    def stop(self, identity):
        prior = self.values.get(identity)
        value = NativeLifecycleObservation(
            identity,
            NativeLifecycleState.TERMINATED,
            prior.native_correlation if prior else None,
            DiagnosticReason.LIFECYCLE_APPLIED,
        )
        self.values[identity] = value
        return value

    def replace(self, identity):
        return self.start(identity)

    def observe(self, identity):
        return self.values.get(identity)


def command(
    state=RuntimeDesiredStateKind.RUNNING,
    operation=RuntimeOperation.START,
    generation=1,
):
    return ScopedRuntimeCommand(
        SCOPE,
        RuntimeDesiredState(
            RuntimeInstanceId("runtime-1"),
            Generation(generation),
            state,
            CommandId(f"command-{generation}"),
            "operator",
            NOW,
            NOW + timedelta(minutes=1),
            "AUTHORIZED_RUNTIME_OPERATION",
        ),
        operation,
        "authorization-1",
        "placement-1",
    )


def test_start_persists_intent_before_effect_and_observes() -> None:
    events = []

    class Repository(InMemoryRuntimeControlRepository):
        def append_desired(self, value):
            events.append("persist")
            super().append_desired(value)

    class Provider(NativeRuntimeProvider):
        def start_runtime(self, identity):
            events.append("effect")
            return super().start_runtime(identity)

    repository = Repository()
    manager = RuntimeManager(
        repository=repository,
        provider=Provider(lifecycle_driver=Driver()),
        clock=lambda: NOW,
    )
    manager.request(command(), authorized_scope=SCOPE)
    result = manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    assert events == ["persist", "effect"]
    assert result.result is CommandResult.OBSERVED


def test_restart_reobserves_without_reissuing_start() -> None:
    repository = InMemoryRuntimeControlRepository()
    provider = NativeRuntimeProvider(lifecycle_driver=Driver())
    first = RuntimeManager(repository=repository, provider=provider, clock=lambda: NOW)
    first.request(command(), authorized_scope=SCOPE)
    first.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    before = provider.observe_runtime("runtime-1")
    restarted = RuntimeManager(
        repository=repository, provider=provider, clock=lambda: NOW
    )
    result = restarted.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    assert result.result is CommandResult.OBSERVED
    assert provider.observe_runtime("runtime-1") == before


def test_ambiguous_effect_requires_recovery_and_is_not_reissued() -> None:
    class AmbiguousProvider(NativeRuntimeProvider):
        calls = 0

        def start_runtime(self, identity):
            self.calls += 1
            raise TimeoutError("untrusted-provider-payload")

    repository = InMemoryRuntimeControlRepository()
    provider = AmbiguousProvider()
    manager = RuntimeManager(
        repository=repository, provider=provider, clock=lambda: NOW
    )
    manager.request(command(), authorized_scope=SCOPE)
    assert (
        manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE).result
        is CommandResult.RECOVERY_REQUIRED
    )
    assert (
        manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE).result
        is CommandResult.RECOVERY_REQUIRED
    )
    assert provider.calls == 1
    assert "untrusted-provider-payload" not in repr(
        repository.facts(RuntimeInstanceId("runtime-1"))
    )


def test_scope_is_checked_before_effect() -> None:
    repository = InMemoryRuntimeControlRepository()
    manager = RuntimeManager(
        repository=repository, provider=NativeRuntimeProvider(), clock=lambda: NOW
    )
    with pytest.raises(RuntimeControlError, match="COMMAND_SCOPE_MISMATCH"):
        manager.request(command(), authorized_scope=ScopeIdentity("other", "domain-a"))


def test_missing_substrate_observation_remains_unknown() -> None:
    repository = InMemoryRuntimeControlRepository()
    manager = RuntimeManager(
        repository=repository,
        provider=NativeRuntimeProvider(),
        clock=lambda: NOW,
    )
    manager.request(command(), authorized_scope=SCOPE)
    result = manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    assert result.result is CommandResult.UNKNOWN


def test_graceful_stop_blocks_assignment_before_termination_effect() -> None:
    repository = InMemoryRuntimeControlRepository()
    provider = NativeRuntimeProvider(lifecycle_driver=Driver())
    manager = RuntimeManager(
        repository=repository, provider=provider, clock=lambda: NOW
    )
    running = command()
    manager.request(running, authorized_scope=SCOPE)
    running_fact = manager.reconcile(
        RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE
    )
    assert accepts_new_assignment(running.desired, running_fact.observation, at=NOW)
    stopping = command(
        RuntimeDesiredStateKind.STOPPED, RuntimeOperation.STOP, generation=2
    )
    manager.request(stopping, authorized_scope=SCOPE)
    assert not accepts_new_assignment(
        stopping.desired, running_fact.observation, at=NOW
    )
    stopped = manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    assert stopped.result is CommandResult.OBSERVED


def test_replacement_changes_correlation_under_same_product_identity() -> None:
    repository = InMemoryRuntimeControlRepository()
    provider = NativeRuntimeProvider(lifecycle_driver=Driver())
    manager = RuntimeManager(
        repository=repository, provider=provider, clock=lambda: NOW
    )
    running = command()
    manager.request(running, authorized_scope=SCOPE)
    first = manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    replacing = command(
        RuntimeDesiredStateKind.REPLACED,
        RuntimeOperation.REPLACE,
        generation=2,
    )
    manager.request(replacing, authorized_scope=SCOPE)
    replaced = manager.reconcile(RuntimeInstanceId("runtime-1"), authorized_scope=SCOPE)
    assert (
        replaced.observation.runtime_instance_id
        == first.observation.runtime_instance_id
    )
    assert (
        replaced.observation.provider_correlation
        != first.observation.provider_correlation
    )
