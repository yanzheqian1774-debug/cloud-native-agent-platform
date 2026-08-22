"""Spike-only deterministic logical router; not a production scheduler."""

from collections import defaultdict

from generic_caller import LogicalAgentOutcome, LogicalAgentRequest
from object_model import (
    AgentInstance,
    ExperimentalRuntimeProvider,
    NativeDispatch,
    RuntimeBinding,
)


class ExperimentalPlatformRouter:
    """Select an Instance, then delegate native translation to its Provider."""

    def __init__(
        self,
        *,
        instances: tuple[AgentInstance, ...],
        bindings: tuple[RuntimeBinding, ...],
        providers: tuple[ExperimentalRuntimeProvider, ...],
    ) -> None:
        self._instances = {item.instance_id: item for item in instances}
        self._bindings = {item.binding_id: item for item in bindings}
        self._providers = {item.provider_id: item for item in providers}
        self._next_index: dict[str, int] = defaultdict(int)
        self.dispatch_evidence: list[NativeDispatch] = []

    def invoke(self, request: LogicalAgentRequest) -> LogicalAgentOutcome:
        instance = self._select_instance(request)
        binding = self._bindings[instance.runtime_binding_id]
        provider = self._providers[binding.provider_id]
        dispatch = provider.translate(
            binding,
            execution_id=request.execution_id,
            payload=request.payload,
        )
        self.dispatch_evidence.append(dispatch)
        return LogicalAgentOutcome(
            execution_id=dispatch.execution_id,
            instance_id=instance.instance_id,
            output=f"accepted:{request.payload}",
        )

    def _select_instance(self, request: LogicalAgentRequest) -> AgentInstance:
        eligible = sorted(
            (
                item
                for item in self._instances.values()
                if item.definition_id == request.definition_id
            ),
            key=lambda item: item.instance_id,
        )
        if request.instance_id is not None:
            eligible = [
                item for item in eligible if item.instance_id == request.instance_id
            ]
        if not eligible:
            raise ValueError("no eligible logical Agent Instance")
        index = self._next_index[request.definition_id] % len(eligible)
        self._next_index[request.definition_id] += 1
        return eligible[index]
