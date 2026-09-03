"""Digital Employee Instance, Assignment, and Placement application services."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from .execution_postgres import (
    AgentInstanceId,
    AppendDisposition,
    AssignmentId,
    AttemptId,
    DigitalEmployeeInstanceId,
    PlacementDecision,
    PlacementRequest,
    PlacementResult,
    RuntimeInstanceId,
    ScopeIdentity,
)


class DigitalEmployeeError(RuntimeError):
    """Stable, non-disclosing application failure."""


class InstanceLifecycle(StrEnum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    RETIRED = "RETIRED"


class AssignmentLifecycle(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class ObservationFreshness(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNOBSERVED = "UNOBSERVED"


@dataclass(frozen=True, slots=True)
class DefinitionReference:
    definition_id: str
    revision_id: str
    digest: str
    published: bool
    eligible: bool


@dataclass(frozen=True, slots=True)
class InstanceRecord:
    scope: ScopeIdentity
    instance_id: DigitalEmployeeInstanceId
    version: int
    definition: DefinitionReference
    owner_id: str
    organization_id: str
    lifecycle: InstanceLifecycle
    workspace_reference: str | None
    model_reference: str | None
    policy_references: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    reobservation_id: str | None = None


@dataclass(frozen=True, slots=True)
class AssignmentRecord:
    scope: ScopeIdentity
    assignment_id: AssignmentId
    instance_id: DigitalEmployeeInstanceId
    assignee_id: str
    business_role: str
    lifecycle: AssignmentLifecycle
    effective_from: datetime
    effective_until: datetime | None
    version: int
    command_id: str
    predecessor_assignment_id: AssignmentId | None = None


@dataclass(frozen=True, slots=True)
class PlacementFacts:
    result: PlacementResult
    freshness: ObservationFreshness
    observation_id: str | None
    active_attempts: tuple[AttemptId, ...]


class DigitalEmployeeRepository(Protocol):
    def create_instance(
        self, value: InstanceRecord, command_id: str
    ) -> AppendDisposition: ...

    def get_instance(
        self, scope: ScopeIdentity, instance_id: DigitalEmployeeInstanceId
    ) -> InstanceRecord | None: ...

    def replace_instance(
        self, value: InstanceRecord, expected_version: int
    ) -> None: ...

    def create_assignment(self, value: AssignmentRecord) -> AppendDisposition: ...

    def assignments_for_instance(
        self, scope: ScopeIdentity, instance_id: DigitalEmployeeInstanceId
    ) -> tuple[AssignmentRecord, ...]: ...

    def decide_placement(
        self,
        scope: ScopeIdentity,
        request: PlacementRequest,
        decision: PlacementDecision,
    ) -> PlacementResult: ...

    def runtime_exists(
        self, scope: ScopeIdentity, runtime_id: RuntimeInstanceId
    ) -> bool: ...

    def agent_exists(self, scope: ScopeIdentity, agent_id: AgentInstanceId) -> bool: ...

    def latest_observation(
        self, scope: ScopeIdentity, runtime_id: RuntimeInstanceId
    ) -> tuple[str, datetime] | None: ...

    def active_attempts(
        self,
        scope: ScopeIdentity,
        runtime_id: RuntimeInstanceId,
        agent_id: AgentInstanceId,
    ) -> tuple[AttemptId, ...]: ...


class DefinitionAuthority(Protocol):
    def resolve(
        self, scope: ScopeIdentity, definition_id: str, revision_id: str
    ) -> DefinitionReference | None: ...


def _required(value: str, code: str) -> str:
    if not value or len(value.encode()) > 200:
        raise DigitalEmployeeError(code)
    return value


def _command_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class DigitalEmployeeApplicationService:
    def __init__(
        self, repository: DigitalEmployeeRepository, definitions: DefinitionAuthority
    ) -> None:
        self.repository = repository
        self.definitions = definitions

    def create_instance(
        self,
        *,
        scope: ScopeIdentity,
        instance_id: DigitalEmployeeInstanceId,
        definition_id: str,
        definition_revision_id: str,
        owner_id: str,
        organization_id: str,
        command_id: str,
        workspace_reference: str | None = None,
        model_reference: str | None = None,
        policy_references: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> tuple[InstanceRecord, AppendDisposition]:
        definition = self.definitions.resolve(
            scope,
            _required(definition_id, "DEFINITION_ID_INVALID"),
            definition_revision_id,
        )
        if definition is None:
            raise DigitalEmployeeError("DEFINITION_NOT_FOUND")
        if not definition.published or not definition.eligible:
            raise DigitalEmployeeError("DEFINITION_INELIGIBLE")
        instant = now or datetime.now(UTC)
        value = InstanceRecord(
            scope,
            instance_id,
            1,
            definition,
            _required(owner_id, "OWNER_INVALID"),
            _required(organization_id, "ORGANIZATION_INVALID"),
            InstanceLifecycle.ENABLED,
            workspace_reference,
            model_reference,
            tuple(sorted(set(policy_references))),
            instant,
            instant,
        )
        disposition = self.repository.create_instance(
            value, _required(command_id, "COMMAND_ID_INVALID")
        )
        readback = self.repository.get_instance(scope, instance_id)
        if readback is None or (
            disposition is AppendDisposition.APPENDED and readback != value
        ):
            raise DigitalEmployeeError("AUTHORITATIVE_READBACK_FAILED")
        return readback, disposition

    def transition(
        self,
        scope: ScopeIdentity,
        instance_id: DigitalEmployeeInstanceId,
        lifecycle: InstanceLifecycle,
        *,
        expected_version: int,
        reobservation_id: str | None = None,
        now: datetime | None = None,
    ) -> InstanceRecord:
        current = self.repository.get_instance(scope, instance_id)
        if current is None:
            raise DigitalEmployeeError("INSTANCE_NOT_FOUND")
        allowed = {
            InstanceLifecycle.ENABLED: {InstanceLifecycle.DISABLED},
            InstanceLifecycle.DISABLED: {
                InstanceLifecycle.ENABLED,
                InstanceLifecycle.RETIRED,
            },
            InstanceLifecycle.RETIRED: set(),
        }
        if lifecycle not in allowed[current.lifecycle]:
            raise DigitalEmployeeError("INVALID_INSTANCE_LIFECYCLE_TRANSITION")
        value = InstanceRecord(
            current.scope,
            current.instance_id,
            current.version + 1,
            current.definition,
            current.owner_id,
            current.organization_id,
            lifecycle,
            current.workspace_reference,
            current.model_reference,
            current.policy_references,
            current.created_at,
            now or datetime.now(UTC),
            reobservation_id,
        )
        self.repository.replace_instance(value, expected_version)
        readback = self.repository.get_instance(scope, instance_id)
        if readback != value:
            raise DigitalEmployeeError("AUTHORITATIVE_READBACK_FAILED")
        return readback

    def assign(self, value: AssignmentRecord) -> AppendDisposition:
        instance = self.repository.get_instance(value.scope, value.instance_id)
        if instance is None:
            raise DigitalEmployeeError("INSTANCE_NOT_FOUND")
        if instance.lifecycle is not InstanceLifecycle.ENABLED:
            raise DigitalEmployeeError("INSTANCE_NOT_ASSIGNABLE")
        _required(value.assignee_id, "ASSIGNEE_INVALID")
        _required(value.business_role, "BUSINESS_ROLE_INVALID")
        if value.version < 1 or (
            value.effective_until and value.effective_until <= value.effective_from
        ):
            raise DigitalEmployeeError("ASSIGNMENT_EFFECTIVE_PERIOD_INVALID")
        return self.repository.create_assignment(value)

    def place(
        self,
        scope: ScopeIdentity,
        request: PlacementRequest,
        decision: PlacementDecision,
        *,
        freshness_window: timedelta,
        now: datetime | None = None,
    ) -> PlacementFacts:
        if request.scope != scope:
            raise DigitalEmployeeError("PLACEMENT_SCOPE_MISMATCH")
        if not self.repository.agent_exists(scope, request.agent_instance_id):
            raise DigitalEmployeeError("AGENT_INSTANCE_NOT_FOUND")
        runtime_id = decision.runtime_instance_id
        if runtime_id is None or not self.repository.runtime_exists(scope, runtime_id):
            raise DigitalEmployeeError("RUNTIME_INSTANCE_NOT_FOUND")
        result = self.repository.decide_placement(scope, request, decision)
        observed = self.repository.latest_observation(scope, runtime_id)
        instant = now or datetime.now(UTC)
        if observed is None:
            freshness, observation_id = ObservationFreshness.UNOBSERVED, None
        else:
            observation_id, observed_at = observed
            freshness = (
                ObservationFreshness.CURRENT
                if instant - observed_at <= freshness_window
                else ObservationFreshness.STALE
            )
        return PlacementFacts(
            result,
            freshness,
            observation_id,
            self.repository.active_attempts(
                scope, runtime_id, request.agent_instance_id
            ),
        )


def assignment_command_digest(value: AssignmentRecord) -> str:
    """Canonical digest used by adapters for replay/conflict classification."""
    return _command_digest(value)
