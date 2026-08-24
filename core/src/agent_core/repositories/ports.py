"""Storage-independent repository ports for Agent Core."""

from typing import Protocol

from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
)


class AgentInstanceRepository(Protocol):
    def save(self, instance: AgentInstance) -> AgentInstance: ...

    def get(self, instance_id: AgentInstanceId) -> AgentInstance: ...

    def list_by_definition(
        self, definition_ref: AgentDefinitionRef
    ) -> tuple[AgentInstance, ...]: ...

    def delete(self, instance_id: AgentInstanceId) -> None: ...
