from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest
from agent_runtime.providers.openclaw import EXACT_TARGET, OpenClawRuntimeProvider
from agent_runtime.providers.openclaw.models import (
    EventType,
    ExecutionLinkage,
    ExecutionObservation,
    ExecutionRequest,
    ExecutionState,
    HealthState,
    LifecycleState,
    OpenClawError,
    ProviderCorrelation,
    ReadinessState,
    ReasonCode,
    RuntimeBinding,
    RuntimeMode,
    RuntimeObservation,
    SessionAffinity,
)

NOW = datetime(2026, 9, 2, tzinfo=UTC)


class Transport:
    def __init__(self):
        self.runtime = {}
        self.executions = {}
        self.sequence = 0
        self.target = EXACT_TARGET

    def preflight(self):
        return self.target

    def observation(self, binding, state=LifecycleState.RUNNING, *, gateway=None):
        return RuntimeObservation(
            binding.runtime_instance_id,
            binding.generation,
            state,
            HealthState.HEALTHY,
            ReadinessState.READY
            if state is LifecycleState.RUNNING
            else ReadinessState.NOT_READY,
            NOW,
            NOW + timedelta(seconds=30),
            ProviderCorrelation(gateway or f"gateway-{self.sequence}"),
        )

    def start(self, binding):
        self.sequence += 1
        value = self.observation(binding)
        self.runtime[binding.runtime_instance_id] = value
        return value

    def observe_runtime(self, binding):
        value = self.runtime.get(binding.runtime_instance_id)
        return () if value is None else (value,)

    def execute(self, request):
        value = ExecutionObservation(
            request.linkage,
            ExecutionState.ACCEPTED,
            NOW,
            ProviderCorrelation(
                "gateway-1", "openclaw-run-1", request.session_reference
            ),
            ReasonCode.EXECUTION_ACCEPTED,
        )
        self.executions[request.idempotency_key] = value
        return value

    def observe_execution(self, request):
        value = self.executions.get(request.idempotency_key)
        return () if value is None else (value,)

    def stop(self, binding):
        prior = self.runtime[binding.runtime_instance_id]
        value = self.observation(
            binding, LifecycleState.TERMINATED, gateway=prior.correlation.gateway_id
        )
        self.runtime[binding.runtime_instance_id] = value
        return value

    def replace(self, binding):
        self.sequence += 1
        value = self.observation(binding)
        self.runtime[binding.runtime_instance_id] = value
        return value


def binding(identity="runtime-1", generation=1, *, stateful=False):
    return RuntimeBinding(
        "tenant-a",
        "domain-a",
        identity,
        f"placement-{identity}",
        generation,
        RuntimeMode.STATEFUL if stateful else RuntimeMode.STATELESS,
        SessionAffinity.REQUIRED if stateful else SessionAffinity.NONE,
        "session-context-1" if stateful else None,
    )


def request(value, *, session=None):
    return ExecutionRequest(
        ExecutionLinkage(
            "workflow-run-1",
            "task-run-1",
            "attempt-1",
            "agent-1",
            value.runtime_instance_id,
            value.placement_id,
        ),
        "input-reference-1",
        "idempotency-1",
        session,
    )


def test_multiple_runtime_instances_are_isolated_and_platform_identity_is_stable() -> (
    None
):
    transport = Transport()
    provider = OpenClawRuntimeProvider(transport)
    first, second = binding("runtime-1"), binding("runtime-2")
    one = provider.start(first, at=NOW)
    two = provider.start(second, at=NOW)
    assert one.runtime_instance_id == "runtime-1"
    assert two.runtime_instance_id == "runtime-2"
    assert one.correlation.gateway_id != two.correlation.gateway_id
    assert one.correlation.gateway_id not in {"runtime-1", "runtime-2"}


def test_accepted_running_and_terminal_execution_preserves_full_linkage() -> None:
    transport = Transport()
    provider = OpenClawRuntimeProvider(transport)
    value = binding()
    provider.start(value, at=NOW)
    execution = request(value)
    accepted = provider.execute(value, execution, at=NOW)
    assert accepted.state is ExecutionState.ACCEPTED
    running = ExecutionObservation(
        execution.linkage,
        ExecutionState.RUNNING,
        NOW,
        accepted.correlation,
        ReasonCode.EXECUTION_RUNNING,
    )
    transport.executions[execution.idempotency_key] = running
    assert provider.observe_execution(execution).state is ExecutionState.RUNNING
    terminal = ExecutionObservation(
        execution.linkage,
        ExecutionState.SUCCEEDED,
        NOW,
        accepted.correlation,
        ReasonCode.EXECUTION_TERMINAL,
        "result-reference-1",
    )
    transport.executions[execution.idempotency_key] = terminal
    assert provider.observe_execution(execution) == terminal


def test_health_readiness_and_freshness_are_independent_fail_closed_facts() -> None:
    transport = Transport()
    provider = OpenClawRuntimeProvider(transport)
    value = binding()
    observed = provider.start(value, at=NOW)
    transport.runtime[value.runtime_instance_id] = RuntimeObservation(
        value.runtime_instance_id,
        value.generation,
        LifecycleState.RUNNING,
        HealthState.DEGRADED,
        ReadinessState.NOT_READY,
        observed.observed_at,
        observed.freshness_deadline,
        observed.correlation,
    )
    assert provider.observe_runtime(value, at=NOW).health is HealthState.DEGRADED
    with pytest.raises(OpenClawError, match=ReasonCode.OBSERVATION_UNKNOWN.value):
        provider.execute(value, request(value), at=NOW)
    with pytest.raises(OpenClawError, match=ReasonCode.OBSERVATION_STALE.value):
        provider.observe_runtime(value, at=NOW + timedelta(minutes=1))


