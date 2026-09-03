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


class AtomicCommandType(StrEnum):
    APPROVE_AND_CONTINUE = "APPROVE_AND_CONTINUE"
    REJECT_PLAN = "REJECT_PLAN"
    APPLY_INTERVENTION_DECISION = "APPLY_INTERVENTION_DECISION"
    RETRY_ATTEMPT = "RETRY_ATTEMPT"
    CREATE_SUCCESSOR_RUN = "CREATE_SUCCESSOR_RUN"
    REPLACE_RUNTIME = "REPLACE_RUNTIME"
    CANCEL_CONTROLLED_EXECUTION = "CANCEL_CONTROLLED_EXECUTION"


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
class InterventionReview:
    review_id: str
    intervention_id: str
    actor_id: str
    authority_basis: str
    reviewed_at: datetime

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class InterventionDecision:
    decision_id: str
    intervention_id: str
    review_id: str
    decision: str
    actor_id: str
    authority_basis: str
    reason_category: str
    decided_at: datetime

    def __post_init__(self) -> None:
        if self.decision not in {"AUTHORIZE", "REJECT"}:
            raise ValueError("INVALID_INTERVENTION_DECISION")

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class WorkflowControlOperation:
    """One already-authorized atomic persistence operation.

    The application layer owns authorization and identity allocation. This record
    contains only exact identities and facts needed for guarded persistence.
    """

    scope: ScopeIdentity
    command_type: AtomicCommandType
    actor_id: str
    idempotency_key: str
    payload: dict[str, Any]
    control_command_id: str
    requested_at: datetime
    retain_until: datetime
    target: InterventionTarget
    target_expected_version: int
    intervention_id: str | None = None
    transition_id: str | None = None
    review: InterventionReview | None = None
    decision: InterventionDecision | None = None
    plan_id: str | None = None
    plan_version: int | None = None
    plan_digest: str | None = None
    approval: ApprovalDecision | None = None
    successor_id: str | None = None
    placement_id: str | None = None
    runtime_command_id: str | None = None
    affected_attempt_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    outcome_ids: tuple[str, ...] = ()

    @property
    def payload_digest(self) -> str:
        return canonical_digest(self.payload)


@dataclass(frozen=True)
class WorkflowControlOperationResult:
    replayed: bool
    command_type: AtomicCommandType
    control_command_id: str
    target_id: str
    target_version: int
    intervention_id: str | None = None
    transition_id: str | None = None
    approval_decision_id: str | None = None
    successor_attempt_id: str | None = None
    successor_workflow_run_id: str | None = None
    runtime_command_id: str | None = None

    def record(self) -> dict[str, Any]:
        return {
            "command_type": self.command_type.value,
            "control_command_id": self.control_command_id,
            "target_id": self.target_id,
            "target_version": self.target_version,
            "intervention_id": self.intervention_id,
            "transition_id": self.transition_id,
            "approval_decision_id": self.approval_decision_id,
            "successor_attempt_id": self.successor_attempt_id,
            "successor_workflow_run_id": self.successor_workflow_run_id,
            "runtime_command_id": self.runtime_command_id,
        }


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
        if hasattr(item, "__dataclass_fields__"):
            return item.__dict__
        raise TypeError(type(item).__name__)

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=default)
    return hashlib.sha256(payload.encode()).hexdigest()
