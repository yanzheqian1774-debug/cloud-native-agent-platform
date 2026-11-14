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


def test_question_ranks_readable_choices_without_implicitly_selecting_a_target():
    contexts = [
        {"title": "销售区域变化诊断", "contextToken": "a" * 64},
        {"title": "供应商逾期交付分析", "contextToken": "b" * 64},
    ]
    selected, choices = route_question("销售哪些区域下降", contexts)
    assert (
        selected is None and choices[0]["contextToken"] == contexts[0]["contextToken"]
    )
    selected, choices = route_question("哪些供应商交付逾期", contexts)
    assert (
        selected is None and choices[0]["contextToken"] == contexts[1]["contextToken"]
    )
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


def invoke(
    a,
    question,
    *,
    problem_id=None,
    deny_plan=None,
    extra_plan_reads=(),
    context_token=None,
):
    with a.repository.pool.connection() as c, c.transaction():
        authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
        original = authority

        class ScopedFixtureRead:
            def require(self, principal, owner, action, resource):
                from agent_console.authority_contracts import AuthorityError

                if owner == "PLAN" and action == "READ":
                    if resource == deny_plan:
                        raise AuthorityError("ISOLATED_PLAN_READ_DENIED")
                    if resource in extra_plan_reads:
                        return None
                return original.require(principal, owner, action, resource)

        authority = ScopedFixtureRead()
        return QuestionActivityInput(a.automation)(
            AuthorizedOwnerCall(
                "PREPARE_QUESTION_ACTIVITY_INPUT",
                a.subject,
                c,
                {
                    "question": question,
                    "idempotencyKey": "fresh-question-test",
                    **({"problemId": problem_id} if problem_id is not None else {}),
                    **(
                        {"contextToken": context_token}
                        if context_token is not None
                        else {}
                    ),
                },
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
    initial = invoke(a, question)
    assert initial["state"] == "NEEDS_BUSINESS_CONTEXT_CLARIFICATION"
    assert initial["planningRequest"] is None and initial["modelCalls"] == 0
    result = invoke(a, question, context_token=initial["choices"][0]["contextToken"])
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


@pytest.mark.parametrize("single_context", [False, True])
def test_inventory_overlap_never_selects_supplier_or_sales(single_context):
    contexts = [
        {"title": "供应商逾期交付分析", "contextToken": "a" * 64},
        {"title": "销售区域变化诊断", "contextToken": "b" * 64},
    ][: 1 if single_context else 2]
    selected, choices = route_question(
        "门店库存与补货诊断:采购提前期、逾期未到货、未来七天缺货风险", contexts
    )
    assert selected is None and len(choices) == len(contexts)


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


def test_current_problem_never_routes_to_a_readable_sibling_or_hidden_context(
    automation,
):
    a = automation
    a.run()
    root = a.e.p.semantics.target.problem.resource_id
    ready = invoke(a, "分析", problem_id=root)
    assert ready["state"] == "ACTIVITY_REQUEST_READY_FOR_GOVERNED_PLANNING"
    assert ready["planningRequest"]["target"]["problem"]["resource_id"] == root
    assert ready["contextRouting"] == "EXPLICIT_CURRENT_PROBLEM_REAUTHORIZED"
    with pytest.raises(WorkbenchOwnerError, match="STALE_OR_UNREADABLE"):
        invoke(a, "分析", problem_id=root, context_token="f" * 64)
    for result in (
        invoke(a, "销售固定合成分析", problem_id="unreadable-sales-problem"),
        invoke(a, "分析", problem_id=root, deny_plan="plan:v2:" + a.e.p.plan_id),
    ):
        assert result["state"] == "BLOCKED_NO_READABLE_CONTEXT"
        assert result["choices"] == [] and result["planningRequest"] is None
        assert result["modelCalls"] == 0


def test_source_commitment_uses_confirmation_time_not_foreign_plan_version(automation):
    from uuid import uuid4

    from agent_console.plan_suggestion_domain import ProposalRevision

    a = automation
    a.run()
    original_id = a.e.p.plan_id
    fresh_id = "isolated-new-plan:" + str(uuid4())
    with a.repository.pool.connection() as c, c.transaction():
        app = a.automation.bound_app(
            type("Call", (), {"connection": c, "authority": a.adapter})()
        )
        head = c.execute(
            "SELECT max(revision) n FROM workflow_planning.proposals "
            "WHERE proposal_id=%s",
            (original_id,),
        ).fetchone()["n"]
        for identity, versions in [
            (original_id, (head + 1, head + 2)),
            (fresh_id, (1,)),
        ]:
            with app.repository.transaction(
                a.e.scope, identity, authorized=True
            ) as cur:
                original = app.repository.proposal(cur, a.e.scope, original_id, head)
                for revision in versions:
                    previous = (
                        app.repository.proposal(cur, a.e.scope, identity, revision - 1)
                        if revision > 1
                        else None
                    )
                    proposal = ProposalRevision(
                        proposal_id=identity,
                        revision=revision,
                        predecessor_digest=previous.digest if previous else None,
                        invocation_id="isolated-source-ordering-only",
                        semantics=original.semantics,
                    )
                    app.repository.add_proposal(cur, a.e.scope, proposal)
                    app.repository.confirmation(
                        cur,
                        a.e.scope,
                        proposal,
                        actor="human:isolated",
                        key=identity + str(revision),
                        expected_plan_version=revision - 1,
                        authority_basis="ISOLATED_TEST_ONLY",
                    )
    root = a.e.p.semantics.target.problem.resource_id
    # Both are otherwise compatible; an older Plan's counter3 must not beat a
    # later confirmed Plan's counter1. Latest unreadable must not fall back.
    ready = invoke(
        a, "分析", problem_id=root, extra_plan_reads=("plan:v2:" + fresh_id,)
    )
    assert ready["activityRequirement"]["sourceProvenance"]["planId"] == fresh_id
    assert ready["activityRequirement"]["sourceProvenance"]["version"] == 1
    blocked = invoke(a, "分析", problem_id=root, deny_plan="plan:v2:" + fresh_id)
    assert blocked["state"] == "BLOCKED_NO_READABLE_CONTEXT"
    with a.repository.pool.connection() as c, c.transaction():
        app = a.automation.bound_app(
            type("Call", (), {"connection": c, "authority": a.adapter})()
        )
        with app.repository.transaction(a.e.scope, fresh_id, authorized=True) as cur:
            previous = app.repository.proposal(cur, a.e.scope, fresh_id, 1)
            expected = previous.semantics.target.expected_problem_version + 1
            target = previous.semantics.target.model_copy(
                update={"expected_problem_version": expected}
            )
            changed = ProposalRevision(
                proposal_id=fresh_id,
                revision=2,
                predecessor_digest=previous.digest,
                invocation_id="isolated-stale-target-only",
                semantics=previous.semantics.model_copy(update={"target": target}),
            )
            app.repository.add_proposal(cur, a.e.scope, changed)
            app.repository.confirmation(
                cur,
                a.e.scope,
                changed,
                actor="human:isolated",
                key="stale-target",
                expected_plan_version=1,
                authority_basis="ISOLATED_TEST_ONLY",
            )
    stale = invoke(
        a, "分析", problem_id=root, extra_plan_reads=("plan:v2:" + fresh_id,)
    )
    assert stale["state"] == "BLOCKED_NO_READABLE_CONTEXT"


def test_source_directory_entry_uses_owner_authorization_and_hides_unavailable_sources(
    automation,
):
    from contextlib import nullcontext

    from agent_console.resource_automation import operations

    a = automation
    a.adapter.controller.protected_request = lambda: nullcontext(a.gen)
    operation = next(
        op for op in operations(a.automation) if op.name == "READ_CONVERSATION_SOURCES"
    )
    grants = tuple(operation.grant_builder(a.subject, {}, {}, {}))
    assert grants
    from agent_console.authority_contracts import AuthorityError

    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        a.adapter.execute(
            a.subject,
            grants,
            operation=operation.name,
            payload={},
            path={},
            query={},
            handler=operation.handler,
        )


@pytest.mark.parametrize(
    "observation,operations,state,gaps",
    [
        ("READ_UNAVAILABLE", [], "BLOCKED_CAPABILITY_READ_UNAVAILABLE", False),
        (
            "UNVERIFIED",
            ["READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"],
            "BLOCKED_CAPABILITY_UNVERIFIED",
            False,
        ),
        (
            "NO_COMPATIBLE_VISIBLE_DECLARATIONS",
            [],
            "BLOCKED_MISSING_COMPATIBLE_TOOLS",
            True,
        ),
        (
            "AUTHORIZED_MEMBER_DECLARATIONS_OBSERVED",
            ["READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"],
            "ACTIVITY_REQUEST_READY_FOR_GOVERNED_PLANNING",
            False,
        ),
    ],
)
def test_preparation_preserves_observation_uncertainty(
    automation, monkeypatch, observation, operations, state, gaps
):
    import agent_console.question_activity_input as module

    a = automation
    a.run()
    monkeypatch.setattr(
        module,
        "observe",
        lambda *args: {
            "state": observation,
            "operations": [
                {"operation": op, "inputKinds": ["CONTEXT"], "outputKind": "CONTEXT"}
                for op in operations
            ],
            "coverageComplete": False,
        },
    )
    result = invoke(
        a, "检查原资料", problem_id=a.e.p.semantics.target.problem.resource_id
    )
    assert result["state"] == state
    assert ("gaps" in result) is gaps
    assert result["modelCalls"] == 0 and result["executionStarted"] is False
    assert result["originalQuestion"] == "检查原资料"
    assert (result["planningRequest"] is not None) == state.startswith(
        "ACTIVITY_REQUEST_READY"
    )
