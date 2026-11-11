# ruff: noqa: F401,F811 -- Existing isolated PostgreSQL owner fixtures.
"""Explicitly synthetic engineering proposals; never real model E2E acceptance."""

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.plan_suggestion_domain import FlexiblePlanSemantics, ProposalRevision
from agent_console.policy_plan_confirmation import PolicyPlanConfirmation
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_problem_resource_coverage import invoke
from test_resource_automation import automation


def pending_proposal(a, *, stale_criteria=False, referenced_optional=False):
    with a.repository.pool.connection() as c, c.transaction():
        app = a.automation.bound_app(
            type("Call", (), {"connection": c, "authority": a.adapter})()
        )
        with app.repository.transaction(
            a.e.scope, a.e.p.plan_id, authorized=True
        ) as cur:
            prior = app.repository.proposal(
                cur, a.e.scope, a.e.p.plan_id, a.e.p.plan_version
            )
            doc = prior.semantics.model_dump(mode="json")
            if stale_criteria:
                doc["target"]["criteria"]["revision_id"] = "stale-criteria-set"
            doc["title"] = "明确标注的隔离合成待匹配方案, 不是模型结果"
            for req in doc["requirements"]:
                req["selected"] = None
            prototype = dict(doc["requirements"][0])
            prototype.update(
                requirement_id="pending-skill",
                kind="SKILL",
                required=not referenced_optional,
                selected=None,
            )
            doc["requirements"].append(prototype)
            for task in doc["tasks"]:
                task["requirement_ids"].append("pending-skill")
            proposal = ProposalRevision(
                proposal_id=prior.proposal_id,
                revision=prior.revision + 1,
                predecessor_digest=prior.digest,
                invocation_id="isolated-engineering-only",
                semantics=FlexiblePlanSemantics.model_validate(doc),
            )
            app.repository.add_proposal(cur, a.e.scope, proposal)
    return proposal


def confirm(a, proposal, *, deny_source=False, **changes):
    with a.repository.pool.connection() as c, c.transaction():
        authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
        if deny_source:
            from agent_console.authority_contracts import AuthorityError

            real = authority

            class DenySource:
                def require(self, principal, owner, action, resource):
                    if owner == "KNOWLEDGE":
                        raise AuthorityError("ISOLATED_SOURCE_READ_DENIED")
                    return real.require(principal, owner, action, resource)

            authority = DenySource()
        payload = dict(
            problem=proposal.semantics.target.problem.model_dump(mode="json"),
            revision=proposal.revision,
            digest=proposal.digest,
            expectedPlanVersion=a.e.p.plan_version,
            idempotencyKey="isolated-policy-confirm",
        )
        payload.update(changes)
        call = AuthorizedOwnerCall(
            "CONFIRM_POLICY_PLAN",
            a.subject,
            c,
            payload,
            {"proposal_id": proposal.proposal_id},
            {},
            (),
            authority,
            1,
            1,
        )
        issuer = a.automation.authenticate(call.context)
        a.automation.decide(
            call,
            [
                ExactGrant(
                    "PLAN",
                    "READ",
                    "plan:prepared:" + a.policy.workScopes[0].problem.resource_id,
                )
            ],
            "isolated-entry-read",
            a.policy.workScopes[0],
            issuer,
        )
        return PolicyPlanConfirmation(a.automation)(call)


