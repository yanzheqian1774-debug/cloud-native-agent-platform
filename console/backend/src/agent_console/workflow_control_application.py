"""Governed Workflow Control application orchestration.

This module maps business actions to the closed persistence commands.  It owns
authorization, bounded input, authoritative readback, and persist-before-effect;
it owns no HTTP route, provider implementation, Kubernetes call, or runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from .execution_domain import ScopeIdentity
from .workflow_control_domain import (
    COMMAND_PERSISTENCE_CONTRACTS,
    AtomicCommandType,
    WorkflowControlOperation,
    WorkflowControlOperationResult,
)

_SECRET = re.compile(
    r"(?:api[_-]?key|authorization|bearer|credential|password|secret|token|raw[_-]?prompt)",
    re.IGNORECASE,
)
_CORRECTION_FIELDS = frozenset(
    {"objective", "constraints", "task_instruction", "resource_selection"}
)


class WorkflowControlApplicationError(RuntimeError):
    """Stable minimum-disclosure application failure."""


class EffectState(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    AUTHORIZED_PENDING = "AUTHORIZED_PENDING"
    OBSERVED = "OBSERVED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True, slots=True)
class TrustedPrincipal:
    actor_id: str
    scope: ScopeIdentity
    permissions: frozenset[AtomicCommandType]


@dataclass(frozen=True, slots=True)
class EffectRequest:
    control_command_id: str
    command_type: AtomicCommandType
    target_id: str
    runtime_command_id: str | None


class EffectPort(Protocol):
    def apply(self, request: EffectRequest) -> str: ...


class EffectFailureRecorder(Protocol):
    def record_recovery_required(
        self,
        *,
        scope: ScopeIdentity,
        result: WorkflowControlOperationResult,
        reason_code: str,
        evidence: dict[str, Any],
    ) -> None: ...


class WorkflowControlStore(Protocol):
    def persist_operation(
        self, operation: WorkflowControlOperation, *, authorized: bool
    ) -> WorkflowControlOperationResult: ...

    def lookup_idempotency(
        self,
        scope: ScopeIdentity,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
    ) -> object | None: ...

    def read_linked_evidence(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[str, ...]: ...

    def read_linked_outcomes(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class WorkflowControlResult:
    durable: WorkflowControlOperationResult
    effect_state: EffectState
    effect_observation_id: str | None
    evidence_ids: tuple[str, ...]
    outcome_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowWorkbenchDTO:
    business_problem: str
    success_criteria: tuple[str, ...]
    plan_id: str
    plan_version: int
    plan_digest: str
    approval_state: str
    workflow_run_id: str
    task_run_ids: tuple[str, ...]
    attempt_ids: tuple[str, ...]
    business_state: str
    pending_human_action: str | None
    intervention_options: tuple[str, ...]
    predecessor_id: str | None
    successor_id: str | None
    digital_employee_definition_id: str | None
    digital_employee_instance_id: str | None
    assignment_id: str | None
    placement_id: str | None
    used_resources: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    outcome_ids: tuple[str, ...]
    availability: str


def minimum_disclosure_evidence(
    *,
    evidence_id: str,
    workflow_id: str,
    task_id: str,
    execution_id: str,
    attempt_ordinal: int,
    event_ordinal: int,
    event_type: str,
    category: str,
    reason_code: str,
    occurred_at: datetime,
) -> dict[str, Any]:
    record = {
        "category": _text(category, "EVIDENCE_CATEGORY_INVALID"),
        "reason_code": _text(reason_code, "EVIDENCE_REASON_INVALID"),
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return {
        "evidence_record_id": _identity(evidence_id, "EVIDENCE_ID_INVALID"),
        "platform_execution_identity": _identity(execution_id, "EXECUTION_ID_INVALID"),
        "workflow_identity": _identity(workflow_id, "WORKFLOW_ID_INVALID"),
        "task_identity": _identity(task_id, "TASK_ID_INVALID"),
        "attempt_ordinal": attempt_ordinal,
        "event_ordinal": event_ordinal,
        "event_type": _text(event_type, "EVIDENCE_TYPE_INVALID"),
        "occurred_at": occurred_at,
        "recorded_at": occurred_at,
        "payload_digest": hashlib.sha256(canonical).hexdigest(),
        "canonical_bytes": canonical,
        "record": record,
    }


def terminal_outcome(
    *,
    outcome_id: str,
    target_id: str,
    terminal_state: str,
    classification: str,
) -> dict[str, Any]:
    record = {
        "classification": _text(classification, "OUTCOME_CLASSIFICATION_INVALID"),
        "terminal_state": terminal_state,
    }
    return {
        "outcome_id": _identity(outcome_id, "OUTCOME_ID_INVALID"),
        "terminal_target_id": _identity(target_id, "TARGET_ID_INVALID"),
        "terminal_state": terminal_state,
        "digest": _digest(record),
        "record": record,
    }


class WorkflowControlApplicationService:
    def __init__(
        self,
        store: WorkflowControlStore,
        *,
        effect_failure_recorder: EffectFailureRecorder | None = None,
    ) -> None:
        self.store = store
        self.effect_failure_recorder = effect_failure_recorder

    def execute(
        self,
        principal: TrustedPrincipal,
        operation: WorkflowControlOperation,
        *,
        effect: EffectPort | None = None,
    ) -> WorkflowControlResult:
        self._validate(principal, operation)
        durable = self.store.persist_operation(operation, authorized=True)
        evidence, outcomes = self._readback(operation, durable)
        if durable.replayed and effect is not None:
            return WorkflowControlResult(
                durable,
                EffectState.AUTHORIZED_PENDING,
                None,
                evidence,
                outcomes,
            )
        if effect is None:
            state = (
                EffectState.AUTHORIZED_PENDING
                if operation.runtime_command_id is not None
                else EffectState.NOT_APPLICABLE
            )
            return WorkflowControlResult(durable, state, None, evidence, outcomes)
        request = EffectRequest(
            durable.control_command_id,
            durable.command_type,
            durable.target_id,
            durable.runtime_command_id,
        )
        try:
            observation_id = effect.apply(request)
        except Exception as exc:
            failure = minimum_disclosure_evidence(
                evidence_id=f"{durable.control_command_id}:effect-failed",
                workflow_id=durable.target_id,
                task_id=durable.target_id,
                execution_id=durable.target_id,
                attempt_ordinal=1,
                event_ordinal=len(evidence) + 1,
                event_type="RUNTIME_EFFECT_FAILED",
                category="RECOVERY_REQUIRED",
                reason_code="RUNTIME_EFFECT_FAILED",
                occurred_at=operation.requested_at,
            )
            if self.effect_failure_recorder is not None:
                self.effect_failure_recorder.record_recovery_required(
                    scope=operation.scope,
                    result=durable,
                    reason_code="RUNTIME_EFFECT_FAILED",
                    evidence=failure,
                )
            raise WorkflowControlApplicationError(
                "RUNTIME_EFFECT_FAILED_RECOVERY_REQUIRED"
            ) from exc
        if not observation_id:
            raise WorkflowControlApplicationError("RUNTIME_OBSERVATION_REQUIRED")
        return WorkflowControlResult(
            durable, EffectState.OBSERVED, observation_id, evidence, outcomes
        )

    def _validate(
        self, principal: TrustedPrincipal, operation: WorkflowControlOperation
    ) -> None:
        if (
            principal.scope != operation.scope
            or principal.actor_id != operation.actor_id
        ):
            raise WorkflowControlApplicationError("NOT_AUTHORIZED")
        if operation.command_type not in principal.permissions:
            raise WorkflowControlApplicationError("NOT_AUTHORIZED")
        if operation.command_type not in COMMAND_PERSISTENCE_CONTRACTS:
            raise WorkflowControlApplicationError("UNSUPPORTED_CONTROL_COMMAND")
        _identity(operation.idempotency_key, "IDEMPOTENCY_KEY_INVALID")
        _identity(operation.control_command_id, "CONTROL_COMMAND_ID_INVALID")
        if (
            operation.requested_at.tzinfo is None
            or operation.retain_until <= operation.requested_at
        ):
            raise WorkflowControlApplicationError("INVALID_COMMAND_TIME")
        if not operation.evidence_records:
            raise WorkflowControlApplicationError("OPERATION_EVIDENCE_REQUIRED")
        if operation.command_type is AtomicCommandType.CORRECT_PLAN:
            correction = operation.correction
            if correction is None or not correction.normalized_correction:
                raise WorkflowControlApplicationError("CORRECTION_REQUIRED")
            if not set(correction.normalized_correction) <= _CORRECTION_FIELDS:
                raise WorkflowControlApplicationError("CORRECTION_FIELD_NOT_ALLOWED")
            _safe(correction.normalized_correction)
        if (
            operation.command_type
            is not AtomicCommandType.COMPLETE_EXECUTION_WITH_OUTCOME
            and operation.outcome_records
        ):
            raise WorkflowControlApplicationError("PREMATURE_OUTCOME_REJECTED")
        if (
            operation.command_type is AtomicCommandType.COMPLETE_EXECUTION_WITH_OUTCOME
            and len(operation.outcome_records) != 1
        ):
            raise WorkflowControlApplicationError("TERMINAL_OUTCOME_REQUIRED")
        _safe(operation.payload)

    def _readback(
        self,
        operation: WorkflowControlOperation,
        result: WorkflowControlOperationResult,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        claim = self.store.lookup_idempotency(
            operation.scope,
            operation.actor_id,
            operation.command_type.value,
            operation.idempotency_key,
        )
        if claim is None or result.control_command_id != operation.control_command_id:
            raise WorkflowControlApplicationError("AUTHORITATIVE_READBACK_FAILED")
        if operation.intervention_id is None:
            raise WorkflowControlApplicationError("INTERVENTION_REQUIRED")
        evidence = self.store.read_linked_evidence(
            operation.scope, operation.intervention_id
        )
        outcomes = self.store.read_linked_outcomes(
            operation.scope, operation.intervention_id
        )
        expected_evidence = tuple(
            item["evidence_record_id"] for item in operation.evidence_records
        )
        expected_outcomes = tuple(
            item["outcome_id"] for item in operation.outcome_records
        )
        if not set(expected_evidence) <= set(evidence) or not set(
            expected_outcomes
        ) <= set(outcomes):
            raise WorkflowControlApplicationError("AUTHORITATIVE_READBACK_FAILED")
        return evidence, outcomes


def with_default_retention(
    operation: WorkflowControlOperation, *, days: int = 30
) -> WorkflowControlOperation:
    if days < 1 or days > 365:
        raise WorkflowControlApplicationError("RETENTION_INVALID")
    return replace(
        operation, retain_until=operation.requested_at + timedelta(days=days)
    )


def _identity(value: str, code: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode()) > 200:
        raise WorkflowControlApplicationError(code)
    return value


def _text(value: str, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or _SECRET.search(value)
    ):
        raise WorkflowControlApplicationError(code)
    return value


def _safe(value: Any) -> None:
    if isinstance(value, dict):
        if any(_SECRET.search(str(key)) for key in value):
            raise WorkflowControlApplicationError("PROTECTED_FIELD_REJECTED")
        for item in value.values():
            _safe(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _safe(item)
    elif isinstance(value, str) and len(value) > 2_000:
        raise WorkflowControlApplicationError("BOUNDED_INPUT_EXCEEDED")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
