from dataclasses import replace
from datetime import timedelta

import pytest
from agent_core.repositories import InMemoryAgentInstanceRepository
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstanceId,
    DefinitionOwnershipConflictError,
    DuplicateInstanceError,
    InstanceNotFoundError,
    NativeCorrelationId,
    NativeRealizationEvidence,
)


def test_save_get_and_update(make_instance, timestamp):
    repository = InMemoryAgentInstanceRepository()
    instance = make_instance()
    repository.save(instance)
    evidence = NativeRealizationEvidence(
        "runtime-family", "process", NativeCorrelationId("native-1"), timestamp
    )
    changed = instance.with_realization(evidence, updated_at=timestamp)

    assert repository.get(instance.instance_id) == instance
    assert repository.save(changed) == changed
    assert repository.get(instance.instance_id).instance_id == instance.instance_id


def test_duplicate_identical_instance_is_explicit(make_instance):
    repository = InMemoryAgentInstanceRepository()
    instance = make_instance()
    repository.save(instance)

    with pytest.raises(DuplicateInstanceError):
        repository.save(instance)


def test_conflicting_aggregate_with_duplicate_id_is_rejected(make_instance, timestamp):
    repository = InMemoryAgentInstanceRepository()
    instance = make_instance()
    repository.save(instance)
    conflicting = replace(instance, created_at=timestamp + timedelta(seconds=1))

    with pytest.raises(DuplicateInstanceError, match="conflicts"):
        repository.save(conflicting)


def test_one_definition_owns_multiple_ordered_instances(make_instance, definition_ref):
    repository = InMemoryAgentInstanceRepository()
    repository.save(make_instance("instance-002"))
    repository.save(make_instance("instance-001"))

    assert [
        item.instance_id.value for item in repository.list_by_definition(definition_ref)
    ] == [
        "instance-001",
        "instance-002",
    ]


def test_list_isolated_by_definition(make_instance):
    repository = InMemoryAgentInstanceRepository()
    repository.save(make_instance())

    assert repository.list_by_definition(AgentDefinitionRef("default", "other")) == ()


def test_definition_ownership_cannot_change(make_instance):
    repository = InMemoryAgentInstanceRepository()
    instance = make_instance()
    repository.save(instance)
    changed = replace(instance, definition_ref=AgentDefinitionRef("default", "other"))

    with pytest.raises(DefinitionOwnershipConflictError):
        repository.save(changed)


def test_delete_and_missing_behavior(make_instance):
    repository = InMemoryAgentInstanceRepository()
    instance = make_instance()
    repository.save(instance)
    repository.delete(instance.instance_id)

    with pytest.raises(InstanceNotFoundError):
        repository.get(instance.instance_id)
    with pytest.raises(InstanceNotFoundError):
        repository.delete(instance.instance_id)


def test_repository_instances_have_no_global_state(make_instance):
    first = InMemoryAgentInstanceRepository()
    second = InMemoryAgentInstanceRepository()
    first.save(make_instance())

    with pytest.raises(InstanceNotFoundError):
        second.get(AgentInstanceId("instance-001"))


def test_repository_does_not_alias_mutable_binding_input(definition_ref, timestamp):
    from agent_core.representation.v0_2 import (
        AgentInstance,
        AgentInstanceLifecycle,
        DesiredRuntimeBinding,
        RuntimeBinding,
    )

    configuration = {"profile": "original"}
    instance = AgentInstance(
        instance_id=AgentInstanceId("instance-001"),
        definition_ref=definition_ref,
        lifecycle=AgentInstanceLifecycle.ACTIVE,
        desired_runtime_binding=DesiredRuntimeBinding(
            RuntimeBinding(
                "binding/1", "provider/1", "MANAGED", configuration=configuration
            )
        ),
        created_at=timestamp,
        updated_at=timestamp,
    )
    repository = InMemoryAgentInstanceRepository()
    repository.save(instance)

    configuration["profile"] = "mutated"

    stored = repository.get(instance.instance_id)
    assert stored.desired_runtime_binding.value.configuration["profile"] == "original"
