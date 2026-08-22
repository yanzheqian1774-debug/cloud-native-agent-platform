"""Falsification tests for S5-SPIKE-004 Checkpoint A."""

import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))

from object_model import (  # noqa: E402
    AgentDefinition,
    AgentInstance,
    DesiredLifecycle,
    ExperimentalRuntimeProvider,
    RuntimeBinding,
)


def test_one_definition_has_two_distinct_instance_identities() -> None:
    definition = AgentDefinition("researcher", "v7")
    instances = (
        AgentInstance(
            "researcher-a",
            *definition.__dict__.values(),
            DesiredLifecycle.RUNNING,
            "binding-a",
        ),
        AgentInstance(
            "researcher-b",
            *definition.__dict__.values(),
            DesiredLifecycle.RUNNING,
            "binding-b",
        ),
    )

    assert {item.definition_id for item in instances} == {definition.definition_id}
    assert {item.definition_version for item in instances} == {definition.version}
    assert len({item.instance_id for item in instances}) == 2


def test_realization_replacement_does_not_replace_instance_identity() -> None:
    instance = AgentInstance(
        "researcher-a", "researcher", "v7", DesiredLifecycle.RUNNING, "binding-a"
    )
    binding = RuntimeBinding("binding-a", instance.instance_id, "kubernetes")
    provider = ExperimentalRuntimeProvider("kubernetes")
    first = provider.realize(
        binding,
        realization_id="realization-1",
        native_kind="Pod",
        native_id="pod-uid-1",
    )
    replacement = provider.replace(
        binding,
        realization_id="realization-2",
        native_kind="Pod",
        native_id="pod-uid-2",
    )

    assert instance.instance_id == "researcher-a"
    assert first.native_id != replacement.native_id
    assert first.realization_id != replacement.realization_id
    assert provider.active(binding) == (replacement,)


def test_one_instance_can_have_multiple_active_realizations() -> None:
    binding = RuntimeBinding("binding-a", "researcher-a", "replicated")
    provider = ExperimentalRuntimeProvider("replicated")

    provider.realize(
        binding, realization_id="replica-a", native_kind="Process", native_id="pid-101"
    )
    provider.realize(
        binding, realization_id="replica-b", native_kind="Process", native_id="pid-102"
    )

    assert len(provider.active(binding)) == 2
    assert {item.binding_id for item in provider.active(binding)} == {
        binding.binding_id
    }


def test_two_instances_can_share_a_runtime_native_gateway() -> None:
    provider = ExperimentalRuntimeProvider("openclaw-like")
    binding_a = RuntimeBinding("binding-a", "researcher-a", provider.provider_id)
    binding_b = RuntimeBinding("binding-b", "researcher-b", provider.provider_id)

    native_a = provider.realize(
        binding_a,
        realization_id="agent-main-session-a",
        native_kind="GatewaySession",
        native_id="gateway-1/session-a",
    )
    native_b = provider.realize(
        binding_b,
        realization_id="agent-main-session-b",
        native_kind="GatewaySession",
        native_id="gateway-1/session-b",
    )

    assert binding_a.instance_id != binding_b.instance_id
    assert native_a.native_id.split("/")[0] == native_b.native_id.split("/")[0]
    assert native_a.native_id != native_b.native_id


def test_provider_cannot_realize_another_providers_binding() -> None:
    binding = RuntimeBinding("binding-a", "researcher-a", "provider-a")
    provider = ExperimentalRuntimeProvider("provider-b")

    try:
        provider.realize(
            binding, realization_id="r1", native_kind="Pod", native_id="pod-1"
        )
    except ValueError as error:
        assert str(error) == "binding belongs to a different provider"
    else:
        raise AssertionError("provider ownership violation was accepted")
