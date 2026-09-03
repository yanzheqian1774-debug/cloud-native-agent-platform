from datetime import UTC, datetime, timedelta

from agent_operator.compatibility_interpreter import interpret_legacy_task
from agent_operator.openclaw_runtime_adapter import (
    OpenClawRuntimeApplicationAdapter,
    OpenClawRuntimeAssembly,
)
from agent_operator.runtime_identity_translation import (
    AgentInstanceId,
    AttemptId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeInstanceId,
    ScopeIdentity,
    TaskRunId,
    WorkflowRunId,
)
from agent_operator.runtime_manager import (
    CommandId,
    CommandResult,
    Generation,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeHealth,
    RuntimeOperation,
    RuntimeReadiness,
    ScopedRuntimeCommand,
)
from agent_runtime.providers.openclaw import EXACT_TARGET, OpenClawRuntimeProvider
from agent_runtime.providers.openclaw.models import (
    HealthState,
    LifecycleState,
    ProviderCorrelation,
    ReadinessState,
    RuntimeMode,
    RuntimeObservation,
    SessionAffinity,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
SCOPE = ScopeIdentity("tenant-a", "domain-a")


class Transport:
    def __init__(self):
        self.runtime = {}
        self.starts = 0
        self.sequence = 0

    def preflight(self):
        return EXACT_TARGET

    def _value(self, binding, state=LifecycleState.RUNNING):
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
            ProviderCorrelation(f"gateway-{self.sequence}"),
        )

    def start(self, binding):
        self.starts += 1
        self.sequence += 1
        value = self._value(binding)
        self.runtime[binding.runtime_instance_id] = value
        return value

    def observe_runtime(self, binding):
        value = self.runtime.get(binding.runtime_instance_id)
        return () if value is None else (value,)

    def stop(self, binding):
        value = self._value(binding, LifecycleState.TERMINATED)
        self.runtime[binding.runtime_instance_id] = value
        return value

    def replace(self, binding):
        self.sequence += 1
        value = self._value(binding)
        self.runtime[binding.runtime_instance_id] = value
        return value

    def execute(self, request):
        raise AssertionError("not used")

    def observe_execution(self, request):
        return ()


def assembly(*, generation=1, stateful=False, operation=RuntimeOperation.START):
    envelope = interpret_legacy_task(
        task_spec={"agentRef": {"name": "definition-1"}},
        task_metadata={"name": "task", "namespace": "tenant-a", "uid": "task-1"},
        namespace="tenant-a",
        agent_candidates=[
            {
                "metadata": {
                    "name": "definition-1",
                    "namespace": "tenant-a",
                    "uid": "agent-uid-1",
                    "creationTimestamp": "2026-09-03T00:00:00Z",
                },
                "spec": {"runtime": {"type": "openclaw"}},
            }
        ],
    )
    request = PlacementRequest(
        PlacementRequestId("request-1"),
        SCOPE,
        WorkflowRunId("workflow-1"),
        TaskRunId("task-1"),
        AttemptId("attempt-1"),
        AgentInstanceId(envelope.selected_instance_id.value),
        "agent-revision-1",
        "profile-1",
        (),
        (),
        (),
        (),
        NOW,
    )
    decision = PlacementDecision.create(
        placement_id=PlacementId("placement-1"),
        request_id=request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=RuntimeInstanceId("runtime-1"),
        policy_version="policy-1",
        compatibility_facts=("OPENCLAW_2026.7.1-2",),
        limitation_codes=(),
        decided_at=NOW,
    )
    desired = {
        RuntimeOperation.START: RuntimeDesiredStateKind.RUNNING,
        RuntimeOperation.STOP: RuntimeDesiredStateKind.STOPPED,
        RuntimeOperation.REPLACE: RuntimeDesiredStateKind.REPLACED,
        RuntimeOperation.OBSERVE: RuntimeDesiredStateKind.OBSERVE,
    }[operation]
    command = ScopedRuntimeCommand(
        SCOPE,
        RuntimeDesiredState(
            RuntimeInstanceId("runtime-1"),
            Generation(generation),
            desired,
            CommandId(f"command-{generation}-{operation.value}"),
            "operator",
            NOW,
            NOW + timedelta(minutes=1),
            "AUTHORIZED",
        ),
        operation,
        "authorization-1",
        "placement-1",
    )
    return OpenClawRuntimeAssembly(
        envelope,
        request,
        decision,
        command,
        RuntimeMode.STATEFUL if stateful else RuntimeMode.STATELESS,
        SessionAffinity.REQUIRED if stateful else SessionAffinity.NONE,
        NOW,
        "session-1" if stateful else None,
    )


def test_openclaw_exact_version_adapter_preserves_identity_and_status_dimensions() -> (
    None
):
    transport = Transport()
    adapter = OpenClawRuntimeApplicationAdapter(OpenClawRuntimeProvider(transport))
    result = adapter.apply(assembly())
    assert result.result is CommandResult.OBSERVED
    assert result.observation.runtime_instance_id == RuntimeInstanceId("runtime-1")
    assert result.observation.health is RuntimeHealth.HEALTHY
    assert result.observation.readiness is RuntimeReadiness.READY
    assert result.observation.provider_correlation.handle == "gateway-1"


def test_replay_observes_without_blind_start_and_restart_reacquires() -> None:
    transport = Transport()
    value = assembly()
    adapter = OpenClawRuntimeApplicationAdapter(OpenClawRuntimeProvider(transport))
    adapter.apply(value)
    adapter.apply(value)
    assert transport.starts == 1
    restarted = OpenClawRuntimeApplicationAdapter(OpenClawRuntimeProvider(transport))
    observed = restarted.apply(value)
    assert observed.result is CommandResult.OBSERVED
    assert transport.starts == 1


def test_stateful_affinity_and_graceful_stop_then_bounded_replacement() -> None:
    transport = Transport()
    adapter = OpenClawRuntimeApplicationAdapter(OpenClawRuntimeProvider(transport))
    adapter.apply(assembly(stateful=True))
    prior = transport.runtime["runtime-1"]
    stopped = adapter.apply(assembly(stateful=True, operation=RuntimeOperation.STOP))
    assert stopped.observation.observed_state.value == "TERMINATED"
    transport.runtime["runtime-1"] = prior
    replaced = adapter.apply(
        assembly(generation=2, stateful=True, operation=RuntimeOperation.REPLACE)
    )
    assert replaced.observation.observed_generation == Generation(2)


def test_provider_failure_is_sanitized_and_classified() -> None:
    class Broken(Transport):
        def start(self, binding):
            raise RuntimeError("secret-token=do-not-leak")

    result = OpenClawRuntimeApplicationAdapter(OpenClawRuntimeProvider(Broken())).apply(
        assembly()
    )
    assert result.result is CommandResult.RECOVERY_REQUIRED
    assert "secret-token" not in repr(result)
