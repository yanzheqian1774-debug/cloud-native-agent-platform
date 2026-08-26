"""Read-only adapters over existing component test seams.

This package imports production components; production code never imports the
Harness. Each adapter asserts an exact, current implementation boundary.
"""

from copy import deepcopy

from agent_core.representation.v0_2 import NativeCorrelationId
from agent_gateway.capability import (
    AuthorizationContext,
    CapabilityGateway,
    CapabilityIdentity,
    CapabilityRequest,
    CapabilityStatus,
    ProviderIdentity,
    RestProvider,
    RestProviderConfiguration,
)
from agent_operator.compatibility_interpreter import interpret_legacy_task
from agent_operator.execution_coordinator import (
    DeclaredCapabilityAuthorization,
    DeterministicSyntheticTransport,
    ExecutionClassification,
    TaskExecutionContext,
    TaskExecutionCoordinator,
    build_capability_plan,
    build_runtime_configuration,
)
from agent_runtime.providers.native import NativeRuntimeProvider

from .models import Criterion, Evidence, EvidenceClassification

TASK_SPEC = {
    "agentRef": {"name": "researcher-agent"},
    "input": {"prompt": "research this topic"},
}
TASK_META = {
    "name": "test-task",
    "namespace": "agent-workloads",
    "uid": "task-uid-s5-test-005",
}
AGENT = {
    "metadata": {
        "name": "researcher-agent",
        "namespace": "agent-workloads",
        "uid": "agent-uid-s5-test-005",
        "creationTimestamp": "2026-08-24T00:00:00Z",
    },
    "spec": {
        "runtime": {"type": "native"},
        "model": {"provider": "mock", "name": "mock-model"},
        "capabilities": ["customer-lookup"],
    },
}


def _envelope():
    return interpret_legacy_task(
        task_spec=TASK_SPEC,
        task_metadata=TASK_META,
        namespace="agent-workloads",
        agent_candidates=[AGENT],
    )


def identity_spine(criterion: Criterion) -> Evidence:
    first = _envelope()
    second = _envelope()
    handed_off = first.with_native_correlation(
        NativeCorrelationId("native-correlation")
    )
    assert first.execution_identity == second.execution_identity
    assert handed_off.execution_identity is first.execution_identity
    assert len(handed_off.native_correlations) == 1
    assert handed_off.native_correlations[0].value != first.execution_identity.value
    return Evidence(
        EvidenceClassification.TESTED,
        True,
        {
            "boundary": criterion.target,
            "platform_execution_identity_authoritative": True,
            "native_identity_correlation_only": True,
        },
    )


def compatibility_interpreter(criterion: Criterion) -> Evidence:
    task = deepcopy(TASK_SPEC)
    agent = deepcopy(AGENT)
    first = _envelope()
    second = _envelope()
    assert first == second
    assert task == TASK_SPEC
    assert agent == AGENT
    return Evidence(
        EvidenceClassification.TESTED,
        True,
        {
            "boundary": criterion.target,
            "deterministic": True,
            "caller_inputs_mutated": False,
        },
    )


def native_provider(criterion: Criterion) -> Evidence:
    envelope = _envelope()
    configuration = build_runtime_configuration(
        definition_evidence=AGENT,
        namespace="agent-workloads",
        agent_name="researcher-agent",
    )
    outcome = TaskExecutionCoordinator(native_provider=NativeRuntimeProvider()).execute(
        context=TaskExecutionContext(
            envelope=envelope, runtime_configuration=configuration
        ),
        input_text="research this topic",
    )
    assert outcome.classification is ExecutionClassification.SUCCEEDED
    assert outcome.platform_execution_identity == envelope.execution_identity.value
    assert (
        outcome.runtime.correlation.native_invocation_id
        != outcome.platform_execution_identity
    )
    return Evidence(
        EvidenceClassification.SUPPORTED_CANDIDATE,
        True,
        {
            "boundary": criterion.target,
            "requested_runtime": outcome.requested_runtime,
            "effective_runtime": outcome.effective_runtime,
        },
    )


def capability_gateway(criterion: Criterion) -> Evidence:
    envelope = _envelope()
    capability = CapabilityIdentity("customer-lookup")
    gateway = CapabilityGateway(
        DeclaredCapabilityAuthorization(capability),
        RestProvider(
            RestProviderConfiguration(
                provider=ProviderIdentity("s5.synthetic-rest"),
                target="https://synthetic.invalid/capabilities/customer-lookup",
                allowed_hosts=("synthetic.invalid",),
                allowed_operations=("invoke",),
            ),
            DeterministicSyntheticTransport(),
        ),
    )
    request = CapabilityRequest(
        capability=capability,
        operation="invoke",
        execution_identity=envelope.execution_identity,
        arguments={"query": "bounded"},
    )
    context = AuthorizationContext(
        subject="researcher-agent",
        tenant="agent-workloads",
        execution_identity=envelope.execution_identity,
    )
    first = gateway.execute(request, context)
    second = gateway.execute(request, context)
    assert first.status is CapabilityStatus.SUCCEEDED
    assert first == second
    assert first.execution_identity == envelope.execution_identity
    return Evidence(
        EvidenceClassification.TESTED,
        True,
        {"boundary": criterion.target, "synthetic_rest": True, "deterministic": True},
    )


def mvs_execution(criterion: Criterion) -> Evidence:
    envelope = _envelope()
    configuration = build_runtime_configuration(
        definition_evidence=AGENT,
        namespace="agent-workloads",
        agent_name="researcher-agent",
    )
    plan = build_capability_plan(
        definition_evidence=AGENT,
        envelope=envelope,
        input_text="research this topic",
    )
    assert plan is not None
    gateway = CapabilityGateway(
        DeclaredCapabilityAuthorization(plan.capability),
        RestProvider(
            RestProviderConfiguration(
                provider=ProviderIdentity("s5.synthetic-rest"),
                target="https://synthetic.invalid/capabilities/customer-lookup",
                allowed_hosts=("synthetic.invalid",),
                allowed_operations=("invoke",),
            ),
            DeterministicSyntheticTransport(),
        ),
    )
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(), capability_gateway=gateway
    ).execute(
        context=TaskExecutionContext(
            envelope=envelope,
            runtime_configuration=configuration,
            capability_plan=plan,
        ),
        input_text="research this topic",
    )
    assert outcome.classification is ExecutionClassification.SUCCEEDED
    assert outcome.capability is not None
    assert outcome.capability.status is CapabilityStatus.SUCCEEDED
    assert outcome.capability.execution_identity == envelope.execution_identity
    return Evidence(
        EvidenceClassification.SUPPORTED_CANDIDATE,
        True,
        {"boundary": criterion.target, "runtime_and_capability_observed": True},
    )


ADAPTERS = {
    "identity_spine": identity_spine,
    "compatibility_interpreter": compatibility_interpreter,
    "native_provider": native_provider,
    "capability_gateway": capability_gateway,
    "mvs_execution": mvs_execution,
}
