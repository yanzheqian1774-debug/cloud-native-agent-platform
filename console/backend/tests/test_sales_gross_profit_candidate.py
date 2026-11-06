"""Local v2 computation/provenance proof; no model, live DB or business Run."""

import csv
import importlib.util
import io
from copy import deepcopy
from pathlib import Path

import pytest
from agent_console.resource_use_domain import canonical_digest
from agent_console.sales_diagnostic_skill import (
    OPERATIONS,
    SalesDiagnosticSkillExecutor,
)
from agent_console.sales_evaluation import evaluate_sales
from agent_console.sales_gross_profit_candidate import revision_candidate
from agent_console.sales_gross_profit_contract import CONTRACT_DIGEST, contract_document
from agent_console.sales_gross_profit_skill import (
    LIMITS,
    SalesGrossProfitFailure,
    SalesGrossProfitSkillExecutor,
)
from agent_console.sales_resource_bundle import resource_content, source_document
from agent_console.skill_executor import SkillExecutorRegistry
from agent_console.skill_invocation_domain import ExecutorRevision, SkillInvocationError
from agent_console.skill_resource_testing import schema_check

ROOT = Path(__file__).resolve().parents[3]
RAW = (ROOT / "examples/sales-diagnostic/synthetic-sales.csv").read_bytes()
REF = {"resource_id": "synthetic-sales", "revision_id": "1", "digest": "b" * 64}
PREDECESSOR = {
    "resource_id": "skill-definition:existing-sales",
    "revision_id": "skill-revision:1",
    "digest": "c" * 64,
}
spec = importlib.util.spec_from_file_location(
    "sales_csv_minor_unit_oracle",
    ROOT / "examples/sales-diagnostic/gross_profit_oracle.py",
)
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def variant(identity, **changes):
    rows = list(csv.DictReader(io.StringIO(RAW.decode())))
    for row in rows:
        if row["rowId"] == identity:
            row.update(changes)
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode()


def invoke(raw=RAW, *, source=None, operation="RENDER_REPORT"):
    source = source_document(raw) if source is None else source
    inputs = {
        "schemaVersion": "sales-diagnostic-input.v2",
        "synthetic": True,
        "source": source,
        "sourceSnapshot": REF,
        "dependencies": {},
    }
    executor = SalesGrossProfitSkillExecutor()
    read = executor.invoke("local-read", "READ_DATA", inputs, 5000).output
    if operation == "READ_DATA":
        return source, read
    return source, executor.invoke(
        "local-report", operation, {**inputs, "dependencies": {"read": read}}, 5000
    ).output


def check(source, report, raw=RAW):
    return oracle.check(raw, source, REF, contract_document(), report)


def test_same_csv_row_terms_and_three_gross_profit_partitions_are_independent():
    source, report = invoke()
    assert check(source, report)["status"] == "LOCAL_MATCHED"
    terms = {r["rowId"]: r for r in report["rowContributions"]}
    assert {k: r["deltaContributions"]["grossProfit"] for k, r in terms.items()} == {
        "S01": "-240.00",
        "S02": "-160.00",
        "S03": "120.00",
        "S04": "140.00",
        "S05": "-20.00",
        "S06": "-40.00",
        "S07": "42.00",
        "S08": "40.00",
    }
    assert {k: r["sourceLine"] for k, r in terms.items()} == {
        "S01": 2,
        "S02": 3,
        "S03": 4,
        "S04": 5,
        "S05": 6,
        "S06": 7,
        "S07": 8,
        "S08": 9,
    }
    assert terms["S05"]["netSales"] == "-50.00"
    assert terms["S05"]["cost"] == "-30.00"
    assert report["excludedRows"][0]["rowId"] == "S09"
    assert report["excludedRows"][0]["sourceLine"] == 10
    assert "S09" not in terms
    expected = {
        "region": {"North": "-120.00", "South": "-40.00"},
        "channel": {"Online": "-120.00", "Direct": "-40.00"},
        "product": {"A": "-120.00", "B": "-40.00"},
    }
    for dimension, groups in expected.items():
        assert {
            r["value"]: r["grossProfit"]["delta"]
            for r in report["dimensions"][dimension]
            if r["currency"] == "CNY"
        } == groups
        assert {
            r["currency"]: r["grossProfit"]
            for r in report["reconciliations"][dimension]
        } == {
            "CNY": {
                "sumGroupDelta": "-160.00",
                "currencyDelta": "-160.00",
                "matches": True,
            },
            "EUR": {"sumGroupDelta": "2.00", "currencyDelta": "2.00", "matches": True},
            "JPY": {
                "sumGroupDelta": "40.00",
                "currencyDelta": "40.00",
                "matches": True,
            },
        }
    jpy = next(r for r in report["currencyComparisons"] if r["currency"] == "JPY")
    assert jpy["grossProfit"]["rate"] == {"status": "BASELINE_ZERO"}
    assert report["contractDigest"] == CONTRACT_DIGEST
    assert report["businessConclusion"] == "UNDETERMINED"


