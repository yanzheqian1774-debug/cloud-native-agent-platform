"""Governed, non-content persistence for pre-Problem draft assistance.

The module deliberately keeps raw user and provider content outside every stored
record.  Draft Assistance owns invocation metadata only; Model Governance,
Authority, Execution Resource Use, Evidence, and Business Problem remain separate
owners connected through narrow ports.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import hmac
import secrets
import struct
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from agent_console.authority_contracts import TrustedRequestContext
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ExactModelUse,
    ModelUseAction,
    ResolvedModelBinding,
)


class DraftAssistanceError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class DraftInvocationState(StrEnum):
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    REJECTED = "REJECTED"
    REQUESTED_AWAITING_CONTENT = "REQUESTED_AWAITING_CONTENT"
    REQUESTED = "REQUESTED"
    FAILED_PRE_DISPATCH = "FAILED_PRE_DISPATCH"
    DISPATCH_RECORDED = "DISPATCH_RECORDED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLATION_CONFIRMED = "CANCELLATION_CONFIRMED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED_BY_USER = "REJECTED_BY_USER"
    CONFLICT_REVIEW_REQUIRED = "CONFLICT_REVIEW_REQUIRED"


class DraftResultKind(StrEnum):
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    DRAFT_READY = "DRAFT_READY"


class AuthorizationState(StrEnum):
    PENDING = "PENDING"
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class ObservationState(StrEnum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    CANCELLATION_CONFIRMED = "CANCELLATION_CONFIRMED"


@dataclass(frozen=True, slots=True)
class DraftScope:
    namespace: str
    security_domain: str

    @classmethod
    def from_context(cls, context: TrustedRequestContext) -> DraftScope:
        return cls(context.scope.tenant_id, context.scope.security_domain)


@dataclass(frozen=True, slots=True)
class DraftAssistanceProfileRevision:
    profile_revision_id: str
    profile_digest: str
    scope: DraftScope
    binding: ExactModelBinding
    provider_id: str
    provider_revision_id: str
    provider_digest: str
    endpoint_id: str
    endpoint_revision_id: str
    endpoint_digest: str
    connection_profile_id: str
    connection_profile_revision_id: str
    connection_profile_digest: str
    adapter_id: str
    adapter_revision: str
    output_schema_version: str = "problem-draft-assistance-output.v1"
    target_format_version: str = "draft-assistance-target.v1"
    maximum_input_bytes: int = 16_384
    maximum_output_tokens: int = 1_024
    total_timeout_seconds: int = 75

    def __post_init__(self) -> None:
        values = (
            self.profile_revision_id,
            self.profile_digest,
            self.provider_id,
            self.provider_revision_id,
            self.provider_digest,
            self.endpoint_id,
            self.endpoint_revision_id,
            self.endpoint_digest,
            self.connection_profile_id,
            self.connection_profile_revision_id,
            self.connection_profile_digest,
            self.adapter_id,
            self.adapter_revision,
        )
        if any(not value or value.strip() != value for value in values):
            raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
        for digest in (
            self.profile_digest,
            self.provider_digest,
            self.endpoint_digest,
            self.connection_profile_digest,
            self.binding.digest,
        ):
            if len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest
            ):
                raise DraftAssistanceError("DRAFT_PROFILE_INVALID")
        if (
            self.maximum_input_bytes < 1
            or self.maximum_output_tokens < 1
            or self.total_timeout_seconds < 1
        ):
            raise DraftAssistanceError("DRAFT_PROFILE_INVALID")


@dataclass(frozen=True, slots=True)
class DraftBindingSnapshot:
    snapshot_id: str
    snapshot_digest: str
    profile_revision_id: str
    profile_digest: str
    model_binding: ExactModelBinding
    provider_id: str
    provider_revision_id: str
    provider_digest: str
    endpoint_id: str
    endpoint_revision_id: str
    endpoint_digest: str
    connection_profile_id: str
    connection_profile_revision_id: str
    connection_profile_digest: str
    adapter_id: str
    adapter_revision: str
    eligibility_high_water: int


@dataclass(frozen=True, slots=True)
class DraftAuthorization:
    state: AuthorizationState
    request_authorization_request_id: str
    model_authorization_request_id: str | None
    request_decision_id: str
    model_decision_id: str | None
    request_version: int
    model_version: int


@dataclass(frozen=True, slots=True)
class DispatchAdmission:
    admission_id: str
    fence: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderObservation:
    observation_id: str
    state: ObservationState
    correlation: str | None = None
    result_kind: DraftResultKind | None = None
    clarification_question: str | None = field(default=None, repr=False)
    title: str | None = field(default=None, repr=False)
    description: str | None = field(default=None, repr=False)
    reason_code: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    understanding: list[dict] | None = field(default=None, repr=False)
    measurement: dict | None = None
    local_cleanup: dict | None = None

    def __post_init__(self) -> None:
        if self.state is ObservationState.SUCCEEDED:
            if self.result_kind is DraftResultKind.NEEDS_CLARIFICATION:
                if not self.clarification_question or self.title or self.description:
                    raise DraftAssistanceError("OUTPUT_SCHEMA_INVALID")
            elif self.result_kind is DraftResultKind.DRAFT_READY:
                if (
                    not self.title
                    or not self.description
                    or self.clarification_question
                ):
                    raise DraftAssistanceError("OUTPUT_SCHEMA_INVALID")
            else:
                raise DraftAssistanceError("OUTPUT_SCHEMA_INVALID")


@dataclass(frozen=True, slots=True)
class ProviderBudgetQuote:
    input_token_upper_bound: int
    output_token_ceiling: int
    worst_case_cost_microusd: int

    def __post_init__(self) -> None:
        if (
            self.input_token_upper_bound < 1
            or self.output_token_ceiling < 1
            or self.worst_case_cost_microusd < 0
        ):
            raise DraftAssistanceError("PROVIDER_BUDGET_QUOTE_INVALID")


@dataclass(frozen=True, slots=True)
class PreparedProviderRequest:
    """Ephemeral provider request; its payload is never persisted or logged."""

    payload: object = field(repr=False)
    quote: ProviderBudgetQuote


@dataclass(frozen=True, slots=True)
class DraftInvocation:
    context_id: str
    turn_id: str
    turn_ordinal: int
    turn_version: int
    invocation_id: str
    snapshot_candidate_id: str
    scope: DraftScope
    initiating_principal_id: str
    scoped_idempotency_key: str
    commitment: str
    commitment_algorithm: str
    canonicalization_version: str
    pepper_reference: str
    pepper_version: str
    created_at: datetime
    replay_not_after: datetime
    profile_revision_id: str
    request_target: str
    model_target: str
    parent_turn_id: str | None = None
    predecessor_invocation_id: str | None = None
    state: DraftInvocationState = DraftInvocationState.AUTHORIZATION_PENDING
    aggregate_version: int = 1
    authorization: DraftAuthorization | None = None
    snapshot: DraftBindingSnapshot | None = None
    admission_id: str | None = None
    dispatch_fence: int | None = None
    budget_reservation_id: str | None = None
    provider_correlation: str | None = None
    measurement: dict | None = None
    pricing: dict | None = None
    settlement_status: str = "NOT_MEASURED"
    local_cleanup: dict | None = None
    terminal_observation_id: str | None = None
    last_observation_id: str | None = None
    result_kind: DraftResultKind | None = None
    reason_code: str | None = None
    owner_write_reason_code: str | None = None
    last_observation_state: ObservationState | None = None
    last_observation_latency_ms: int | None = None
    last_observation_input_tokens: int | None = None
    last_observation_output_tokens: int | None = None
    content_disposition: str = "CONTENT_NOT_RETAINED"
    resource_use_id: str | None = None
    evidence_id: str | None = None
    problem_id: str | None = None
    problem_revision_id: str | None = None
    problem_digest: str | None = None


@dataclass(frozen=True, slots=True)
class DraftResponse:
    invocation: DraftInvocation
    clarification_question: str | None = field(default=None, repr=False)
    title: str | None = field(default=None, repr=False)
    description: str | None = field(default=None, repr=False)
    synthetic: bool = True
    understanding: list[dict] | None = field(default=None, repr=False)


class DraftAssistanceRepository(Protocol):
    def claim(self, candidate: DraftInvocation) -> tuple[DraftInvocation, bool]: ...

    def get(self, scope: DraftScope, invocation_id: str) -> DraftInvocation | None: ...

    def get_by_key(
        self, scope: DraftScope, principal_id: str, key: str
    ) -> DraftInvocation | None: ...

    def find_by_target(
        self, scope: DraftScope, principal_id: str, target: str
    ) -> DraftInvocation | None: ...

    def get_context_head(
        self, scope: DraftScope, context_id: str
    ) -> DraftInvocation | None: ...

    def compare_and_set(
        self, expected_version: int, replacement: DraftInvocation
    ) -> DraftInvocation | None: ...


class DraftAuthorizationPort(Protocol):
    def resolve(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> DraftAuthorization: ...

    def can_read(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> bool: ...

    def validate_current_and_admit(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        snapshot: DraftBindingSnapshot,
    ) -> DispatchAdmission | None: ...

    def can_cancel(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> bool: ...


class DraftModelResolver(Protocol):
    def resolve_exact(
        self, profile: DraftAssistanceProfileRevision, exact_use: ExactModelUse
    ) -> ResolvedModelBinding: ...


class IdempotencyPepperResolver(Protocol):
    def active(self) -> tuple[str, str, bytes]: ...

    def resolve(self, reference: str, version: str) -> bytes | None: ...


class ProviderCredentialResolver(Protocol):
    def resolve(
        self, profile: DraftAssistanceProfileRevision, invocation_id: str
    ) -> object: ...


class DraftProviderTransport(Protocol):
    synthetic: bool

    def prepare(
        self,
        *,
        invocation_id: str,
        content: str,
        profile: DraftAssistanceProfileRevision,
    ) -> PreparedProviderRequest: ...

    def dispatch(
        self,
        *,
        invocation_id: str,
        request: PreparedProviderRequest,
        credential: object,
        profile: DraftAssistanceProfileRevision,
    ) -> ProviderObservation: ...

    def observe(self, correlation: str) -> ProviderObservation: ...

    def cancel(self, correlation: str) -> ProviderObservation: ...


class ProviderCallBudgetPort(Protocol):
    def reserve(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        quote: ProviderBudgetQuote,
    ) -> str: ...

    def record_usage(
        self,
        operation_id: str,
        reservation_id: str,
        observation: ProviderObservation,
    ) -> None: ...


class ContextualResourceUsePort(Protocol):
    def record_requested(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        snapshot: DraftBindingSnapshot,
    ) -> str: ...

    def record_observation(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        observation: ProviderObservation,
    ) -> None: ...

    def attach_evidence(
        self, operation_id: str, resource_use_id: str, evidence_id: str
    ) -> None: ...


class DraftEvidencePort(Protocol):
    def append(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        observation: ProviderObservation,
    ) -> str: ...


class InMemoryDraftAssistanceRepository:
    """Conformance adapter; PostgreSQL is the deployment authority."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[tuple[str, str, str], DraftInvocation] = {}
        self._claims: dict[tuple[str, str, str, str], str] = {}

    @staticmethod
    def _identity_parts(scope: DraftScope, invocation_id: str) -> tuple[str, str, str]:
        return scope.namespace, scope.security_domain, invocation_id

    @staticmethod
    def _claim_parts(
        scope: DraftScope, principal_id: str, key: str
    ) -> tuple[str, str, str, str]:
        return scope.namespace, scope.security_domain, principal_id, key

    def claim(self, candidate: DraftInvocation) -> tuple[DraftInvocation, bool]:
        with self._lock:
            claim = self._claim_parts(
                candidate.scope,
                candidate.initiating_principal_id,
                candidate.scoped_idempotency_key,
            )
            existing_id = self._claims.get(claim)
            if existing_id is not None:
                existing = self._records[
                    self._identity_parts(candidate.scope, existing_id)
                ]
                return existing, False
            self._claims[claim] = candidate.invocation_id
            self._records[
                self._identity_parts(candidate.scope, candidate.invocation_id)
            ] = candidate
            return candidate, True

    def get(self, scope: DraftScope, invocation_id: str) -> DraftInvocation | None:
        with self._lock:
            return self._records.get(self._identity_parts(scope, invocation_id))

    def get_by_key(
        self, scope: DraftScope, principal_id: str, key: str
    ) -> DraftInvocation | None:
        with self._lock:
            identity = self._claims.get(self._claim_parts(scope, principal_id, key))
            return None if identity is None else self.get(scope, identity)

    def find_by_target(
        self, scope: DraftScope, principal_id: str, target: str
    ) -> DraftInvocation | None:
        with self._lock:
            return next(
                (
                    value
                    for value in self._records.values()
                    if value.scope == scope
                    and value.initiating_principal_id == principal_id
                    and target
                    in {
                        value.request_target,
                        value.model_target,
                        f"draft-assistance:invocation:{value.invocation_id}",
                    }
                ),
                None,
            )

    def get_context_head(
        self, scope: DraftScope, context_id: str
    ) -> DraftInvocation | None:
        with self._lock:
            values = tuple(
                value
                for value in self._records.values()
                if value.scope == scope and value.context_id == context_id
            )
            return max(values, key=lambda value: value.turn_ordinal, default=None)

    def compare_and_set(
        self, expected_version: int, replacement: DraftInvocation
    ) -> DraftInvocation | None:
        with self._lock:
            identity = self._identity_parts(
                replacement.scope, replacement.invocation_id
            )
            current = self._records.get(identity)
            if current is None or current.aggregate_version != expected_version:
                return None
            if replacement.aggregate_version != expected_version + 1:
                raise DraftAssistanceError("DRAFT_VERSION_INVALID")
            self._records[identity] = replacement
            return replacement


