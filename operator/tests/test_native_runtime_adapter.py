from datetime import UTC, datetime, timedelta

import pytest
from agent_operator.compatibility_interpreter import interpret_legacy_task
from agent_operator.native_runtime_adapter import (
    NativeRuntimeAdapterError,
    NativeRuntimeApplicationAdapter,
    NativeRuntimeAssembly,
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
    Generation,
    InMemoryRuntimeControlRepository,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeManager,
    RuntimeOperation,
    ScopedRuntimeCommand,
)
from agent_runtime.providers.native import NativeRuntimeProvider
from agent_runtime.providers.native.models import (
    DiagnosticReason,
    NativeLifecycleObservation,
    NativeLifecycleState,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
SCOPE = ScopeIdentity("tenant-a", "domain-a")


class Driver:
    def __init__(self):
        self.values = {}
        self.calls = 0

    def start(self, identity):
        self.calls += 1
        value = NativeLifecycleObservation(
            identity,
            NativeLifecycleState.RUNNING,
            f"native-{self.calls}",
            DiagnosticReason.LIFECYCLE_APPLIED,
        )
        self.values[identity] = value
        return value

    def stop(self, identity):
        value = NativeLifecycleObservation(
            identity,
            NativeLifecycleState.TERMINATED,
            "native-stopped",
            DiagnosticReason.LIFECYCLE_APPLIED,
        )
        self.values[identity] = value
        return value

    def replace(self, identity):
        return self.start(identity)

    def observe(self, identity):
        return self.values.get(identity)


def assembly(*, placement_agent_id=None):
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
                "spec": {"runtime": {"type": "native"}},
            }
        ],
    )
    agent_id = placement_agent_id or envelope.selected_instance_id.value
    request = PlacementRequest(
        PlacementRequestId("request-1"),
        SCOPE,
        WorkflowRunId("workflow-1"),
        TaskRunId("task-1"),
        AttemptId("attempt-1"),
        AgentInstanceId(agent_id),
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
        compatibility_facts=("NATIVE",),
        limitation_codes=(),
        decided_at=NOW,
    )
    command = ScopedRuntimeCommand(
        SCOPE,
        RuntimeDesiredState(
            RuntimeInstanceId("runtime-1"),
            Generation(1),
            RuntimeDesiredStateKind.RUNNING,
            CommandId("command-1"),
            "operator",
            NOW,
            NOW + timedelta(minutes=1),
            "AUTHORIZED",
        ),
        RuntimeOperation.START,
        "authorization-1",
        "placement-1",
    )
    return NativeRuntimeAssembly(envelope, request, decision, command)


def test_native_adapter_reuses_manager_and_preserves_all_product_identities() -> None:
    driver = Driver()
    repository = InMemoryRuntimeControlRepository()
    adapter = NativeRuntimeApplicationAdapter(
        RuntimeManager(
            repository=repository,
            provider=NativeRuntimeProvider(lifecycle_driver=driver),
            clock=lambda: NOW,
        )
    )
    result = adapter.apply(assembly())
    assert result.observation.runtime_instance_id == RuntimeInstanceId("runtime-1")
    assert result.command.desired.command_id == CommandId("command-1")
    assert driver.calls == 1


def test_native_adapter_rejects_agent_identity_substitution_before_effect() -> None:
    driver = Driver()
    adapter = NativeRuntimeApplicationAdapter(
        RuntimeManager(
            repository=InMemoryRuntimeControlRepository(),
            provider=NativeRuntimeProvider(lifecycle_driver=driver),
            clock=lambda: NOW,
        )
    )
    with pytest.raises(
        NativeRuntimeAdapterError, match="AGENT_INSTANCE_IDENTITY_MISMATCH"
    ):
        adapter.apply(assembly(placement_agent_id="provider-session-1"))
    assert driver.calls == 0