@pytest.mark.parametrize("dimension", ["region", "channel", "product"])
@pytest.mark.parametrize("unknown", ["", "UNKNOWN", " 未知 ", "N/A", "unspecified"])
def test_unknown_dimensions_stay_in_an_explicit_reconciled_group(dimension, unknown):
    raw = variant("S03", **{dimension: unknown})
    source, report = invoke(raw)
    assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
    bucket = next(
        g for g in report["dimensions"][dimension] if g["valueStatus"] == "UNRESOLVED"
    )
    assert bucket["value"] == "" and bucket["grossProfit"]["delta"] == "120.00"
    assert bucket["sourceRows"] == [
        {"period": "2026-08", "rowIds": []},
        {"period": "2026-09", "rowIds": ["S03"]},
    ]
    assert report["inputIssues"] == [
        {
            "rowId": "S03",
            "sourceLine": 4,
            "field": dimension,
            "reason": "DIMENSION_UNRESOLVED_INCLUDED",
            "rawValue": unknown,
            "sourceValueState": "PRESENT",
        }
    ]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("cost", "", "COST_REQUIRED"),
        ("cost", "NaN", "MONEY_INVALID"),
        ("cost", "1.001", "MONEY_INVALID"),
        ("cost", "1e10000", "MONEY_INVALID"),
        ("netSales", "", "NET_SALES_REQUIRED"),
        ("currency", "cny", "CURRENCY_INVALID"),
        ("period", "2026-10", "PERIOD_INVALID"),
        ("kind", "FORECAST", "CLASSIFICATION_INVALID"),
    ],
)
def test_invalid_posted_data_has_a_known_row_diagnostic(field, value, reason):
    with pytest.raises(SalesGrossProfitFailure, match=reason) as raised:
        invoke(variant("S03", **{field: value}))
    assert raised.value.outcome_unknown is False
    assert raised.value.details == {
        "rowId": "S03",
        "sourceLine": 4,
        "field": field if field != "kind" else "",
    }


@pytest.mark.parametrize("field", ["netSales", "cost"])
def test_return_sign_is_never_inferred_or_flipped(field):
    with pytest.raises(SalesGrossProfitFailure, match="SIGN_INCONSISTENT") as raised:
        invoke(variant("S05", **{field: "30"}))
    assert raised.value.details["rowId"] == "S05"
    assert raised.value.details["field"] == field
    assert raised.value.outcome_unknown is False


def test_cancelled_unusable_amounts_are_excluded_without_zero_imputation():
    raw = variant("S09", cost="", netSales="not-a-posted-amount")
    source, report = invoke(raw)
    assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
    assert report["excludedRows"][0]["rawValues"]["cost"] == ""
    assert report["excludedRows"][0]["rawValues"]["netSales"] == "not-a-posted-amount"
    assert (
        next(r for r in report["currencyComparisons"] if r["currency"] == "CNY")[
            "grossProfit"
        ]["delta"]
        == "-160.00"
    )


def test_negative_gross_profit_base_uses_absolute_denominator_and_no_causal_claim():
    raw = variant("S06", cost="110")
    source, report = invoke(raw)
    assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
    eur = next(r for r in report["currencyComparisons"] if r["currency"] == "EUR")
    assert eur["grossProfit"] == {
        "baseline": "-10.00",
        "current": "42.00",
        "delta": "52.00",
        "rate": {"status": "DEFINED", "value": "5.2"},
    }
    assert "OBSERVATIONAL_NOT_CAUSAL" in report["limitations"]


