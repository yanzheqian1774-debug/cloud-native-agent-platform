# ruff: noqa: F401,F811 -- Existing isolated PostgreSQL fixtures.
from copy import deepcopy

import pytest
from agent_console.resource_automation_validation import EXECUTORS
from agent_console.skill_executor import SkillExecutorResult
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


@pytest.mark.parametrize("automation", ["new"], indirect=True)
def test_new_draft_is_tested_independently_before_policy_publication_and_assembly(
    automation,
):
    a = automation
    result = a.run()
    assert result["state"] == "READY" and result["assembly"]["state"] == "ASSEMBLED"
    skill = next(x for x in result["resources"] if x["kind"] == "skill")
    actual = next(
        x for x in skill["checks"] if x["check"] == "EXACT_SOURCE_ACTUAL_TESTS"
    )
    assert actual["passed"] and actual["ownerTestRecordsWritten"]
    assert all(
        x["actualExecution"] and x["status"] == "PASSED" for x in actual["tests"]
    )
    assert all(x["result"] == "SATISFIED" for x in actual["independentChecks"])
    service = a.services["skill"]
    scope = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
    record = service.repository.get(scope, "skill", a.refs["skill"].resource_id)
    assert record["publishedRevisionId"] == a.refs["skill"].revision_id
    assert len(record["testResults"]) == len(actual["tests"])
    assert all(
        x["verificationContext"]["source"] == actual["source"]
        for x in record["testResults"]
    )
    assert a.run() == result and a.run(read=True) == result
    assert service.repository.get(scope, "skill", a.refs["skill"].resource_id) == record


@pytest.mark.parametrize("automation", ["new"], indirect=True)
def test_bad_amount_preserves_failed_independent_test(automation, monkeypatch):
    a = automation
    resolve = EXECUTORS.resolve

    def corrupt(revision):
        delegate = resolve(revision)

        class Executor:
            def invoke(self, *args):
                response = delegate.invoke(*args)
                output = deepcopy(response.output)
                if args[1] == "RENDER_REPORT":
                    output["currencyComparisons"][0]["netSales"]["current"] = (
                        "999999.00"
                    )
                return SkillExecutorResult(
                    response.accepted, output, response.provider_observation_id
                )

        value = Executor()
        value.revision = delegate.revision
        return value

    monkeypatch.setattr(EXECUTORS, "resolve", corrupt)
    result = a.run()
    skill = next(x for x in result["resources"] if x["kind"] == "skill")
    assert skill["state"] == "BLOCKED" and skill["publication"] is None
    assert result["assembly"]["state"] == "BLOCKED"
    service = a.services["skill"]
    scope = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
    record = service.repository.get(scope, "skill", a.refs["skill"].resource_id)
    assert record["publishedRevisionId"] is None and not record["reviews"]
    failed = record["testResults"][-1]
    assert failed["status"] == "FAILED" and failed["actualExecution"]
    assert any(
        x["check"] == "totals" and x["result"] == "NOT_SATISFIED"
        for x in failed["independentChecks"]
    )
    assert (
        failed["actual"]["currencyComparisons"][0]["netSales"]["current"] == "999999.00"
    )
    assert a.run(read=True) == result


def test_existing_published_owner_is_unchanged_and_recovery_never_reexecutes(
    automation, monkeypatch
):
    a = automation
    service = a.services["skill"]
    scope = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
    before = service.repository.get(scope, "skill", a.refs["skill"].resource_id)
    calls = []
    original = EXECUTORS.resolve

    def track(revision):
        delegate = original(revision)

        class Executor:
            def invoke(self, *args):
                calls.append(args[1])
                return delegate.invoke(*args)

        value = Executor()
        value.revision = delegate.revision
        return value

    monkeypatch.setattr(EXECUTORS, "resolve", track)
    result = a.run()
    count = len(calls)
    assert count > 0
    assert a.run() == result and a.run(read=True) == result and len(calls) == count
    assert service.repository.get(scope, "skill", a.refs["skill"].resource_id) == before
