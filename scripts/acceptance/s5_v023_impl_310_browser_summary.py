#!/usr/bin/env python3
"""Emit a bounded, secret-free summary for the IMPL-310 real browser gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_TITLE = (
    "REAL_SERVICE trusted Digital Employee reads preserve authorization and identity"
)
SECURITY_REASON_CODES = (
    "AUTHENTICATION_REQUIRED",
    "AUTHORIZATION_NOT_FOUND",
    "EMPLOYEE_NOT_FOUND",
    "PLACEMENT_NOT_FOUND",
)
STARTUP_STAGES = {
    "DATABASE_CONNECTION",
    "DATABASE_MIGRATION",
    "SAMPLE_PREPARATION",
    "AUTHORIZATION_PREPARATION",
    "TLS_CONFIGURATION",
    "LISTENER_READINESS",
}
STARTUP_EXCEPTION_CATEGORIES = {
    "NONE",
    "CONNECTION_ERROR",
    "DATABASE_ERROR",
    "TIMEOUT_ERROR",
    "FILESYSTEM_ERROR",
    "VALIDATION_ERROR",
    "TLS_ERROR",
    "UNKNOWN",
}
STARTUP_REASON_CODES = {
    "NONE",
    "DATABASE_CONNECTION_FAILED",
    "DATABASE_MIGRATION_FAILED",
    "SAMPLE_PREPARATION_FAILED",
    "AUTHORIZATION_PREPARATION_FAILED",
    "TLS_CONFIGURATION_FAILED",
    "LISTENER_READINESS_FAILED",
    "UNKNOWN",
}


def _startup_status(path: Path) -> tuple[dict[str, str], str]:
    unavailable = {
        "state": "UNKNOWN",
        "lastStartedStage": "UNKNOWN",
        "lastCompletedStage": "UNKNOWN",
        "exceptionCategory": "UNKNOWN",
        "reasonCode": "UNKNOWN",
    }
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return unavailable, "UNAVAILABLE"
    except (OSError, json.JSONDecodeError):
        return unavailable, "INVALID"
    if not isinstance(raw, dict):
        return unavailable, "INVALID"
    state = raw.get("state")
    started = raw.get("lastStartedStage")
    completed = raw.get("lastCompletedStage")
    if (
        raw.get("schemaVersion") != "s5-v023-impl-310-fixture-startup.v1"
        or state not in {"STARTING", "READY", "FAILED"}
        or started not in STARTUP_STAGES
        or completed not in {"NONE", *STARTUP_STAGES}
    ):
        return unavailable, "INVALID"
    category = raw.get("exceptionCategory")
    reason_code = raw.get("reasonCode")
    return {
        "state": state,
        "lastStartedStage": started,
        "lastCompletedStage": completed,
        "exceptionCategory": (
            category if category in STARTUP_EXCEPTION_CATEGORIES else "UNKNOWN"
        ),
        "reasonCode": reason_code if reason_code in STARTUP_REASON_CODES else "UNKNOWN",
    }, "AVAILABLE"


def _tests(report: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def visit(suite: dict[str, Any]) -> None:
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                item = dict(test)
                item["title"] = spec.get("title", "")
                found.append(item)
        for child in suite.get("suites", []):
            visit(child)

    for suite in report.get("suites", []):
        visit(suite)
    return found


def build_summary(
    *,
    report_path: Path,
    commit_sha: str,
    tree_sha: str,
    execution_outcome: str,
    static_stages: dict[str, str],
    startup_status_path: Path,
) -> tuple[dict[str, Any], bool]:
    report: dict[str, Any] | None = None
    report_state = "AVAILABLE"
    try:
        report = json.loads(report_path.read_text())
        if not isinstance(report, dict):
            raise ValueError
    except FileNotFoundError:
        report_state = "UNAVAILABLE"
    except (json.JSONDecodeError, ValueError):
        report_state = "INVALID"

    tests = _tests(report) if report is not None else []
    selected = len(tests)
    statuses: list[str] = []
    for test in tests:
        results = test.get("results", [])
        if results:
            statuses.append(results[-1].get("status", "not-run"))
        elif test.get("expectedStatus") == "skipped":
            statuses.append("skipped")
        else:
            statuses.append("not-run")
    skipped = sum(status == "skipped" for status in statuses)
    passed = sum(status == "passed" for status in statuses)
    failed = sum(status in {"failed", "timedOut", "interrupted"} for status in statuses)
    executed = sum(status not in {"skipped", "not-run"} for status in statuses)
    titles = sorted({str(test.get("title", "")) for test in tests})
    static_ok = bool(static_stages) and all(
        outcome == "success" for outcome in static_stages.values()
    )
    exact_selection = selected == 1 and titles == [EXPECTED_TITLE]
    startup, startup_state = _startup_status(startup_status_path)
    startup_ok = (
        startup_state == "AVAILABLE"
        and startup["state"] == "READY"
        and startup["lastCompletedStage"] == "LISTENER_READINESS"
        and startup["exceptionCategory"] == "NONE"
        and startup["reasonCode"] == "NONE"
    )
    passed_gate = (
        static_ok
        and startup_ok
        and report_state == "AVAILABLE"
        and execution_outcome == "success"
        and exact_selection
        and executed == 1
        and passed == 1
        and failed == 0
        and skipped == 0
    )

    if not static_ok:
        failure_category = "STATIC_STAGE_FAILURE"
    elif startup_state == "UNAVAILABLE":
        failure_category = "FIXTURE_DIAGNOSTIC_UNAVAILABLE"
    elif startup_state == "INVALID":
        failure_category = "FIXTURE_DIAGNOSTIC_INVALID"
    elif startup["state"] == "FAILED":
        failure_category = "FIXTURE_STARTUP_FAILURE"
    elif not startup_ok:
        failure_category = "FIXTURE_NOT_READY"
    elif report_state == "UNAVAILABLE":
        failure_category = "REPORT_UNAVAILABLE"
    elif report_state == "INVALID":
        failure_category = "REPORT_INVALID"
    elif not exact_selection:
        failure_category = "SCENARIO_SELECTION_MISMATCH"
    elif skipped:
        failure_category = "SCENARIO_SKIPPED"
    elif "timedOut" in statuses:
        failure_category = "BROWSER_TIMEOUT"
    elif execution_outcome != "success" or failed or passed != 1:
        failure_category = "BROWSER_ASSERTION_OR_EXECUTION_FAILURE"
    else:
        failure_category = "NONE"

    summary: dict[str, Any] = {
        "schemaVersion": "s5-v023-impl-310-browser-evidence.v1",
        "candidateCommitSha": commit_sha,
        "candidateTreeSha": tree_sha,
        "status": "PASSED" if passed_gate else "FAILED",
        "failureCategory": failure_category,
        "reportState": report_state,
        "executionOutcome": execution_outcome,
        "fixtureStartup": {"availability": startup_state, **startup},
        "staticStages": dict(sorted(static_stages.items())),
        "counts": {
            "selected": selected,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "expectedScenario": EXPECTED_TITLE,
        "securityEvidence": {
            "available": passed_gate,
            "assertedReasonCodes": list(SECURITY_REASON_CODES) if passed_gate else [],
            "formalHttpsSession": passed_gate,
            "dynamicPlacementGrantRevocation": passed_gate,
            "noBrowserIdentityHeaders": passed_gate,
            "noPrivateApiFallback": passed_gate,
        },
    }
    return summary, passed_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--execution-outcome", required=True)
    parser.add_argument("--startup-status", required=True, type=Path)
    parser.add_argument("--static-stage", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    stages: dict[str, str] = {}
    for value in args.static_stage:
        name, separator, outcome = value.partition("=")
        if not separator or not name or not outcome or name in stages:
            raise SystemExit("STATIC_STAGE_INVALID")
        stages[name] = outcome
    summary, passed = build_summary(
        report_path=args.report,
        commit_sha=args.commit_sha,
        tree_sha=args.tree_sha,
        execution_outcome=args.execution_outcome,
        static_stages=stages,
        startup_status_path=args.startup_status,
    )
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
