"""Repository ports for the PostgreSQL-owned Resource Use authority."""

from collections.abc import Callable
from typing import Any, Protocol

from agent_core.execution_contract import ScopeIdentity

from .resource_use_domain import (
    ResourceMeasurement,
    ResourceUseBinding,
    ResourceUseFact,
    ResourceUseSnapshot,
)


class ResourceUseRepository(Protocol):
    def prepare_dispatch(
        self,
        binding: ResourceUseBinding,
        facts: tuple[ResourceUseFact, ...],
        *,
        idempotency_key: str,
        payload_digest: str,
        transaction_hook: Callable[[Any], None] | None = None,
    ) -> ResourceUseSnapshot: ...

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
        transaction_hook: Callable[[Any], None] | None = None,
    ) -> ResourceUseSnapshot: ...

    def get_binding(
        self, scope: ScopeIdentity, resource_use_id: str
    ) -> ResourceUseBinding | None: ...

    def get_snapshot(
        self, scope: ScopeIdentity, resource_use_id: str
    ) -> ResourceUseSnapshot | None: ...

    def list_snapshots(
        self, scope: ScopeIdentity
    ) -> tuple[ResourceUseSnapshot, ...]: ...

    def count(self, scope: ScopeIdentity) -> int: ...
