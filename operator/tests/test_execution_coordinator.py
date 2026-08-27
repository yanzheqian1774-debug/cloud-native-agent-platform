from dataclasses import replace

import pytest
from agent_core.execution_evidence import (
    AppendDisposition,
    AppendResult,
    EvidenceDigestConflict,
    EvidenceRepositoryUnavailable,
)
from agent_gateway.capability import (
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationResult,
    CapabilityGateway,
    CapabilityStatus,
    DecisionReason,
    ProviderIdentity,
    ProviderResponse,
    RestProvider,
    RestProviderConfiguration,
    TransportAmbiguityError,
)
from agent_operator.compatibility_interpreter import interpret_legacy_task
from agent_operator.execution_coordinator import (
    CapabilityPlan,
    EvidenceAvailability,
    ExecutionClassification,
    TaskExecutionContext,
    TaskExecutionCoordinator,
    build_capability_plan,
    build_runtime_configuration,
)
from agent_runtime.providers.native import NativeRuntimeProvider
from agent_runtime.providers.native.provider import NativeInvocationAmbiguousTimeout

TASK_SPEC = {
    "agentRef": {"name": "researcher-agent"},
    "input": {"prompt": "research this topic"},
}
TASK_META = {
    "name": "test-task",
    "namespace": "agent-workloads",
    "uid": "task-uid-001",
}
AGENT = {
    "metadata": {
        "name": "researcher-agent",
        "namespace": "agent-workloads",
        "uid": "agent-uid-001",
        "creationTimestamp": "2026-08-24T00:00:00Z",
    },
    "spec": {
        "runtime": {"type": "native"},
        "model": {"provider": "mock", "name": "mock-model"},
        "capabilities": ["customer-lookup"],
    },
}


def execution_context(*, capability: bool = False) -> TaskExecutionContext:
    envelope = interpret_legacy_task(
        task_spec=TASK_SPEC,
        task_metadata=TASK_META,
        namespace="agent-workloads",
        agent_candidates=[AGENT],
    )
    return TaskExecutionContext(
        envelope=envelope,
        runtime_configuration=build_runtime_configuration(
            definition_evidence=AGENT,
            namespace="agent-workloads",
            agent_name="researcher-agent",
        ),
        capability_plan=(
            build_capability_plan(
                definition_evidence=AGENT,
                envelope=envelope,
                input_text="research this topic",
            )
            if capability
            else None
        ),
    )


class FixedAuthorization:
    def __init__(self, decision: AuthorizationDecision) -> None:
        self.decision = decision
        self.calls = 0

    def decide(self, request, context):
        self.calls += 1
        return AuthorizationResult(
            decisions=(self.decision,), reason=DecisionReason("TEST_DECISION")
        )


class CountingTransport:
    def __init__(self) -> None:
        self.calls = []

    def send(self, request):
        self.calls.append(request)
        return ProviderResponse(200, {"quality": "accepted"})


def capability_gateway(decision: AuthorizationDecision):
    authorization = FixedAuthorization(decision)
    transport = CountingTransport()
    provider = RestProvider(
        RestProviderConfiguration(
            provider=ProviderIdentity("test.synthetic-rest"),
            target="https://synthetic.invalid/capabilities/customer-lookup",
            allowed_hosts=("synthetic.invalid",),
            allowed_operations=("invoke",),
        ),
        transport,
    )
    return CapabilityGateway(authorization, provider), authorization, transport


def test_native_execution_preserves_platform_identity_and_invokes_once() -> None:
    calls = []

    def invoke(identity, input_text, configuration):
        calls.append((identity, input_text, configuration))
        from agent_runtime.providers.native.models import NativeInvocation

        return NativeInvocation("native result", "native-correlation")

    context = execution_context()
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(invoke)
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is ExecutionClassification.SUCCEEDED
    assert outcome.result == "native result"
    assert len(calls) == 1
    assert calls[0][0] == context.envelope.execution_identity.value
    assert outcome.platform_execution_identity == calls[0][0]
    assert outcome.runtime.correlation.native_invocation_id == "native-correlation"
    assert outcome.runtime.correlation.native_invocation_id != calls[0][0]


def test_capability_absent_does_not_invoke_gateway() -> None:
    class FailIfInvokedGateway:
        def execute(self, request, context):
            raise AssertionError("Capability Gateway must not be invoked")

    context = execution_context(capability=False)
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(),
        capability_gateway=FailIfInvokedGateway(),
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is ExecutionClassification.SUCCEEDED
    assert outcome.capability is None