def test_graceful_stop_and_bounded_replacement_preserve_runtime_identity() -> None:
    transport = Transport()
    provider = OpenClawRuntimeProvider(transport)
    first = binding()
    started = provider.start(first, at=NOW)
    assert provider.stop(first, at=NOW).state is LifecycleState.TERMINATED
    # Re-establish the old observation, then replace at the successor generation.
    transport.runtime[first.runtime_instance_id] = started
    successor = binding(generation=2)
    replaced = provider.replace(successor, at=NOW)
    assert replaced.runtime_instance_id == first.runtime_instance_id
    assert replaced.correlation.gateway_id != started.correlation.gateway_id


def test_stateful_requires_affinity_and_stateless_prohibits_it() -> None:
    with pytest.raises(OpenClawError, match=ReasonCode.SESSION_AFFINITY_REQUIRED.value):
        RuntimeBinding(
            "tenant",
            "domain",
            "runtime",
            "placement",
            1,
            RuntimeMode.STATEFUL,
            SessionAffinity.REQUIRED,
        )
    transport = Transport()
    provider = OpenClawRuntimeProvider(transport)
    stateful = binding(stateful=True)
    provider.start(stateful, at=NOW)
    with pytest.raises(OpenClawError, match=ReasonCode.SESSION_AFFINITY_REQUIRED.value):
        provider.execute(stateful, request(stateful), at=NOW)
    assert (
        provider.execute(
            stateful, request(stateful, session="session-context-1"), at=NOW
        ).state
        is ExecutionState.ACCEPTED
    )


def test_missing_conflicting_unknown_and_opaque_id_substitution_fail_closed() -> None:
    transport = Transport()
    provider = OpenClawRuntimeProvider(transport)
    value = binding()
    with pytest.raises(OpenClawError, match=ReasonCode.OBSERVATION_MISSING.value):
        provider.observe_runtime(value, at=NOW)
    provider.start(value, at=NOW)
    valid = transport.runtime[value.runtime_instance_id]
    transport.observe_runtime = lambda ignored: (valid, valid)
    with pytest.raises(OpenClawError, match=ReasonCode.OBSERVATION_CONFLICTING.value):
        provider.observe_runtime(value, at=NOW)
    transport.observe_runtime = lambda ignored: (
        RuntimeObservation(
            value.runtime_instance_id,
            value.generation,
            LifecycleState.UNKNOWN,
            HealthState.UNKNOWN,
            ReadinessState.UNKNOWN,
            NOW,
            NOW + timedelta(seconds=30),
            valid.correlation,
        ),
    )
    with pytest.raises(OpenClawError, match=ReasonCode.OBSERVATION_UNKNOWN.value):
        provider.observe_runtime(value, at=NOW)


def test_restart_reobserves_without_starting_and_evidence_is_sanitized() -> None:
    transport = Transport()
    first = OpenClawRuntimeProvider(transport)
    value = binding()
    first.start(value, at=NOW)
    sequence = transport.sequence
    restarted = OpenClawRuntimeProvider(transport)
    restarted.observe_runtime(value, at=NOW)
    assert transport.sequence == sequence
    execution = request(value)
    transport.executions[execution.idempotency_key] = ExecutionObservation(
        execution.linkage,
        ExecutionState.SUCCEEDED,
        NOW,
        ProviderCorrelation("gateway-private", "run-private", None),
        ReasonCode.EXECUTION_TERMINAL,
        "result-reference-1",
    )
    terminal = restarted.observe_execution(execution)
    evidence = restarted.evidence(
        EventType.EXECUTION_TERMINAL,
        ReasonCode.EXECUTION_TERMINAL,
        value,
        execution,
        terminal,
        recorded_at=NOW,
    )
    serialized = repr(asdict(evidence))
    assert "gateway-private" not in serialized
    assert "run-private" not in serialized
    assert "input-reference-1" not in serialized
    assert "result-reference-1" not in serialized
    assert len(evidence.provider_correlation_digest) == 64


def test_ambiguous_execution_is_never_blindly_reissued() -> None:
    class AmbiguousTransport(Transport):
        calls = 0

        def execute(self, request):
            self.calls += 1
            raise TimeoutError("raw-provider-payload")

    transport = AmbiguousTransport()
    provider = OpenClawRuntimeProvider(transport)
    value = binding()
    provider.start(value, at=NOW)
    execution = request(value)
    for _ in range(2):
        with pytest.raises(
            OpenClawError, match=ReasonCode.PROVIDER_EFFECT_AMBIGUOUS.value
        ):
            provider.execute(value, execution, at=NOW)
    assert transport.calls == 1
    assert "raw-provider-payload" not in repr(provider)


def test_transport_has_no_arbitrary_command_or_disclosure_api() -> None:
    names = set(Transport.__dict__)
    prohibited = {"exec", "command", "apply_yaml", "environment", "logs", "secret"}
    assert names.isdisjoint(prohibited)
