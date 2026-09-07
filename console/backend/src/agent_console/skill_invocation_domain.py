"""Typed governed READ_ONLY Skill invocation records and projections."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .execution_domain import ScopeIdentity
from .resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    canonical_digest,
    stable_id,
)


class SkillInvocationError(ValueError):
    """Stable, bounded application failure."""


class SkillInvocationConflict(SkillInvocationError):
    """A replay, slot, CAS, or immutable-history conflict."""


class SideEffectClass(StrEnum):
    READ_ONLY = "READ_ONLY"
    IDEMPOTENT_WRITE = "IDEMPOTENT_WRITE"
    NON_IDEMPOTENT_WRITE = "NON_IDEMPOTENT_WRITE"
    UNKNOWN = "UNKNOWN"


class InvocationFactKind(StrEnum):
    INVOCATION_REQUESTED = "INVOCATION_REQUESTED"
    DISPATCH_RECORDED = "DISPATCH_RECORDED"
    INVOCATION_ACCEPTED = "INVOCATION_ACCEPTED"
    INVOCATION_RUNNING = "INVOCATION_RUNNING"
    INVOCATION_SUCCEEDED = "INVOCATION_SUCCEEDED"
    INVOCATION_FAILED = "INVOCATION_FAILED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    INVOCATION_CANCELLED = "INVOCATION_CANCELLED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class InvocationState(StrEnum):
    REQUESTED = "REQUESTED"
    DISPATCH_RECORDED = "DISPATCH_RECORDED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLED = "CANCELLED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


FACT_STATE = {
    InvocationFactKind.INVOCATION_REQUESTED: InvocationState.REQUESTED,
    InvocationFactKind.DISPATCH_RECORDED: InvocationState.DISPATCH_RECORDED,
    InvocationFactKind.INVOCATION_ACCEPTED: InvocationState.ACCEPTED,
    InvocationFactKind.INVOCATION_RUNNING: InvocationState.RUNNING,
    InvocationFactKind.INVOCATION_SUCCEEDED: InvocationState.SUCCEEDED,
    InvocationFactKind.INVOCATION_FAILED: InvocationState.FAILED,
    InvocationFactKind.CANCELLATION_REQUESTED: InvocationState.CANCELLATION_REQUESTED,
    InvocationFactKind.INVOCATION_CANCELLED: InvocationState.CANCELLED,
    InvocationFactKind.OUTCOME_UNKNOWN: InvocationState.OUTCOME_UNKNOWN,
}
TERMINAL_STATES = frozenset(
    {
        InvocationState.SUCCEEDED,
        InvocationState.FAILED,
        InvocationState.CANCELLED,
        InvocationState.OUTCOME_UNKNOWN,
    }
)


def _required(value: str, code: str, *, maximum: int = 500) -> None:
    if not isinstance(value, str) or not value or len(value.encode()) > maximum:
        raise SkillInvocationError(code)


def _digest(value: str, code: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SkillInvocationError(code)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise SkillInvocationError("SKILL_INPUT_NOT_CANONICAL_JSON") from exc


@dataclass(frozen=True, slots=True)
class SkillIOLimits:
    policy_id: str
    policy_revision: str
    max_input_bytes: int
    max_output_bytes: int
    max_object_depth: int
    max_properties: int
    timeout_ms: int

    def __post_init__(self) -> None:
        _required(self.policy_id, "IO_POLICY_ID_REQUIRED")
        _required(self.policy_revision, "IO_POLICY_REVISION_REQUIRED")
        for name in (
            "max_input_bytes",
            "max_output_bytes",
            "max_object_depth",
            "max_properties",
            "timeout_ms",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SkillInvocationError(f"IO_{name.upper()}_INVALID")

    @property
    def digest(self) -> str:
        return canonical_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class SideEffectPolicy:
    policy_id: str
    policy_revision: str
    policy_digest: str
    allowed_class: SideEffectClass

    def __post_init__(self) -> None:
        _required(self.policy_id, "SIDE_EFFECT_POLICY_ID_REQUIRED")
        _required(self.policy_revision, "SIDE_EFFECT_POLICY_REVISION_REQUIRED")
        _required(self.policy_digest, "SIDE_EFFECT_POLICY_DIGEST_REQUIRED")
        _digest(self.policy_digest, "SIDE_EFFECT_POLICY_DIGEST_INVALID")
        if self.allowed_class is not SideEffectClass.READ_ONLY:
            raise SkillInvocationError("SKILL_SIDE_EFFECT_NOT_ALLOWED")


@dataclass(frozen=True, slots=True)
class ExecutorRevision:
    executor_id: str
    executor_revision: str
    configuration_digest: str

    def __post_init__(self) -> None:
        _required(self.executor_id, "EXECUTOR_ID_REQUIRED")
        _required(self.executor_revision, "EXECUTOR_REVISION_REQUIRED")
        _required(self.configuration_digest, "EXECUTOR_DIGEST_REQUIRED")
        _digest(self.configuration_digest, "EXECUTOR_DIGEST_INVALID")


@dataclass(frozen=True, slots=True)
class SkillInvocationRequest:
    scope: ScopeIdentity
    idempotency_key: str
    attempt_id: str
    workflow_run_id: str
    task_run_id: str
    plan_id: str
    plan_version: int
    plan_digest: str
    approval_id: str
    assignment_id: str
    digital_employee_definition_id: str
    digital_employee_definition_revision_id: str
    digital_employee_definition_digest: str
    digital_employee_instance_id: str
    agent_instance_id: str | None
    runtime_instance_id: str | None
    skill_id: str
    skill_revision_id: str
    skill_digest: str
    operation: str
    input_schema_digest: str
    output_schema_digest: str
    binding_id: str
    binding_digest: str
    executor: ExecutorRevision
    side_effect_class: SideEffectClass
    policy: SideEffectPolicy
    io_limits: SkillIOLimits
    authorization_decision_id: str
    resource_use: ResourceUseBinding

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise SkillInvocationError("SKILL_INVOCATION_SCOPE_REQUIRED")
        for name in (
            "idempotency_key",
            "attempt_id",
            "workflow_run_id",
            "task_run_id",
            "plan_id",
            "plan_digest",
            "approval_id",
            "assignment_id",
            "digital_employee_definition_id",
            "digital_employee_definition_revision_id",
            "digital_employee_definition_digest",
            "digital_employee_instance_id",
            "skill_id",
            "skill_revision_id",
            "skill_digest",
            "operation",
            "input_schema_digest",
            "output_schema_digest",
            "binding_id",
            "binding_digest",
            "authorization_decision_id",
        ):
            _required(getattr(self, name), f"{name.upper()}_REQUIRED")
        if isinstance(self.plan_version, bool) or self.plan_version < 1:
            raise SkillInvocationError("PLAN_VERSION_INVALID")
        for name in (
            "plan_digest",
            "digital_employee_definition_digest",
            "skill_digest",
            "input_schema_digest",
            "output_schema_digest",
            "binding_digest",
        ):
            _digest(getattr(self, name), f"{name.upper()}_INVALID")
        if self.side_effect_class is not SideEffectClass.READ_ONLY:
            raise SkillInvocationError("SKILL_SIDE_EFFECT_NOT_ALLOWED")
        if self.policy.allowed_class is not SideEffectClass.READ_ONLY:
            raise SkillInvocationError("SKILL_SIDE_EFFECT_POLICY_MISMATCH")
        if self.resource_use.scope != self.scope:
            raise SkillInvocationError("SKILL_RESOURCE_USE_SCOPE_MISMATCH")
        expected_use_id = stable_id(
            "resource-use",
            self.scope.namespace,
            self.scope.security_domain,
            self.attempt_id,
            "SKILL",
            "skill:primary",
            "1",
        )
        if (
            self.resource_use.resource_use_id != expected_use_id
            or self.resource_use.resource_kind is not ResourceKind.SKILL
            or self.resource_use.slot_key != "skill:primary"
            or self.resource_use.occurrence_ordinal != 1
            or self.resource_use.attempt_id != self.attempt_id
            or self.resource_use.workflow_run_id != self.workflow_run_id
            or self.resource_use.task_run_id != self.task_run_id
            or self.resource_use.plan_id != self.plan_id
            or self.resource_use.plan_version != self.plan_version
            or self.resource_use.plan_digest != self.plan_digest
            or self.resource_use.digital_employee_definition_id
            != self.digital_employee_definition_id
            or self.resource_use.digital_employee_definition_revision_id
            != self.digital_employee_definition_revision_id
            or self.resource_use.digital_employee_definition_digest
            != self.digital_employee_definition_digest
            or self.resource_use.digital_employee_instance_id
            != self.digital_employee_instance_id
            or self.resource_use.agent_instance_id != self.agent_instance_id
            or self.resource_use.runtime_instance_id != self.runtime_instance_id
            or self.resource_use.resource_id != self.skill_id
            or self.resource_use.resource_revision_id != self.skill_revision_id
            or self.resource_use.resource_digest != self.skill_digest
            or self.resource_use.binding_id != self.binding_id
            or self.resource_use.binding_digest != self.binding_digest
            or self.resource_use.authorization_decision_id
            != self.authorization_decision_id
            or self.resource_use.executor_id != self.executor.executor_id
            or self.resource_use.executor_revision != self.executor.executor_revision
        ):
            raise SkillInvocationError("SKILL_RESOURCE_USE_BINDING_MISMATCH")

    @property
    def invocation_id(self) -> str:
        return stable_id(
            "skill-invocation",
            self.scope.namespace,
            self.scope.security_domain,
            self.attempt_id,
            self.idempotency_key,
        )

    def payload_digest(self, inputs: dict[str, Any]) -> str:
        return canonical_digest(
            {"request": asdict(self), "inputDigest": canonical_digest(inputs)}
        )


@dataclass(frozen=True, slots=True)
class SkillInvocationFact:
    fact_id: str
    kind: InvocationFactKind
    source: str
    source_observation_id: str
    source_digest: str
    observed_at: datetime
    limitation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, code in (
            (self.fact_id, "SKILL_INVOCATION_FACT_ID_REQUIRED"),
            (self.source, "SKILL_INVOCATION_FACT_SOURCE_REQUIRED"),
            (self.source_observation_id, "SKILL_INVOCATION_OBSERVATION_REQUIRED"),
        ):
            _required(value, code)
        _digest(self.source_digest, "SKILL_INVOCATION_SOURCE_DIGEST_INVALID")
        if (
            not isinstance(self.kind, InvocationFactKind)
            or self.observed_at.tzinfo is None
        ):
            raise SkillInvocationError("SKILL_INVOCATION_FACT_INVALID")


@dataclass(frozen=True, slots=True)
class SkillInvocationSnapshot:
    invocation_id: str
    state: InvocationState
    high_water: int
    payload_digest: str
    input_digest: str
    output_digest: str | None
    evidence_id: str | None
    resource_use_id: str
    fact_kinds: tuple[InvocationFactKind, ...]
    error_code: str | None
    limitation_codes: tuple[str, ...]
    technical_success_not_business_success: bool

    def __post_init__(self) -> None:
        if not isinstance(self.state, InvocationState) or self.high_water < 1:
            raise SkillInvocationError("SKILL_INVOCATION_SNAPSHOT_INVALID")
        _digest(self.payload_digest, "SKILL_INVOCATION_PAYLOAD_DIGEST_INVALID")
        _digest(self.input_digest, "SKILL_INVOCATION_INPUT_DIGEST_INVALID")
        if self.output_digest is not None:
            _digest(self.output_digest, "SKILL_INVOCATION_OUTPUT_DIGEST_INVALID")
        if not self.technical_success_not_business_success:
            raise SkillInvocationError("BUSINESS_OUTCOME_SEPARATION_REQUIRED")

    def canonical_read_model(self) -> dict[str, Any]:
        return {
            "schemaVersion": "skill-invocation-read.v1",
            "invocationId": self.invocation_id,
            "state": self.state.value,
            "resultKnown": self.state
            in {
                InvocationState.SUCCEEDED,
                InvocationState.FAILED,
                InvocationState.CANCELLED,
            },
            "technicalSuccessNotBusinessSuccess": True,
            "resourceUseId": self.resource_use_id,
            "evidenceId": self.evidence_id,
            "errorCode": self.error_code,
            "limitations": list(self.limitation_codes),
            "technical": {
                "highWater": self.high_water,
                "payloadDigest": self.payload_digest,
                "inputDigest": self.input_digest,
                "outputDigest": self.output_digest,
                "factSequence": [item.value for item in self.fact_kinds],
            },
        }
