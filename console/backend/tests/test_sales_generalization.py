"""Second-domain checks with independently specified amounts and mutated evidence."""

from copy import deepcopy
from pathlib import Path

import pytest
from agent_console.resource_use_domain import canonical_digest
from agent_console.sales_diagnostic_skill import FIELDS, SalesDiagnosticSkillExecutor
from agent_console.sales_evaluation import CHECKS, evaluate_sales
from agent_console.sales_resource_bundle import resource_content, source_document
from agent_console.skill_executor import SkillExecutorFailure, SkillExecutorRegistry
from agent_console.skill_invocation_domain import ExecutorRevision, SkillInvocationError
from agent_console.tabular_snapshot import SnapshotInputError, read_csv_snapshot

CSV = (
    Path(__file__).resolve().parents[3]
    / "examples/sales-diagnostic/synthetic-sales.csv"
)
REF = {"resource_id": "synthetic-sales", "revision_id": "1", "digest": "b" * 64}


def source():
    return source_document(CSV.read_bytes())


def report(value=None):
    value = source() if value is None else value
    executor = SalesDiagnosticSkillExecutor()
    inputs = {
        "schemaVersion": "sales-diagnostic-input.v1",
        "synthetic": True,
        "source": value,
        "sourceSnapshot": REF,
    }
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    return executor.invoke(
        "report", "RENDER_REPORT", {**inputs, "dependencies": {"read": read}}, 1000
    ).output


def reseal(value):
    snapshot = value["snapshot"]
    snapshot["snapshotDigest"] = canonical_digest(
        {k: v for k, v in snapshot.items() if k != "snapshotDigest"}
    )
    return value


def test_sales_amounts_returns_and_currency_separation():
    value = report()
    rows = {r["currency"]: r for r in value["currencyComparisons"]}
    assert set(rows) == {"CNY", "EUR", "JPY"}
    assert rows["CNY"]["netSales"] == {
        "baseline": "1000.00",
        "current": "800.00",
        "delta": "-200.00",
        "changeRate": "-0.2",
        "rateReason": None,
    }
    assert rows["CNY"]["grossProfit"]["delta"] == "-160.00"
    assert rows["EUR"]["netSales"]["delta"] == "20.00"
    assert rows["EUR"]["grossProfit"]["delta"] == "2.00"
    assert rows["JPY"]["netSales"]["changeRate"] is None
    assert rows["JPY"]["netSales"]["rateReason"] == "BASELINE_ZERO"
    assert value["excludedRows"] == [
        {"rowId": "S09", "sourceLine": 10, "reason": "CANCELLED"}
    ]
    assert value["businessConclusion"] == "UNDETERMINED"
    cny = [r for r in value["dimensions"]["region"] if r["currency"] == "CNY"]
    assert [(r["value"], r["delta"]) for r in cny] == [
        ("North", "-200.00"),
        ("South", "0.00"),
    ]


@pytest.mark.parametrize("check", CHECKS)
def test_independent_checks_and_provenance(check):
    s, r = source(), report()
    assert evaluate_sales(check, s, r, REF)[0] == "SATISFIED"
    r["sourceSnapshot"] = {**REF, "revision_id": "supplier-v1"}
    assert evaluate_sales(check, s, r, REF)[0] == "NOT_SATISFIED"


@pytest.mark.parametrize("check", CHECKS)
def test_mutated_report_cannot_pass(check):
    r = report()
    if check == "source":
        r["sourceDigest"] = "a" * 64
    elif check == "totals":
        r["currencyComparisons"][0]["netSales"]["current"] = "9999.00"
    elif check == "contributions":
        r["dimensions"]["region"][0]["delta"] = "0.00"
    elif check == "exceptions":
        r["excludedRows"] = []
    else:
        r["businessConclusion"] = "IMPROVED"
    assert evaluate_sales(check, source(), r, REF)[0] == "NOT_SATISFIED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("netSales", "NaN"),
        ("netSales", "1.001"),
        ("cost", "1e999999"),
        ("currency", "cny"),
        ("kind", "FORECAST"),
        ("period", "2026-10"),
        ("rowId", "S02"),
        ("netSales", "-1"),
    ],
)
def test_bad_source_rejected_without_unknown_call(field, value):
    s = source()
    s["snapshot"]["rows"][0]["values"][field] = value
    with pytest.raises(SkillExecutorFailure) as raised:
        report(reseal(s))
    assert raised.value.outcome_unknown is False


def test_snapshot_tampering_and_unhashable_periods_are_bounded():
    s = source()
    s["snapshot"]["rows"][0]["values"]["netSales"] = "1"
    with pytest.raises(SkillExecutorFailure):
        report(s)
    s = source()
    s["periods"] = [{}, {}]
    with pytest.raises(SkillExecutorFailure):
        report(s)


@pytest.mark.parametrize(
    "raw,columns,limit",
    [
        (b"\xff", {"x": "x"}, 1),
        (b"x,x\n1,2", {"x": "x"}, 1),
        (b"x\n1,2", {"x": "x"}, 1),
        (b"x\n1\n2", {"x": "x"}, 1),
        (b"x\n1", {"x": "missing"}, 1),
        (b"x\n1", {"x": "x"}, True),
    ],
)
def test_csv_failure_is_explicit(raw, columns, limit):
    with pytest.raises(SnapshotInputError):
        read_csv_snapshot(
            raw, source_id="test", columns=columns, required=("x",), max_rows=limit
        )


def test_explicit_mapping_bom_and_quoted_multiline_traceability():
    s = read_csv_snapshot(
        b'\xef\xbb\xbfamount,note\n"12","a\nb"\n',
        source_id="test",
        columns={"value": "amount", "memo": "note"},
        required=("value",),
    )
    assert s["rows"] == [{"sourceLine": 3, "values": {"value": "12", "memo": "a\nb"}}]


def test_existing_registry_and_resource_schema_support_both_domains():
    from agent_console.synthetic_delivery_skill import SyntheticDeliverySkillExecutor

    executor = SalesDiagnosticSkillExecutor()
    registry = SkillExecutorRegistry((executor, SyntheticDeliverySkillExecutor()))
    assert registry.resolve(executor.revision) is executor
    with pytest.raises(SkillInvocationError):
        registry.resolve(ExecutorRevision(executor.revision.executor_id, "1", "0" * 64))
    bundle = resource_content(source())
    assert set(bundle["skill"]["capabilities"]) == {
        "READ_DATA",
        "VALIDATE_DATA",
        "SUMMARIZE",
        "ANALYZE_DATA",
        "RENDER_REPORT",
    }
    assert all(
        op["executorConfigurationDigest"] == executor.revision.configuration_digest
        for op in bundle["skill"]["operations"]
    )
    assert set(FIELDS) == set(source()["snapshot"]["columnMapping"])


def test_dependency_from_other_scenario_is_rejected():
    s = source()
    executor = SalesDiagnosticSkillExecutor()
    inputs = {
        "schemaVersion": "sales-diagnostic-input.v1",
        "synthetic": True,
        "source": s,
        "sourceSnapshot": REF,
    }
    dependency = executor.invoke("read", "READ_DATA", inputs, 1000).output
    altered = deepcopy(dependency)
    altered["source"]["snapshot"]["sourceId"] = "supplier-source"
    with pytest.raises(SkillExecutorFailure):
        executor.invoke(
            "report",
            "RENDER_REPORT",
            {**inputs, "dependencies": {"read": altered}},
            1000,
        )
