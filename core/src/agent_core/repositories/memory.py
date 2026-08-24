"""Deterministic in-memory repository for prototype evidence only."""

from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    DefinitionOwnershipConflictError,
    DuplicateInstanceError,
    InstanceNotFoundError,
    agent_instance_from_dict,
    agent_instance_to_dict,
)


class InMemoryAgentInstanceRepository:
    """Isolated prototype store crossing the canonical copy boundary."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}

    def save(self, instance: AgentInstance) -> AgentInstance:
        key = instance.instance_id.value
        current = self._records.get(key)
        if current is not None:
            stored = agent_instance_from_dict(current)
            if stored.definition_ref != instance.definition_ref:
                raise DefinitionOwnershipConflictError(
                    "Agent Instance Definition ownership cannot change"
                )
            if stored == instance:
                raise DuplicateInstanceError("duplicate Agent Instance")
        self._records[key] = agent_instance_to_dict(instance)
        return self.get(instance.instance_id)

    def get(self, instance_id: AgentInstanceId) -> AgentInstance:
        if not isinstance(instance_id, AgentInstanceId):
            raise InstanceNotFoundError("Agent Instance not found")
        try:
            return agent_instance_from_dict(self._records[instance_id.value])
        except KeyError as error:
            raise InstanceNotFoundError("Agent Instance not found") from error

    def list_by_definition(
        self, definition_ref: AgentDefinitionRef
    ) -> tuple[AgentInstance, ...]:
        if not isinstance(definition_ref, AgentDefinitionRef):
            return ()
        matches = (
            agent_instance_from_dict(record) for record in self._records.values()
        )
        return tuple(
            sorted(
                (item for item in matches if item.definition_ref == definition_ref),
                key=lambda item: item.instance_id.value,
            )
        )

    def delete(self, instance_id: AgentInstanceId) -> None:
        if not isinstance(instance_id, AgentInstanceId):
            raise InstanceNotFoundError("Agent Instance not found")
        try:
            del self._records[instance_id.value]
        except KeyError as error:
            raise InstanceNotFoundError("Agent Instance not found") from error
