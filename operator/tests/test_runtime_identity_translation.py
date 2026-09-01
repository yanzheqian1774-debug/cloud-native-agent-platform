from datetime import UTC, datetime

import pytest
from agent_operator.runtime_identity_translation import (
    AgentInstanceId,
    AttemptId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeIdentityTranslationError,
    RuntimeInstanceId,
    ScopeIdentity,
    TaskRunId,
    WorkflowRunId,
    translate_native_identity,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)
SCOPE = ScopeIdentity("tenant-a", "domain-a")


def placement():
    request = PlacementRequest(
        PlacementRequestId("request-1"),
        SCOPE,
        WorkflowRunId("workflow-1"),
        TaskRunId("task-1"),
        AttemptId("attempt-1"),
        AgentInstanceId("agent-1"),
        "agent-revision-1",
        "runtime-profile-1",
        (),
        (),
        (),
        (),
        NOW,
    )
    decision = PlacementDecision.create(
        placement_id=PlacementId("placement-1"),
        request_id=request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=RuntimeInstanceId("runtime-product-1"),
        policy_version="policy-1",
        compatibility_facts=("NATIVE",),
        limitation_codes=(),
        decided_at=NOW,
    )
    return request, decision


def test_consumes_product_identity_without_reminting() -> None:
    request, decision = placement()
    translated = translate_native_identity(request, decision, authorized_scope=SCOPE)
    assert translated.runtime_instance_id is decision.runtime_instance_id
    assert translated.attempt_id == "attempt-1"


def test_scope_and_placement_authority_fail_closed() -> None:
    request, decision = placement()
    with pytest.raises(
        RuntimeIdentityTranslationError, match="PLACEMENT_SCOPE_MISMATCH"
    ):
        translate_native_identity(
            request, decision, authorized_scope=ScopeIdentity("other", "domain-a")
        )
    rejected = PlacementDecision.create(
        placement_id=PlacementId("placement-2"),
        request_id=request.request_id,
        decision=PlacementDecisionKind.REJECTED,
        runtime_instance_id=None,
        policy_version="policy-1",
        compatibility_facts=(),
        limitation_codes=("DENIED",),
        decided_at=NOW,
    )
    with pytest.raises(
        RuntimeIdentityTranslationError, match="PLACEMENT_NOT_AUTHORIZED"
    ):
        translate_native_identity(request, rejected, authorized_scope=SCOPE)
