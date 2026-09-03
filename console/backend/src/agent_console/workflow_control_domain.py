"""Typed, minimum-disclosure persistence records for Workflow Control."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .execution_domain import ScopeIdentity


class WorkflowControlError(RuntimeError):
    """Stable error without SQL or protected-object disclosure."""


class WorkflowControlConflict(WorkflowControlError):
    pass


class WorkflowControlNotAuthorized(WorkflowControlError):
    pass


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


class InterventionState(StrEnum):
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    APPLICATION_PENDING = "APPLICATION_PENDING"
    APPLIED = "APPLIED"
    OBSERVED = "OBSERVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


TERMINAL_INTERVENTION_STATES = frozenset(
    {
        InterventionState.OBSERVED,
        InterventionState.REJECTED,
        InterventionState.EXPIRED,
        InterventionState.CANCELLED,
        InterventionState.FAILED,
    }
)


@dataclass(frozen=True)
class PlanRecord:
    scope: ScopeIdentity
    plan_id: str
    plan_version: int
    workflow_definition_id: str
    workflow_definition_revision_id: str
    workflow_definition_digest: str
    status: PlanStatus
    aggregate_version: int
    plan_digest: str
    canonical_bytes: bytes
    created_at: datetime
    updated_at: datetime
    predecessor_plan_id: str | None = None
    predecessor_plan_version: int | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    approval_decision_id: str
    plan_id: str
    plan_version: int
    plan_digest: str
    ordinal: int
    decision: str
    actor_id: str
    authority_basis: str
    reason_category: str
    decision_digest: str
    decided_at: datetime


@dataclass(frozen=True)
class InterventionTarget:
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    attempt_id: str | None = None

    def __post_init__(self) -> None:
        if sum(value is not None for value in self.values()) != 1:
            raise ValueError("EXACTLY_ONE_INTERVENTION_TARGET_REQUIRED")

    def values(self) -> tuple[str | None, str | None, str | None]:
        return self.workflow_run_id, self.task_run_id, self.attempt_id


@dataclass(frozen=True)
class InterventionRequest:
    intervention_id: str
    action_type: str
    reason_category: str
    actor_id: str
    authority_basis: str
    expected_target_version: int
    target: InterventionTarget
    fact: dict[str, Any]
    requested_at: datetime

    @property
    def digest(self) -> str:
        return canonical_digest(self.fact)


@dataclass(frozen=True)
class InterventionTransition:
    transition_id: str
    intervention_id: str
    ordinal: int
    from_state: InterventionState | None
    to_state: InterventionState
    actor_id: str
    authority_basis: str
    reason_category: str
    transitioned_at: datetime

    @property
    def digest(self) -> str:
        return canonical_digest(
            {
                "transition_id": self.transition_id,
                "intervention_id": self.intervention_id,
                "ordinal": self.ordinal,
                "from_state": self.from_state,
                "to_state": self.to_state,
                "actor_id": self.actor_id,
                "authority_basis": self.authority_basis,
                "reason_category": self.reason_category,
                "transitioned_at": self.transitioned_at,
            }
        )


@dataclass(frozen=True)
class AtomicControlCommand:
    scope: ScopeIdentity
    command_type: str
    idempotency_key: str
    payload_digest: str
    request: InterventionRequest
    transition: InterventionTransition
    control_command_id: str
    target_state: str
    command_record: dict[str, Any]
    retain_until: datetime
    evidence_ids: tuple[str, ...] = ()
    outcome_ids: tuple[str, ...] = ()
    evidence_records: tuple[dict[str, Any], ...] = ()
    outcome_records: tuple[dict[str, Any], ...] = ()
    successor_plan: PlanRecord | None = None
    successor_workflow_run: dict[str, Any] | None = None


@dataclass(frozen=True)
class AtomicControlResult:
    replayed: bool
    intervention_id: str
    transition_id: str
    control_command_id: str
    target_version: int


def canonical_digest(value: Any) -> str:
    def default(item: Any) -> str:
        if isinstance(item, (datetime, StrEnum)):
            return item.isoformat() if isinstance(item, datetime) else item.value
        raise TypeError(type(item).__name__)

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=default)
    return hashlib.sha256(payload.encode()).hexdigest()
