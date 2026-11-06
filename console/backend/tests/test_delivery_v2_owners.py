# ruff: noqa: F401,F811 -- Disposable PostgreSQL owner fixtures, never history DB.
"""Actual policy publication and exact-member selection for six logical roles."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.resource_automation import ResourceAutomation
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_problem_resource_coverage import invoke
from test_resource_automation import automation


@pytest.mark.parametrize(
    "automation",
    [
        {"resources": mode, "deliveryV2": True}
        for mode in ("existing", "new", "expanded", "batch")
    ],
    indirect=True,
)
def test_six_roles_publication_selection_and_read_recovery(automation):
    a = automation
    result = a.run()
    assert result["state"] == "READY", (result, a.errors)
    actual = next(
        check
        for resource in result["resources"]
        if resource["kind"] == "skill"
        for check in resource["checks"]
        if check["check"] == "EXACT_SOURCE_ACTUAL_TESTS"
    )
    assert actual["passed"]
    assert "CLASSIFY_OVERDUE" in actual["operations"]
    assert all(
        t["actualExecution"] and t["status"] == "PASSED" for t in actual["tests"]
    )
    assert all(c["result"] == "SATISFIED" for c in actual["independentChecks"])
    before = deepcopy(result)
    assert a.run(read=True) == result and a.run() == result
    assert (
        before == result and result["humanApprovalClicks"] == result["modelCalls"] == 0
    )
    coverage = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE")
    assert coverage["selection"] is not None, coverage
    selected = invoke(a, "SELECT_PROBLEM_RESOURCES")
    semantics = selected["confirmation"]["plan"]["semantics"]
    roles = [r for r in semantics["requirements"] if r["kind"] == "EMPLOYEE"]
    assert len(roles) == 6
    assert len({repr(r["selected"]) for r in roles}) == 1
    assert len(coverage["candidates"][0]["checks"]["stepBindings"]) == 6
    assert invoke(a, "READ_PROBLEM_RESOURCE_SELECTION") == selected
    assert invoke(a, "SELECT_PROBLEM_RESOURCES") == selected
    assert selected["newRuns"] == 0


def test_different_employee_commitments_reject_before_any_member_read():
    refs = [
        SimpleNamespace(kind="EMPLOYEE", selected=identity)
        for identity in ("exact-one", "exact-two")
    ]
    plan = SimpleNamespace(semantics=SimpleNamespace(requirements=refs))
    with pytest.raises(WorkbenchOwnerError, match="SINGLE_EXACT_EMPLOYEE_REQUIRED"):
        ResourceAutomation.derive(None, None, plan, None, None, None)
