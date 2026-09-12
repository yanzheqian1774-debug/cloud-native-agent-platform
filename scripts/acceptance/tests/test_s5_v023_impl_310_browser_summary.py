from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "s5_v023_impl_310_browser_summary.py"
SPEC = importlib.util.spec_from_file_location("s5_310_summary", MODULE_PATH)
assert SPEC and SPEC.loader
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


def report(status: str = "passed", title: str = SUMMARY.EXPECTED_TITLE) -> dict:
    return {
        "suites": [
            {
                "specs": [
                    {
                        "title": title,
                        "tests": [{"results": [{"status": status}]}],
                    }
                ]
            }
        ]
    }


def step(title: str, line: int, *, failed: bool = False) -> dict:
    value = {
        "title": title,
        "location": {
            "file": f"/runner/work/repository/{SUMMARY.TEST_SPEC_SUFFIX}",
            "line": line,
            "column": 3,
        },
        "duration": 5,
    }
    if failed:
        value["error"] = {"message": "locator and secret must not escape"}
    return value


def ready_startup(tmp_path: Path) -> Path:
    path = tmp_path / "startup.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "s5-v023-impl-310-fixture-startup.v1",
                "state": "READY",
                "lastStartedStage": "LISTENER_READINESS",
                "lastCompletedStage": "LISTENER_READINESS",
                "exceptionCategory": "NONE",
                "reasonCode": "NONE",
            }
        )
    )
    return path


def test_summary_accepts_exact_single_success_without_copying_raw_output(
    tmp_path,
) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps({**report(), "errors": ["bootstrap-secret-value"]}))
    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="success",
        static_stages={"build": "success", "eslint": "success", "discovery": "success"},
        startup_status_path=ready_startup(tmp_path),
    )
    assert passed
    assert summary["counts"] == {
        "selected": 1,
        "executed": 1,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert "bootstrap-secret-value" not in json.dumps(summary)
    assert summary["securityEvidence"]["noPrivateApiFallback"] is True


def test_summary_fails_closed_for_skip_timeout_or_missing_report(tmp_path) -> None:
    cases = (("skipped", "SCENARIO_SKIPPED"), ("timedOut", "BROWSER_TIMEOUT"))
    for status, category in cases:
        raw = tmp_path / f"{status}.json"
        raw.write_text(json.dumps(report(status)))
        summary, passed = SUMMARY.build_summary(
            report_path=raw,
            commit_sha="a" * 40,
            tree_sha="b" * 40,
            execution_outcome="failure",
            static_stages={"build": "success"},
            startup_status_path=ready_startup(tmp_path),
        )
        assert not passed
        assert summary["failureCategory"] == category
        assert summary["securityEvidence"]["available"] is False

    skipped_without_result = report()
    skipped_without_result["suites"][0]["specs"][0]["tests"] = [
        {"expectedStatus": "skipped", "results": []}
    ]
    raw = tmp_path / "skipped-without-result.json"
    raw.write_text(json.dumps(skipped_without_result))
    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="success",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )
    assert not passed
    assert summary["counts"]["skipped"] == 1
    assert summary["failureCategory"] == "SCENARIO_SKIPPED"

    summary, passed = SUMMARY.build_summary(
        report_path=tmp_path / "missing.json",
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="skipped",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )
    assert not passed
    assert summary["failureCategory"] == "REPORT_UNAVAILABLE"


def test_summary_fails_closed_for_missing_or_failed_startup_diagnostics(
    tmp_path,
) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(report()))
    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="success",
        static_stages={"build": "success"},
        startup_status_path=tmp_path / "missing-startup.json",
    )
    assert not passed
    assert summary["failureCategory"] == "FIXTURE_DIAGNOSTIC_UNAVAILABLE"
    assert summary["fixtureStartup"]["reasonCode"] == "UNKNOWN"

    startup = tmp_path / "failed-startup.json"
    startup.write_text(
        json.dumps(
            {
                "schemaVersion": "s5-v023-impl-310-fixture-startup.v1",
                "state": "FAILED",
                "lastStartedStage": "DATABASE_CONNECTION",
                "lastCompletedStage": "NONE",
                "exceptionCategory": "CONNECTION_ERROR",
                "reasonCode": "DATABASE_CONNECTION_FAILED",
                "exception": "postgresql://operator:secret@database/session-token",
            }
        )
    )
    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="failure",
        static_stages={"build": "success"},
        startup_status_path=startup,
    )
    assert not passed
    assert summary["failureCategory"] == "FIXTURE_STARTUP_FAILURE"
    assert summary["fixtureStartup"] == {
        "availability": "AVAILABLE",
        "state": "FAILED",
        "lastStartedStage": "DATABASE_CONNECTION",
        "lastCompletedStage": "NONE",
        "exceptionCategory": "CONNECTION_ERROR",
        "reasonCode": "DATABASE_CONNECTION_FAILED",
    }
    assert "secret" not in json.dumps(summary)