def test_synthetic_pending_confirmation_system_binding_preparation_and_recovery(
    automation,
):
    a = automation
    assert a.run()["state"] == "READY"
    add_compatible_candidate(a)
    proposal = pending_proposal(a)
    value = confirm(a, proposal)
    assert (
        value["confirmation"]["approval"]["actor_id"]
        == "service:resource-preparation-policy"
    )
    assert value["executionStarted"] is False
    assert confirm(a, proposal)["confirmation"] == value["confirmation"]
    with a.repository.pool.connection() as c, c.transaction():
        app = a.automation.bound_app(
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
        # Simulate the committed response being lost; recover using normal owner GET.
        recovered = app.read(
            a.e.principal,
            proposal.proposal_id,
            value["confirmation"]["plan"]["version"],
        )
        assert recovered["plan"] == value["confirmation"]["plan"]
    plan = value["confirmation"]["plan"]
    a.e.p = a.e.p.model_copy(
        update={
            "plan_version": plan["version"],
            "plan_digest": value["confirmation"]["digest"],
            "semantics": proposal.semantics,
        }
    )
    report = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE")
    assert report["selection"] is not None, report
    assert (
        len(
            [
                c
                for c in report["candidates"]
                if c["state"] == "SELECTABLE_FOR_VERIFICATION"
            ]
        )
        == 2
    )
    chosen = invoke(a, "SELECT_PROBLEM_RESOURCES")
    assert chosen["newRuns"] == 0
    resolved = chosen["confirmation"]["plan"]
    assert all(
        r["selected"] for r in resolved["semantics"]["requirements"] if r["required"]
    )
    assert (
        a.run(key="pending-resources", version=resolved["version"])["state"] == "READY"
    )
    assert invoke(a, "READ_PROBLEM_RESOURCE_SELECTION") == chosen
    assert invoke(a, "SELECT_PROBLEM_RESOURCES") == chosen


def add_compatible_candidate(a):
    from dataclasses import replace

    from agent_console.digital_employee_definition import EmployeeRevision

    original = next(
        r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
    )
    with a.repository.pool.connection() as c, c.transaction():
        repo = a.automation.employees
        data = repo._read(c, a.e.scope, original.resource_id, original.revision_id)
        revision = replace(
            EmployeeRevision.from_record(data["revision"]),
            definition_id="employee-definition:zz-compatible",
            revision_id="employee-revision:zz-compatible",
        )
        value = repo.create_for_workbench(
            c,
            revision,
            expected_version=0,
            decision_id="explicit-isolated-candidate-fixture",
            command_id="second-create",
            authorized=True,
        )
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            value = repo.decide_for_workbench(
                c,
                a.e.scope,
                revision.definition_id,
                revision.revision_id,
                revision.digest,
                action,
                expected_version=value["aggregateVersion"],
                decision_id="explicit-isolated-candidate-fixture",
                command_id="second-" + action,
                authorized=True,
            )
        call = AuthorizedOwnerCall(
            "FIXTURE_CANDIDATE_READ",
            a.subject,
            c,
            {},
            {},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        a.automation.decide(
            call,
            [
                ExactGrant(
                    "EMPLOYEE",
                    "READ",
                    f"employee:{revision.definition_id}:{revision.revision_id}",
                )
            ],
            "second-visible",
            a.policy.workScopes[0],
            a.automation.authenticate(a.subject),
        )


@pytest.mark.parametrize("failure", ["digest", "version", "criteria"])
def test_policy_confirmation_rejects_conflicting_digest_or_head(automation, failure):
    from agent_console.plan_suggestion_domain import PlanningError
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError

    a = automation
    a.run()
    proposal = pending_proposal(a, stale_criteria=failure == "criteria")
    changes = (
        {"digest": "0" * 64}
        if failure == "digest"
        else {"expectedPlanVersion": 999}
        if failure == "version"
        else {}
    )
    with pytest.raises((PlanningError, WorkbenchOwnerError)):
        confirm(a, proposal, **changes)
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT max(version) n FROM workflow_planning.plans").fetchone()[
                "n"
            ]
            == a.e.p.plan_version
        )


def test_policy_confirmation_does_not_elevate_unreadable_source(automation):
    from agent_console.authority_contracts import AuthorityError

    a = automation
    a.run()
    proposal = pending_proposal(a)
    with pytest.raises(AuthorityError, match="ISOLATED_SOURCE_READ_DENIED"):
        confirm(a, proposal, deny_source=True)
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT max(version) n FROM workflow_planning.plans").fetchone()[
                "n"
            ]
            == a.e.p.plan_version
        )


@pytest.mark.parametrize("mismatch", ["employee", "business_resources"])
def test_capability_selection_rejects_substitution_before_successor(
    automation, monkeypatch, mismatch
):
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError

    a = automation
    assert a.run()["state"] == "READY"
    report = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE")
    employee = report["selection"]
    if mismatch == "employee":
        employee = {**employee, "revision_id": "different-fixed-revision"}
    # Source provenance itself is covered separately; this controlled adapter
    # exercises the actual PostgreSQL selection owner before successor writes.
    monkeypatch.setattr(
        "agent_console.resource_preparation_plan.validate_source",
        lambda *args: {
            "contract": {"bindings": [{"kind": "EMPLOYEE", "reference": employee}]}
        },
    )
    with a.repository.pool.connection() as c:
        before = c.execute(
            "SELECT count(*) n FROM workflow_planning.proposals"
        ).fetchone()["n"]
    expected = (
        "EMPLOYEE_MISMATCH"
        if mismatch == "employee"
        else "UNDECLARED_BUSINESS_RESOURCE"
    )
    with pytest.raises(WorkbenchOwnerError, match=expected):
        invoke(a, "SELECT_PROBLEM_RESOURCES", key="fixed-capability-reject")
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM workflow_planning.proposals").fetchone()[
                "n"
            ]
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM "
                "execution_authority.resource_policy_plan_commands"
            ).fetchone()["n"]
            == 0
        )
