"""Track A persistence seams not owned by the durable core Contract."""

from typing import Protocol

from agent_core.execution_contract import CommandId, ScopeIdentity

from .execution_domain import CommandResultFact, ImportCheckpoint, VersionedAggregate


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


class CommandResultFactRepository(Protocol):
    def append_command_result(
        self, scope: ScopeIdentity, fact: CommandResultFact
    ) -> object: ...

    def read_command_results(
        self, scope: ScopeIdentity, command_id: CommandId
    ) -> tuple[CommandResultFact, ...]: ...
