"""Authorization-first governed Attempt Skill invocation application boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from .execution_domain import ScopeIdentity
from .skill_executor import SkillExecutorFailure, SkillExecutorRegistry
from .skill_invocation_domain import (
    TERMINAL_STATES,
    InvocationState,
    SideEffectPolicy,
    SkillInvocationError,
    SkillInvocationRequest,
    SkillInvocationSnapshot,
    canonical_json_bytes,
)
from .skill_invocation_repository import SkillInvocationRepository


class SkillInvocationAuthorization(Protocol):
    def require(self, scope: ScopeIdentity, action: str, identity: str) -> str: ...


class SkillSideEffectPolicyAuthority(Protocol):
    def evaluate(self, request: SkillInvocationRequest) -> SideEffectPolicy: ...


@dataclass(frozen=True, slots=True)
class ScopedSkillInvocationAuthorization:
    scope: ScopeIdentity
    actor_id: str
    permissions: frozenset[str]
    decision_id: str

    def require(self, scope: ScopeIdentity, action: str, identity: str) -> str:
        if (
            scope != self.scope
            or action not in self.permissions
            or not self.actor_id
            or not self.decision_id
            or not identity
        ):
            raise SkillInvocationError("SKILL_INVOCATION_NOT_FOUND")
        return self.decision_id


@dataclass(frozen=True, slots=True)
class FixedReadOnlyPolicyAuthority:
    policy: SideEffectPolicy

    def evaluate(self, request: SkillInvocationRequest) -> SideEffectPolicy:
        if request.side_effect_class != self.policy.allowed_class:
            raise SkillInvocationError("SKILL_SIDE_EFFECT_NOT_ALLOWED")
        return self.policy


class GovernedAttemptSkillInvocationService:
    """Formal backend application entry; no HTTP/product API is implied."""

    def __init__(
        self,
        repository: SkillInvocationRepository,
        authorization: SkillInvocationAuthorization | None,
        policy_authority: SkillSideEffectPolicyAuthority,
        executors: SkillExecutorRegistry,
        *,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.authorization = authorization
        self.policy_authority = policy_authority
        self.executors = executors
        self.clock = clock

    def _authorize(self, scope: ScopeIdentity, action: str, identity: str) -> str:
        if self.authorization is None:
            raise SkillInvocationError("SKILL_INVOCATION_NOT_FOUND")
        return self.authorization.require(scope, action, identity)

    def invoke(
        self, request: SkillInvocationRequest, inputs: dict[str, Any]
    ) -> SkillInvocationSnapshot:
        # Authorization precedes repository lookup and executor resolution.
        decision = self._authorize(request.scope, "INVOKE_SKILL", request.attempt_id)
        if decision != request.authorization_decision_id:
            raise SkillInvocationError("SKILL_AUTHORIZATION_DECISION_MISMATCH")
        policy = self.policy_authority.evaluate(request)
        if policy != request.policy:
            raise SkillInvocationError("SKILL_SIDE_EFFECT_POLICY_MISMATCH")
        encoded = canonical_json_bytes(inputs)
        if len(encoded) > request.io_limits.max_input_bytes:
            raise SkillInvocationError("SKILL_INPUT_TOO_LARGE")
        _validate_shape(
            inputs,
            request.io_limits.max_object_depth,
            request.io_limits.max_properties,
        )
        executor = self.executors.resolve(request.executor)
        payload_digest = request.payload_digest(inputs)
        started_at = self.clock()
        snapshot, created = self.repository.prepare_dispatch(
            request, inputs, payload_digest=payload_digest, now=started_at
        )
        if not created:
            return snapshot
        try:
            result = executor.invoke(
                request.invocation_id,
                request.operation,
                inputs,
                request.io_limits.timeout_ms,
            )
            encoded_output = canonical_json_bytes(result.output)
            if len(encoded_output) > request.io_limits.max_output_bytes:
                raise SkillExecutorFailure(
                    "SKILL_OUTPUT_TOO_LARGE", outcome_unknown=False
                )
            try:
                _validate_shape(
                    result.output,
                    request.io_limits.max_object_depth,
                    request.io_limits.max_properties,
                )
            except SkillInvocationError as exc:
                raise SkillExecutorFailure(str(exc), outcome_unknown=False) from exc
            return self.repository.commit_terminal(
                request,
                state=InvocationState.SUCCEEDED,
                output=result.output,
                provider_observation_id=result.provider_observation_id,
                error_code=None,
                started_at=started_at,
                observed_at=self.clock(),
            )

        except SkillExecutorFailure as exc:
            return self.repository.commit_terminal(
                request,
                state=(
                    InvocationState.OUTCOME_UNKNOWN
                    if exc.outcome_unknown
                    else InvocationState.FAILED
                ),
                output=None,
                provider_observation_id=f"executor-error:{request.invocation_id}",
                error_code=str(exc),
                started_at=started_at,
                observed_at=self.clock(),
            )

    def recover(
        self, request: SkillInvocationRequest, inputs: dict[str, Any]
    ) -> SkillInvocationSnapshot:
        """Recover a durable dispatch without ever invoking the provider again."""
        decision = self._authorize(request.scope, "INVOKE_SKILL", request.attempt_id)
        if decision != request.authorization_decision_id:
            raise SkillInvocationError("SKILL_AUTHORIZATION_DECISION_MISMATCH")
        if self.policy_authority.evaluate(request) != request.policy:
            raise SkillInvocationError("SKILL_SIDE_EFFECT_POLICY_MISMATCH")
        now = self.clock()
        snapshot, created = self.repository.prepare_dispatch(
            request,
            inputs,
            payload_digest=request.payload_digest(inputs),
            now=now,
        )
        if created:
            raise SkillInvocationError("SKILL_RECOVERY_REQUIRES_DURABLE_DISPATCH")
        if snapshot.state in TERMINAL_STATES:
            return snapshot
        return self.repository.commit_terminal(
            request,
            state=InvocationState.OUTCOME_UNKNOWN,
            output=None,
            provider_observation_id=f"recovery:{request.invocation_id}",
            error_code="SKILL_RESULT_PENDING_CONFIRMATION",
            started_at=now,
            observed_at=self.clock(),
        )

    def read(self, scope: ScopeIdentity, invocation_id: str) -> dict[str, Any]:
        self._authorize(scope, "READ_SKILL_INVOCATION", invocation_id)
        value = self.repository.get_snapshot(scope, invocation_id)
        if value is None:
            raise SkillInvocationError("SKILL_INVOCATION_NOT_FOUND")
        return value.canonical_read_model()


def _validate_shape(value: Any, max_depth: int, max_properties: int) -> None:
    properties = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal properties
        if depth > max_depth:
            raise SkillInvocationError("SKILL_IO_DEPTH_EXCEEDED")
        if isinstance(item, dict):
            properties += len(item)
            if properties > max_properties:
                raise SkillInvocationError("SKILL_IO_PROPERTIES_EXCEEDED")
            for key, child in item.items():
                if not isinstance(key, str):
                    raise SkillInvocationError("SKILL_IO_KEY_INVALID")
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise SkillInvocationError("SKILL_IO_TYPE_INVALID")

    walk(value, 1)
