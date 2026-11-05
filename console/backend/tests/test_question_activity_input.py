# ruff: noqa: F401, F811 -- Isolated existing owner fixtures, not live data.

import pytest
from agent_console.plan_suggestion_invocation import PlanningRequest
from agent_console.question_activity_input import (
    QuestionActivityInput,
    QuestionActivityRequest,
    route_question,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from pydantic import ValidationError
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


def test_question_routes_only_unambiguous_readable_context_and_one_business_choice():
    contexts = [
        {"title": "销售区域变化诊断", "contextToken": "a" * 64},
        {"title": "供应商逾期交付分析", "contextToken": "b" * 64},
    ]
    assert route_question("销售哪些区域下降", contexts)[0] == contexts[0]
    assert route_question("哪些供应商交付逾期", contexts)[0] == contexts[1]
    selected, choices = route_question("请分析情况", contexts)
    assert selected is None and len(choices) == 2
    assert route_question("请分析情况", contexts, "b" * 64)[0] == contexts[1]
    with pytest.raises(WorkbenchOwnerError):
        route_question("请分析情况", contexts, "c" * 64)
    with pytest.raises(ValidationError):
        QuestionActivityRequest.model_validate(
            {
                "question": "销售情况",
                "idempotencyKey": "test",
                "planId": "fixed-old-plan",
            }
        )


def invoke(a, question):
    with a.repository.pool.connection() as c, c.transaction():
        authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
        return QuestionActivityInput(a.automation)(
            AuthorizedOwnerCall(
                "PREPARE_QUESTION_ACTIVITY_INPUT",
                a.subject,
                c,
                {"question": question, "idempotencyKey": "fresh-question-test"},
                {},
                {},
                (),
                authority,
                1,
                1,
            )
        )


def test_raw_question_creates_fresh_governed_request_without_predecessor_plan(
    automation,
):
    a = automation
    a.run()
    with a.repository.pool.connection() as c:
        p = a.automation.bound_app(
            type(
                "Call",
                (),
                {
                    "connection": c,
                    "authority": AuthorizedOwnerAuthority(
                        a.adapter, a.subject, c, 1, ()
                    ),
                },
            )()
        )
        title = p.current_input(
            a.e.principal, a.e.p.semantics.target.problem.resource_id, c
        )["title"]
        before = c.execute("SELECT count(*) n FROM workflow_planning.plans").fetchone()[
            "n"
        ]
    question = title + " 请列出变化与异常依据"
    result = invoke(a, question)
    assert result["state"] == "ACTIVITY_REQUEST_READY_FOR_GOVERNED_PLANNING", result
    request = PlanningRequest.model_validate(result["planningRequest"])
    assert request.answers[0] == question
    assert request.source_proposal is None and request.predecessor_invocation_id is None
    activity = result["activityRequirement"]
    assert activity["goal"] == question and activity["priorTaskGraphCopied"] is False
    assert "tasks" not in activity and "stages" not in activity
    assert (
        activity["sourceProvenance"]["usage"]
        == "SOURCE_COMMITMENT_ONLY_NO_TASK_GRAPH_COPIED"
    )
    assert result["modelCalls"] == 0 and result["executionStarted"] is False
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM workflow_planning.plans").fetchone()["n"]
            == before
        )
    assert (
        invoke(a, "采购流程当前活动怎么办")["state"]
        == "BLOCKED_PROCESS_CONTEXT_NOT_AVAILABLE"
    )
    assert (
        invoke(a, "自动下单并发送邮件")["state"]
        == "BLOCKED_ACTION_OUTSIDE_READONLY_CONTEXT"
    )
    assert invoke(a, "星际飞船维修")["planningRequest"] is None


def test_question_entry_keeps_existing_collection_authorization_gate():
    from types import SimpleNamespace

    from agent_console.resource_automation import operations

    dummy = SimpleNamespace(
        select_employee=lambda call: None, source_change=lambda call: None
    )
    operation = next(
        x for x in operations(dummy) if x.name == "PREPARE_QUESTION_ACTIVITY_INPUT"
    )
    assert len(operation.grant_builder(None, {}, {}, {})) == 1
