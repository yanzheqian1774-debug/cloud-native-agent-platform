from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest
from agent_core.interface_spine.v0_2 import (
    ROUTING_POLICY,
    AmbiguousInstanceSelectionError,
    DefinitionFacingRequest,
    DeterministicPrototypeInstanceSelector,
    DuplicateSelectionIdentityError,
    ExecutionEnvelopeBuilder,
    InstanceSelectionRequest,
    InternalExecutionEnvelope,
    InvalidDefinitionProjectionError,
    InvalidSelectedInstanceError,
    MissingEffectiveBindingError,
    NativeIdentitySubstitutionError,
    NoEligibleInstanceError,
    RejectAmbiguousInstanceSelector,
    SelectedInstanceResult,
    project_definition,
    select_deterministically,
)
from agent_core.repositories import InMemoryAgentInstanceRepository
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    AgentInstanceLifecycle,
    DesiredRuntimeBinding,
    EffectiveRuntimeBinding,
    NativeCorrelationId,
    PlatformExecutionIdentity,
    RuntimeBinding,
    SelectedInstanceEvidence,
)

NOW = datetime(2026, 8, 24, tzinfo=UTC)


def binding(binding_id: str, *, provider: str = "provider.example") -> RuntimeBinding:
    return RuntimeBinding(
        binding_id=binding_id,
        provider_ref=provider,
        mode="managed",
    )


def instance(
    value: str,
    definition: AgentDefinitionRef,
    *,
    effective: bool = True,
    lifecycle: AgentInstanceLifecycle = AgentInstanceLifecycle.ACTIVE,
) -> AgentInstance:
    desired = DesiredRuntimeBinding(binding("desired"))
    return AgentInstance(
        instance_id=AgentInstanceId(value),
        definition_ref=definition,
        lifecycle=lifecycle,
        desired_runtime_binding=desired,
        effective_runtime_binding=(
            EffectiveRuntimeBinding(binding("effective"), resolved_at=NOW)
            if effective
            else None
        ),
        created_at=NOW,
        updated_at=NOW,
    )


def request(definition: AgentDefinitionRef) -> InstanceSelectionRequest:
    return InstanceSelectionRequest(
        definition_ref=definition,
        desired_runtime_binding=DesiredRuntimeBinding(binding("requested")),
    )


def test_current_task_target_projects_to_definition_without_mutation() -> None:
    task = {"agentRef": {"name": "researcher"}}
    original = {"agentRef": {"name": "researcher"}}
    projected = project_definition(
        DefinitionFacingRequest(
            namespace="workloads",
            agent_name=task["agentRef"]["name"],
            desired_runtime_binding=DesiredRuntimeBinding(binding("desired")),
        )
    )
    assert projected.definition_ref == AgentDefinitionRef("workloads", "researcher")
    assert task == original


@pytest.mark.parametrize("namespace,name", [("", "agent"), ("ns", "")])
def test_invalid_definition_projection_fails_explicitly(
    namespace: str, name: str
) -> None:
    with pytest.raises(InvalidDefinitionProjectionError):
        project_definition(
            DefinitionFacingRequest(
                namespace=namespace,
                agent_name=name,
                desired_runtime_binding=DesiredRuntimeBinding(binding("desired")),
            )
        )


def test_one_definition_may_have_multiple_instances_with_stable_policy() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    candidates = (
        instance("instance-b", definition),
        instance("instance-a", definition),
    )
    first = select_deterministically(request(definition), candidates)
    second = select_deterministically(request(definition), tuple(reversed(candidates)))
    assert first.instance_id == second.instance_id == AgentInstanceId("instance-a")
    assert first.evidence.authority == ROUTING_POLICY


def test_no_eligible_instance_fails_explicitly() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    with pytest.raises(NoEligibleInstanceError):
        select_deterministically(
            request(definition),
            (
                instance(
                    "inactive", definition, lifecycle=AgentInstanceLifecycle.INACTIVE
                ),
            ),
        )


def test_ambiguous_policy_can_fail_closed() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance("a", definition))
    repository.save(instance("b", definition))
    with pytest.raises(AmbiguousInstanceSelectionError):
        RejectAmbiguousInstanceSelector(repository).select(request(definition))


def test_definition_mismatch_is_rejected() -> None:
    with pytest.raises(InvalidSelectedInstanceError):
        select_deterministically(
            request(AgentDefinitionRef("workloads", "requested")),
            (instance("a", AgentDefinitionRef("workloads", "other")),),
        )


def test_duplicate_instance_identity_is_rejected() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    duplicate = instance("same", definition)
    with pytest.raises(DuplicateSelectionIdentityError):
        select_deterministically(request(definition), (duplicate, duplicate))


def test_missing_effective_binding_is_rejected() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    with pytest.raises(MissingEffectiveBindingError):
        select_deterministically(
            request(definition), (instance("a", definition, effective=False),)
        )


def test_repository_selector_returns_typed_result() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance("a", definition))
    selected = DeterministicPrototypeInstanceSelector(repository).select(
        request(definition)
    )
    assert isinstance(selected, SelectedInstanceResult)
    assert selected.definition_ref == definition


def test_builder_mints_once_and_preserves_identity_through_handoff() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance("instance-a", definition))
    calls = 0

    def mint() -> PlatformExecutionIdentity:
        nonlocal calls
        calls += 1
        return PlatformExecutionIdentity("execution-1")

    envelope = ExecutionEnvelopeBuilder(
        selector=DeterministicPrototypeInstanceSelector(repository),
        identity_minter=mint,
    ).build(
        DefinitionFacingRequest(
            namespace="workloads",
            agent_name="researcher",
            desired_runtime_binding=DesiredRuntimeBinding(binding("requested")),
            source_task_name="task-1",
        )
    )
    handed_off = envelope.with_native_correlation(NativeCorrelationId("native-1"))
    assert calls == 1
    assert handed_off.execution_identity is envelope.execution_identity
    assert handed_off.selected_instance_id == envelope.selected_instance_id
    assert handed_off.effective_runtime_binding is envelope.effective_runtime_binding
    assert handed_off.source_task_ref is not None
    assert handed_off.source_task_ref.name == "task-1"