@pytest.mark.parametrize(
    ("decision", "classification", "provider_calls"),
    [
        (AuthorizationDecision.ALLOW, ExecutionClassification.SUCCEEDED, 1),
        (AuthorizationDecision.DENY, ExecutionClassification.DENIED, 0),
    ],
)
def test_capability_authorization_precedes_exact_invocation_count(
    decision, classification, provider_calls
) -> None:
    gateway, authorization, transport = capability_gateway(decision)
    context = execution_context(capability=True)
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(), capability_gateway=gateway
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is classification
    assert authorization.calls == 1
    assert len(transport.calls) == provider_calls
    assert outcome.capability is not None
    assert outcome.capability.execution_identity == context.envelope.execution_identity
    if decision is AuthorizationDecision.ALLOW:
        assert outcome.capability.status is CapabilityStatus.SUCCEEDED


def test_runtime_timeout_is_unknown_and_capability_is_not_invoked() -> None:
    def ambiguous(*_):
        raise NativeInvocationAmbiguousTimeout

    gateway, authorization, transport = capability_gateway(AuthorizationDecision.ALLOW)
    context = execution_context(capability=True)
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(ambiguous), capability_gateway=gateway
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is ExecutionClassification.UNKNOWN
    assert outcome.retry_safe is False
    assert outcome.result is None
    assert authorization.calls == 0
    assert transport.calls == []


def test_non_mock_native_profile_is_rejected_before_invocation() -> None:
    calls = []

    def invoke(*args):
        calls.append(args)
        raise AssertionError("mismatched profile must not invoke")

    context = execution_context()
    context = replace(
        context,
        runtime_configuration={
            **context.runtime_configuration,
            "MODEL_PROVIDER": "openai-compatible",
        },
    )
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(invoke)
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is ExecutionClassification.FAILED
    assert outcome.result is None
    assert calls == []


def test_non_native_runtime_binding_is_rejected_before_invocation() -> None:
    calls = []

    def invoke(*args):
        calls.append(args)
        raise AssertionError("non-Native target must not invoke")

    external_agent = {
        **AGENT,
        "spec": {**AGENT["spec"], "runtime": {"type": "external"}},
    }
    envelope = interpret_legacy_task(
        task_spec=TASK_SPEC,
        task_metadata=TASK_META,
        namespace="agent-workloads",
        agent_candidates=[external_agent],
    )
    context = TaskExecutionContext(
        envelope=envelope,
        runtime_configuration=build_runtime_configuration(
            definition_evidence=external_agent,
            namespace="agent-workloads",
            agent_name="researcher-agent",
        ),
    )
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(invoke)
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is ExecutionClassification.FAILED
    assert outcome.result is None
    assert calls == []


def test_capability_identity_mismatch_fails_before_gateway() -> None:
    gateway, authorization, transport = capability_gateway(AuthorizationDecision.ALLOW)
    context = execution_context(capability=True)
    assert context.capability_plan is not None
    mismatched = AuthorizationContext(
        subject="researcher-agent",
        tenant="agent-workloads",
        execution_identity=replace(
            context.envelope.execution_identity, value="different-execution"
        ),
    )
    context = replace(
        context,
        capability_plan=replace(context.capability_plan, authorization=mismatched),
    )

    with pytest.raises(ValueError, match="identity mismatch"):
        TaskExecutionCoordinator(
            native_provider=NativeRuntimeProvider(), capability_gateway=gateway
        ).execute(context=context, input_text="research this topic")

    assert authorization.calls == 0
    assert transport.calls == []


def test_requested_capability_requires_explicit_gateway() -> None:
    context = execution_context(capability=True)
    with pytest.raises(ValueError, match="without a configured gateway"):
        TaskExecutionCoordinator(native_provider=NativeRuntimeProvider()).execute(
            context=context, input_text="research this topic"
        )


def test_capability_plan_does_not_mutate_agent_or_input() -> None:
    context = execution_context()
    capabilities_before = list(AGENT["spec"]["capabilities"])
    prompt = "research this topic"
    plan = build_capability_plan(
        definition_evidence=AGENT,
        envelope=context.envelope,
        input_text=prompt,
    )

    assert isinstance(plan, CapabilityPlan)
    assert AGENT["spec"]["capabilities"] == capabilities_before
    assert prompt == "research this topic"


def test_execution_context_defensively_copies_caller_mappings() -> None:
    envelope = execution_context().envelope
    runtime_configuration = {"MODEL_PROVIDER": "mock"}
    arguments = {"nested": {"value": "original"}}
    plan = CapabilityPlan(
        capability=build_capability_plan(
            definition_evidence=AGENT,
            envelope=envelope,
            input_text="research this topic",
        ).capability,
        operation="invoke",
        arguments=arguments,
        authorization=AuthorizationContext(
            subject="researcher-agent",
            tenant="agent-workloads",
            execution_identity=envelope.execution_identity,
        ),
    )
    context = TaskExecutionContext(
        envelope=envelope,
        runtime_configuration=runtime_configuration,
        capability_plan=plan,
    )

    runtime_configuration["MODEL_PROVIDER"] = "changed"
    arguments["nested"]["value"] = "changed"

    assert context.runtime_configuration["MODEL_PROVIDER"] == "mock"
    assert context.capability_plan is not None
    assert context.capability_plan.arguments["nested"]["value"] == "original"


