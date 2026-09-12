"""Track A persistence seams not owned by the durable core Contract."""

from typing import Protocol

from agent_core.execution_contract import (
    CommandId,
    Generation,
    RuntimeInstanceId,
    ScopeIdentity,
)
from agent_core.openclaw_binding import (
    OpenClawBindingObservation,
    OpenClawGenerationBinding,
    OpenClawRuntimeBinding,
)

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


class OpenClawBindingRepository(Protocol):
    def save_openclaw_binding(
        self,
        binding: OpenClawRuntimeBinding,
        generation: OpenClawGenerationBinding,
    ) -> object: ...

    def get_openclaw_binding(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        generation: Generation,
    ) -> tuple[OpenClawRuntimeBinding, OpenClawGenerationBinding] | None: ...

    def append_openclaw_observation(
        self, observation: OpenClawBindingObservation
    ) -> object: ...

    def read_openclaw_observations(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        generation: Generation,
    ) -> tuple[OpenClawBindingObservation, ...]: ...
