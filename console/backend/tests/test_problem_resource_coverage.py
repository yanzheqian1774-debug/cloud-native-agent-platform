# ruff: noqa: F401, F811 -- Existing isolated PostgreSQL fixtures, never live DB.
"""Coverage and automatic choice use existing owners, no scenario candidate seed."""

import copy
from dataclasses import replace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.plan_suggestion_domain import ConfirmedPlanRevision
from agent_console.problem_resource_coverage import ProblemResourceCoverage, assess
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


def invoke(a, operation, *, key="auto-choice-1", digest=None, authority=None):
    with a.repository.pool.connection() as c, c.transaction():
        app = a.automation.bound_app(
            type("Call", (), {"connection": c, "authority": a.adapter})()
        )
        with app.repository.transaction(
            a.e.scope, a.e.p.plan_id, authorized=True
        ) as cur:
            value = app.repository.read_plan(
                cur, a.e.scope, a.e.p.plan_id, a.e.p.plan_version
            )
        plan = ConfirmedPlanRevision.model_validate(value["plan"])
        payload = {
            "version": plan.version,
            "digest": digest or plan.digest,
            "expectedProposalRevision": plan.source_proposal_revision,
            "idempotencyKey": key,
        }
        query = {
            "version": plan.version,
            **({"key": key} if operation == "READ_PROBLEM_RESOURCE_SELECTION" else {}),
        }
        call = AuthorizedOwnerCall(
            operation,
            a.subject,
            c,
            payload,
            {"proposal_id": plan.plan_id},
            query,
            (),
            authority or AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        return ProblemResourceCoverage(a.automation)(call)


def test_exact_coverage_auto_choice_and_committed_response_loss_readback(
    automation, monkeypatch
):
    a = automation
    assert a.run()["state"] == "READY"
    report = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE")
    assert report["state"] == "SELECTION_AVAILABLE", report
    assert report["executionReady"] is False
    assert len(report["gaps"]) == 6
    assert report["selection"]["resource_id"] == "employee-definition:d11-setup"
    selected = next(
        c for c in report["candidates"] if c["reference"] == report["selection"]
    )
    assert selected["checks"]["actualTests"] == "REQUIRED_IN_RESOURCE_PREPARATION"
    assert selected["compatibility"] == "EXACT_IO_AND_DEPENDENCY_CHECKED"
    result = invoke(a, "SELECT_PROBLEM_RESOURCES")
    assert result["automaticCoverage"]["selection"] == report["selection"]
    assert result["newRuns"] == 0
    with a.repository.pool.connection() as c:
        count = c.execute("SELECT count(*) n FROM workflow_planning.plans").fetchone()[
            "n"
        ]
    # Simulate a committed response never reaching its caller; GET must not scan
    # or reselect even if the directory is currently unavailable.
    monkeypatch.setattr(
        "agent_console.problem_resource_coverage.identities",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("recovery rescanned")
        ),
    )
    assert invoke(a, "READ_PROBLEM_RESOURCE_SELECTION") == result
    assert invoke(a, "SELECT_PROBLEM_RESOURCES") == result
    with a.repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM workflow_planning.plans").fetchone()["n"]
            == count
        )
    with pytest.raises(WorkbenchOwnerError, match="AUTOMATIC_SELECTION_KEY_CONFLICT"):
        invoke(a, "SELECT_PROBLEM_RESOURCES", digest="0" * 64)


def test_runtime_unavailable_and_hidden_candidates_never_selected(automation):
    a = automation
    assert a.run()["state"] == "READY"
    a.automation.runtime_probe = lambda scope: {"status": "FAILED"}
    report = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE")
    assert report["selection"] is None
    assert all(c["state"] == "REJECTED" for c in report["candidates"])
    with pytest.raises(
        WorkbenchOwnerError, match="AUTOMATIC_SELECTION_COVERAGE_BLOCKED"
    ):
        invoke(a, "SELECT_PROBLEM_RESOURCES")
    with pytest.raises(WorkbenchOwnerError, match="AUTOMATIC_SELECTION_NOT_FOUND"):
        invoke(a, "READ_PROBLEM_RESOURCE_SELECTION")
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM "
                "execution_authority.resource_policy_plan_commands"
            ).fetchone()["n"]
            == 0
        )

    class DenyEmployees:
        def require(self, principal, owner, action, target):
            if owner == "EMPLOYEE":
                raise AuthorityError("RESOURCE_NOT_READABLE")
            return a.adapter.authorize(principal, owner, action, target)

    # Existing target validation needs the real transaction-bound authority;
    # deny only the exact employee candidates after binding it.
    original = a.automation.bound_app

    def bound(call):
        if not isinstance(call, AuthorizedOwnerCall):
            return original(call)
        return original(
            replace(
                call,
                authority=AuthorizedOwnerAuthority(
                    a.adapter, a.subject, call.connection, 1, ()
                ),
            )
        )

    a.automation.bound_app = bound
    report = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE", authority=DenyEmployees())
    assert report["candidates"] == [] and report["selection"] is None
    assert "employee-definition:d11-setup" not in repr(report)


