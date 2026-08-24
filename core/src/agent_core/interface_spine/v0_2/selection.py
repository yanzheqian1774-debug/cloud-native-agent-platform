"""Instance-selection port and explicit prototype policy."""

from dataclasses import dataclass
from typing import Protocol

from agent_core.repositories import AgentInstanceRepository
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    AgentInstance,
    AgentInstanceId,
    AgentInstanceLifecycle,
    DesiredRuntimeBinding,
    EffectiveRuntimeBinding,
    SelectedInstanceEvidence,
)

from .errors import (
    AmbiguousInstanceSelectionError,
    DuplicateSelectionIdentityError,
    InvalidSelectedInstanceError,
    MissingEffectiveBindingError,
    NativeIdentitySubstitutionError,
    NoEligibleInstanceError,
)

ROUTING_POLICY = "PROTOTYPE_LEXICAL_INSTANCE_ID_NOT_FROZEN"


@dataclass(frozen=True, slots=True)
class InstanceSelectionRequest:
    definition_ref: AgentDefinitionRef
    desired_runtime_binding: DesiredRuntimeBinding


@dataclass(frozen=True, slots=True)
class SelectedInstanceResult:
    instance_id: AgentInstanceId
    definition_ref: AgentDefinitionRef
    desired_runtime_binding: DesiredRuntimeBinding
    effective_runtime_binding: EffectiveRuntimeBinding
    evidence: SelectedInstanceEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, AgentInstanceId):
            raise NativeIdentitySubstitutionError(
                "only a Platform Instance ID can identify the selected Instance"
            )
        if not isinstance(self.definition_ref, AgentDefinitionRef):
            raise InvalidSelectedInstanceError("selection Definition is invalid")
        if not isinstance(self.desired_runtime_binding, DesiredRuntimeBinding):
            raise MissingEffectiveBindingError("selection desired Binding is invalid")
        if not isinstance(self.effective_runtime_binding, EffectiveRuntimeBinding):
            raise MissingEffectiveBindingError("selection effective Binding is invalid")
        if not isinstance(self.evidence, SelectedInstanceEvidence):
            raise InvalidSelectedInstanceError("selection evidence is invalid")
        if self.evidence.definition_ref != self.definition_ref:
            raise InvalidSelectedInstanceError("selection evidence Definition mismatch")
        if self.evidence.instance_id != self.instance_id:
            raise InvalidSelectedInstanceError("selection evidence Instance mismatch")


class InstanceSelector(Protocol):
    def select(self, request: InstanceSelectionRequest) -> SelectedInstanceResult: ...


class DeterministicPrototypeInstanceSelector:
    """Repository-backed deterministic policy for component evidence only."""

    def __init__(self, repository: AgentInstanceRepository) -> None:
        self._repository = repository

    def select(self, request: InstanceSelectionRequest) -> SelectedInstanceResult:
        candidates = self._repository.list_by_definition(request.definition_ref)
        return select_deterministically(request, candidates)


def select_deterministically(
    request: InstanceSelectionRequest,
    candidates: tuple[AgentInstance, ...],
) -> SelectedInstanceResult:
    """Select the lexical eligible Instance; this policy is explicitly unfrozen."""
    if not isinstance(request.definition_ref, AgentDefinitionRef):
        raise InvalidSelectedInstanceError("selection requires a Definition reference")
    seen: set[str] = set()
    eligible: list[AgentInstance] = []
    for candidate in candidates:
        if not isinstance(candidate, AgentInstance):
            raise InvalidSelectedInstanceError("selection candidate is not an Instance")
        key = candidate.instance_id.value
        if key in seen:
            raise DuplicateSelectionIdentityError(f"duplicate Instance identity: {key}")
        seen.add(key)
        if candidate.definition_ref != request.definition_ref:
            raise InvalidSelectedInstanceError(
                "selected Instance does not belong to requested Definition"
            )
        if candidate.lifecycle is AgentInstanceLifecycle.ACTIVE:
            eligible.append(candidate)
    if not eligible:
        raise NoEligibleInstanceError("no eligible Instance for Definition")
    eligible.sort(key=lambda item: item.instance_id.value)
    selected = eligible[0]
    if selected.effective_runtime_binding is None:
        raise MissingEffectiveBindingError(
            "selected Instance has no effective Runtime Binding"
        )
    evidence = SelectedInstanceEvidence(
        definition_ref=selected.definition_ref,
        instance_id=selected.instance_id,
        authority=ROUTING_POLICY,
        reason="lowest lexical eligible Instance ID",
    )
    return SelectedInstanceResult(
        instance_id=selected.instance_id,
        definition_ref=selected.definition_ref,
        desired_runtime_binding=request.desired_runtime_binding,
        effective_runtime_binding=selected.effective_runtime_binding,
        evidence=evidence,
    )


class RejectAmbiguousInstanceSelector:
    """Alternative explicit policy proving ambiguity can fail closed."""

    def __init__(self, repository: AgentInstanceRepository) -> None:
        self._repository = repository

    def select(self, request: InstanceSelectionRequest) -> SelectedInstanceResult:
        candidates = self._repository.list_by_definition(request.definition_ref)
        if len(candidates) > 1:
            raise AmbiguousInstanceSelectionError(
                "multiple candidates require an explicit deterministic policy"
            )
        return select_deterministically(request, candidates)
