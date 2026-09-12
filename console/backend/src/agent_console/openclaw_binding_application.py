"""Authorization-first application service for durable OpenClaw observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from agent_core.execution_contract import (
    Generation,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    RuntimeDesiredState,
    RuntimeDesiredStateKind,
    RuntimeInstanceId,
    ScopeIdentity,
    canonical_digest,
)
from agent_core.openclaw_binding import (
    AssociationStatus,
    OpenClawBindingObservation,
    OpenClawGenerationBinding,
    OpenClawRuntimeBinding,
)

from .execution_domain import ExecutionConflict
from .execution_repository import OpenClawBindingRepository
from .governed_execution_authorization import (
    GovernedExecutionAuthority,
    GovernedPrincipal,
)

EXACT_SOURCE_VERSION = "2026.7.1-2"


class OpenClawBindingApplicationError(ValueError):
    """Stable, minimum-disclosure application failure."""


class OpenClawExecutionAuthority(OpenClawBindingRepository, Protocol):
    def get(
        self, scope: ScopeIdentity, placement_id: PlacementId
    ) -> PlacementDecision | None: ...

    def get_command(
        self, scope: ScopeIdentity, command_id
    ) -> RuntimeDesiredState | None: ...


class OpenClawObserver(Protocol):
    def observe(
        self,
        binding: OpenClawRuntimeBinding,
        generation: OpenClawGenerationBinding,
        *,
        high_water: int,
        at: datetime | None = None,
    ) -> OpenClawBindingObservation: ...


@dataclass(frozen=True, slots=True)
class RecordOpenClawBinding:
    scope: ScopeIdentity
    runtime_instance_id: RuntimeInstanceId
    generation: Generation
    placement_id: PlacementId
    desired_command: RuntimeDesiredState
    idempotency_key: str
    gateway_digest: str
    agent_id: str
    canonical_workspace: str
    workspace_host: str
    workspace_storage_domain: str
    session_key: str
    session_id: str


def observation_resource(
    scope: ScopeIdentity,
    runtime_instance_id: RuntimeInstanceId,
    generation: Generation,
    placement_id: PlacementId,
) -> str:
    return (
        "openclaw-binding:observe:"
        f"{scope.namespace}:{scope.security_domain}:{runtime_instance_id}:"
        f"{generation.value}:{placement_id}"
    )


class OpenClawBindingApplicationService:
    def __init__(
        self,
        repository: OpenClawExecutionAuthority,
        authorization: GovernedExecutionAuthority,
        observer: OpenClawObserver,
    ) -> None:
        self._repository = repository
        self._authorization = authorization
        self._observer = observer

    @staticmethod
    def _scope(principal: GovernedPrincipal) -> ScopeIdentity:
        return ScopeIdentity(principal.tenant_id, principal.security_domain)

    def _authorize(
        self,
        principal: GovernedPrincipal,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        generation: Generation,
        placement_id: PlacementId,
    ):
        if self._scope(principal) != scope:
            raise OpenClawBindingApplicationError("OPENCLAW_BINDING_NOT_FOUND")
        return self._authorization.require(
            principal,
            "EXECUTION",
            "OBSERVE",
            observation_resource(scope, runtime_instance_id, generation, placement_id),
        )

    def _placement(
        self,
        scope: ScopeIdentity,
        placement_id: PlacementId,
        runtime_instance_id: RuntimeInstanceId,
    ) -> PlacementDecision:
        placement = self._repository.get(scope, placement_id)
        if (
            placement is None
            or placement.decision is not PlacementDecisionKind.PLACED
            or placement.runtime_instance_id != runtime_instance_id
        ):
            raise OpenClawBindingApplicationError("OPENCLAW_PLACEMENT_NOT_VALID")
        return placement

    def record(
        self, command: RecordOpenClawBinding, *, principal: GovernedPrincipal
    ) -> tuple[OpenClawRuntimeBinding, OpenClawGenerationBinding]:
        desired = command.desired_command
        if (
            desired.runtime_instance_id != command.runtime_instance_id
            or desired.desired_generation != command.generation
            or desired.desired_state is not RuntimeDesiredStateKind.OBSERVE
        ):
            raise OpenClawBindingApplicationError("OPENCLAW_COMMAND_NOT_VALID")
        decision = self._authorize(
            principal,
            command.scope,
            command.runtime_instance_id,
            command.generation,
            command.placement_id,
        )
        self._placement(
            command.scope, command.placement_id, command.runtime_instance_id
        )
        stored = self._repository.get_command(command.scope, desired.command_id)
        if stored != desired:
            raise OpenClawBindingApplicationError("OPENCLAW_COMMAND_NOT_VALID")
        existing = self._repository.get_openclaw_binding(
            command.scope, command.runtime_instance_id, command.generation
        )
        if existing is not None:
            binding, generation = existing
            if (
                binding.placement_id == command.placement_id
                and binding.gateway_digest == command.gateway_digest
                and binding.agent_id == command.agent_id
                and binding.canonical_workspace == command.canonical_workspace
                and binding.workspace_host == command.workspace_host
                and binding.workspace_storage_domain == command.workspace_storage_domain
                and generation.session_key == command.session_key
                and generation.session_id == command.session_id
                and generation.command_id == desired.command_id
                and generation.idempotency_key == command.idempotency_key
                and generation.command_payload_digest == canonical_digest(desired)
            ):
                return existing
            raise OpenClawBindingApplicationError(
                "OPENCLAW_GENERATION_BINDING_CONFLICT"
            )
        now = datetime.now(UTC)
        binding = OpenClawRuntimeBinding(
            command.scope,
            command.runtime_instance_id,
            command.placement_id,
            command.gateway_digest,
            command.agent_id,
            command.canonical_workspace,
            command.workspace_host,
            command.workspace_storage_domain,
            EXACT_SOURCE_VERSION,
            decision.decision_id,
            now,
        )
        generation = OpenClawGenerationBinding(
            command.scope,
            command.runtime_instance_id,
            command.generation,
            command.session_key,
            command.session_id,
            desired.command_id,
            command.idempotency_key,
            canonical_digest(desired),
            AssociationStatus.UNVERIFIED,
            0,
            now,
        )
        try:
            self._repository.save_openclaw_binding(binding, generation)
        except ExecutionConflict as exc:
            raise OpenClawBindingApplicationError(str(exc)) from exc
        recovered = self._repository.get_openclaw_binding(
            command.scope, command.runtime_instance_id, command.generation
        )
        if recovered is None:
            raise OpenClawBindingApplicationError("OPENCLAW_BINDING_NOT_FOUND")
        return recovered

    def observe(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        generation: Generation,
        *,
        principal: GovernedPrincipal,
        at: datetime | None = None,
    ) -> OpenClawBindingObservation:
        persisted = self._repository.get_openclaw_binding(
            scope, runtime_instance_id, generation
        )
        if persisted is None:
            raise OpenClawBindingApplicationError("OPENCLAW_BINDING_NOT_FOUND")
        binding, generation_binding = persisted
        self._authorize(
            principal,
            scope,
            runtime_instance_id,
            generation,
            binding.placement_id,
        )
        self._placement(scope, binding.placement_id, runtime_instance_id)
        observation = self._observer.observe(
            binding,
            generation_binding,
            high_water=generation_binding.observation_high_water + 1,
            at=at,
        )
        try:
            self._repository.append_openclaw_observation(observation)
        except ExecutionConflict as exc:
            raise OpenClawBindingApplicationError(str(exc)) from exc
        return observation
