"""Server-side creation of inert Native dispatch intent.

This application performs exact readback and queues a PostgreSQL-owned command.
It never claims work and never calls Kubernetes, Runtime, or a provider.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from .authority_contracts import ExactGrant, TrustedRequestContext
from .execution_postgres import (
    AgentInstanceId,
    AppendDisposition,
    AttemptId,
    CommandId,
    Generation,
    NativeDispatchCommand,
    PlacementDecisionKind,
    PlacementId,
    RuntimeInstanceId,
    ScopeIdentity,
)


class NativeDispatchApplicationError(ValueError):
    """Stable fail-closed command rejection."""


@dataclass(frozen=True, slots=True)
class QueueNativeDispatch:
    scope: ScopeIdentity
    attempt_id: AttemptId
    placement_id: PlacementId
    approved_plan_digest: str
    runtime_generation: Generation
    agent_instance_id: AgentInstanceId
    context: TrustedRequestContext
    exact_grant: ExactGrant
    authority_generation: Generation
    recovery_epoch: Generation
    agent_name: str
    input_text: str
    timeout_seconds: int
    idempotency_key: str
    queued_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class QueueNativeDispatchResult:
    disposition: AppendDisposition
    command: NativeDispatchCommand


class NativeDispatchApplication:
    def __init__(self, execution_repository) -> None:
        self.repository = execution_repository

    @staticmethod
    def _command_id(command: QueueNativeDispatch) -> CommandId:
        if not command.idempotency_key or len(command.idempotency_key) > 200:
            raise NativeDispatchApplicationError("NATIVE_DISPATCH_IDEMPOTENCY_INVALID")
        semantic = "\0".join(
            (
                command.scope.namespace,
                command.scope.security_domain,
                str(command.attempt_id),
                str(command.placement_id),
                command.context.principal_id,
                command.idempotency_key,
            )
        )
        digest = hashlib.sha256(semantic.encode()).hexdigest()
        return CommandId(f"native-dispatch:{digest}")

    def queue(self, request: QueueNativeDispatch) -> QueueNativeDispatchResult:
        context_scope = request.context.scope
        if (
            context_scope.tenant_id != request.scope.namespace
            or context_scope.security_domain != request.scope.security_domain
            or not request.context.principal_id
            or not request.context.session_id_or_service_credential_id
        ):
            raise NativeDispatchApplicationError("NATIVE_DISPATCH_NOT_FOUND")
        identity = self.repository.get_attempt(request.scope, request.attempt_id)
        placement = self.repository.get(request.scope, request.placement_id)
        if (
            identity is None
            or placement is None
            or placement.decision is not PlacementDecisionKind.PLACED
            or placement.runtime_instance_id is None
            or str(identity.attempt.attempt_id) != str(request.attempt_id)
        ):
            raise NativeDispatchApplicationError("NATIVE_DISPATCH_NOT_FOUND")
        command = NativeDispatchCommand(
            command_id=self._command_id(request),
            scope=request.scope,
            attempt_id=request.attempt_id,
            assignment_id=self.repository.dispatch_assignment(
                request.scope, request.attempt_id, identity.assignment.assignment_id
            ),
            approved_plan_revision_id=(identity.workflow_run.approved_plan_revision_id),
            approved_plan_digest=request.approved_plan_digest,
            placement_id=request.placement_id,
            placement_digest=placement.digest,
            runtime_instance_id=RuntimeInstanceId(str(placement.runtime_instance_id)),
            runtime_generation=request.runtime_generation,
            agent_instance_id=request.agent_instance_id,
            principal_id=request.context.principal_id,
            credential_id=request.context.session_id_or_service_credential_id,
            authentication_source=request.context.authentication_source.value,
            authority_generation=request.authority_generation,
            recovery_epoch=request.recovery_epoch,
            authorization_owner=request.exact_grant.owner,
            authorization_action=request.exact_grant.action,
            authorization_resource=request.exact_grant.exact_resource,
            agent_name=request.agent_name,
            input_text=request.input_text,
            timeout_seconds=request.timeout_seconds,
            queued_at=(request.queued_at or datetime.now(UTC)),
        )
        disposition = self.repository.enqueue(command)
        exact = self.repository.get_dispatch(request.scope, command.command_id)
        if exact != command:
            raise NativeDispatchApplicationError("NATIVE_DISPATCH_READBACK_CONFLICT")
        return QueueNativeDispatchResult(disposition, exact)
