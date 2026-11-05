# ruff: noqa: F401,F811 -- Existing exact isolated-PG fixtures.
from copy import deepcopy
from pathlib import Path

import pytest
from agent_console.sales_resource_bundle import resource_content, source_document
from agent_console.skill_resource_testing import coverage, version_impact
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import command, manager


def fixture_content():
    csv = (
        Path(__file__).resolve().parents[3]
        / "examples/sales-diagnostic/synthetic-sales.csv"
    )
    source = source_document(csv.read_bytes())
    return resource_content(source)["skill"], {
        "schemaVersion": "sales-diagnostic-input.v1",
        "synthetic": True,
        "sourceSnapshot": {
            "resource_id": "synthetic-sales",
            "revision_id": "1",
            "digest": "b" * 64,
        },
        "dependencies": {},
        "source": source,
    }


def create(manager):
    content, inputs = fixture_content()
    # One declared operation is enough to verify exact coverage; this is not a
    # fake executor. It uses the registered SalesDiagnosticSkillExecutor.
    content["operations"] = content["operations"][:1]
    content["capabilities"] = ["READ_DATA"]
    row = command(manager, "create", name="真实销售Skill测试", content=content)[
        "resource"
    ]
    return row, inputs


def test_actual_output_is_independent_and_failed_retest_blocks_checked_publication(
    manager,
):
    row, inputs = create(manager)
    identity = row["resourceId"]
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_OPERATION_TESTS_REQUIRED"):
        command(
            manager,
            "publish-tested",
            identity=identity,
            expectedVersion=row["aggregateVersion"],
        )

    def run(row, expected, key):
        return command(
            manager,
            "test",
            key=key,
            identity=identity,
            expectedVersion=row["aggregateVersion"],
            operation="READ_DATA",
            testName="销售金额",
            testInput=inputs,
            expectedOutput=expected,
            comparison="subset",
        )["resource"]

    failed = run(row, {"impossible": "invented output"}, "actual-wrong-case")
    result = failed["testResults"][-1]
    assert result["status"] == "FAILED" and result["actualExecution"] is True
    assert (
        result["actual"]["synthetic"] is True and "impossible" not in result["actual"]
    )
    passed = run(
        failed,
        {"currencyComparisons": result["actual"]["currencyComparisons"]},
        "actual-correct-case",
    )
    rev = passed["revisions"][-1]
    assert coverage(passed, rev)["ready"] is True
    later = run(passed, {"impossible": "fail after pass"}, "actual-later-failed")
    assert coverage(later, later["revisions"][-1])["ready"] is False
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_OPERATION_TESTS_REQUIRED"):
        command(
            manager,
            "publish-tested",
            key="failed-publish-attempt",
            identity=identity,
            expectedVersion=later["aggregateVersion"],
        )
    restored = run(
        later, {"synthetic": True, "operation": "READ_DATA"}, "actual-fixed-case"
    )
    published = command(
        manager,
        "publish-tested",
        key="checked-publish-once",
        identity=identity,
        expectedVersion=restored["aggregateVersion"],
    )["resource"]
    assert (
        published["publishedRevisionId"]
        and coverage(published, published["revisions"][-1])["ready"]
    )
    old = deepcopy(published["revisions"][-1])
    successor = command(
        manager,
        "successor",
        identity=identity,
        expectedVersion=published["aggregateVersion"],
    )["resource"]
    impact = version_impact(successor)
    assert (
        impact["testCoverage"]["ready"] is False and impact["olderTestsNotCurrent"] == 4
    )
    assert successor["revisions"][0] == old
    assert impact["previousPublished"]["digest"] == old["digest"]
    assert impact["automaticMigration"] is False


def test_exact_executor_identity_input_schema_and_operation_coverage_fail_closed(
    manager,
):
    row, inputs = create(manager)
    identity = row["resourceId"]
    bad = deepcopy(inputs)
    bad["synthetic"] = False
    rejected = command(
        manager,
        "test",
        key="non-synthetic-case",
        identity=identity,
        expectedVersion=row["aggregateVersion"],
        operation="READ_DATA",
        testName="错误来源",
        testInput=bad,
        expectedOutput={"synthetic": True},
    )["resource"]
    assert rejected["testResults"][-1]["actualExecution"] is False
    assert rejected["testResults"][-1]["status"] != "PASSED"
    content, _ = fixture_content()
    content["operations"][0]["executorConfigurationDigest"] = "f" * 64
    edited = command(
        manager,
        "edit",
        identity=identity,
        expectedVersion=rejected["aggregateVersion"],
        content=content,
    )["resource"]
    missing = command(
        manager,
        "test",
        key="unknown-exact-executor",
        identity=identity,
        expectedVersion=edited["aggregateVersion"],
        operation="READ_DATA",
        testName="未登记执行器",
        testInput=inputs,
        expectedOutput={"synthetic": True},
    )["resource"]
    assert missing["testResults"][-1]["status"] == "NOT_EXECUTED"
    assert missing["testResults"][-1]["reasonCode"] == "EXECUTOR_REVISION_UNAVAILABLE"
    assert not coverage(missing, missing["revisions"][-1])["ready"]


@pytest.mark.parametrize(
    "mutation", ["side-effect", "input-limit", "schema", "source-ref"]
)
def test_denied_or_invalid_input_never_executes_or_passes(manager, mutation):
    content, inputs = fixture_content()
    content["operations"] = content["operations"][:1]
    operation = content["operations"][0]
    if mutation == "side-effect":
        operation["sideEffectClass"] = "IDEMPOTENT_WRITE"
    elif mutation == "input-limit":
        operation["ioLimits"]["maxInputBytes"] = 100
    elif mutation == "schema":
        operation["inputSchema"]["allOf"] = []
    else:
        inputs["sourceSnapshot"]["digest"] = "not-a-digest"
    if mutation == "side-effect":
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="SKILL_SIDE_EFFECT_NOT_ALLOWED"):
            command(manager, "create", name="拒绝执行边界", content=content)
        return
    row = command(manager, "create", name="拒绝执行边界", content=content)["resource"]
    payload = dict(
        identity=row["resourceId"],
        expectedVersion=row["aggregateVersion"],
        operation="READ_DATA",
        testName="拒绝边界",
        testInput=inputs,
        expectedOutput={"synthetic": True},
    )
    result = command(manager, "test", key="exact-test-case-replay", **payload)
    replay = command(manager, "test", key="exact-test-case-replay", **payload)
    assert replay == result
    final = result["resource"]
    assert len(final["testResults"]) == 1
    assert final["testResults"][0]["actualExecution"] is False
    assert final["testResults"][0]["status"] != "PASSED"
    assert coverage(final, final["revisions"][-1])["ready"] is False


def test_subset_and_exact_do_not_treat_boolean_as_number():
    from agent_console.skill_resource_testing import exact, subset

    assert not exact({"value": [True]}, {"value": [1]})
    assert not subset({"value": [True]}, {"value": [1]})
    assert subset({"value": {"n": 2}}, {"value": {"n": 2, "other": 3}})
    assert not subset({"value": [2]}, {"value": [2, 3]})