def test_repeated_builds_are_explicitly_distinct_executions() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance("instance-a", definition))
    values = iter(
        (
            PlatformExecutionIdentity("execution-1"),
            PlatformExecutionIdentity("execution-2"),
        )
    )
    builder = ExecutionEnvelopeBuilder(
        selector=DeterministicPrototypeInstanceSelector(repository),
        identity_minter=lambda: next(values),
    )
    source = DefinitionFacingRequest(
        namespace="workloads",
        agent_name="researcher",
        desired_runtime_binding=DesiredRuntimeBinding(binding("requested")),
    )
    assert (
        builder.build(source).execution_identity
        != builder.build(source).execution_identity
    )


def test_native_identity_cannot_be_minted_as_platform_identity() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance("instance-a", definition))
    builder = ExecutionEnvelopeBuilder(
        selector=DeterministicPrototypeInstanceSelector(repository),
        identity_minter=lambda: NativeCorrelationId("native"),  # type: ignore[arg-type,return-value]
    )
    with pytest.raises(NativeIdentitySubstitutionError):
        builder.build(
            DefinitionFacingRequest(
                namespace="workloads",
                agent_name="researcher",
                desired_runtime_binding=DesiredRuntimeBinding(binding("requested")),
            )
        )


@pytest.mark.parametrize(
    "wrong_identity",
    [AgentInstanceId("instance"), AgentDefinitionRef("workloads", "agent")],
)
def test_definition_or_instance_identity_cannot_replace_execution_identity(
    wrong_identity: object,
) -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance("instance-a", definition))
    builder = ExecutionEnvelopeBuilder(
        selector=DeterministicPrototypeInstanceSelector(repository),
        identity_minter=lambda: wrong_identity,  # type: ignore[arg-type,return-value]
    )
    with pytest.raises(NativeIdentitySubstitutionError):
        builder.build(
            DefinitionFacingRequest(
                namespace="workloads",
                agent_name="researcher",
                desired_runtime_binding=DesiredRuntimeBinding(binding("requested")),
            )
        )


def test_envelope_rejects_definition_instance_mismatch() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    selected = select_deterministically(
        request(definition), (instance("a", definition),)
    )
    with pytest.raises(InvalidSelectedInstanceError):
        InternalExecutionEnvelope(
            definition_ref=AgentDefinitionRef("workloads", "other"),
            selected_instance_id=selected.instance_id,
            execution_identity=PlatformExecutionIdentity("execution"),
            desired_runtime_binding=selected.desired_runtime_binding,
            effective_runtime_binding=selected.effective_runtime_binding,
            selection_evidence=selected.evidence,
        )


def test_desired_and_effective_binding_remain_distinct() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    selected = select_deterministically(
        request(definition), (instance("a", definition),)
    )
    assert selected.desired_runtime_binding.value.binding_id == "requested"
    assert selected.effective_runtime_binding.value.binding_id == "effective"


def test_envelope_is_immutable_and_provider_neutral() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    selected = select_deterministically(
        request(definition), (instance("a", definition),)
    )
    envelope = InternalExecutionEnvelope(
        definition_ref=definition,
        selected_instance_id=selected.instance_id,
        execution_identity=PlatformExecutionIdentity("execution"),
        desired_runtime_binding=selected.desired_runtime_binding,
        effective_runtime_binding=selected.effective_runtime_binding,
        selection_evidence=selected.evidence,
    )
    with pytest.raises(FrozenInstanceError):
        envelope.execution_identity = PlatformExecutionIdentity("changed")  # type: ignore[misc]
    assert "kubernetes" not in repr(envelope).casefold()
    assert "credentials" not in repr(envelope).casefold()


def test_envelope_defensively_copies_native_evidence_collection() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    selected = select_deterministically(
        request(definition), (instance("a", definition),)
    )
    correlations = [NativeCorrelationId("native-1")]
    envelope = InternalExecutionEnvelope(
        definition_ref=definition,
        selected_instance_id=selected.instance_id,
        execution_identity=PlatformExecutionIdentity("execution"),
        desired_runtime_binding=selected.desired_runtime_binding,
        effective_runtime_binding=selected.effective_runtime_binding,
        selection_evidence=selected.evidence,
        native_correlations=correlations,  # type: ignore[arg-type]
    )
    correlations.append(NativeCorrelationId("native-2"))
    assert envelope.native_correlations == (NativeCorrelationId("native-1"),)


def test_realization_replacement_preserves_instance_identity() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    original = instance("stable", definition)
    changed = replace(
        original,
        effective_runtime_binding=EffectiveRuntimeBinding(
            binding("replacement", provider="provider.replacement"), resolved_at=NOW
        ),
    )
    assert changed.instance_id is original.instance_id
    assert changed.definition_ref is original.definition_ref


def test_selected_result_rejects_mismatched_evidence() -> None:
    definition = AgentDefinitionRef("workloads", "researcher")
    selected = select_deterministically(
        request(definition), (instance("a", definition),)
    )
    with pytest.raises(InvalidSelectedInstanceError):
        replace(
            selected,
            evidence=SelectedInstanceEvidence(
                definition_ref=definition,
                instance_id=AgentInstanceId("other"),
                authority="test",
            ),
        )
