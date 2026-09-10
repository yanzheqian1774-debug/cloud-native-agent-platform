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
