"""Owner-separated deterministic adapters for Draft Assistance acceptance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from agent_console.authority_contracts import TrustedRequestContext
from agent_console.draft_assistance import (
    AuthorizationState,
    DispatchAdmission,
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftAuthorization,
    DraftBindingSnapshot,
    DraftInvocation,
    ProviderObservation,
)
from agent_console.model_binding_resolution import ExactModelUse, ResolvedModelBinding


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class StaticDraftAuthorization:
    """Deterministic authority adapter used only by tests and synthetic fixtures."""

    def __init__(
        self,
        *,
        state: AuthorizationState = AuthorizationState.ALLOWED,
        readable: bool = True,
        cancellable: bool = True,
        admitted: bool = True,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self.state = state
        self.readable = readable
        self.cancellable = cancellable
        self.admitted = admitted
        self.clock = clock
        self.resolve_count = 0
        self.admission_count = 0

    def resolve(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> DraftAuthorization:
        del context
        self.resolve_count += 1
        suffix = _digest(
            [invocation.request_target, invocation.model_target, self.state.value]
        )
        return DraftAuthorization(
            self.state,
            f"request:{suffix}",
            f"model-request:{suffix}",
            f"request-decision:{suffix}",
            f"model-decision:{suffix}",
            1,
            1,
        )

    def can_read(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> bool:
        return (
            self.readable
            and context.principal_id == invocation.initiating_principal_id
            and context.scope.tenant_id == invocation.scope.namespace
            and context.scope.security_domain == invocation.scope.security_domain
        )

    def validate_current_and_admit(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        snapshot: DraftBindingSnapshot,
    ) -> DispatchAdmission | None:
        self.admission_count += 1
        if not self.admitted or not self.can_read(context, invocation):
            return None
        admission_digest = _digest([invocation.invocation_id, snapshot.snapshot_digest])
        return DispatchAdmission(
            f"dispatch-admission:{admission_digest}",
            self.admission_count,
            self.clock() + timedelta(seconds=30),
        )

    def can_cancel(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> bool:
        return self.cancellable and self.can_read(context, invocation)


class ExactProfileModelResolver:
    def __init__(self, resolved: ResolvedModelBinding) -> None:
        self.resolved = resolved
        self.calls = 0

    def resolve_exact(
        self, profile: DraftAssistanceProfileRevision, exact_use: ExactModelUse
    ) -> ResolvedModelBinding:
        self.calls += 1
        if exact_use.binding != profile.binding:
            raise DraftAssistanceError("MODEL_BINDING_MISMATCH")
        return self.resolved


class OpaqueSyntheticCredentialResolver:
    """Returns a sealed sentinel, never a credential string or environment value."""

    def __init__(self) -> None:
        self.calls = 0

    def resolve(
        self, profile: DraftAssistanceProfileRevision, invocation_id: str
    ) -> object:
        del profile, invocation_id
        self.calls += 1
        return object()


@dataclass(frozen=True, slots=True)
class ContextualResourceUseRecord:
    resource_use_id: str
    context_kind: str
    context_id: str
    resource_kind: str
    binding_snapshot_id: str
    status: str
    evidence_id: str | None = None


class InMemoryContextualResourceUseOwner:
    """Execution-owned non-Attempt sibling with operation-id idempotency."""

    def __init__(self) -> None:
        self.operations: dict[str, tuple[str, object]] = {}
        self.records: dict[str, ContextualResourceUseRecord] = {}

    def _once(self, operation_id: str, kind: str, payload: object) -> bool:
        existing = self.operations.get(operation_id)
        if existing is None:
            self.operations[operation_id] = (kind, payload)
            return True
        if existing != (kind, payload):
            raise DraftAssistanceError("RESOURCE_USE_OPERATION_CONFLICT")
        return False

    def record_requested(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        snapshot: DraftBindingSnapshot,
    ) -> str:
        resource_use_id = f"contextual-resource-use:{invocation.invocation_id}"
        payload = (
            invocation.scope,
            invocation.invocation_id,
            snapshot.snapshot_id,
            snapshot.snapshot_digest,
        )
        if self._once(operation_id, "REQUESTED", payload):
            self.records[resource_use_id] = ContextualResourceUseRecord(
                resource_use_id,
                "DRAFT_ASSISTANCE_INVOCATION",
                invocation.invocation_id,
                "MODEL",
                snapshot.snapshot_id,
                "REQUESTED",
            )
        return resource_use_id

    def record_observation(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        observation: ProviderObservation,
    ) -> None:
        payload = (
            invocation.invocation_id,
            observation.observation_id,
            observation.state,
        )
        if not self._once(operation_id, "OBSERVATION", payload):
            return
        if invocation.resource_use_id is None:
            raise DraftAssistanceError("RESOURCE_USE_NOT_FOUND")
        current = self.records[invocation.resource_use_id]
        self.records[invocation.resource_use_id] = ContextualResourceUseRecord(
            current.resource_use_id,
            current.context_kind,
            current.context_id,
            current.resource_kind,
            current.binding_snapshot_id,
            observation.state.value,
            current.evidence_id,
        )

    def attach_evidence(
        self, operation_id: str, resource_use_id: str, evidence_id: str
    ) -> None:
        if not self._once(operation_id, "EVIDENCE", (resource_use_id, evidence_id)):
            return
        current = self.records[resource_use_id]
        self.records[resource_use_id] = ContextualResourceUseRecord(
            current.resource_use_id,
            current.context_kind,
            current.context_id,
            current.resource_kind,
            current.binding_snapshot_id,
            current.status,
            evidence_id,
        )


@dataclass(frozen=True, slots=True)
class ModelDraftEvidence:
    evidence_id: str
    schema_version: str
    invocation_id: str
    binding_snapshot_id: str
    resource_use_id: str | None
    observation_id: str
    status: str
    provider_correlation: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    limitation_code: str | None


class InMemoryDraftEvidenceOwner:
    SCHEMA_VERSION = "model-draft-assistance-invocation-evidence.v1"

    def __init__(self) -> None:
        self.operations: dict[str, tuple[object, ModelDraftEvidence]] = {}

    def append(
        self,
        operation_id: str,
        invocation: DraftInvocation,
        observation: ProviderObservation,
    ) -> str:
        if invocation.snapshot is None:
            raise DraftAssistanceError("EVIDENCE_INPUT_INVALID")
        payload = (
            invocation.invocation_id,
            invocation.snapshot.snapshot_id,
            invocation.resource_use_id,
            observation.observation_id,
            observation.state.value,
            observation.correlation,
            observation.latency_ms,
            observation.input_tokens,
            observation.output_tokens,
            observation.reason_code,
        )
        existing = self.operations.get(operation_id)
        if existing is not None:
            if existing[0] != payload:
                raise DraftAssistanceError("EVIDENCE_OPERATION_CONFLICT")
            return existing[1].evidence_id
        evidence_id = f"model-evidence:{_digest(payload)}"
        evidence = ModelDraftEvidence(
            evidence_id,
            self.SCHEMA_VERSION,
            invocation.invocation_id,
            invocation.snapshot.snapshot_id,
            invocation.resource_use_id,
            observation.observation_id,
            observation.state.value,
            observation.correlation,
            observation.latency_ms,
            observation.input_tokens,
            observation.output_tokens,
            observation.reason_code,
        )
        self.operations[operation_id] = (payload, evidence)
        return evidence_id
