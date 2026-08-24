"""Pure Definition projection for current Agent-facing logical addresses."""

from dataclasses import dataclass

from agent_core.representation.v0_2 import (
    AgentDefinitionProjection,
    AgentDefinitionRef,
    CoreRepresentationError,
    DesiredRuntimeBinding,
)

from .errors import InvalidDefinitionProjectionError


@dataclass(frozen=True, slots=True)
class DefinitionFacingRequest:
    """Minimum internal request derived from the current Task target."""

    namespace: str
    agent_name: str
    desired_runtime_binding: DesiredRuntimeBinding
    source_task_name: str | None = None


def project_definition(request: DefinitionFacingRequest) -> AgentDefinitionProjection:
    """Project the current namespaced Agent address without mutating its source."""
    if not isinstance(request, DefinitionFacingRequest):
        raise InvalidDefinitionProjectionError("invalid Definition-facing request")
    try:
        definition_ref = AgentDefinitionRef(
            namespace=request.namespace,
            name=request.agent_name,
        )
    except CoreRepresentationError as exc:
        raise InvalidDefinitionProjectionError(str(exc)) from exc
    if not isinstance(request.desired_runtime_binding, DesiredRuntimeBinding):
        raise InvalidDefinitionProjectionError(
            "Definition projection requires desired Runtime Binding intent"
        )
    if request.source_task_name is not None and not request.source_task_name.strip():
        raise InvalidDefinitionProjectionError("source Task name cannot be empty")
    return AgentDefinitionProjection(
        definition_ref=definition_ref,
        desired_runtime_binding=request.desired_runtime_binding,
    )
