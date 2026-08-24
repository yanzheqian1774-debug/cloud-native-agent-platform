"""Immutable, Provider-neutral internal execution envelope."""

from dataclasses import dataclass, replace

from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstanceId,
    DesiredRuntimeBinding,
    EffectiveRuntimeBinding,
    NativeCorrelationId,
    PlatformExecutionIdentity,
    SelectedInstanceEvidence,
)

from .errors import InvalidSelectedInstanceError, NativeIdentitySubstitutionError


@dataclass(frozen=True, slots=True)
class SourceTaskRef:
    namespace: str
    name: str

    def __post_init__(self) -> None:
        if not self.namespace.strip() or not self.name.strip():
            raise InvalidSelectedInstanceError("source Task reference is incomplete")


@dataclass(frozen=True, slots=True)
class InternalExecutionEnvelope:
    definition_ref: AgentDefinitionRef
    selected_instance_id: AgentInstanceId
    execution_identity: PlatformExecutionIdentity
    desired_runtime_binding: DesiredRuntimeBinding
    effective_runtime_binding: EffectiveRuntimeBinding
    selection_evidence: SelectedInstanceEvidence
    native_correlations: tuple[NativeCorrelationId, ...] = ()
    source_task_ref: SourceTaskRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.definition_ref, AgentDefinitionRef):
            raise InvalidSelectedInstanceError(
                "envelope requires a Definition reference"
            )
        if not isinstance(self.selected_instance_id, AgentInstanceId):
            raise NativeIdentitySubstitutionError(
                "only a Platform Instance ID can identify the selected Instance"
            )
        if not isinstance(self.execution_identity, PlatformExecutionIdentity):
            raise NativeIdentitySubstitutionError(
                "only a Platform identity can identify the execution"
            )
        if not isinstance(self.desired_runtime_binding, DesiredRuntimeBinding):
            raise InvalidSelectedInstanceError("envelope desired Binding is invalid")
        if not isinstance(self.effective_runtime_binding, EffectiveRuntimeBinding):
            raise InvalidSelectedInstanceError("envelope effective Binding is invalid")
        if not isinstance(self.selection_evidence, SelectedInstanceEvidence):
            raise InvalidSelectedInstanceError("envelope selection evidence is invalid")
        if self.selection_evidence.definition_ref != self.definition_ref:
            raise InvalidSelectedInstanceError("envelope Definition mismatch")
        if self.selection_evidence.instance_id != self.selected_instance_id:
            raise InvalidSelectedInstanceError("envelope Instance mismatch")
        if not all(
            isinstance(item, NativeCorrelationId) for item in self.native_correlations
        ):
            raise NativeIdentitySubstitutionError(
                "native correlation evidence has an invalid identity type"
            )
        object.__setattr__(self, "native_correlations", tuple(self.native_correlations))

    def with_native_correlation(
        self, correlation: NativeCorrelationId
    ) -> "InternalExecutionEnvelope":
        """Add evidence without changing any Platform identity or Binding."""
        if not isinstance(correlation, NativeCorrelationId):
            raise NativeIdentitySubstitutionError("invalid native correlation evidence")
        return replace(
            self, native_correlations=(*self.native_correlations, correlation)
        )
