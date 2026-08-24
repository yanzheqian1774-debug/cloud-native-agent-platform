from dataclasses import fields

import pytest
from agent_core.representation.v0_2 import (
    AgentDefinitionProjection,
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    EffectiveRuntimeBinding,
    ExecutionIdentityRecord,
    InvalidBindingError,
    InvalidDomainValueError,
    NativeCorrelationId,
    NativeRealizationEvidence,
    PlatformExecutionIdentity,
    RuntimeBinding,
    SelectedInstanceEvidence,
    mint_agent_instance_id,
    mint_platform_execution_identity,
)


@pytest.mark.parametrize(
    ("factory", "value"),
    [
        (AgentInstanceId, ""),
        (PlatformExecutionIdentity, " "),
        (NativeCorrelationId, ""),
        (lambda value: AgentDefinitionRef(value, "name"), ""),
        (lambda value: AgentDefinitionRef("default", value), ""),
    ],
)
def test_empty_identifiers_are_rejected(factory, value):
    with pytest.raises(InvalidDomainValueError):
        factory(value)


def test_definition_and_instance_identity_are_distinct_types(definition_ref):
    instance_id = AgentInstanceId("instance-001")

    assert type(definition_ref) is AgentDefinitionRef
    assert type(instance_id) is AgentInstanceId
    assert definition_ref != instance_id


def test_instance_rejects_definition_identity_substitution(make_instance):
    instance = make_instance()

    with pytest.raises(InvalidDomainValueError):
        AgentInstance(
            instance_id=instance.definition_ref,  # type: ignore[arg-type]
            definition_ref=instance.definition_ref,
            lifecycle=instance.lifecycle,
            desired_runtime_binding=instance.desired_runtime_binding,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )


def test_native_id_cannot_replace_platform_id(make_instance):
    instance = make_instance()

    with pytest.raises(InvalidDomainValueError):
        AgentInstance(
            instance_id=NativeCorrelationId("pod-123"),  # type: ignore[arg-type]
            definition_ref=instance.definition_ref,
            lifecycle=instance.lifecycle,
            desired_runtime_binding=instance.desired_runtime_binding,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )

    assert PlatformExecutionIdentity("execution-1") != NativeCorrelationId(
        "execution-1"
    )
    with pytest.raises(InvalidDomainValueError):
        AgentInstanceId(NativeCorrelationId("native-1"))  # type: ignore[arg-type]
    with pytest.raises(InvalidDomainValueError):
        PlatformExecutionIdentity(  # type: ignore[arg-type]
            NativeCorrelationId("native-2")
        )


def test_platform_minting_is_opaque_and_injectable():
    assert mint_agent_instance_id(lambda: "deterministic-instance") == AgentInstanceId(
        "deterministic-instance"
    )
    assert mint_platform_execution_identity(
        lambda: "deterministic-execution"
    ) == PlatformExecutionIdentity("deterministic-execution")
    assert mint_agent_instance_id().value
    assert mint_platform_execution_identity().value


def test_minting_rejects_native_typed_values():
    with pytest.raises(InvalidDomainValueError):
        mint_agent_instance_id(
            lambda: NativeCorrelationId("native-1")  # type: ignore[arg-type]
        )
    with pytest.raises(InvalidDomainValueError):
        mint_platform_execution_identity(
            lambda: NativeCorrelationId("native-2")  # type: ignore[arg-type]
        )


def test_platform_identity_string_is_redaction_safe():
    value = PlatformExecutionIdentity("sensitive-full-identifier")

    assert str(value) == "PlatformExecutionIdentity(sensitiv...)"
    assert "full-identifier" not in str(value)
    assert str(AgentInstanceId("sensitive-instance-identifier")) == (
        "AgentInstanceId(sensitiv...)"
    )


def test_desired_and_effective_bindings_are_distinct(desired_binding, timestamp):
    effective = EffectiveRuntimeBinding(desired_binding.value, timestamp)

    assert type(desired_binding) is not type(effective)
    assert effective.value == desired_binding.value