def test_member_contract_rejects_source_io_and_dependency_mismatch(automation):
    a = automation
    a.run()
    from agent_console.planning_candidates import read_published

    with a.repository.pool.connection() as c:
        from agent_console.plan_suggestion_domain import ExactReference

        ref = next(
            r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
        )
        employee, _ = read_published(c, a.e.scope, "EMPLOYEE", ref)
        contents = {}
        for m in employee["members"]:
            kind = "RUNTIME" if m["kind"] == "RUNTIME_PROFILE" else m["kind"]
            value, _ = read_published(
                c,
                a.e.scope,
                kind,
                ExactReference(
                    resource_id=m["resource_id"],
                    revision_id=m["revision_id"],
                    digest=m["digest"].removeprefix("sha256:"),
                ),
            )
            contents[kind.lower()] = value
    work = a.policy.workScopes[0]
    good = assess(
        a.e.p.semantics, employee["members"], contents, work, {"status": "PASSED"}
    )
    assert good["executionReady"] is False
    bad = copy.deepcopy(contents)
    bad["skill"]["operations"][0]["inputSchema"]["properties"]["schemaVersion"][
        "enum"
    ] = ["wrong-family.v1"]
    with pytest.raises(AuthorityError, match="RESOURCE_EXECUTOR_SCHEMA_MISMATCH"):
        assess(a.e.p.semantics, employee["members"], bad, work, {"status": "PASSED"})
    members = copy.deepcopy(employee["members"])
    next(m for m in members if m["kind"] == "KNOWLEDGE")["revision_id"] = (
        "other-revision"
    )
    with pytest.raises(ValueError, match="APPROVED_SOURCE_EXACT_VERSION_REQUIRED"):
        assess(a.e.p.semantics, members, contents, work, {"status": "PASSED"})


def test_recovery_rechecks_revoked_member_read_without_reselection(automation):
    from agent_console.authority_contracts import GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand
    from agent_console.workbench_prepared_resources import reference

    a = automation
    a.run()
    result = invoke(a, "SELECT_PROBLEM_RESOURCES")
    ref = a.refs["skill"]
    with a.repository.pool.connection() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants "
            "WHERE owner='SKILL' AND action='READ_RESOURCE' AND exact_resource=%s",
            (reference("skill", ref.resource_id, ref.revision_id),),
        ).fetchone()["grant_id"]
    a.automation.grants.revoke_grant(
        a.subject,
        GrantRevocationCommand(
            GrantId(grant), "USER_REQUESTED", "coverage-revoke-test", True
        ),
    )
    with pytest.raises(AuthorityError):
        invoke(a, "READ_PROBLEM_RESOURCE_SELECTION")
    with a.repository.pool.connection() as c:
        record = c.execute(
            "SELECT record FROM execution_authority.resource_policy_plan_commands "
            "WHERE request_key=%s",
            ("auto-choice-1",),
        ).fetchone()["record"]
        assert record == result


@pytest.mark.parametrize(
    "reason,expected",
    [
        ("READONLY_COMPOSITION_MAPPING_UNSUPPORTED", "MAPPING"),
        ("AUTHORIZATION_NOT_FOUND", "PERMISSION"),
        ("APPROVED_SOURCE_EXACT_VERSION_REQUIRED", "DATA"),
        ("BUSINESS_RULE_FAMILY_UNSUPPORTED", "RULES"),
        ("RESOURCE_EXECUTOR_SCHEMA_MISMATCH", "TOOL"),
        ("LIVE_RUNTIME_NOT_AVAILABLE", "ENVIRONMENT_OR_CREDENTIAL"),
    ],
)
def test_gap_categories_are_not_inferred_from_readonly_prefix(reason, expected):
    from agent_console.problem_resource_coverage import gap_for

    assert gap_for(reason) == expected
