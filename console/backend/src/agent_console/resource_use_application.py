"""Authorization-first application boundary for Resource Use writes and reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_core.execution_contract import ScopeIdentity

from .resource_use_domain import (
    ResourceMeasurement,
    ResourceUseBinding,
    ResourceUseError,
    ResourceUseFact,
    ResourceUseSnapshot,
)
from .resource_use_repository import ResourceUseRepository


class ResourceUseAuthorization(Protocol):
    def require(self, scope: ScopeIdentity, action: str, identity: str) -> str: ...


@dataclass(frozen=True, slots=True)
class ScopedResourceUseAuthorization:
    scope: ScopeIdentity
    actor_id: str
    permissions: frozenset[str]
    decision_id: str

    def require(self, scope: ScopeIdentity, action: str, identity: str) -> str:
        if (
            scope != self.scope
            or action not in self.permissions
            or not self.actor_id
            or not self.decision_id
            or not identity
        ):
            raise ResourceUseError("RESOURCE_USE_NOT_FOUND")
        return self.decision_id


class ResourceUseApplicationService:
    def __init__(
        self,
        repository: ResourceUseRepository,
        authorization: ResourceUseAuthorization | None,
    ) -> None:
        self.repository = repository
        self.authorization = authorization

    def _authorize(self, scope: ScopeIdentity, action: str, identity: str) -> str:
        if self.authorization is None:
            raise ResourceUseError("RESOURCE_USE_NOT_FOUND")
        decision = self.authorization.require(scope, action, identity)
        if not decision:
            raise ResourceUseError("RESOURCE_USE_NOT_FOUND")
        return decision

    def prepare_dispatch(
        self,
        binding: ResourceUseBinding,
        facts: tuple[ResourceUseFact, ...],
        *,
        idempotency_key: str,
        payload_digest: str,
    ) -> ResourceUseSnapshot:
        decision = self._authorize(binding.scope, "WRITE", binding.resource_use_id)
        if binding.authorization_decision_id != decision:
            raise ResourceUseError("RESOURCE_USE_AUTHORIZATION_MISMATCH")
        return self.repository.prepare_dispatch(
            binding,
            facts,
            idempotency_key=idempotency_key,
            payload_digest=payload_digest,
        )

    def commit_observation(
        self,
        scope: ScopeIdentity,
        resource_use_id: str,
        facts: tuple[ResourceUseFact, ...],
        measurements: tuple[ResourceMeasurement, ...],
        *,
        evidence_records: tuple[dict[str, object], ...],
        claim: dict[str, object],
        idempotency_key: str,
        payload_digest: str,
        expected_high_water: int,
    ) -> ResourceUseSnapshot:
        self._authorize(scope, "WRITE", resource_use_id)
        return self.repository.commit_observation(
            scope,
            resource_use_id,
            facts,
            measurements,
            evidence_records=evidence_records,
            claim=claim,
            idempotency_key=idempotency_key,
            payload_digest=payload_digest,
            expected_high_water=expected_high_water,
        )

    def get_snapshot(
        self, scope: ScopeIdentity, resource_use_id: str
    ) -> ResourceUseSnapshot:
        self._authorize(scope, "READ", resource_use_id)
        value = self.repository.get_snapshot(scope, resource_use_id)
        if value is None:
            raise ResourceUseError("RESOURCE_USE_NOT_FOUND")
        return value

    def list_snapshots(self, scope: ScopeIdentity) -> tuple[ResourceUseSnapshot, ...]:
        self._authorize(scope, "LIST", "resource-uses")
        return self.repository.list_snapshots(scope)

    def count(self, scope: ScopeIdentity) -> int:
        self._authorize(scope, "COUNT", "resource-uses")
        return self.repository.count(scope)
