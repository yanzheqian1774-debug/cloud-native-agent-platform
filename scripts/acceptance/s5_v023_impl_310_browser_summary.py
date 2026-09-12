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
TEST_STEP_IDS = (
    "FULL_LOGIN_FORM",
    "FULL_LOGIN_SUBMIT_CLICK",
    "FULL_LOGIN_POST_REQUEST_OBSERVED",
    "FULL_LOGIN_POST_RESPONSE_OBSERVED",
    "FULL_LOGIN_POST_STATUS_ASSERTION",
    "FULL_LOGIN_POST_LOCATION_ASSERTION",
    "FULL_SESSION_READY",
    "EMPLOYEE_LIST_NAVIGATION",
    "EMPLOYEE_LIST_NAVIGATION_STATUS",
    "EMPLOYEE_LIST_ROUTE_ASSERTION",
    "EMPLOYEE_LIST_SHELL_VISIBLE",
    "EMPLOYEE_LIST_REQUEST_OBSERVED",
    "EMPLOYEE_LIST_RESPONSE_OBSERVED",
    "EMPLOYEE_LIST_STATUS_ASSERTION",
    "EMPLOYEE_LIST_BUTTON_COUNT",
    "EMPLOYEE_LIST_BUTTON_VISIBLE",
    "EMPLOYEE_EXACT_UI_READ",
    "EMPLOYEE_EXACT_API_READ",
    "AGENT_EXACT_API_READ",
    "EMPLOYEE_DETAIL_RENDER",
    "EMPLOYEE_PAGINATION_FIRST",
    "EMPLOYEE_PAGINATION_NEXT",
    "AGENT_PAGINATION_FIRST",
    "AGENT_PAGINATION_NEXT",
    "WORK_CHAIN_INITIAL_READ",
    "WORK_CHAIN_RELOAD_READ",
    "PARENT_ASSIGNMENT_DENIAL",
    "PARENT_ATTEMPT_DENIAL",
    "PARENT_AGENT_DENIAL",
    "PLACEMENT_GRANT_REVOKE",
    "PLACEMENT_REVOKED_DENIAL",
    "FULL_SESSION_LOGOUT",
    "LISTER_LOGIN_FORM",
    "LISTER_LOGIN_SUBMIT_REDIRECT",
    "LISTER_SESSION_READY",
    "LISTER_LIST_ALLOWED",
    "LISTER_EXACT_DENIED",
    "WRONG_SCOPE_LOGIN_FORM",
    "WRONG_SCOPE_LOGIN_SUBMIT_REDIRECT",
    "WRONG_SCOPE_SESSION_READY",
    "WRONG_SCOPE_EXACT_DENIED",
    "WRONG_GRANT_LOGIN_FORM",
    "WRONG_GRANT_LOGIN_SUBMIT_REDIRECT",
    "WRONG_GRANT_SESSION_READY",
    "WRONG_GRANT_EXACT_DENIED",
    "TRANSPORT_BOUNDARY_ASSERTIONS",
)
TEST_STEP_SET = frozenset(TEST_STEP_IDS)
FULL_LOGIN_SUBMIT_STEP_SET = frozenset(TEST_STEP_IDS[1:6])
EMPLOYEE_LIST_STEP_SET = frozenset(TEST_STEP_IDS[7:16])
LOGIN_DIAGNOSTIC_TYPES = {
    "S5_310_LOGIN_REQUEST_OBSERVED": "requestObserved",
    "S5_310_LOGIN_RESPONSE_OBSERVED": "responseObserved",
    "S5_310_LOGIN_HTTP_STATUS": "httpStatus",
    "S5_310_LOGIN_LOCATION_CLASS": "locationClass",
}
EMPLOYEE_LIST_DIAGNOSTIC_TYPES = {
    "S5_310_EMPLOYEE_LIST_NAVIGATION_STATUS": "navigationStatus",
    "S5_310_EMPLOYEE_LIST_ROUTE_CLASS": "routeClass",
    "S5_310_EMPLOYEE_LIST_REQUEST_OBSERVED": "requestObserved",
    "S5_310_EMPLOYEE_LIST_RESPONSE_OBSERVED": "responseObserved",
    "S5_310_EMPLOYEE_LIST_HTTP_STATUS": "httpStatus",
}
EMPLOYEE_LIST_ROUTE_CLASSES = {"EXPECTED", "OTHER", "UNKNOWN"}
LOCATION_CLASSES = {"EXPECTED_WORKBENCH", "OTHER", "MISSING", "UNKNOWN"}
LOGIN_FAILURE_CATEGORIES = {
    "NONE",
    "INCOMPLETE",
    "TIMEOUT",
    "INTERRUPTED",
    "ASSERTION_OR_EXECUTION_FAILURE",
    "UNKNOWN",
}
TEST_SPEC_SUFFIX = (
    "console/frontend/tests/e2e/digital-employee-work-participation.real.spec.ts"
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


def _declared_step_lines() -> dict[str, int]:
    try:
        lines = (Path(__file__).parents[2] / TEST_SPEC_SUFFIX).read_text().splitlines()
    except OSError:
        return {}
    return {
        step_id: index
        for step_id in TEST_STEP_IDS
        for index, line in enumerate(lines, start=1)
        if f'"{step_id}"' in line
    }


def _step_line(
    step: dict[str, Any], step_id: str, declared_lines: dict[str, int]
) -> int | str:
    location = step.get("location")
    if not isinstance(location, dict):
        return declared_lines.get(step_id, "UNKNOWN")
    path = location.get("file")
    line = location.get("line")
    if (
        not isinstance(path, str)
        or not path.replace("\\", "/").endswith(TEST_SPEC_SUFFIX)
        or isinstance(line, bool)
        or not isinstance(line, int)
        or not 1 <= line <= 1000
    ):
        return declared_lines.get(step_id, "UNKNOWN")
    return line


def _empty_step_diagnostics(availability: str = "UNAVAILABLE") -> dict[str, Any]:
    return {
        "availability": availability,
        "lastCompletedStep": "UNKNOWN",
        "lastCompletedLine": "UNKNOWN",
        "firstFailedOrIncompleteStep": "UNKNOWN",
        "firstFailedOrIncompleteLine": "UNKNOWN",
        "failureCategory": "UNKNOWN",
        "counts": {
            "expected": len(TEST_STEP_IDS),
            "started": 0,
            "completed": 0,
            "failedOrIncomplete": 0,
        },
    }


def _step_diagnostics(test: dict[str, Any] | None) -> dict[str, Any]:
    unavailable = _empty_step_diagnostics()
    if test is None:
        return unavailable
    results = test.get("results")
    if (
        not isinstance(results, list)
        or not results
        or not isinstance(results[-1], dict)
    ):
        return unavailable
    result = results[-1]
    steps = result.get("steps")
    if not isinstance(steps, list):
        return unavailable
    observed: dict[str, dict[str, Any]] = {}

    def visit(values: list[Any]) -> None:
        for value in values:
            if not isinstance(value, dict):
                continue
            title = value.get("title")
            if (
                isinstance(title, str)
                and title in TEST_STEP_SET
                and title not in observed
            ):
                observed[title] = value
            children = value.get("steps")
            if isinstance(children, list):
                visit(children)

    visit(steps)
    if not observed:
        return unavailable
    declared_lines = _declared_step_lines()
    last_completed = "NONE"
    last_completed_line: int | str = "UNKNOWN"
    first_incomplete = "NONE"
    first_incomplete_line: int | str = "UNKNOWN"
    completed = 0
    failure_category = "NONE"
    status = result.get("status")
    for step_id in TEST_STEP_IDS:
        step = observed.get(step_id)
        if step is None:
            first_incomplete = step_id
            first_incomplete_line = declared_lines.get(step_id, "UNKNOWN")
            failure_category = "INCOMPLETE"
            break
        if step.get("error") is not None:
            first_incomplete = step_id
            first_incomplete_line = _step_line(step, step_id, declared_lines)
            failure_category = {
                "timedOut": "TIMEOUT",
                "interrupted": "INTERRUPTED",
                "failed": "ASSERTION_OR_EXECUTION_FAILURE",
            }.get(status, "UNKNOWN")
            break
        completed += 1
        last_completed = step_id
        last_completed_line = _step_line(step, step_id, declared_lines)
    if first_incomplete == "NONE" and status != "passed":
        first_incomplete = "UNKNOWN"
        failure_category = "TEST_FAILURE_OUTSIDE_STEP"
    failed_or_incomplete = 0 if first_incomplete == "NONE" else 1
    return {
        "availability": "AVAILABLE",
        "lastCompletedStep": last_completed,
        "lastCompletedLine": last_completed_line,
        "firstFailedOrIncompleteStep": first_incomplete,
        "firstFailedOrIncompleteLine": first_incomplete_line,
        "failureCategory": failure_category,
        "counts": {
            "expected": len(TEST_STEP_IDS),
            "started": len(observed),
            "completed": completed,
            "failedOrIncomplete": failed_or_incomplete,
        },
    }


def _safe_step_diagnostics(test: dict[str, Any] | None) -> dict[str, Any]:
    try:
        return _step_diagnostics(test)
    except (KeyError, TypeError, ValueError, OSError):
        return _empty_step_diagnostics("INVALID")


def _login_submit_diagnostics(
    test: dict[str, Any] | None, step_diagnostics: dict[str, Any]
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "availability": "UNAVAILABLE",
        "requestObserved": "UNKNOWN",
        "responseObserved": "UNKNOWN",
        "httpStatus": "UNKNOWN",
        "locationClass": "UNKNOWN",
        "failureCategory": "UNKNOWN",
    }
    if test is None:
        return values
    results = test.get("results")
    if (
        not isinstance(results, list)
        or not results
        or not isinstance(results[-1], dict)
    ):
        return values
    values["availability"] = "AVAILABLE"
    annotations = results[-1].get("annotations")
    if not isinstance(annotations, list):
        annotations = []
    observed: dict[str, list[str]] = {
        output: [] for output in LOGIN_DIAGNOSTIC_TYPES.values()
    }
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        output = LOGIN_DIAGNOSTIC_TYPES.get(annotation.get("type"))
        description = annotation.get("description")
        if output is not None and isinstance(description, str):
            observed[output].append(description)
    for output in ("requestObserved", "responseObserved"):
        descriptions = observed[output]
        if len(descriptions) == 1 and descriptions[0] in {"true", "false"}:
            values[output] = descriptions[0] == "true"
    descriptions = observed["httpStatus"]
    if len(descriptions) == 1 and descriptions[0].isdigit():
        status = int(descriptions[0])
        if 100 <= status <= 599:
            values["httpStatus"] = status
    descriptions = observed["locationClass"]
    if len(descriptions) == 1 and descriptions[0] in LOCATION_CLASSES:
        values["locationClass"] = descriptions[0]
    failed_step = step_diagnostics.get("firstFailedOrIncompleteStep")
    if failed_step in FULL_LOGIN_SUBMIT_STEP_SET:
        category = step_diagnostics.get("failureCategory")
        if category in LOGIN_FAILURE_CATEGORIES:
            values["failureCategory"] = category
    elif all(
        step_diagnostics.get("lastCompletedStep") in TEST_STEP_SET
        and TEST_STEP_IDS.index(step_diagnostics["lastCompletedStep"])
        >= TEST_STEP_IDS.index(step_id)
        for step_id in FULL_LOGIN_SUBMIT_STEP_SET
    ):
        values["failureCategory"] = "NONE"
    return values


def _employee_list_diagnostics(
    test: dict[str, Any] | None, step_diagnostics: dict[str, Any]
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "availability": "UNAVAILABLE",
        "navigationStatus": "UNKNOWN",
        "routeClass": "UNKNOWN",
        "requestObserved": "UNKNOWN",
        "responseObserved": "UNKNOWN",
        "httpStatus": "UNKNOWN",
        "failureCategory": "UNKNOWN",
    }
    if test is None:
        return values
    results = test.get("results")
    if (
        not isinstance(results, list)
        or not results
        or not isinstance(results[-1], dict)
    ):
        return values
    values["availability"] = "AVAILABLE"
    annotations = results[-1].get("annotations")
    if not isinstance(annotations, list):
        annotations = []
    observed: dict[str, list[str]] = {
        output: [] for output in EMPLOYEE_LIST_DIAGNOSTIC_TYPES.values()
    }
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        output = EMPLOYEE_LIST_DIAGNOSTIC_TYPES.get(annotation.get("type"))
        description = annotation.get("description")
        if output is not None and isinstance(description, str):
            observed[output].append(description)
    for output in ("requestObserved", "responseObserved"):
        descriptions = observed[output]
        if len(descriptions) == 1 and descriptions[0] in {"true", "false"}:
            values[output] = descriptions[0] == "true"
    descriptions = observed["httpStatus"]
    if len(descriptions) == 1 and descriptions[0].isdigit():
        status = int(descriptions[0])
        if 100 <= status <= 599:
            values["httpStatus"] = status
    descriptions = observed["navigationStatus"]
    if len(descriptions) == 1 and descriptions[0].isdigit():
        status = int(descriptions[0])
        if 100 <= status <= 599:
            values["navigationStatus"] = status
    descriptions = observed["routeClass"]
    if len(descriptions) == 1 and descriptions[0] in EMPLOYEE_LIST_ROUTE_CLASSES:
        values["routeClass"] = descriptions[0]
    failed_step = step_diagnostics.get("firstFailedOrIncompleteStep")
    if failed_step in EMPLOYEE_LIST_STEP_SET:
        category = step_diagnostics.get("failureCategory")
        if category in LOGIN_FAILURE_CATEGORIES:
            values["failureCategory"] = category
    elif all(
        step_diagnostics.get("lastCompletedStep") in TEST_STEP_SET
        and TEST_STEP_IDS.index(step_diagnostics["lastCompletedStep"])
        >= TEST_STEP_IDS.index(step_id)
        for step_id in EMPLOYEE_LIST_STEP_SET
    ):
        values["failureCategory"] = "NONE"
    return values


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
    expected_test = next(
        (test for test in tests if test.get("title") == EXPECTED_TITLE), None
    )
    step_diagnostics = _safe_step_diagnostics(expected_test)
    login_submit_diagnostics = _login_submit_diagnostics(
        expected_test, step_diagnostics
    )
    employee_list_diagnostics = _employee_list_diagnostics(
        expected_test, step_diagnostics
    )
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
        "stepDiagnostics": step_diagnostics,
        "loginSubmitDiagnostics": login_submit_diagnostics,
        "employeeListDiagnostics": employee_list_diagnostics,
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