def test_summary_emits_only_whitelisted_step_position_and_counts(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    value = report("timedOut")
    value["suites"][0]["specs"][0]["tests"][0]["results"][0]["steps"] = [
        step("FULL_LOGIN_FORM", 40),
        step("FULL_LOGIN_SUBMIT_CLICK", 45),
        step("FULL_LOGIN_POST_REQUEST_OBSERVED", 50),
        step("FULL_LOGIN_POST_RESPONSE_OBSERVED", 55),
        step("FULL_LOGIN_POST_STATUS_ASSERTION", 60),
        step("FULL_LOGIN_POST_LOCATION_ASSERTION", 65),
        step("FULL_SESSION_READY", 70, failed=True),
        step("untrusted locator https://example.invalid/?token=secret", 999),
    ]
    raw.write_text(json.dumps(value))

    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="failure",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )

    assert not passed
    assert summary["failureCategory"] == "BROWSER_TIMEOUT"
    assert summary["stepDiagnostics"] == {
        "availability": "AVAILABLE",
        "lastCompletedStep": "FULL_LOGIN_POST_LOCATION_ASSERTION",
        "lastCompletedLine": 65,
        "firstFailedOrIncompleteStep": "FULL_SESSION_READY",
        "firstFailedOrIncompleteLine": 70,
        "failureCategory": "TIMEOUT",
        "counts": {
            "expected": len(SUMMARY.TEST_STEP_IDS),
            "started": 7,
            "completed": 6,
            "failedOrIncomplete": 1,
        },
    }
    serialized = json.dumps(summary)
    assert "locator" not in serialized
    assert "example.invalid" not in serialized
    assert "secret" not in serialized


def test_summary_marks_missing_step_without_overriding_browser_result(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    value = report("failed")
    value["suites"][0]["specs"][0]["tests"][0]["results"][0]["steps"] = [
        step("FULL_LOGIN_FORM", 40)
    ]
    raw.write_text(json.dumps(value))

    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="failure",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )

    assert not passed
    assert summary["failureCategory"] == "BROWSER_ASSERTION_OR_EXECUTION_FAILURE"
    assert summary["stepDiagnostics"]["lastCompletedStep"] == "FULL_LOGIN_FORM"
    assert (
        summary["stepDiagnostics"]["firstFailedOrIncompleteStep"]
        == "FULL_LOGIN_SUBMIT_CLICK"
    )
    assert isinstance(summary["stepDiagnostics"]["firstFailedOrIncompleteLine"], int)
    assert summary["stepDiagnostics"]["failureCategory"] == "INCOMPLETE"


def test_summary_emits_only_whitelisted_login_response_diagnostics(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    value = report("failed")
    result = value["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result["steps"] = [
        step("FULL_LOGIN_FORM", 40),
        step("FULL_LOGIN_SUBMIT_CLICK", 45),
        step("FULL_LOGIN_POST_REQUEST_OBSERVED", 50),
        step("FULL_LOGIN_POST_RESPONSE_OBSERVED", 55),
        step("FULL_LOGIN_POST_STATUS_ASSERTION", 60, failed=True),
    ]
    result["annotations"] = [
        {"type": "S5_310_LOGIN_REQUEST_OBSERVED", "description": "true"},
        {"type": "S5_310_LOGIN_RESPONSE_OBSERVED", "description": "true"},
        {"type": "S5_310_LOGIN_HTTP_STATUS", "description": "422"},
        {"type": "S5_310_LOGIN_LOCATION_CLASS", "description": "MISSING"},
        {
            "type": "untrusted",
            "description": "https://example.invalid/workbench?token=secret",
        },
    ]
    raw.write_text(json.dumps(value))

    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="failure",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )

    assert not passed
    assert summary["loginSubmitDiagnostics"] == {
        "availability": "AVAILABLE",
        "requestObserved": True,
        "responseObserved": True,
        "httpStatus": 422,
        "locationClass": "MISSING",
        "failureCategory": "ASSERTION_OR_EXECUTION_FAILURE",
    }
    serialized = json.dumps(summary)
    assert "example.invalid" not in serialized
    assert "secret" not in serialized


def test_summary_rejects_ambiguous_or_unapproved_login_diagnostics(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    value = report("failed")
    result = value["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result["steps"] = [step("FULL_LOGIN_FORM", 40)]
    result["annotations"] = [
        {"type": "S5_310_LOGIN_REQUEST_OBSERVED", "description": "true"},
        {"type": "S5_310_LOGIN_REQUEST_OBSERVED", "description": "false"},
        {"type": "S5_310_LOGIN_RESPONSE_OBSERVED", "description": "secret"},
        {"type": "S5_310_LOGIN_HTTP_STATUS", "description": "999"},
        {"type": "S5_310_LOGIN_LOCATION_CLASS", "description": "/workbench"},
    ]
    raw.write_text(json.dumps(value))

    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="failure",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )

    assert not passed
    assert summary["loginSubmitDiagnostics"] == {
        "availability": "AVAILABLE",
        "requestObserved": "UNKNOWN",
        "responseObserved": "UNKNOWN",
        "httpStatus": "UNKNOWN",
        "locationClass": "UNKNOWN",
        "failureCategory": "INCOMPLETE",
    }
    assert "secret" not in json.dumps(summary)


def test_summary_step_allowlist_matches_the_real_spec() -> None:
    source = (
        Path(__file__).parents[3]
        / "console/frontend/tests/e2e/digital-employee-work-participation.real.spec.ts"
    ).read_text()

    assert all(source.count(f'"{step_id}"') == 1 for step_id in SUMMARY.TEST_STEP_IDS)


def test_step_diagnostic_error_does_not_replace_browser_result(
    tmp_path, monkeypatch
) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(report("timedOut")))
    monkeypatch.setattr(
        SUMMARY,
        "_step_diagnostics",
        lambda _test: (_ for _ in ()).throw(ValueError("secret locator")),
    )

    summary, passed = SUMMARY.build_summary(
        report_path=raw,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        execution_outcome="failure",
        static_stages={"build": "success"},
        startup_status_path=ready_startup(tmp_path),
    )

    assert not passed
    assert summary["failureCategory"] == "BROWSER_TIMEOUT"
    assert summary["stepDiagnostics"]["availability"] == "INVALID"
    assert "secret locator" not in json.dumps(summary)
