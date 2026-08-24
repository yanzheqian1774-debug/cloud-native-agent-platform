from datetime import timedelta

import pytest
from agent_core.representation.v0_2 import (
    EffectiveRuntimeBinding,
    ExecutionIdentityRecord,
    InvalidDomainValueError,
    NativeCorrelationId,
    NativeRealizationEvidence,
    PlatformExecutionIdentity,
    agent_instance_from_dict,
    agent_instance_to_dict,
    execution_identity_from_dict,
    execution_identity_to_dict,
)
from agent_core.representation.v0_2.serialization import SCHEMA_VERSION


def test_internal_fixture_round_trip_preserves_typed_distinctions(
    make_instance, desired_binding, timestamp
):
    instance = (
        make_instance()
        .with_effective_binding(
            EffectiveRuntimeBinding(desired_binding.value, timestamp),
            updated_at=timestamp,
        )
        .with_realization(
            NativeRealizationEvidence(
                "runtime-family", "process", NativeCorrelationId("native-1"), timestamp
            ),
            updated_at=timestamp + timedelta(seconds=1),
        )
    )

    payload = agent_instance_to_dict(instance)
    restored = agent_instance_from_dict(payload)

    assert payload["schemaVersion"] == SCHEMA_VERSION
    assert restored == instance
    assert payload["instance"]["instanceId"] != payload["instance"]["definitionRef"]
    assert (
        payload["instance"]["desiredRuntimeBinding"]
        != payload["instance"]["effectiveRuntimeBinding"]
    )
    assert payload["instance"]["realizations"][0]["id"] == "native-1"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(schemaVersion="unknown"),
        lambda payload: payload.update(extra=True),
        lambda payload: payload["instance"].update(instanceId=""),
        lambda payload: payload["instance"]["definitionRef"].update(
            kind="AgentInstance"
        ),
    ],
)
def test_internal_fixture_fails_safely(make_instance, mutation):
    payload = agent_instance_to_dict(make_instance())
    mutation(payload)

    with pytest.raises((InvalidDomainValueError, ValueError)):
        agent_instance_from_dict(payload)


def test_execution_identity_round_trip_preserves_platform_and_native_types(timestamp):
    record = ExecutionIdentityRecord(
        execution_id=PlatformExecutionIdentity("execution-child"),
        root_execution_id=PlatformExecutionIdentity("execution-root"),
        parent_execution_id=PlatformExecutionIdentity("execution-parent"),
        attempt=2,
        native_correlations=(
            NativeCorrelationId("native-1"),
            NativeCorrelationId("native-2"),
        ),
        created_at=timestamp,
    )

    payload = execution_identity_to_dict(record)

    assert execution_identity_from_dict(payload) == record
    assert payload["executionIdentity"]["executionId"] == "execution-child"
    assert payload["executionIdentity"]["nativeCorrelations"] == [
        "native-1",
        "native-2",
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["instance"]["realizations"][0].update(extra=True),
        lambda payload: payload["instance"]["realizations"][0].pop("kind"),
    ],
)
def test_native_realization_fixture_rejects_shape_confusion(
    make_instance, timestamp, mutation
):
    instance = make_instance().with_realization(
        NativeRealizationEvidence(
            "runtime-family", "process", NativeCorrelationId("native-1"), timestamp
        ),
        updated_at=timestamp,
    )
    payload = agent_instance_to_dict(instance)
    mutation(payload)

    with pytest.raises(InvalidDomainValueError, match="realization fixture"):
        agent_instance_from_dict(payload)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attempt": 0},
        {"attempt": "1"},
        {"parent_execution_id": PlatformExecutionIdentity("execution-parent")},
        {
            "execution_id": PlatformExecutionIdentity("execution-child"),
            "root_execution_id": PlatformExecutionIdentity("execution-root"),
            "parent_execution_id": None,
        },
    ],
)
def test_execution_identity_rejects_invalid_internal_tree_metadata(timestamp, kwargs):
    values = {
        "execution_id": PlatformExecutionIdentity("execution-root"),
        "root_execution_id": PlatformExecutionIdentity("execution-root"),
        "parent_execution_id": None,
        "attempt": 1,
        "native_correlations": (),
        "created_at": timestamp,
    }
    values.update(kwargs)

    with pytest.raises(InvalidDomainValueError):
        ExecutionIdentityRecord(**values)
