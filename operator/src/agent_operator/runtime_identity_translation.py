"""Strict translation from durable Placement identity to the Native seam."""

from dataclasses import dataclass

from agent_core.execution_contract import (
    AgentInstanceId,
    AttemptId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeInstanceId,
    ScopeIdentity,
    TaskRunId,
    WorkflowRunId,
)

__all__ = [
    "AgentInstanceId",
    "AttemptId",
    "PlacementDecision",
    "PlacementDecisionKind",
    "PlacementId",
    "PlacementRequest",
    "PlacementRequestId",
    "RuntimeIdentityTranslationError",
    "RuntimeInstanceId",
    "ScopeIdentity",
    "TaskRunId",
    "WorkflowRunId",
    "translate_native_identity",
]


class RuntimeIdentityTranslationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NativeRuntimeIdentity:
    scope: ScopeIdentity
    runtime_instance_id: RuntimeInstanceId
    placement_id: str
    attempt_id: str
    agent_instance_id: str


def translate_native_identity(
    request: PlacementRequest,
    decision: PlacementDecision,
    *,
    authorized_scope: ScopeIdentity,
) -> NativeRuntimeIdentity:
    """Consume authority exactly; never derive or remint Product identity."""
    if request.scope != authorized_scope:
        raise RuntimeIdentityTranslationError("PLACEMENT_SCOPE_MISMATCH")
    if decision.request_id != request.request_id:
        raise RuntimeIdentityTranslationError("PLACEMENT_REQUEST_MISMATCH")
    if decision.decision is not PlacementDecisionKind.PLACED:
        raise RuntimeIdentityTranslationError("PLACEMENT_NOT_AUTHORIZED")
    decision.verify_digest()
    if not isinstance(decision.runtime_instance_id, RuntimeInstanceId):
        raise RuntimeIdentityTranslationError("RUNTIME_INSTANCE_REQUIRED")
    return NativeRuntimeIdentity(
        scope=request.scope,
        runtime_instance_id=decision.runtime_instance_id,
        placement_id=str(decision.placement_id),
        attempt_id=str(request.attempt_id),
        agent_instance_id=str(request.agent_instance_id),
    )
