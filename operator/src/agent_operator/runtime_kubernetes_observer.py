"""Sanitized Kubernetes Pod observation for Product Runtime reconciliation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from agent_core.execution_contract import (
    ExternalCorrelation,
    Generation,
    ObservationId,
    RuntimeHealth,
    RuntimeInstanceId,
    RuntimeObservation,
    RuntimeObservedStateKind,
    RuntimeReadiness,
    current_observed_state,
)

__all__ = [
    "Generation",
    "KubernetesObservationError",
    "ObservationId",
    "RuntimeInstanceId",
    "RuntimeObservedStateKind",
    "RuntimeReadiness",
    "current_observed_state",
    "normalize_pod_observation",
]


class KubernetesObservationError(ValueError):
    pass


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def normalize_pod_observation(
    pod: Mapping[str, Any],
    *,
    runtime_instance_id: RuntimeInstanceId,
    generation: Generation,
    observed_at: datetime,
    freshness: timedelta,
    observation_id: ObservationId,
) -> RuntimeObservation:
    """Normalize allowlisted Pod facts; never expose env, Secret, logs, or spec."""
    metadata = _mapping(pod.get("metadata"))
    status = _mapping(pod.get("status"))
    uid = metadata.get("uid")
    name = metadata.get("name")
    namespace = metadata.get("namespace")
    if not all(isinstance(value, str) and value for value in (uid, name, namespace)):
        raise KubernetesObservationError("POD_CORRELATION_REQUIRED")
    if observed_at.tzinfo is None or freshness <= timedelta(0):
        raise KubernetesObservationError("INVALID_OBSERVATION_TIME")
    observed_at = observed_at.astimezone(UTC)
    phase = status.get("phase")
    deleting = metadata.get("deletionTimestamp") is not None
    conditions = status.get("conditions")
    ready = False
    if isinstance(conditions, Sequence) and not isinstance(conditions, (str, bytes)):
        ready = any(
            _mapping(item).get("type") == "Ready"
            and _mapping(item).get("status") == "True"
            for item in conditions
        )
    if deleting or phase == "Succeeded":
        state = RuntimeObservedStateKind.TERMINATED
    elif phase == "Running":
        state = RuntimeObservedStateKind.RUNNING
    elif phase == "Failed":
        state = RuntimeObservedStateKind.FAILED
    elif phase == "Pending":
        state = RuntimeObservedStateKind.PENDING
    else:
        state = RuntimeObservedStateKind.UNKNOWN
    health = (
        RuntimeHealth.HEALTHY
        if state is RuntimeObservedStateKind.RUNNING and ready
        else RuntimeHealth.UNHEALTHY
        if state is RuntimeObservedStateKind.FAILED
        else RuntimeHealth.UNKNOWN
    )
    readiness = (
        RuntimeReadiness.READY if ready and not deleting else RuntimeReadiness.NOT_READY
    )
    return RuntimeObservation(
        observation_id=observation_id,
        runtime_instance_id=runtime_instance_id,
        observed_generation=generation,
        observed_state=state,
        health=health,
        readiness=readiness,
        observed_at=observed_at,
        freshness_deadline=observed_at + freshness,
        provider_correlation=None,
        kubernetes_correlation=ExternalCorrelation(
            system="kubernetes",
            kind="Pod",
            handle=f"{namespace}/{name}/{uid}",
        ),
        limitation_codes=("POD_PHASE_NOT_BUSINESS_SUCCESS",),
    )