def test_identical_labels_in_different_currencies_never_combine():
    raw = variant("S07", region="North", channel="Online", product="A")
    source, report = invoke(raw)
    assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
    for dimension, name in [
        ("region", "North"),
        ("channel", "Online"),
        ("product", "A"),
    ]:
        rows = [r for r in report["dimensions"][dimension] if r["value"] == name]
        assert {r["currency"] for r in rows} == {"CNY", "EUR"}
        assert len(report["reconciliations"][dimension]) == 3


@pytest.mark.parametrize(
    "damage",
    [
        "gp",
        "group",
        "line",
        "omit",
        "duplicate",
        "reconcile",
        "zero_rate",
        "claim",
        "boolean",
        "excluded",
    ],
)
def test_independent_csv_oracle_rejects_mutated_contribution_or_provenance(damage):
    source, report = invoke()
    if damage == "gp":
        report["currencyComparisons"][0]["grossProfit"]["delta"] = "0.00"
    elif damage == "group":
        report["dimensions"]["channel"][0]["grossProfit"]["current"] = "0.00"
    elif damage == "line":
        report["rowContributions"][0]["sourceLine"] = 999
    elif damage == "omit":
        report["rowContributions"].pop()
    elif damage == "duplicate":
        report["rowContributions"].append(deepcopy(report["rowContributions"][0]))
    elif damage == "reconcile":
        report["reconciliations"]["region"][0]["grossProfit"]["sumGroupDelta"] = "0.00"
    elif damage == "zero_rate":
        report["currencyComparisons"][-1]["grossProfit"]["rate"]["value"] = "0"
    elif damage == "claim":
        report["businessConclusion"] = "IMPROVED"
    elif damage == "boolean":
        report["synthetic"] = 1
    else:
        report["excludedRows"] = []
    assert check(source, report)["status"] == "LOCAL_MISMATCH"


@pytest.mark.parametrize("damage", ["v1", "ref", "source", "money", "boolean"])
def test_v2_dependencies_are_exact_and_cannot_silently_reuse_v1(damage):
    source, read = invoke(operation="READ_DATA")
    inputs = {
        "schemaVersion": "sales-diagnostic-input.v2",
        "synthetic": True,
        "source": source,
        "sourceSnapshot": REF,
        "dependencies": {"read": read},
    }
    if damage == "v1":
        read["schemaVersion"] = "sales-diagnostic-output.v1"
    elif damage == "ref":
        read["sourceSnapshot"]["revision_id"] = "other"
    elif damage == "source":
        read["sourceDigest"] = "a" * 64
    elif damage == "boolean":
        read["synthetic"] = 1
    else:
        read["rowContributions"][0]["grossProfit"] = "999.00"
    with pytest.raises(
        SalesGrossProfitFailure, match="DEPENDENCY_SOURCE_OR_CONTENT_MISMATCH"
    ):
        SalesGrossProfitSkillExecutor().invoke(
            "local-altered", "RENDER_REPORT", inputs, 5000
        )


def test_current_registry_v1_contract_and_criteria_remain_separate():
    source = source_document(RAW)
    v1, v2 = SalesDiagnosticSkillExecutor(), SalesGrossProfitSkillExecutor()
    registry = SkillExecutorRegistry((v1, v2))
    assert registry.resolve(v1.revision) is v1 and registry.resolve(v2.revision) is v2
    with pytest.raises(SkillInvocationError, match="UNAVAILABLE"):
        SkillExecutorRegistry((v1,)).resolve(v2.revision)
    with pytest.raises(SkillInvocationError, match="UNAVAILABLE"):
        registry.resolve(ExecutorRevision(v2.revision.executor_id, "2", "0" * 64))
    old = v1.invoke(
        "old-read",
        "READ_DATA",
        {
            "schemaVersion": "sales-diagnostic-input.v1",
            "synthetic": True,
            "source": source,
            "sourceSnapshot": REF,
        },
        5000,
    ).output
    assert old["schemaVersion"] == "sales-diagnostic-output.v1"
    assert "grossProfit" not in old["dimensions"]["region"][0]
    assert old["currencyComparisons"][-1]["grossProfit"]["changeRate"] is None
    _, new = invoke()
    assert evaluate_sales("totals", source, new, REF)[0] == "UNKNOWN"
    with pytest.raises(SalesGrossProfitFailure, match="INPUT_CONTRACT_INVALID"):
        v2.invoke(
            "wrong-input",
            "READ_DATA",
            {
                "schemaVersion": "sales-diagnostic-input.v1",
                "synthetic": True,
                "source": source,
                "sourceSnapshot": REF,
                "dependencies": {},
            },
            5000,
        )


