# ruff: noqa: RUF001
"""S5-IMPL-041 exact Problem-to-approved-plan authority tests."""

from __future__ import annotations

from itertools import pairwise

from agent_console.problems import (
    ProblemPlanningError,
    ProblemPlanningService,
    TrustedPrincipal,
)


class Model:
    provider_id = "controlled-test-provider"
    model = "controlled-planner-v1"
    embedding_model = "multilingual-embed-v1"

    def embed(self, texts):
        return [[float(index + 1), 1.0, 0.0, 0.0] for index, _ in enumerate(texts)]

    def propose(self, problem, context):
        return {
            "classification": "SUPPLIER_QUALITY",
            "summary": "验证原因并形成待审批整改计划",
            "needs_clarification": False,
            "tasks": [{"title": "执行整改", "purpose": "untrusted model proposal"}],
        }


class Vector:
    def __init__(self):
        self.points = []

    def rebuild(self, chunks, vectors):
        self.points = list(chunks)
        return "sha256:" + str(len(chunks)) * 64

    def query(self, vector, limit):
        return [
            {"score": 0.9 - index / 10, "payload": {"chunk_id": item["chunkId"]}}
            for index, item in enumerate(self.points)
        ]


def principal(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "security_domain": "supplier-quality",
        "principal_id": "human:manager",
    }
    values.update(overrides)
    return TrustedPrincipal(**values)


def create(service, include=False):
    return service.create(
        {
            "name": "供应商质量整改",
            "description": "某供应商近期交付质量持续下降，请分析原因，制定整改计划。",
            "includeNewKnowledge": include,
        },
        principal(),
    )


def test_problem_identity_plan_digest_stream_and_inert_boundary():
    service = ProblemPlanningService(Model(), Vector())
    problem = create(service)
    assert problem["problemId"].startswith("problem:")
    assert problem["revision"] == 1
    assert problem["status"] == "PLAN_REVIEW"
    revision = problem["planRevisions"][0]
    assert revision["canonicalDigest"].startswith("sha256:")
    assert revision["provenance"]["schemaValidation"] == "PASS"
    assert (
        revision["provenance"]["ruleValidation"]
        == "PASS_WITH_EXECUTION_BOUNDARY_ENFORCED"
    )
    assert all(task["lifecycle"] == "PLANNED" for task in revision["tasks"])
    assert not any(task["name"] == "执行整改" for task in revision["tasks"])
    assert [event["sequence"] for event in problem["events"]] == list(range(1, 15))
    assert problem["events"][2]["classification"] == "PARTIAL"
    assert problem["events"][-1]["eventType"] == "STREAM_COMPLETED"


def test_two_actual_runs_have_exact_knowledge_influence():
    service = ProblemPlanningService(Model(), Vector())
    run_a = create(service, False)
    run_b = create(service, True)
    assert len(run_a["knowledge"]["citations"]) == 1
    assert len(run_b["knowledge"]["citations"]) == 2
    assert len(run_a["planRevisions"][0]["tasks"]) == 3
    assert len(run_b["planRevisions"][0]["tasks"]) == 5
    assert all(
        item["influence"] == "INFLUENCED_PLAN"
        for item in run_b["knowledge"]["citations"]
    )
    assert (
        run_a["knowledge"]["indexManifestDigest"]
        != run_b["knowledge"]["indexManifestDigest"]
    )
    assert run_b["timings"]["totalMs"] >= 0
    assert set(run_b["timings"]) == {
        "problemAcceptanceMs",
        "retrievalMs",
        "controlledModelPlanningMs",
        "schemaAndRuleValidationMs",
        "comparisonAssemblyMs",
        "totalMs",
    }
    changed = run_b["planRevisions"][0]["tasks"][-1]
    assert "连续三批缺陷率低于百分之一" in changed["validationCriteria"]
    assert "quality-manager-escalation" in changed["approvalRequirements"]
    assert "连续三批效果数据" in changed["expectedEvidence"]


