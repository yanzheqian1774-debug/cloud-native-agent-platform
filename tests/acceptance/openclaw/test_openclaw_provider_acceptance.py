import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_runtime.providers.openclaw import EXACT_TARGET, OpenClawRuntimeProvider
from agent_runtime.providers.openclaw.models import (
    ExecutionLinkage,
    ExecutionObservation,
    ExecutionRequest,
    ExecutionState,
    HealthState,
    LifecycleState,
    ProviderCorrelation,
    ReadinessState,
    ReasonCode,
    RuntimeBinding,
    RuntimeMode,
    RuntimeObservation,
    SessionAffinity,
)

NOW = datetime(2026, 9, 2, tzinfo=UTC)
MANIFEST = (
    Path(__file__).parents[3] / "manifests/acceptance/openclaw/openclaw-2026.7.1-2.json"
)


class ExactVersionAcceptanceTransport:
    """Deterministic provider-local protocol peer, never a live-execution claim."""

    def __init__(self):
        self.runtime = None
        self.execution = None
        self.sequence = 0

    def preflight(self):
        return EXACT_TARGET

    def start(self, binding):
        self.sequence += 1
        self.runtime = RuntimeObservation(
            binding.runtime_instance_id,
            binding.generation,
            LifecycleState.RUNNING,
            HealthState.HEALTHY,
            ReadinessState.READY,
            NOW,
            NOW + timedelta(seconds=30),
            ProviderCorrelation(f"gateway-{self.sequence}"),
        )
        return self.runtime

    def observe_runtime(self, binding):
        return (self.runtime,) if self.runtime else ()

    def execute(self, request):
        self.execution = ExecutionObservation(
            request.linkage,
            ExecutionState.ACCEPTED,
            NOW,
            ProviderCorrelation(self.runtime.correlation.gateway_id, "run-1"),
            ReasonCode.EXECUTION_ACCEPTED,
        )
        return self.execution

    def observe_execution(self, request):
        return (self.execution,) if self.execution else ()

    def stop(self, binding):
        self.runtime = RuntimeObservation(
            binding.runtime_instance_id,
            binding.generation,
            LifecycleState.TERMINATED,
            HealthState.UNKNOWN,
            ReadinessState.NOT_READY,
            NOW,
            NOW + timedelta(seconds=30),
            self.runtime.correlation,
        )
        return self.runtime

    def replace(self, binding):
        return self.start(binding)


def test_exact_version_provider_local_acceptance() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["runtime_exact_version"] == EXACT_TARGET.version
    assert manifest["runtime_tag_commit"] == EXACT_TARGET.tag_commit
    assert manifest["npm_integrity"] == EXACT_TARGET.package_integrity

    transport = ExactVersionAcceptanceTransport()
    provider = OpenClawRuntimeProvider(transport)
    binding = RuntimeBinding(
        "acceptance",
        "domain",
        "runtime-acceptance-1",
        "placement-acceptance-1",
        1,
        RuntimeMode.STATELESS,
        SessionAffinity.NONE,
    )
    provider.start(binding, at=NOW)
    linkage = ExecutionLinkage(
        "workflow-run-1",
        "task-run-1",
        "attempt-1",
        "agent-1",
        binding.runtime_instance_id,
        binding.placement_id,
    )
    request = ExecutionRequest(linkage, "input-reference-1", "idempotency-1")
    accepted = provider.execute(binding, request, at=NOW)
    transport.execution = ExecutionObservation(
        linkage,
        ExecutionState.SUCCEEDED,
        NOW,
        accepted.correlation,
        ReasonCode.EXECUTION_TERMINAL,
        "result-reference-1",
    )
    assert provider.observe_execution(request).state is ExecutionState.SUCCEEDED
    assert provider.stop(binding, at=NOW).state is LifecycleState.TERMINATED