def test_candidate_is_content_addressed_unpublished_and_has_usable_shapes():
    source = source_document(RAW)
    original = resource_content(source)["skill"]
    before = deepcopy(original)
    proposal = revision_candidate(
        PREDECESSOR, original, 4, REF, canonical_digest(source)
    )
    assert original == before
    assert proposal["predecessorContentDigest"] == canonical_digest(original)
    assert proposal["predecessor"] == PREDECESSOR
    assert proposal["candidateId"] == "skill-revision-candidate:" + canonical_digest(
        {k: v for k, v in proposal.items() if k != "candidateId"}
    )
    assert proposal["formalRevisionIdentity"] == "NOT_ASSIGNED_BY_RESOURCE_OWNER"
    assert proposal["publication"] == proposal["executionAdmission"] == "NOT_REQUESTED"
    assert proposal["permissionsAdded"] is False
    assert proposal["candidateContent"]["permissions"] == original["permissions"]
    for operation in OPERATIONS:
        _, report = invoke(operation=operation)
        op = next(
            x
            for x in proposal["candidateContent"]["operations"]
            if x["name"] == operation
        )
        schema_check(report, op["outputSchema"], "OUTPUT_INVALID")
        assert op["executorRevision"] == "2"
        assert (
            op["sideEffectPolicy"]
            == next(x for x in original["operations"] if x["name"] == operation)[
                "sideEffectPolicy"
            ]
        )
    wrong = deepcopy(original)
    wrong["operations"][0]["executorRevision"] = "wrong"
    with pytest.raises(ValueError, match="PREDECESSOR_REQUIRED"):
        revision_candidate(PREDECESSOR, wrong, 4, REF, canonical_digest(source))


def test_source_tampering_and_row_limits_fail_with_known_outcomes():
    source = source_document(RAW)
    source["snapshot"]["rows"][0]["values"]["cost"] = "0"
    with pytest.raises(SalesGrossProfitFailure, match="SNAPSHOT_INVALID"):
        invoke(source=source)
    source = source_document(RAW)
    base = source["snapshot"]["rows"][0]
    source["snapshot"]["rows"] = [
        {"sourceLine": i + 2, "values": {**base["values"], "rowId": str(i)}}
        for i in range(LIMITS["maxRows"] + 1)
    ]
    source["snapshot"]["snapshotDigest"] = canonical_digest(
        {k: v for k, v in source["snapshot"].items() if k != "snapshotDigest"}
    )
    with pytest.raises(SalesGrossProfitFailure, match="ROW_BOUNDS_INVALID"):
        invoke(source=source)


def test_committed_csv_bytes_are_checked_by_the_independent_oracle():
    source, report = invoke()
    with pytest.raises(ValueError, match="CSV_BYTES_MISMATCH"):
        check(source, report, RAW + b"\n")


def test_baseline_return_keeps_both_return_and_period_signs():
    raw = variant("S01", kind="RETURN", netSales="-600", cost="-360")
    source, report = invoke(raw)
    assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
    row = next(r for r in report["rowContributions"] if r["rowId"] == "S01")
    assert row["grossProfit"] == "-240.00"
    assert row["deltaContributions"]["grossProfit"] == "240.00"
    assert (
        next(r for r in report["currencyComparisons"] if r["currency"] == "CNY")[
            "grossProfit"
        ]["delta"]
        == "320.00"
    )


def test_negative_zero_return_is_canonical_zero_without_growth_invention():
    raw = variant("S05", netSales="-0.00", cost="-0.00")
    source, report = invoke(raw)
    assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
    term = next(r for r in report["rowContributions"] if r["rowId"] == "S05")
    assert all(term[m] == "0.00" for m in ("netSales", "cost", "grossProfit"))