def test_correction_is_immutable_successor_and_stale_approval_is_rejected():
    service = ProblemPlanningService(Model(), Vector())
    problem = create(service)
    first = problem["planRevisions"][0]
    corrected = service.correct(
        problem["problemId"],
        {
            "predecessorDigest": first["canonicalDigest"],
            "summary": "Human 修订摘要",
            "reason": "补充验证门槛",
        },
        principal(),
    )
    second = corrected["planRevisions"][-1]
    assert len(corrected["planRevisions"]) == 2
    assert second["predecessorRevisionId"] == first["planRevisionId"]
    assert first["summary"] != second["summary"]
    try:
        service.approve(
            problem["problemId"],
            {
                "planRevisionId": first["planRevisionId"],
                "canonicalDigest": first["canonicalDigest"],
            },
            principal(),
        )
    except ProblemPlanningError as exc:
        assert exc.reason == "STALE_OR_SUPERSEDED_PLAN"
    else:
        raise AssertionError("stale revision approved")
    approved = service.approve(
        problem["problemId"],
        {
            "planRevisionId": second["planRevisionId"],
            "canonicalDigest": second["canonicalDigest"],
        },
        principal(),
    )
    assert approved["approval"]["canonicalDigest"] == second["canonicalDigest"]
    assert approved["approval"]["evidence"]["type"] == "HUMAN_PLAN_APPROVAL"
    assert approved["planRevisions"][-1]["approvalState"] == "APPROVED"
    assert approved["dispatchBoundary"]["state"] == "INERT"
    try:
        service.approve(
            problem["problemId"],
            {
                "planRevisionId": second["planRevisionId"],
                "canonicalDigest": second["canonicalDigest"],
            },
            principal(),
        )
    except ProblemPlanningError as exc:
        assert exc.reason == "PLAN_ALREADY_APPROVED"
    else:
        raise AssertionError("duplicate approval accepted")


def test_authorization_first_nondisclosure_and_restart_truthfulness():
    service = ProblemPlanningService(Model(), Vector())
    problem = create(service)
    assert problem["blueprints"][1]["state"] == "UNAVAILABLE_OR_DENIED"
    assert "不会披露资源身份和数量" in problem["blueprints"][1]["description"]
    try:
        service.get(problem["problemId"], principal(tenant_id="tenant-b"))
    except ProblemPlanningError as exc:
        assert (exc.reason, exc.status) == ("PROBLEM_NOT_FOUND", 404)
    else:
        raise AssertionError("cross-tenant disclosure")
    try:
        ProblemPlanningService(Model(), Vector()).get(problem["problemId"], principal())
    except ProblemPlanningError as exc:
        assert exc.reason == "PREVIEW_STATE_UNAVAILABLE_AFTER_RESTART"
    else:
        raise AssertionError("restart state fabricated")


def test_list_is_the_canonical_problem_plan_task_inventory():
    service = ProblemPlanningService(Model(), Vector())
    run_a = create(service, False)
    run_b = create(service, True)
    inventory = service.list(principal())
    assert [item["problemId"] for item in inventory] == [
        run_a["problemId"],
        run_b["problemId"],
    ]
    revision = inventory[-1]["planRevisions"][-1]
    assert revision["planRevisionId"] == run_b["currentPlanRevisionId"]
    assert [item["taskId"] for item in revision["tasks"]] == [
        item["taskId"] for item in run_b["planRevisions"][-1]["tasks"]
    ]
    for task in revision["tasks"]:
        assert task["agentRevision"]
        assert task["skillRevisions"]
        assert task["mcpRevisions"]
        assert task["knowledgeSnapshotId"] == revision["knowledgeSnapshotId"]
        assert task["runtimeRequirements"] == ["runtime:native:planning-only:v1"]


def test_governed_interventions_create_successors_events_and_exact_evidence():
    service = ProblemPlanningService(Model(), Vector())
    problem = create(service, True)
    first = problem["planRevisions"][-1]
    corrected = service.intervene(
        problem["problemId"],
        {
            "predecessorDigest": first["canonicalDigest"],
            "kind": "INTERPRETATION",
            "reason": "确认供应商范围和改善指标",
            "payload": {
                "supplierScope": "当前受控供应商",
                "timeRange": "最近三个月",
                "improvementIndicator": "连续三批缺陷率低于百分之一",
            },
        },
        principal(),
    )
    successor = corrected["planRevisions"][-1]
    assert successor["revision"] == 2
    assert successor["predecessorRevisionId"] == first["planRevisionId"]
    assert successor["canonicalDigest"] != first["canonicalDigest"]
    assert corrected["interpretations"][-1]["source"] == "HUMAN_CORRECTED"
    assert corrected["humanDecisions"][-1]["evidenceId"].startswith("evidence:")
    assert [item["eventType"] for item in corrected["events"][-3:]] == [
        "CLARIFICATION_SUBMITTED",
        "INTERPRETATION_CORRECTED",
        "PLAN_REVISION_CREATED",
    ]


