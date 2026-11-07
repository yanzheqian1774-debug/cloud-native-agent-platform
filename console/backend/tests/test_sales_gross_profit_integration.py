# ruff: noqa: F401, F811 -- Isolated PostgreSQL fixtures.
"""Explicit opt-in integration; actual installation and owner approval not asserted."""

import json
from copy import deepcopy

import pytest
from agent_console.resource_automation_validation import executor_registry, validate
from agent_console.sales_gross_profit_candidate import revision_candidate
from agent_console.sales_gross_profit_evaluation import (
    CHECKS,
    criterion_candidate,
    evaluate,
)
from agent_console.sales_gross_profit_integration import (
    IO_LIMITS,
    bounded_content,
    require_source,
)
from agent_console.sales_resource_bundle import resource_content
from agent_console.skill_invocation_application import _validate_shape
from agent_console.skill_invocation_domain import SkillInvocationError
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_sales_gross_profit_candidate import PREDECESSOR, RAW, REF, invoke


def content():
    source, report = invoke()
    return (
        source,
        report,
        bounded_content(
            revision_candidate(
                PREDECESSOR,
                resource_content(source)["skill"],
                1,
                REF,
                report["sourceDigest"],
            )["candidateContent"]
        ),
    )


def test_default_closed_bounded_registration_and_upstream_body():
    source, report, candidate = content()
    with pytest.raises(SkillInvocationError, match="EXECUTOR_REVISION_UNAVAILABLE"):
        validate("skill", candidate, None)
    assert validate(
        "skill",
        candidate,
        None,
        expected_source_schema=source["schemaVersion"],
        sales_v2_candidate=True,
    )
    assert (
        len(
            json.dumps(
                {"content": candidate, "expectedVersion": 1}, ensure_ascii=False
            ).encode()
        )
        < 128 * 1024
    )
    assert (
        len(json.dumps(report, ensure_ascii=False).encode())
        < IO_LIMITS["maxOutputBytes"]
    )
    inputs = {"source": source, "dependencies": {str(i): report for i in range(4)}}
    _validate_shape(inputs, IO_LIMITS["maxObjectDepth"], IO_LIMITS["maxProperties"])
    assert (
        len(json.dumps(inputs, ensure_ascii=False).encode())
        < IO_LIMITS["maxInputBytes"]
    )
    original = deepcopy(candidate)
    for mutation in ("limit", "schema", "digest", "mixed"):
        bad = deepcopy(original)
        op = bad["operations"][0]
        if mutation == "limit":
            op["ioLimits"]["maxInputBytes"] *= 2
        if mutation == "schema":
            op["outputSchema"]["properties"]["contractDigest"]["enum"] = ["0" * 64]
        if mutation == "digest":
            op["executorConfigurationDigest"] = "0" * 64
        if mutation == "mixed":
            bad["operations"][0] = resource_content(source)["skill"]["operations"][0]
        with pytest.raises((ValueError, SkillInvocationError)):
            validate("skill", bad, None, sales_v2_candidate=True)
    with pytest.raises(ValueError, match="EXACT_SOURCE"):
        require_source({**source, "periods": ["other", "source"]})


@pytest.mark.parametrize(
    "field",
    [
        "dimensions",
        "rowContributions",
        "reconciliations",
        "currencyComparisons",
        "sourceSnapshot",
        "contractDigest",
        "schemaVersion",
    ],
)
def test_versioned_evaluation_rejects_tampering_and_v1_criteria(field):
    source, report, _ = content()
    assert all(
        evaluate(criterion_candidate(check), source, report, REF)[0] == "SATISFIED"
        for check in CHECKS
    )
    bad = deepcopy(report)
    bad[field] = (
        []
        if isinstance(bad[field], list)
        else {}
        if isinstance(bad[field], dict)
        else "wrong"
    )
    assert any(
        evaluate(criterion_candidate(check), source, bad, REF)[0] != "SATISFIED"
        for check in CHECKS
    )
    criterion = criterion_candidate("totals")
    criterion["evaluator_version"] = "1"
    assert evaluate(criterion, source, report, REF)[0] == "UNKNOWN"
    from agent_console.sales_evaluation import evaluate as old_evaluate

    assert old_evaluate(criterion, source, report, REF)[0] == "UNKNOWN"


@pytest.mark.parametrize(
    "automation", [{"resources": "new", "salesV2": True}], indirect=True
)
def test_plan_resource_preparation_candidate_publication_only_in_disposable_pg(
    automation,
):
    a = automation
    result = a.run()
    assert result["state"] == "READY", result
    skill = next(x for x in result["resources"] if x["kind"] == "skill")
    actual = next(
        x for x in skill["checks"] if x["check"] == "EXACT_SOURCE_ACTUAL_TESTS"
    )
    assert actual["passed"] and actual["ownerTestRecordsWritten"]
    assert len(actual["tests"]) == 5
    assert all(x["result"] == "SATISFIED" for x in actual["independentChecks"])
    assert a.run() == result and a.run(read=True) == result
    assert result["executionStarted"] is False


@pytest.mark.parametrize(
    "automation",
    [{"resources": "new", "continuation": True, "salesV2": True}],
    indirect=True,
)
def test_v2_existing_plan_selection_instance_assembly_and_native_queue(
    automation, monkeypatch, tmp_path
):
    import test_readonly_continuation as continuation

    continuation.test_readonly_continuation_queues_one_run_and_get_replay_never_dispatches_again(
        automation, monkeypatch, tmp_path, False
    )