@pytest.mark.parametrize("bad", ["missing_cost", "duplicate_line", "duplicate_id"])
def test_missing_cost_and_ambiguous_source_rows_are_not_dropped(bad):
    source = source_document(RAW)
    rows = source["snapshot"]["rows"]
    if bad == "missing_cost":
        rows[0]["values"].pop("cost")
        reason = "COST_REQUIRED"
    elif bad == "duplicate_line":
        rows[1]["sourceLine"] = rows[0]["sourceLine"]
        reason = "SOURCE_LINE_INVALID"
    else:
        rows[1]["values"]["rowId"] = rows[0]["values"]["rowId"]
        reason = "DUPLICATE_ROW"
    source["snapshot"]["snapshotDigest"] = canonical_digest(
        {k: v for k, v in source["snapshot"].items() if k != "snapshotDigest"}
    )
    with pytest.raises(SalesGrossProfitFailure, match=reason) as raised:
        invoke(source=source)
    assert raised.value.outcome_unknown is False


def test_bounded_deadline_and_oversized_inputs_have_known_outcomes(monkeypatch):
    import agent_console.sales_gross_profit_skill as skill

    source = source_document(RAW)
    inputs = {
        "schemaVersion": "sales-diagnostic-input.v2",
        "synthetic": True,
        "source": source,
        "sourceSnapshot": REF,
        "dependencies": {},
    }
    executor = SalesGrossProfitSkillExecutor()
    oversized = deepcopy(inputs)
    oversized["source"]["extra"] = "x" * LIMITS["maxInputBytes"]
    with pytest.raises(SalesGrossProfitFailure, match="BYTE_BOUNDS_EXCEEDED"):
        executor.invoke("too-large", "READ_DATA", oversized, 5000)
    clock = iter([0, 10])
    monkeypatch.setattr(skill, "monotonic", lambda: next(clock))
    with pytest.raises(SalesGrossProfitFailure, match="COMPUTATION_DEADLINE") as raised:
        executor.invoke("deadline", "READ_DATA", inputs, 5000)
    assert raised.value.outcome_unknown is False


def test_read_and_later_operation_dependency_policies_are_explicit():
    source, read = invoke(operation="READ_DATA")
    inputs = {
        "schemaVersion": "sales-diagnostic-input.v2",
        "synthetic": True,
        "source": source,
        "sourceSnapshot": REF,
        "dependencies": {},
    }
    executor = SalesGrossProfitSkillExecutor()
    with pytest.raises(SalesGrossProfitFailure, match="DEPENDENCY_REQUIRED"):
        executor.invoke("missing-dependency", "RENDER_REPORT", inputs, 5000)
    with pytest.raises(SalesGrossProfitFailure, match="READ_DEPENDENCY_FORBIDDEN"):
        executor.invoke(
            "extra-dependency",
            "READ_DATA",
            {**inputs, "dependencies": {"read": read}},
            5000,
        )


def test_candidate_cannot_relabel_a_mismatched_v1_input_contract():
    source = source_document(RAW)
    content = resource_content(source)["skill"]
    content["operations"][0]["inputSchema"]["properties"]["schemaVersion"]["enum"] = [
        "other-input.v1"
    ]
    with pytest.raises(ValueError, match="PREDECESSOR_REQUIRED"):
        revision_candidate(PREDECESSOR, content, 4, REF, canonical_digest(source))


def test_decimal_host_rounding_and_inexact_traps_cannot_change_candidate_or_oracle():
    from decimal import ROUND_UP, Inexact, localcontext

    raw = RAW.replace(
        b"S06,2026-08,Europe,Partner,C,EUR,SALE,POSTED,100,60",
        b"S06,2026-08,Europe,Partner,C,EUR,SALE,POSTED,3,0",
    ).replace(
        b"S07,2026-09,Europe,Partner,C,EUR,SALE,POSTED,120,78",
        b"S07,2026-09,Europe,Partner,C,EUR,SALE,POSTED,4,0",
    )
    with localcontext() as host:
        host.prec = 6
        host.rounding = ROUND_UP
        host.traps[Inexact] = True
        source, report = invoke(raw)
        assert check(source, report, raw)["status"] == "LOCAL_MATCHED"
        eur = next(r for r in report["currencyComparisons"] if r["currency"] == "EUR")
        assert eur["grossProfit"]["rate"] == {
            "status": "DEFINED",
            "value": "0." + "3" * 38,
        }
        assert host.prec == 6 and host.rounding == ROUND_UP and host.traps[Inexact]