class StaticPepperResolver:
    def __init__(self, reference: str, version: str, pepper: bytes) -> None:
        if len(pepper) < 32:
            raise DraftAssistanceError("IDEMPOTENCY_PEPPER_INVALID")
        self.reference = reference
        self.version = version
        self.pepper = pepper

    def active(self) -> tuple[str, str, bytes]:
        return self.reference, self.version, self.pepper

    def resolve(self, reference: str, version: str) -> bytes | None:
        if (reference, version) != (self.reference, self.version):
            return None
        return self.pepper


class DeterministicSyntheticDraftTransport:
    """Explicit synthetic-only adapter; it performs no network or provider call."""

    synthetic = True

    def __init__(self) -> None:
        self.dispatch_count = 0
        self.observations: dict[str, ProviderObservation] = {}

    def prepare(self, *, invocation_id, content, profile):
        del invocation_id
        from agent_console.draft_assistance_policy import legacy_content

        content = legacy_content(content)
        return PreparedProviderRequest(
            content,
            ProviderBudgetQuote(
                max(1, len(content.encode("utf-8"))),
                profile.maximum_output_tokens,
                0,
            ),
        )

    def dispatch(self, *, invocation_id, request, credential, profile):
        del credential, profile
        self.dispatch_count += 1
        correlation = f"synthetic:{invocation_id}"
        content = request.payload
        if not isinstance(content, str):
            raise DraftAssistanceError("PROVIDER_REQUEST_INVALID")
        normalized = content.strip()
        if "[UNKNOWN]" in normalized:
            observation = ProviderObservation(
                f"observation:{invocation_id}:unknown",
                ObservationState.UNKNOWN,
                correlation=correlation,
                reason_code="TRANSPORT_AMBIGUOUS",
            )
        elif "[FAIL]" in normalized:
            observation = ProviderObservation(
                f"observation:{invocation_id}:failed",
                ObservationState.FAILED,
                correlation=correlation,
                reason_code="PROVIDER_RESPONSE_INVALID",
            )
        elif (
            len(normalized) < 24
            or normalized.endswith("?")
            or normalized.endswith("？")
        ):
            observation = ProviderObservation(
                f"observation:{invocation_id}:clarification",
                ObservationState.SUCCEEDED,
                correlation=correlation,
                result_kind=DraftResultKind.NEEDS_CLARIFICATION,
                clarification_question="请补充期望结果、影响范围和判断完成的标准。",
                latency_ms=1,
            )
        else:
            title = normalized.split("。", 1)[0].split("\n", 1)[0][:48]
            observation = ProviderObservation(
                f"observation:{invocation_id}:draft",
                ObservationState.SUCCEEDED,
                correlation=correlation,
                result_kind=DraftResultKind.DRAFT_READY,
                title=title or "待确认的业务问题",
                description=normalized,
                latency_ms=1,
            )
        self.observations[correlation] = observation
        return observation

    def observe(self, correlation: str) -> ProviderObservation:
        return self.observations.get(
            correlation,
            ProviderObservation(
                f"observation:{correlation}:unknown",
                ObservationState.UNKNOWN,
                correlation=correlation,
                reason_code="PROVIDER_OBSERVATION_UNAVAILABLE",
            ),
        )

    def cancel(self, correlation: str) -> ProviderObservation:
        observation = ProviderObservation(
            f"observation:{correlation}:cancelled",
            ObservationState.CANCELLATION_CONFIRMED,
            correlation=correlation,
        )
        self.observations[correlation] = observation
        return observation


