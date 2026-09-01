"""Track A persistence seams not owned by the durable core Contract."""

from typing import Protocol

from agent_core.execution_contract import ScopeIdentity

from .execution_domain import ImportCheckpoint, VersionedAggregate


class AggregateRepository(Protocol):
    def create(self, aggregate: VersionedAggregate) -> VersionedAggregate: ...

    def replace(
        self, aggregate: VersionedAggregate, *, expected_version: int
    ) -> VersionedAggregate: ...

    def get(
        self, scope: ScopeIdentity, aggregate_id: str
    ) -> VersionedAggregate | None: ...


class CutoverCheckpointRepository(Protocol):
    def load(self) -> ImportCheckpoint: ...

    def replace(self, checkpoint: ImportCheckpoint) -> ImportCheckpoint: ...