@pytest.mark.parametrize(
    "capabilities",
    [
        ["customer-lookup", "document-read"],
        [""],
        "customer-lookup",
    ],
)
def test_malformed_or_ambiguous_capability_declaration_fails_closed(
    capabilities,
) -> None:
    context = execution_context()
    invalid_agent = {**AGENT, "spec": {**AGENT["spec"], "capabilities": capabilities}}

    with pytest.raises(ValueError, match="capability evidence"):
        build_capability_plan(
            definition_evidence=invalid_agent,
            envelope=context.envelope,
            input_text="research this topic",
        )


def test_capability_transport_ambiguity_is_unknown_without_retry() -> None:
    class AmbiguousTransport:
        def __init__(self) -> None:
            self.calls = 0

        def send(self, request):
            self.calls += 1
            raise TransportAmbiguityError

    authorization = FixedAuthorization(AuthorizationDecision.ALLOW)
    transport = AmbiguousTransport()
    provider = RestProvider(
        RestProviderConfiguration(
            provider=ProviderIdentity("test.synthetic-rest"),
            target="https://synthetic.invalid/capabilities/customer-lookup",
            allowed_hosts=("synthetic.invalid",),
            allowed_operations=("invoke",),
        ),
        transport,
    )
    context = execution_context(capability=True)
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(),
        capability_gateway=CapabilityGateway(authorization, provider),
    ).execute(context=context, input_text="research this topic")

    assert outcome.classification is ExecutionClassification.UNKNOWN
    assert outcome.retry_safe is False
    assert outcome.result is None
    assert authorization.calls == 1
    assert transport.calls == 1


class RecordingEvidenceRepository:
    def __init__(self, failure=None):
        self.records = []
        self.failure = failure

    def append(self, record):
        self.records.append(record)
        if self.failure is not None:
            raise self.failure
        return AppendResult(AppendDisposition.APPENDED, record)


def test_successful_native_outcome_captures_normalized_evidence() -> None:
    repository = RecordingEvidenceRepository()
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(),
        evidence_repository=repository,
        security_domain="business-unit-a",
        clock=lambda: "2026-08-27T08:00:00Z",
    ).execute(context=execution_context(), input_text="research this topic")

    assert outcome.classification is ExecutionClassification.SUCCEEDED
    assert outcome.evidence_availability is EvidenceAvailability.AVAILABLE
    assert len(repository.records) == 1
    evidence = repository.records[0]
    assert evidence.security_domain == "business-unit-a"
    assert evidence.platform_execution_identity == outcome.platform_execution_identity
    assert "research this topic" not in repr(evidence.canonical_payload)


@pytest.mark.parametrize(
    "failure",
    [
        EvidenceRepositoryUnavailable("EVIDENCE_APPEND_UNAVAILABLE"),
        EvidenceDigestConflict("EVIDENCE_DIGEST_CONFLICT"),
    ],
)
def test_evidence_failure_preserves_truthful_execution_without_provider_replay(
    failure,
) -> None:
    calls = []

    def invoke(identity, input_text, configuration):
        calls.append(identity)
        from agent_runtime.providers.native.models import NativeInvocation

        return NativeInvocation("native result", "native-correlation")

    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(invoke),
        evidence_repository=RecordingEvidenceRepository(failure),
        clock=lambda: "2026-08-27T08:00:00Z",
    ).execute(context=execution_context(), input_text="research this topic")

    assert outcome.classification is ExecutionClassification.SUCCEEDED
    assert outcome.result == "native result"
    assert outcome.evidence_availability is EvidenceAvailability.UNAVAILABLE
    assert outcome.evidence_reason_code == failure.reason_code
    assert len(calls) == 1


def test_deny_evidence_has_zero_provider_calls_and_citations() -> None:
    gateway, _, transport = capability_gateway(AuthorizationDecision.DENY)
    repository = RecordingEvidenceRepository()
    outcome = TaskExecutionCoordinator(
        native_provider=NativeRuntimeProvider(),
        capability_gateway=gateway,
        evidence_repository=repository,
        clock=lambda: "2026-08-27T08:00:00Z",
    ).execute(
        context=execution_context(capability=True), input_text="research this topic"
    )

    assert outcome.classification is ExecutionClassification.DENIED
    assert transport.calls == []
    assert repository.records[0].provider_call_count == 0
    assert repository.records[0].citation_references == ()