def draft_request_target(context_id: str, turn_id: str, version: int) -> str:
    return f"draft-assistance:context:{context_id}:turn:{turn_id}:version:{version}"


def draft_invocation_target(
    context_id: str,
    turn_id: str,
    invocation_id: str,
    snapshot_id: str,
    binding: ExactModelBinding,
) -> str:
    return (
        f"model:invocation:draft-assistance:{context_id}:{turn_id}:{invocation_id}:"
        f"{snapshot_id}:{binding.resource_id}:{binding.revision_id}:{binding.digest}"
    )


def _field(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _operation_id(kind: str, invocation_id: str, suffix: str) -> str:
    value = hashlib.sha256(f"{kind}\0{invocation_id}\0{suffix}".encode()).hexdigest()
    return f"{kind}:{value}"


class DraftAssistanceService:
    CANONICALIZATION_VERSION = "draft-assistance-canonical.v1"
    COMMITMENT_ALGORITHM = "HMAC-SHA-256"

    def __init__(
        self,
        repository: DraftAssistanceRepository,
        profile: DraftAssistanceProfileRevision,
        authorization: DraftAuthorizationPort,
        model_resolver: DraftModelResolver,
        peppers: IdempotencyPepperResolver,
        credentials: ProviderCredentialResolver,
        transport: DraftProviderTransport,
        resource_use: ContextualResourceUsePort,
        evidence: DraftEvidencePort,
        budget: ProviderCallBudgetPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        identity_factory: Callable[[str], str] = lambda prefix: (
            f"{prefix}:{secrets.token_hex(16)}"
        ),
        replay_window: timedelta = timedelta(hours=24),
    ) -> None:
        self.repository = repository
        self.profile = profile
        self.authorization = authorization
        self.model_resolver = model_resolver
        self.peppers = peppers
        self.credentials = credentials
        self.transport = transport
        self.resource_use = resource_use
        self.evidence = evidence
        self.budget = budget
        self.clock = clock
        self.identity_factory = identity_factory
        self.replay_window = replay_window

    def _canonical(
        self,
        context: TrustedRequestContext,
        key: str,
        content: str,
        parent_turn_id: str | None,
        expected_parent_version: int,
    ) -> bytes:
        values = (
            "PROBLEM_DRAFT_ASSISTANCE",
            self.CANONICALIZATION_VERSION,
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            "REQUEST_DRAFT_ASSISTANCE",
            key,
            "FIRST" if parent_turn_id is None else "EXISTING_TURN",
            parent_turn_id or "ABSENT",
            str(expected_parent_version),
            content,
        )
        return b"".join(_field(value) for value in values)

    def _commitment(
        self,
        context: TrustedRequestContext,
        key: str,
        content: str,
        parent_turn_id: str | None,
        expected_parent_version: int,
        pepper: bytes,
    ) -> str:
        return hmac.new(
            pepper,
            self._canonical(
                context, key, content, parent_turn_id, expected_parent_version
            ),
            hashlib.sha256,
        ).hexdigest()

    def _validate_content(self, key: str, content: str) -> None:
        if not key or len(key) > 128 or key.strip() != key:
            raise DraftAssistanceError("IDEMPOTENCY_KEY_INVALID")
        if (
            not content.strip()
            or len(content.encode()) > self.profile.maximum_input_bytes
        ):
            raise DraftAssistanceError("DRAFT_CONTENT_INVALID")

    def begin(
        self,
        context: TrustedRequestContext,
        *,
        key: str,
        content: str,
        parent_context_id: str | None = None,
        parent_turn_id: str | None = None,
        expected_parent_version: int = 0,
        predecessor_invocation_id: str | None = None,
    ) -> DraftResponse:
        self._validate_content(key, content)
        scope = DraftScope.from_context(context)
        if scope != self.profile.scope:
            raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
        existing = self.repository.get_by_key(scope, context.principal_id, key)
        if existing is not None:
            if not self.authorization.can_read(context, existing):
                raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
            self._verify_replay(context, existing, content)
            return self._resume(context, existing, content)
        if parent_turn_id is None:
            if (
                parent_context_id is not None
                or predecessor_invocation_id is not None
                or expected_parent_version != 0
            ):
                raise DraftAssistanceError("DRAFT_TURN_VERSION_CONFLICT")
        else:
            if parent_context_id is None or predecessor_invocation_id is None:
                raise DraftAssistanceError("DRAFT_TURN_VERSION_CONFLICT")
            head = self.repository.get_context_head(scope, parent_context_id)
            if (
                head is None
                or head.initiating_principal_id != context.principal_id
                or head.turn_id != parent_turn_id
                or head.turn_version != expected_parent_version
                or head.invocation_id != predecessor_invocation_id
            ):
                raise DraftAssistanceError("DRAFT_TURN_VERSION_CONFLICT")
        pepper_reference, pepper_version, pepper = self.peppers.active()
        now = self.clock()
        context_id = parent_context_id or self.identity_factory("draft-context")
        turn_id = self.identity_factory("draft-turn")
        invocation_id = self.identity_factory("draft-invocation")
        snapshot_id = self.identity_factory("draft-snapshot")
        commitment = self._commitment(
            context,
            key,
            content,
            parent_turn_id,
            expected_parent_version,
            pepper,
        )
        turn_version = expected_parent_version + 1
        candidate = DraftInvocation(
            context_id,
            turn_id,
            turn_version,
            turn_version,
            invocation_id,
            snapshot_id,
            scope,
            context.principal_id,
            key,
            commitment,
            self.COMMITMENT_ALGORITHM,
            self.CANONICALIZATION_VERSION,
            pepper_reference,
            pepper_version,
            now,
            now + self.replay_window,
            self.profile.profile_revision_id,
            draft_request_target(context_id, turn_id, turn_version),
            draft_invocation_target(
                context_id, turn_id, invocation_id, snapshot_id, self.profile.binding
            ),
            parent_turn_id,
            predecessor_invocation_id,
        )
        invocation, won = self.repository.claim(candidate)
        if not won:
            if not self.authorization.can_read(context, invocation):
                raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
            self._verify_replay(context, invocation, content)
            return self._resume(context, invocation, content)
        return self._authorize_and_dispatch(context, invocation, content)

    def _verify_replay(
        self, context: TrustedRequestContext, invocation: DraftInvocation, content: str
    ) -> None:
        now = self.clock()
        if now >= invocation.replay_not_after:
            raise DraftAssistanceError("IDEMPOTENCY_REPLAY_WINDOW_EXPIRED")
        pepper = self.peppers.resolve(
            invocation.pepper_reference, invocation.pepper_version
        )
        if pepper is None:
            raise DraftAssistanceError("IDEMPOTENCY_REPLAY_UNVERIFIABLE")
        candidate = self._commitment(
            context,
            invocation.scoped_idempotency_key,
            content,
            invocation.parent_turn_id,
            invocation.turn_version - 1,
            pepper,
        )
        if not hmac.compare_digest(candidate, invocation.commitment):
            raise DraftAssistanceError("IDEMPOTENCY_PAYLOAD_MISMATCH")

    def _replace(self, invocation: DraftInvocation, **changes) -> DraftInvocation:
        replacement = replace(
            invocation,
            aggregate_version=invocation.aggregate_version + 1,
            **changes,
        )
        saved = self.repository.compare_and_set(
            invocation.aggregate_version, replacement
        )
        if saved is None:
            current = self.repository.get(invocation.scope, invocation.invocation_id)
            if current is None:
                raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
            return current
        return saved

    def _authorize_and_dispatch(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        content: str,
    ) -> DraftResponse:
        decision = self.authorization.resolve(context, invocation)
        if decision.state is AuthorizationState.PENDING:
            current = self._replace(
                invocation,
                authorization=decision,
                state=DraftInvocationState.AUTHORIZATION_PENDING,
            )
            return DraftResponse(current, synthetic=self.transport.synthetic)
        if decision.state is AuthorizationState.DENIED:
            current = self._replace(
                invocation,
                authorization=decision,
                state=DraftInvocationState.REJECTED,
                reason_code="DRAFT_ASSISTANCE_AUTHORIZATION_DENIED",
            )
            return DraftResponse(current, synthetic=self.transport.synthetic)
        exact_use = ExactModelUse(
            self.profile.binding,
            ModelUseAction.INVOKE_MODEL,
            invocation.model_target,
        )
        try:
            resolved = self.model_resolver.resolve_exact(self.profile, exact_use)
        except Exception as exc:
            self._replace(
                invocation,
                authorization=decision,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="MODEL_BINDING_NOT_ELIGIBLE",
            )
            raise DraftAssistanceError("MODEL_BINDING_NOT_ELIGIBLE") from exc
        if (
            resolved.binding != self.profile.binding
            or resolved.provider.provider_id != self.profile.provider_id
            or resolved.provider.revision_id != self.profile.provider_revision_id
            or resolved.provider.digest != self.profile.provider_digest
            or resolved.endpoint.endpoint_id != self.profile.endpoint_id
            or resolved.endpoint.revision_id != self.profile.endpoint_revision_id
            or resolved.endpoint.digest != self.profile.endpoint_digest
            or resolved.connection_profile.profile_id
            != self.profile.connection_profile_id
            or resolved.connection_profile.revision_id
            != self.profile.connection_profile_revision_id
            or resolved.connection_profile.digest
            != self.profile.connection_profile_digest
            or not resolved.eligibility.allows_new_use
        ):
            self._replace(
                invocation,
                authorization=decision,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="MODEL_BINDING_MISMATCH",
            )
            raise DraftAssistanceError("MODEL_BINDING_MISMATCH")
        snapshot_semantic = (
            f"{invocation.snapshot_candidate_id}\0{self.profile.profile_revision_id}\0"
            f"{self.profile.profile_digest}\0{self.profile.binding.resource_id}\0"
            f"{self.profile.binding.revision_id}\0{self.profile.binding.digest}\0"
            f"{resolved.eligibility.high_water.ordinal}"
        ).encode()
        snapshot = DraftBindingSnapshot(
            invocation.snapshot_candidate_id,
            hashlib.sha256(snapshot_semantic).hexdigest(),
            self.profile.profile_revision_id,
            self.profile.profile_digest,
            self.profile.binding,
            self.profile.provider_id,
            self.profile.provider_revision_id,
            self.profile.provider_digest,
            self.profile.endpoint_id,
            self.profile.endpoint_revision_id,
            self.profile.endpoint_digest,
            self.profile.connection_profile_id,
            self.profile.connection_profile_revision_id,
            self.profile.connection_profile_digest,
            self.profile.adapter_id,
            self.profile.adapter_revision,
            resolved.eligibility.high_water.ordinal,
        )
        requested = self._replace(
            invocation,
            authorization=decision,
            snapshot=snapshot,
            state=DraftInvocationState.REQUESTED,
        )
        return self._dispatch(context, requested, content)

    def _resume(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        content: str,
    ) -> DraftResponse:
        if invocation.state is DraftInvocationState.AUTHORIZATION_PENDING:
            return self._authorize_and_dispatch(context, invocation, content)
        if invocation.state in {
            DraftInvocationState.REQUESTED,
            DraftInvocationState.REQUESTED_AWAITING_CONTENT,
        }:
            return self._dispatch(context, invocation, content)
        if invocation.owner_write_reason_code is not None:
            invocation = self._repair_owner_writes(invocation)
        return DraftResponse(invocation, synthetic=self.transport.synthetic)

    def _dispatch(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        content: str,
    ) -> DraftResponse:
        if invocation.snapshot is None:
            raise DraftAssistanceError("MODEL_BINDING_MISMATCH")
        try:
            prepared = self.transport.prepare(
                invocation_id=invocation.invocation_id,
                content=content,
                profile=self.profile,
            )
        except Exception as exc:
            self._replace(
                invocation,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="PROVIDER_REQUEST_INVALID",
            )
            if isinstance(exc, DraftAssistanceError):
                raise
            raise DraftAssistanceError("PROVIDER_REQUEST_INVALID") from exc
        try:
            resource_use_id = self.resource_use.record_requested(
                _operation_id("resource-use-requested", invocation.invocation_id, "v1"),
                invocation,
                invocation.snapshot,
            )
        except Exception as exc:
            self._replace(
                invocation,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="RESOURCE_USE_ADMISSION_FAILED",
            )
            raise DraftAssistanceError("RESOURCE_USE_ADMISSION_FAILED") from exc
        try:
            budget_reservation_id = self.budget.reserve(
                _operation_id(
                    "provider-budget-reservation", invocation.invocation_id, "v1"
                ),
                invocation,
                prepared.quote,
            )
        except Exception as exc:
            self._replace(
                invocation,
                resource_use_id=resource_use_id,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="PROVIDER_BUDGET_DENIED",
            )
            raise DraftAssistanceError("PROVIDER_BUDGET_DENIED") from exc
        admitted = self.authorization.validate_current_and_admit(
            context, invocation, invocation.snapshot
        )
        if admitted is None or admitted.expires_at <= self.clock():
            self._replace(
                invocation,
                resource_use_id=resource_use_id,
                budget_reservation_id=budget_reservation_id,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="DISPATCH_ADMISSION_DENIED",
            )
            raise DraftAssistanceError("DISPATCH_ADMISSION_DENIED")
        replacement = replace(
            invocation,
            aggregate_version=invocation.aggregate_version + 1,
            resource_use_id=resource_use_id,
            budget_reservation_id=budget_reservation_id,
            pricing=self.budget.pricing() if hasattr(self.budget, "pricing") else None,
            settlement_status="PENDING_RECONCILIATION"
            if hasattr(self.budget, "pricing")
            else "NOT_MEASURED",
            admission_id=admitted.admission_id,
            dispatch_fence=admitted.fence,
            state=DraftInvocationState.DISPATCH_RECORDED,
        )
        dispatch_recorded = self.repository.compare_and_set(
            invocation.aggregate_version, replacement
        )
        if dispatch_recorded is None:
            current = self.repository.get(invocation.scope, invocation.invocation_id)
            if current is None:
                raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
            return DraftResponse(current, synthetic=self.transport.synthetic)
        try:
            credential = self.credentials.resolve(
                self.profile, invocation.invocation_id
            )
        except Exception as exc:
            self._replace(
                dispatch_recorded,
                state=DraftInvocationState.FAILED_PRE_DISPATCH,
                reason_code="CREDENTIAL_RESOLUTION_FAILED",
            )
            raise DraftAssistanceError("CREDENTIAL_RESOLUTION_FAILED") from exc
        provider_entered = False
        try:
            from contextlib import nullcontext

            guard = getattr(self.budget, "dispatch_guard", None)
            context_guard = getattr(self.budget, "dispatch_context_guard", None)
            boundary = (
                context_guard(context, invocation, prepared.quote)
                if context_guard
                else guard(invocation, prepared.quote)
                if guard
                else nullcontext()
            )
            with boundary:
                provider_entered = True
                observation = self.transport.dispatch(
                    invocation_id=invocation.invocation_id,
                    request=prepared,
                    credential=credential,
                    profile=self.profile,
                )
        except Exception as exc:
            from .authority_contracts import AuthorityError

            if isinstance(exc, AuthorityError) and not provider_entered:
                self._replace(
                    dispatch_recorded,
                    state=DraftInvocationState.FAILED_PRE_DISPATCH,
                    reason_code="DISPATCH_ADMISSION_DENIED",
                )
                raise DraftAssistanceError("DISPATCH_ADMISSION_DENIED") from exc
            self._replace(
                dispatch_recorded,
                state=DraftInvocationState.OUTCOME_UNKNOWN,
                reason_code="TRANSPORT_AMBIGUOUS",
                local_cleanup=getattr(exc, "diagnostic", None),
            )
            raise DraftAssistanceError("TRANSPORT_AMBIGUOUS") from exc
        return self._record_observation(dispatch_recorded, observation)

    def _record_observation(
        self, invocation: DraftInvocation, observation: ProviderObservation
    ) -> DraftResponse:
        current = self.repository.get(invocation.scope, invocation.invocation_id)
        if (
            current is not None
            and current.aggregate_version != invocation.aggregate_version
            and current.state is DraftInvocationState.CANCELLATION_REQUESTED
        ):
            invocation = current
            if observation.state is ObservationState.SUCCEEDED:
                # Preserve billable usage without accepting a stale business success.
                observation = replace(
                    observation,
                    state=ObservationState.UNKNOWN,
                    result_kind=None,
                    clarification_question=None,
                    title=None,
                    description=None,
                    understanding=None,
                    reason_code="LATE_RESULT_AFTER_CANCEL_REQUEST",
                )
        state_map = {
            ObservationState.ACCEPTED: DraftInvocationState.ACCEPTED,
            ObservationState.RUNNING: DraftInvocationState.RUNNING,
            ObservationState.SUCCEEDED: DraftInvocationState.SUCCEEDED,
            ObservationState.FAILED: DraftInvocationState.FAILED,
            ObservationState.UNKNOWN: DraftInvocationState.OUTCOME_UNKNOWN,
            ObservationState.CANCELLATION_CONFIRMED: (
                DraftInvocationState.CANCELLATION_CONFIRMED
            ),
        }
        projected_state = state_map[observation.state]
        if (
            invocation.state is DraftInvocationState.CANCELLATION_REQUESTED
            and observation.state
            in {
                ObservationState.ACCEPTED,
                ObservationState.RUNNING,
                ObservationState.UNKNOWN,
            }
        ):
            projected_state = DraftInvocationState.CANCELLATION_REQUESTED
        if invocation.last_observation_id == observation.observation_id:
            if invocation.state is projected_state:
                repaired = self._complete_observation_refs(invocation, observation)
                return DraftResponse(repaired, synthetic=self.transport.synthetic)
            conflicted = self._replace(
                invocation,
                state=DraftInvocationState.CONFLICT_REVIEW_REQUIRED,
                reason_code="OBSERVATION_ID_CONFLICT",
            )
            return DraftResponse(conflicted, synthetic=self.transport.synthetic)
        if invocation.terminal_observation_id:
            conflicted = self._replace(
                invocation,
                state=DraftInvocationState.CONFLICT_REVIEW_REQUIRED,
                reason_code="TERMINAL_CONFLICT",
            )
            return DraftResponse(conflicted, synthetic=self.transport.synthetic)
        updated = self._replace(
            invocation,
            state=projected_state,
            provider_correlation=observation.correlation,
            measurement=observation.measurement or invocation.measurement,
            local_cleanup=observation.local_cleanup or invocation.local_cleanup,
            last_observation_id=observation.observation_id,
            terminal_observation_id=(
                observation.observation_id
                if observation.state
                in {
                    ObservationState.SUCCEEDED,
                    ObservationState.FAILED,
                    ObservationState.CANCELLATION_CONFIRMED,
                }
                else None
            ),
            result_kind=observation.result_kind,
            reason_code=observation.reason_code,
            owner_write_reason_code=None,
            last_observation_state=observation.state,
            last_observation_latency_ms=observation.latency_ms,
            last_observation_input_tokens=observation.input_tokens,
            last_observation_output_tokens=observation.output_tokens,
        )
        updated = self._complete_observation_refs(updated, observation)
        return DraftResponse(
            updated,
            clarification_question=observation.clarification_question,
            understanding=observation.understanding,
            title=observation.title,
            description=observation.description,
            synthetic=self.transport.synthetic,
        )

    def _complete_observation_refs(
        self, invocation: DraftInvocation, observation: ProviderObservation
    ) -> DraftInvocation:
        updated = invocation
        pending_reason: str | None = None
        if invocation.budget_reservation_id is not None:
            try:
                if (
                    invocation.pricing is not None
                    and invocation.pricing != self.budget.pricing()
                ):
                    raise DraftAssistanceError("PROVIDER_PRICE_VERSION_CONFLICT")
                if observation.measurement is None or observation.measurement.get(
                    "settleable"
                ):
                    self.budget.record_usage(
                        _operation_id(
                            "provider-budget-usage",
                            invocation.invocation_id,
                            observation.observation_id,
                        ),
                        invocation.budget_reservation_id,
                        observation,
                    )
                if hasattr(self.budget, "read_settlement"):
                    status = self.budget.read_settlement(
                        invocation.budget_reservation_id
                    )["status"]
                    if status != updated.settlement_status:
                        updated = self._replace(updated, settlement_status=status)
            except Exception:
                pending_reason = "PROVIDER_BUDGET_SETTLEMENT_PENDING"
                if updated.settlement_status != "SETTLEMENT_WRITE_PENDING":
                    updated = self._replace(
                        updated, settlement_status="SETTLEMENT_WRITE_PENDING"
                    )
        try:
            self.resource_use.record_observation(
                _operation_id(
                    "resource-use-observation",
                    invocation.invocation_id,
                    observation.observation_id,
                ),
                invocation,
                observation,
            )
        except Exception:
            pending_reason = "RESOURCE_USE_COMPLETION_PENDING"
        try:
            evidence_id = self.evidence.append(
                _operation_id(
                    "model-evidence",
                    invocation.invocation_id,
                    observation.observation_id,
                ),
                invocation,
                observation,
            )
            if invocation.resource_use_id:
                self.resource_use.attach_evidence(
                    _operation_id(
                        "resource-use-evidence",
                        invocation.invocation_id,
                        evidence_id,
                    ),
                    invocation.resource_use_id,
                    evidence_id,
                )
            if invocation.evidence_id != evidence_id or pending_reason is not None:
                updated = self._replace(
                    updated,
                    evidence_id=evidence_id,
                    owner_write_reason_code=pending_reason,
                )
        except Exception:
            if updated.owner_write_reason_code != "EVIDENCE_APPEND_PENDING":
                updated = self._replace(
                    updated, owner_write_reason_code="EVIDENCE_APPEND_PENDING"
                )
        if (
            pending_reason is None
            and updated.evidence_id is not None
            and updated.owner_write_reason_code
            in {
                "RESOURCE_USE_COMPLETION_PENDING",
                "EVIDENCE_APPEND_PENDING",
                "PROVIDER_BUDGET_SETTLEMENT_PENDING",
            }
        ):
            updated = self._replace(updated, owner_write_reason_code=None)
        return updated

    @staticmethod
    def _persisted_observation(invocation: DraftInvocation) -> ProviderObservation:
        state = invocation.last_observation_state
        observation_id = invocation.last_observation_id
        if state is None or observation_id is None:
            raise DraftAssistanceError("OBSERVATION_RECOVERY_UNAVAILABLE")
        clarification = None
        title = None
        description = None
        if state is ObservationState.SUCCEEDED:
            if invocation.result_kind is DraftResultKind.NEEDS_CLARIFICATION:
                clarification = "CONTENT_NOT_RETAINED"
            elif invocation.result_kind is DraftResultKind.DRAFT_READY:
                title = description = "CONTENT_NOT_RETAINED"
        return ProviderObservation(
            observation_id,
            state,
            correlation=invocation.provider_correlation,
            measurement=invocation.measurement,
            local_cleanup=invocation.local_cleanup,
            result_kind=invocation.result_kind,
            clarification_question=clarification,
            title=title,
            description=description,
            reason_code=invocation.reason_code,
            latency_ms=invocation.last_observation_latency_ms,
            input_tokens=invocation.last_observation_input_tokens,
            output_tokens=invocation.last_observation_output_tokens,
        )

    def _repair_owner_writes(self, invocation: DraftInvocation) -> DraftInvocation:
        return self._complete_observation_refs(
            invocation, self._persisted_observation(invocation)
        )

    def read(self, context: TrustedRequestContext, invocation_id: str) -> DraftResponse:
        return read_authorized_invocation(
            self.repository,
            self.authorization,
            context,
            invocation_id,
            synthetic=self.transport.synthetic,
        )

    def read_usage(self, context, invocation_id):
        from .provider_usage import authorize, projection

        require = getattr(self.authorization, "require_usage", None)
        if require is None:
            raise DraftAssistanceError("PROVIDER_USAGE_NOT_FOUND")
        authorize(
            lambda *grant: require(context, *grant), "understanding", invocation_id
        )
        value = self.repository.get(
            DraftScope(context.scope.tenant_id, context.scope.security_domain),
            invocation_id,
        )
        if value is None:
            raise DraftAssistanceError("PROVIDER_USAGE_NOT_FOUND")
        settlement = {"status": "NOT_MEASURED", "reservation_retained": True}
        if value.budget_reservation_id and hasattr(self.budget, "read_settlement"):
            settlement = self.budget.read_settlement(value.budget_reservation_id)
        return projection(
            value.measurement,
            value.pricing,
            value.budget_reservation_id,
            settlement,
            local_cleanup=value.local_cleanup,
        )

    def observe(
        self, context: TrustedRequestContext, invocation_id: str
    ) -> DraftResponse:
        value = self.read(context, invocation_id).invocation
        if value.owner_write_reason_code is not None:
            repaired = self._repair_owner_writes(value)
            return DraftResponse(repaired, synthetic=self.transport.synthetic)
        if value.terminal_observation_id or not value.provider_correlation:
            return DraftResponse(value, synthetic=self.transport.synthetic)
        return self._record_observation(
            value, self.transport.observe(value.provider_correlation)
        )

    def cancel(
        self, context: TrustedRequestContext, invocation_id: str
    ) -> DraftResponse:
        value = self.read(context, invocation_id).invocation
        if not self.authorization.can_cancel(context, value):
            raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
        if value.state in {
            DraftInvocationState.AUTHORIZATION_PENDING,
            DraftInvocationState.REQUESTED_AWAITING_CONTENT,
            DraftInvocationState.REQUESTED,
        }:
            return DraftResponse(
                self._replace(value, state=DraftInvocationState.REJECTED_BY_USER),
                synthetic=self.transport.synthetic,
            )
        if value.state not in {
            DraftInvocationState.DISPATCH_RECORDED,
            DraftInvocationState.ACCEPTED,
            DraftInvocationState.RUNNING,
            DraftInvocationState.OUTCOME_UNKNOWN,
            DraftInvocationState.CANCELLATION_REQUESTED,
        }:
            raise DraftAssistanceError("DRAFT_STATE_CONFLICT")
        requested = self._replace(
            value, state=DraftInvocationState.CANCELLATION_REQUESTED
        )
        if not requested.provider_correlation:
            return DraftResponse(requested, synthetic=self.transport.synthetic)
        return self._record_observation(
            requested, self.transport.cancel(requested.provider_correlation)
        )

    def reject(
        self, context: TrustedRequestContext, invocation_id: str
    ) -> DraftResponse:
        value = self.read(context, invocation_id).invocation
        if value.state not in {
            DraftInvocationState.SUCCEEDED,
            DraftInvocationState.FAILED,
            DraftInvocationState.OUTCOME_UNKNOWN,
        }:
            raise DraftAssistanceError("DRAFT_STATE_CONFLICT")
        return DraftResponse(
            self._replace(value, state=DraftInvocationState.REJECTED_BY_USER),
            synthetic=self.transport.synthetic,
        )

    def link_problem(
        self,
        context: TrustedRequestContext,
        invocation_id: str,
        *,
        problem_id: str,
        problem_revision_id: str,
        problem_digest: str,
    ) -> DraftResponse:
        value = self.read(context, invocation_id).invocation
        if value.problem_id:
            if (
                value.problem_id,
                value.problem_revision_id,
                value.problem_digest,
            ) != (problem_id, problem_revision_id, problem_digest):
                raise DraftAssistanceError("DRAFT_PROBLEM_LINK_CONFLICT")
            return DraftResponse(value, synthetic=self.transport.synthetic)
        if value.state is not DraftInvocationState.SUCCEEDED:
            raise DraftAssistanceError("DRAFT_STATE_CONFLICT")
        return DraftResponse(
            self._replace(
                value,
                problem_id=problem_id,
                problem_revision_id=problem_revision_id,
                problem_digest=problem_digest,
            ),
            synthetic=self.transport.synthetic,
        )


def read_authorized_invocation(
    repository: DraftAssistanceRepository,
    authorization: DraftAuthorizationPort,
    context: TrustedRequestContext,
    invocation_id: str,
    *,
    synthetic: bool,
) -> DraftResponse:
    """Read persisted facts with the same exact authorization, without a transport."""
    value = repository.get(DraftScope.from_context(context), invocation_id)
    if value is None or not authorization.can_read(context, value):
        raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
    return DraftResponse(value, synthetic=synthetic)