def test_task_intervention_revalidates_dag_and_rejects_cycle():
    service = ProblemPlanningService(Model(), Vector())
    problem = create(service, True)
    current = problem["planRevisions"][-1]
    first, second = current["tasks"][:2]
    try:
        service.intervene(
            problem["problemId"],
            {
                "predecessorDigest": current["canonicalDigest"],
                "kind": "TASK",
                "reason": "验证循环保护",
                "payload": {
                    "taskId": first["taskId"],
                    "changes": {"dependencies": [second["taskId"]]},
                },
            },
            principal(),
        )
    except ProblemPlanningError as exc:
        assert exc.reason == "TASK_DAG_CYCLE"
    else:
        raise AssertionError("cyclic DAG accepted")
    assert len(problem["planRevisions"]) == 1


def test_display_codes_catalog_candidates_and_approval_event_are_stable():
    service = ProblemPlanningService(Model(), Vector())
    problem = create(service, True)
    revision = problem["planRevisions"][-1]
    assert problem["displayCode"] == "PRB-0001"
    assert revision["displayCode"] == "PLN-0001-R01"
    assert [task["displayCode"] for task in revision["tasks"]] == [
        f"TSK-{index:04d}" for index in range(1, 6)
    ]
    assert revision["tasks"][0]["candidateMatches"]["agentRevisions"] == [
        revision["tasks"][0]["agentRevision"]
    ]
    approved = service.approve(
        problem["problemId"],
        {
            "planRevisionId": revision["planRevisionId"],
            "canonicalDigest": revision["canonicalDigest"],
        },
        principal(),
    )
    assert approved["events"][-1]["eventType"] == "PLAN_APPROVED"


def test_real_analysis_stream_pauses_resumes_and_replays_without_duplicates():
    service = ProblemPlanningService(Model(), Vector())
    command = {
        "name": "供应商质量整改",
        "description": "某供应商近期交付质量持续下降，请分析原因，制定整改计划。",
        "includeNewKnowledge": True,
    }
    initial = list(service.begin_analysis(command, principal()))
    assert initial[0]["eventType"] == "PROBLEM_SUBMITTED"
    assert initial[-1]["eventType"] == "CLARIFICATION_REQUESTED"
    assert all(item["classification"] == "PARTIAL" for item in initial)
    stream_id = initial[0]["streamId"]
    resumed = list(
        service.resume_analysis(
            stream_id,
            {
                "supplierScope": "当前受控供应商",
                "timeRange": "最近三个月交付批次",
                "improvementIndicator": "连续三批缺陷率低于百分之一",
            },
            principal(),
        )
    )
    events = [*initial, *resumed]
    assert [item["sequence"] for item in events] == list(range(1, len(events) + 1))
    assert all(
        current["previousEventDigest"] == previous["eventDigest"]
        for previous, current in pairwise(events)
    )
    assert events[-1]["eventType"] == "PLAN_READY_FOR_HUMAN_REVIEW"
    assert events[-1]["terminal"] is True
    assert any(item["eventType"] == "TASK_PROPOSED" for item in resumed)
    assert any(item["eventType"] == "RESOURCE_MATCH_PROPOSED" for item in resumed)
    replay = service.replay_analysis(stream_id, initial[-1]["eventId"], principal())
    assert [item["eventId"] for item in replay] == [item["eventId"] for item in resumed]
    assert len({item["eventId"] for item in events}) == len(events)


def test_analysis_stream_restart_and_unknown_replay_are_truthful():
    service = ProblemPlanningService(Model(), Vector())
    initial = list(
        service.begin_analysis(
            {
                "description": "供应商质量下降",
                "includeNewKnowledge": True,
            },
            principal(),
        )
    )
    try:
        service.replay_analysis(initial[0]["streamId"], "event:unknown", principal())
    except ProblemPlanningError as exc:
        assert exc.reason == "ANALYSIS_RESUME_UNAVAILABLE"
    else:
        raise AssertionError("unknown replay position accepted")
    try:
        ProblemPlanningService(Model(), Vector()).replay_analysis(
            initial[0]["streamId"], None, principal()
        )
    except ProblemPlanningError as exc:
        assert exc.reason == "ANALYSIS_STREAM_UNAVAILABLE_AFTER_RESTART"
    else:
        raise AssertionError("restart fabricated analysis stream")
