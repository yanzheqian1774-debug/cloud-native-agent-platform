from datetime import UTC, datetime

import pytest
from agent_core.execution_contract import (
    AgentInstanceId,
    AttemptId,
    Generation,
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
from agent_operator.openclaw_runtime_driver import (
    OpenClawDriverError,
    translate_openclaw_placement,
)
from agent_runtime.providers.openclaw.models import RuntimeMode, SessionAffinity

NOW = datetime(2026, 9, 2, tzinfo=UTC)
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
        "openclaw-profile-revision-1",
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
        runtime_instance_id=RuntimeInstanceId("runtime-1"),
        policy_version="policy-1",
        compatibility_facts=("OPENCLAW_2026.7.1-2",),
        limitation_codes=(),
        decided_at=NOW,
    )
    return request, decision


def test_consumes_exact_placement_and_never_remints_platform_identity() -> None:
    request, decision = placement()
    translated = translate_openclaw_placement(
        request,
        decision,
        authorized_scope=SCOPE,
        workflow_run_id="workflow-1",
        task_run_id="task-1",
        attempt_id="attempt-1",
        agent_instance_id="agent-1",
        generation=Generation(1),
        mode=RuntimeMode.STATELESS,
        session_affinity=SessionAffinity.NONE,
    )
    assert translated.binding.runtime_instance_id == str(decision.runtime_instance_id)
    assert translated.binding.placement_id == str(decision.placement_id)
    assert translated.linkage.attempt_id == str(request.attempt_id)


def test_scope_rejection_and_identity_conflict_fail_closed() -> None:
    request, decision = placement()
    values = dict(
        request=request,
        decision=decision,
        authorized_scope=SCOPE,
        workflow_run_id="workflow-1",
        task_run_id="task-1",
        attempt_id="attempt-1",
        agent_instance_id="agent-1",
        generation=Generation(1),
        mode=RuntimeMode.STATELESS,
        session_affinity=SessionAffinity.NONE,
    )
    with pytest.raises(OpenClawDriverError, match="PLACEMENT_SCOPE_MISMATCH"):
        translate_openclaw_placement(
            **{**values, "authorized_scope": ScopeIdentity("other", "domain-a")}
        )
    with pytest.raises(OpenClawDriverError, match="EXECUTION_IDENTITY_MISMATCH"):
        translate_openclaw_placement(**{**values, "attempt_id": "reminted-attempt"})
