"""Strict Placement-to-OpenClaw translation without Platform ID reminting."""

from dataclasses import dataclass

from agent_core.execution_contract import (
    Generation,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementRequest,
    RuntimeInstanceId,
    ScopeIdentity,
)
from agent_runtime.providers.openclaw.models import (
    ExecutionLinkage,
    RuntimeBinding,
    RuntimeMode,
    SessionAffinity,
)


class OpenClawDriverError(ValueError):
    """Stable sanitized translation error."""


@dataclass(frozen=True, slots=True)
class OpenClawPlacement:
    binding: RuntimeBinding
    linkage: ExecutionLinkage


def translate_openclaw_placement(
    request: PlacementRequest,
    decision: PlacementDecision,
    *,
    authorized_scope: ScopeIdentity,
    workflow_run_id: str,
    task_run_id: str,
    attempt_id: str,
    agent_instance_id: str,
    generation: Generation,
    mode: RuntimeMode,
    session_affinity: SessionAffinity,
    session_reference: str | None = None,
) -> OpenClawPlacement:
    """Consume the exact accepted Placement and its Platform-owned identities."""
    if request.scope != authorized_scope:
        raise OpenClawDriverError("PLACEMENT_SCOPE_MISMATCH")
    if decision.request_id != request.request_id:
        raise OpenClawDriverError("PLACEMENT_REQUEST_MISMATCH")
    if decision.decision is not PlacementDecisionKind.PLACED:
        raise OpenClawDriverError("PLACEMENT_NOT_AUTHORIZED")
    decision.verify_digest()
    if not isinstance(decision.runtime_instance_id, RuntimeInstanceId):
        raise OpenClawDriverError("RUNTIME_INSTANCE_REQUIRED")
    exact = (
        (workflow_run_id, str(request.workflow_run_id)),
        (task_run_id, str(request.task_run_id)),
        (attempt_id, str(request.attempt_id)),
        (agent_instance_id, str(request.agent_instance_id)),
    )
    if any(provided != authoritative for provided, authoritative in exact):
        raise OpenClawDriverError("EXECUTION_IDENTITY_MISMATCH")
    runtime_instance_id = str(decision.runtime_instance_id)
    placement_id = str(decision.placement_id)
    return OpenClawPlacement(
        binding=RuntimeBinding(
            namespace=request.scope.namespace,
            security_domain=request.scope.security_domain,
            runtime_instance_id=runtime_instance_id,
            placement_id=placement_id,
            generation=generation.value,
            mode=mode,
            session_affinity=session_affinity,
            session_reference=session_reference,
        ),
        linkage=ExecutionLinkage(
            workflow_run_id=workflow_run_id,
            task_run_id=task_run_id,
            attempt_id=attempt_id,
            agent_instance_id=agent_instance_id,
            runtime_instance_id=runtime_instance_id,
            placement_id=placement_id,
        ),
    )
