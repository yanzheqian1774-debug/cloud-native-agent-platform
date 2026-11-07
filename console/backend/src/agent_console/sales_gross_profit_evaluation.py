"""Versioned same-source independent measurements, never business acceptance."""

from .resource_use_domain import canonical_digest
from .sales_gross_profit_contract import CONTRACT_DIGEST, contract_document
from .sales_gross_profit_integration import SOURCE_DIGEST, require_source
from .sales_gross_profit_oracle import expectations

CHECKS = (
    "source",
    "totals",
    "gross_profit_dimensions",
    "row_contributions",
    "reconciliations",
    "exceptions",
    "claim_boundary",
)
FIELDS = {
    "source": ("source", "sourceSnapshot", "sourceDigest", "periods"),
    "totals": ("currencyComparisons",),
    "gross_profit_dimensions": ("dimensions",),
    "row_contributions": ("rowContributions",),
    "reconciliations": ("reconciliations",),
    "exceptions": ("excludedRows", "inputIssues"),
    "claim_boundary": (
        "synthetic",
        "metric",
        "grossProfitDefinition",
        "limitations",
        "businessConclusion",
    ),
}


def evaluate_sales(check, source, report, reference):
    if check not in CHECKS or not isinstance(report, dict):
        return "UNKNOWN", "SALES_V2_EVIDENCE_MISSING"
    try:
        require_source(source)
        if (
            report.get("schemaVersion") != "sales-diagnostic-output.v2"
            or report.get("contractDigest") != CONTRACT_DIGEST
            or report.get("operation") != "RENDER_REPORT"
        ):
            return "UNKNOWN", "SALES_V2_EXACT_CONTRACT_REQUIRED"
        expected = expectations(None, source, reference, contract_document())
        if any(
            canonical_digest(report.get(k)) != canonical_digest(expected[k])
            for k in FIELDS["source"]
        ):
            return "NOT_SATISFIED", "SALES_V2_SOURCE_MISMATCH"
        matched = all(
            canonical_digest(report.get(k)) == canonical_digest(expected[k])
            for k in FIELDS[check]
        )
        if check == "claim_boundary":
            matched = matched and set(report) == set(expected)
        return (
            ("SATISFIED", "SALES_V2_INDEPENDENT_CHECK_PASSED")
            if matched
            else ("NOT_SATISFIED", "SALES_V2_REPORT_MISMATCH")
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return "UNKNOWN", "SALES_V2_EVIDENCE_INVALID"


def criterion_candidate(check):
    if check not in CHECKS:
        raise ValueError("SALES_V2_UNKNOWN_CHECK")
    return {
        "criterion_type": "DETERMINISTIC_BOOLEAN",
        "measurement": {"expected": True},
        "evaluator_type": "SYNTHETIC_SALES",
        "evaluator_version": "2",
        "required_evidence_kinds": [
            "NATIVE_EXECUTION_ARTIFACT",
            "PUBLISHED_SYNTHETIC_SOURCE",
        ],
        "applicability": {
            "check": check,
            "sourceContentDigest": SOURCE_DIGEST,
            "contractDigest": CONTRACT_DIGEST,
        },
    }


def evaluate(criterion, source, report, reference):
    if not isinstance(criterion, dict):
        return "UNKNOWN", "SALES_V2_EXACT_CRITERION_REQUIRED"
    check = criterion.get("applicability", {}).get("check")
    if check not in CHECKS or any(
        criterion.get(k) != v for k, v in criterion_candidate(check).items()
    ):
        return "UNKNOWN", "SALES_V2_EXACT_CRITERION_REQUIRED"
    if canonical_digest(source) != SOURCE_DIGEST:
        return "UNKNOWN", "SALES_V2_EXACT_SOURCE_REQUIRED"
    return evaluate_sales(check, source, report, reference)
