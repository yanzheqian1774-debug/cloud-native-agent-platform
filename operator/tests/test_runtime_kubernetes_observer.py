from datetime import UTC, datetime, timedelta

import pytest
from agent_operator.runtime_kubernetes_observer import (
    Generation,
    KubernetesObservationError,
    ObservationId,
    RuntimeInstanceId,
    RuntimeObservedStateKind,
    RuntimeReadiness,
    current_observed_state,
    normalize_pod_observation,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def pod(uid="uid-1", phase="Running", ready="True"):
    return {
        "metadata": {"uid": uid, "name": "agent-pod", "namespace": "agent-workloads"},
        "spec": {"containers": [{"env": [{"value": "secret-must-not-leak"}]}]},
        "status": {"phase": phase, "conditions": [{"type": "Ready", "status": ready}]},
    }


def test_normalizes_only_correlation_and_safe_status() -> None:
    observation = normalize_pod_observation(
        pod(),
        runtime_instance_id=RuntimeInstanceId("runtime-1"),
        generation=Generation(1),
        observed_at=NOW,
        freshness=timedelta(seconds=10),
        observation_id=ObservationId("observation-1"),
    )
    assert observation.observed_state is RuntimeObservedStateKind.RUNNING
    assert observation.readiness is RuntimeReadiness.READY
    assert (
        observation.kubernetes_correlation.handle == "agent-workloads/agent-pod/uid-1"
    )
    assert "secret-must-not-leak" not in repr(observation)
    assert (
        current_observed_state(observation, at=NOW + timedelta(seconds=11))
        is RuntimeObservedStateKind.STALE
    )


def test_replacement_changes_uid_correlation_not_product_identity() -> None:
    values = [
        normalize_pod_observation(
            pod(uid),
            runtime_instance_id=RuntimeInstanceId("runtime-1"),
            generation=Generation(1),
            observed_at=NOW,
            freshness=timedelta(seconds=10),
            observation_id=ObservationId(f"observation-{uid}"),
        )
        for uid in ("uid-1", "uid-2")
    ]
    assert values[0].runtime_instance_id == values[1].runtime_instance_id
    assert values[0].kubernetes_correlation != values[1].kubernetes_correlation


def test_missing_pod_identity_is_rejected_without_payload_disclosure() -> None:
    with pytest.raises(
        KubernetesObservationError, match="POD_CORRELATION_REQUIRED"
    ) as error:
        normalize_pod_observation(
            {"metadata": {"name": "sensitive"}},
            runtime_instance_id=RuntimeInstanceId("runtime-1"),
            generation=Generation(1),
            observed_at=NOW,
            freshness=timedelta(seconds=10),
            observation_id=ObservationId("observation-1"),
        )
    assert "sensitive" not in str(error.value)
