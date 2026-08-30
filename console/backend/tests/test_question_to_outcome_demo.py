"""S5-IMPL-040 question-first product-demo acceptance tests."""
# ruff: noqa: RUF001

from __future__ import annotations

import itertools
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.app import _create_supplier_quality_execution_authority
from agent_console.live_journey import LiveJourneyCoordinator, TrustedJourneyPrincipal
from agent_console.live_journey_stream import JourneyStreamScope
from agent_console.supplier_quality_demo import (
    NAMESPACE,
    SCENARIO_ID,
    SupplierQualityDemoFailure,
    SupplierQualityDemoService,
)
from agent_console.supplier_quality_demo_schemas import SupplierQualityDemoStartRequest

ROOT = Path(__file__).parents[3]
PACK = ROOT / "examples/s5-v0.2-supplier-quality"
NOW = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)
QUESTION = "某供应商近期交付质量持续下降，请分析原因，制定整改计划，并验证改善效果。"


@pytest.fixture
def subject(tmp_path: Path) -> SupplierQualityDemoService:
    target = tmp_path / NAMESPACE
    completed = subprocess.run(
        [
            str(PACK / "bootstrap.sh"),
            "--scenario",
            SCENARIO_ID,
            "--namespace",
            NAMESPACE,
            "--target-dir",
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    issued = itertools.count(1)
    return SupplierQualityDemoService(
        materialized_root=target,
        live_journeys=LiveJourneyCoordinator(),
        clock=lambda: NOW,
        opaque_id=lambda: f"question-issued-{next(issued)}",
        execution_authority_factory=_create_supplier_quality_execution_authority,
    )


@pytest.fixture
def principal() -> TrustedJourneyPrincipal:
    return TrustedJourneyPrincipal(
        "human:quality-reviewer", "tenant-a", "supplier-quality", True
    )


def request(question: str = QUESTION) -> SupplierQualityDemoStartRequest:
    return SupplierQualityDemoStartRequest(
        scenarioId=SCENARIO_ID,
        replayIdentity="question-first-start",
        locale="zh-CN",
        question=question,
    )


@pytest.mark.parametrize(
    "untrusted_principal",
    (
        TrustedJourneyPrincipal("", "", "", False),
        TrustedJourneyPrincipal(
            "human:quality-reviewer", "tenant-b", "supplier-quality", True
        ),
        TrustedJourneyPrincipal("human:quality-reviewer", "tenant-a", "finance", True),
    ),
)
def test_missing_or_wrong_trusted_demo_context_is_denied_before_all_downstream_work(
    subject: SupplierQualityDemoService,
    untrusted_principal: TrustedJourneyPrincipal,
) -> None:
    with pytest.raises(
        SupplierQualityDemoFailure, match="SUPPLIER_QUALITY_DEMO_ACCESS_DENIED"
    ):
        subject.start(request(), untrusted_principal)

    assert subject.counts.model_dump() == {
        "planningGenerator": 0,
        "matchingRequests": 0,
        "knowledgeSourceReads": 0,
        "placementEvaluations": 0,
        "coordinatorExecutions": 0,
        "nativeProviderInvocations": 0,
        "capabilityGatewayInvocations": 0,
        "fixtureExecutions": 0,
    }


def test_explicit_question_returns_reviewable_non_executing_equal_projection(
    subject: SupplierQualityDemoService, principal: TrustedJourneyPrincipal
) -> None:
    started = subject.start(request(), principal)
    revision = started.live.successor

    assert QUESTION in revision.objective
    assert "形成可审批、可验证的整改计划" in revision.objective
    assert "提交的问题仅使用经过脱敏的演示数据" in revision.understanding.assumptions
    assert revision.approvalState == "PENDING"
    assert revision.executionState == "NOT_REQUESTED"
    assert revision.identity.platformExecutionIdentity is None
    assert revision.identity.evidenceIds == []
    assert revision.answer is None and revision.outcome is None
    assert len(revision.projectedTasks) == 3
    assert revision.planTaskIds == [task.taskId for task in revision.projectedTasks]
    assert revision.projectedTasks[0].dependencies == []
    assert revision.projectedTasks[1].dependencies == [
        revision.projectedTasks[0].taskId
    ]
    assert revision.projectedTasks[2].dependencies == [
        revision.projectedTasks[1].taskId
    ]
    assert {task.definitionId for task in revision.projectedTasks} == {
        "definition.supplier-quality-analyst",
        "definition.quality-reviewer",
    }
    assert all(task.descriptorId for task in revision.projectedTasks)
    assert all(task.publicationState == "PUBLISHED" for task in revision.projectedTasks)
    assert all(
        task.matchAuthorization == "MATCHABLE" for task in revision.projectedTasks
    )
    assert all(task.publicationDecisionId for task in revision.projectedTasks)
    assert sum(len(task.skills) for task in revision.projectedTasks) == 6
    assert sum(len(task.mcpCapabilities) for task in revision.projectedTasks) == 3
    assert sum(len(task.knowledgeRefs) for task in revision.projectedTasks) == 3
    assert sum(len(task.runtimeRefs) for task in revision.projectedTasks) == 3
    tasks_by_agent = {
        definition_id: [
            task.taskId
            for task in revision.projectedTasks
            if task.definitionId == definition_id
        ]
        for definition_id in {task.definitionId for task in revision.projectedTasks}
    }
    assert sorted(map(len, tasks_by_agent.values())) == [1, 2]
    analyst_tasks = revision.projectedTasks[:2]
    shared_skills = set(analyst_tasks[0].skills) & set(analyst_tasks[1].skills)
    assert len(shared_skills) == 2
    assert all(len(task.skills) == 2 for task in analyst_tasks)
    assert not any(
        task.matchedRole in task.skills
        or task.title in task.mcpCapabilities
        or task.purpose in task.knowledgeRefs
        for task in revision.projectedTasks
    )
    assert QUESTION in revision.understanding.scope[0]
    assert QUESTION in revision.decomposition[0]
    assert QUESTION in revision.projectedTasks[0].purpose
    assert started.live.product.revision == started.live.technical.revision
    assert started.callCounts.coordinatorExecutions == 0
    assert started.callCounts.nativeProviderInvocations == 0
    assert subject.execution_evidence == ()


def test_correction_is_immutable_successor_and_execution_requires_exact_approval(
    subject: SupplierQualityDemoService, principal: TrustedJourneyPrincipal
) -> None:
    started = subject.start(request(), principal)
    original = started.live.successor
    corrected = subject.correct(
        started.journeyId,
        principal,
        predecessor_revision_id=original.identity.canonicalWorkflowRevisionId,
        predecessor_digest=original.identity.canonicalDigest,
        objective="供应商交付质量下降，请优先分析高严重度缺陷并制定整改计划。",
        reason_code="HUMAN_CORRECTION",
    )
    assert corrected.predecessor == original.model_copy(
        update={"lifecycle": "SUPERSEDED"}
    )
    assert corrected.successor.revision == 2
    assert corrected.successor.approvalState == "PENDING"
    assert subject.counts.coordinatorExecutions == 0

    approved = subject.approve(
        started.journeyId,
        principal,
        candidate_digest=corrected.successor.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="question-first-approval",
    )
    assert approved.successor.executionState == "NOT_REQUESTED"
    assert subject.counts.coordinatorExecutions == 0

    completed = subject.rerun(
        started.journeyId,
        principal,
        revision_id=approved.successor.identity.canonicalWorkflowRevisionId,
        digest=approved.successor.identity.canonicalDigest,
    )
    assert completed.successor.executionState == "SUCCEEDED"
    assert completed.successor.outcome is not None
    assert {task.state for task in completed.successor.projectedTasks} == {"SUCCEEDED"}
    assert completed.successor.planTaskIds == corrected.successor.planTaskIds
    assert [task.taskId for task in completed.successor.projectedTasks] == [
        task.taskId for task in corrected.successor.projectedTasks
    ]
    assert {record.evidence_record_id for record in subject.execution_evidence} < set(
        completed.successor.identity.evidenceIds
    )
    assert completed.successor.citations[0].retrievalEvidenceId in set(
        completed.successor.identity.evidenceIds
    )
    assert subject.counts.coordinatorExecutions == 3


def test_initial_draft_can_be_approved_then_explicitly_executed(
    subject: SupplierQualityDemoService, principal: TrustedJourneyPrincipal
) -> None:
    started = subject.start(request(), principal)
    draft = started.live.successor
    approved = subject.approve(
        started.journeyId,
        principal,
        candidate_digest=draft.identity.canonicalDigest,
        decision="APPROVE",
        reason_code="HUMAN_APPROVED",
        replay_identity="initial-question-approval",
    )
    completed = subject.rerun(
        started.journeyId,
        principal,
        revision_id=approved.successor.identity.canonicalWorkflowRevisionId,
        digest=approved.successor.identity.canonicalDigest,
    )
    assert completed.successor.executionState == "SUCCEEDED"
    assert completed.predecessor is None
    scope = JourneyStreamScope("tenant-a", "supplier-quality", started.journeyId)
    events = subject._live.event_source._buffers[scope.key].events
    assert [event.eventType for event in events] == [
        "JOURNEY_REGISTERED",
        "EXECUTION_AUTHORIZED",
        "EXECUTION_STARTED",
        "EXECUTION_SUCCEEDED",
    ]


def test_unsupported_question_has_zero_downstream_effects(
    subject: SupplierQualityDemoService, principal: TrustedJourneyPrincipal
) -> None:
    with pytest.raises(
        SupplierQualityDemoFailure, match="UNSUPPORTED_SUPPLIER_QUALITY_QUESTION"
    ):
        subject.start(request("请帮我规划下一季度的市场营销活动和预算。"), principal)
    assert subject.counts.coordinatorExecutions == 0
    assert subject.counts.nativeProviderInvocations == 0
    assert subject.execution_evidence == ()