def test_binding_rejects_secret_shaped_configuration():
    with pytest.raises(InvalidBindingError, match="secret-shaped"):
        RuntimeBinding(
            "binding/1", "provider/1", "MANAGED", configuration={"api_token": "x"}
        )


def test_instance_identity_survives_realization_and_binding_changes(
    make_instance, desired_binding, timestamp
):
    instance = make_instance()
    evidence = NativeRealizationEvidence(
        system="runtime-family",
        kind="process",
        correlation_id=NativeCorrelationId("native-1"),
        observed_at=timestamp,
    )
    effective = EffectiveRuntimeBinding(desired_binding.value, timestamp)

    realized = instance.with_realization(evidence, updated_at=timestamp)
    rebound = realized.with_effective_binding(effective, updated_at=timestamp)

    assert realized.instance_id == instance.instance_id
    assert rebound.instance_id == instance.instance_id
    assert rebound.definition_ref == instance.definition_ref


def test_native_evidence_supports_multiple_temporal_values(make_instance, timestamp):
    instance = make_instance()
    first = NativeRealizationEvidence(
        "runtime-family", "process", NativeCorrelationId("native-1"), timestamp, False
    )
    second = NativeRealizationEvidence(
        "runtime-family", "process", NativeCorrelationId("native-2"), timestamp, True
    )

    changed = instance.with_realization(first, updated_at=timestamp).with_realization(
        second, updated_at=timestamp
    )

    assert [item.correlation_id.value for item in changed.realizations] == [
        "native-1",
        "native-2",
    ]


def test_native_evidence_collection_is_defensively_copied(make_instance, timestamp):
    evidence = NativeRealizationEvidence(
        "runtime-family", "process", NativeCorrelationId("native-1"), timestamp
    )
    mutable_realizations = [evidence]
    template = make_instance()
    instance = AgentInstance(
        instance_id=template.instance_id,
        definition_ref=template.definition_ref,
        lifecycle=template.lifecycle,
        desired_runtime_binding=template.desired_runtime_binding,
        created_at=template.created_at,
        updated_at=template.updated_at,
        realizations=mutable_realizations,  # type: ignore[arg-type]
    )

    mutable_realizations.clear()

    assert instance.realizations == (evidence,)


def test_selected_instance_evidence_is_definition_facing_and_internal(
    definition_ref, timestamp
):
    selected = SelectedInstanceEvidence(
        definition_ref,
        AgentInstanceId("instance-001"),
        authority="internal-router",
        reason="eligible",
        selected_at=timestamp,
    )

    assert selected.definition_ref == definition_ref
    assert selected.instance_id == AgentInstanceId("instance-001")


def test_definition_projection_keeps_definition_owned_intent(
    definition_ref, desired_binding
):
    projection = AgentDefinitionProjection(
        definition_ref,
        desired_binding,
        source_uid="kubernetes-provenance-only",
        source_generation=7,
    )

    assert projection.definition_ref == definition_ref
    assert projection.desired_runtime_binding == desired_binding


def test_execution_record_keeps_native_correlations_separate(timestamp):
    execution_id = PlatformExecutionIdentity("execution-1")
    record = ExecutionIdentityRecord(
        execution_id=execution_id,
        root_execution_id=execution_id,
        parent_execution_id=None,
        attempt=1,
        native_correlations=(NativeCorrelationId("native-1"),),
        created_at=timestamp,
    )

    assert record.execution_id == record.root_execution_id
    assert record.native_correlations != (record.execution_id,)


def test_stable_core_types_have_no_provider_specific_fields():
    prohibited = {"kubernetes", "openclaw", "hermes", "pod", "container"}
    core_types = (
        AgentDefinitionRef,
        AgentInstanceId,
        PlatformExecutionIdentity,
        NativeCorrelationId,
        AgentInstance,
    )

    assert not prohibited.intersection(
        {
            field.name.casefold()
            for core_type in core_types
            for field in fields(core_type)
        }
    )
