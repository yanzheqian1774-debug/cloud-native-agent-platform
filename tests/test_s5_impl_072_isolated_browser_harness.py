from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1] / "scripts/acceptance/isolated_browser_harness.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("isolated_browser_harness", MODULE_PATH)
assert SPEC and SPEC.loader
harness_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness_module)
Harness = harness_module.Harness
release_manifest = harness_module.release_manifest
minimum_disclosure = importlib.import_module("minimum_disclosure")
build_preflight = importlib.import_module("browser_build_preflight")
KNOWLEDGE_LIFECYCLE_TITLE = (
    "completes the real Knowledge lifecycle, retrieval, recovery and purge journey"
)


def summary_report(status="failed", *, known=True):
    name, title = next(iter(harness_module.FIRST_FAILURE_ASSERTION_IDS))
    return {
        "stats": {"expected": 0, "unexpected": 1, "skipped": 0, "flaky": 0},
        "suites": [
            {
                "file": name if known else "private-dynamic.spec.ts",
                "specs": [
                    {
                        "title": title if known else "PRIVATE_DYNAMIC_TITLE",
                        "line": 42,
                        "tests": [
                            {
                                "status": "unexpected",
                                "results": [
                                    {
                                        "status": status,
                                        "errors": [
                                            {
                                                "message": "PRIVATE_MESSAGE "
                                                "expect(locator)"
                                            }
                                        ],
                                        "attachments": [
                                            {"path": "/tmp/PRIVATE_ATTACHMENT"}
                                        ],
                                        "locator": "PRIVATE_LOCATOR",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def make_summary(report, restart_count=0):
    raw = json.dumps(report).encode()
    failure = harness_module.sanitized_first_failure_record(
        raw, "journey-274", restart_count
    )
    return harness_module.build_failure_summary(
        raw,
        failure,
        {
            "buildModeIdentity": "LIVE_DEMO",
            "frontendManifestDigest": "a" * 64,
        },
    )


@pytest.mark.parametrize(
    "mapping", list(harness_module.FIRST_FAILURE_ASSERTION_IDS.items())
)
def test_summary_static_scenarios(mapping):
    (name, title), scenario = mapping
    report = summary_report()
    report["suites"][0]["file"] = name
    report["suites"][0]["specs"][0]["title"] = title
    summary = make_summary(report)
    assert len(harness_module.FIRST_FAILURE_ASSERTION_IDS) == 19
    assert summary["scenarioId"] == scenario
    assert summary["spec"] == "console/frontend/tests/e2e/" + name
    assert summary["sourceLine"] == 42
    assert summary["locationKind"] == "TEST_DECLARATION"
    encoded = harness_module.encode_failure_summary(summary)
    assert "PRIVATE" not in encoded
    assert "\n" not in encoded


@pytest.mark.parametrize("status", ["failed", "timedOut", "interrupted"])
def test_summary_counts_and_unknown_scenario(status):
    summary = make_summary(summary_report(status, known=False))
    assert summary["scenarioId"] == "NOT_RETAINED"
    assert summary["spec"] is None and summary["sourceLine"] is None
    assert summary["counts"] == {
        "selected": 1,
        "executed": 1,
        "passed": 0,
        "failed": 1,
        "skipped": 0,
        "flaky": 0,
    }
    assert "PRIVATE" not in harness_module.encode_failure_summary(summary)


def test_summary_multiple_suites_skips_and_missing_counts():
    report = summary_report()
    report["suites"].append(
        {
            "specs": [
                {
                    "tests": [
                        {"status": "expected", "results": [{"status": "passed"}]},
                        {"status": "skipped", "results": []},
                    ]
                }
            ]
        }
    )
    report["stats"].update(expected=1, skipped=1)
    assert harness_module.summary_counts(report) == {
        "selected": 3,
        "executed": 2,
        "passed": 1,
        "failed": 1,
        "skipped": 1,
        "flaky": 0,
    }
    report["stats"]["expected"] = 4
    assert all(v is None for v in harness_module.summary_counts(report).values())
    assert all(v is None for v in harness_module.summary_counts({}).values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("extra", "PRIVATE"),
        ("sourceLine", True),
        ("sourceLine", -1),
        ("spec", "/tmp/PRIVATE"),
        ("locationKind", "FAILURE_LINE"),
        ("scenarioId", "PRIVATE"),
        ("actionClass", "PRIVATE"),
        ("restartCountClass", "PRIVATE"),
        ("restartCountScope", "SCENARIO"),
        ("frontendManifestDigest", "x" * 5000),
    ],
)
def test_summary_rejects_unsafe_or_unbounded_fields(field, value):
    summary = make_summary(summary_report())
    summary[field] = value
    with pytest.raises(ValueError):
        harness_module.encode_failure_summary(summary)


def test_summary_malformed_output_is_fixed_gap(monkeypatch, capsys):
    failure = harness_module.sanitized_first_failure_record(
        b'{"stats":{"unexpected":1}}', "journey-274", 0
    )
    harness_module.emit_failure_summary(b"not json PRIVATE", failure, {})
    assert (
        capsys.readouterr().err
        == harness_module.SUMMARY_PREFIX + '{"diagnosticState":"DIAGNOSTIC_GAP"}\n'
    )


@pytest.mark.parametrize("returncode", [0, 1, 7])
@pytest.mark.parametrize("broken_summary", [False, True])
@pytest.mark.parametrize("gate_failure", [None, "scan", "immutable"])
def test_summary_main_preserves_exit_and_cleanup(
    tmp_path, monkeypatch, capsys, returncode, broken_summary, gate_failure
):
    events = []
    output = tmp_path / "playwright-output"
    output.mkdir()
    (output / "raw.txt").write_text("PRIVATE")
    args = Namespace(
        release_root=tmp_path,
        build_mode_identity=tmp_path / "identity",
        postgres_url="unused",
        postgres_validation_role="unused",
        frontend_port=1,
        qdrant_url="unused",
        command=["synthetic"],
        journey_id="journey-274",
    )

    class FakeHarness:
        runtime = release = tmp_path
        metadata_path = tmp_path / "metadata"
        token = "unused"
        url = "unused"
        restart_count = 0

        def __init__(self, args):
            pass

        def start(self):
            pass

        def serve(self, ready):
            ready.set()

        def stop(self):
            events.append("stop")

        def verify_release(self):
            events.append("immutable")
            assert not output.exists()
            if gate_failure == "immutable":
                raise RuntimeError("mandatory immutable gate")
            return {}

        def write_minimum_disclosure_evidence(self, after, code):
            assert code == (returncode or 1)
            return tmp_path / "evidence"

    monkeypatch.setattr(harness_module, "parse_args", lambda: args)
    monkeypatch.setattr(harness_module, "Harness", FakeHarness)
    monkeypatch.setattr(
        harness_module,
        "verify_build_identity",
        lambda *a: {
            "buildModeIdentity": "LIVE_DEMO",
            "frontendManifestDigest": "a" * 64,
        },
    )
    monkeypatch.setattr(
        harness_module, "verify_postgres_role_readiness", lambda *a: None
    )
    monkeypatch.setattr(
        harness_module.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            [], returncode, json.dumps(summary_report()).encode(), b"PRIVATE"
        ),
    )
    original = harness_module.build_failure_summary

    def build(*a):
        events.append("summary")
        assert output.exists()
        if broken_summary:
            raise ValueError("PRIVATE")
        return original(*a)

    monkeypatch.setattr(harness_module, "build_failure_summary", build)
    if gate_failure == "scan":

        def fail_scan(paths):
            raise RuntimeError("mandatory disclosure gate")

        monkeypatch.setattr(harness_module, "scan_generated_artifacts", fail_scan)
    if gate_failure:
        with pytest.raises(RuntimeError, match="mandatory"):
            harness_module.main()
    else:
        assert harness_module.main() == (returncode or 1)
    assert events == (
        ["stop", "immutable"]
        if gate_failure == "scan"
        else ["summary", "stop", "immutable"]
    )
    assert "PRIVATE" not in capsys.readouterr().err


def test_summary_print_failure_is_best_effort(monkeypatch):
    calls = []

    def fail_print(value, **kwargs):
        calls.append(value)
        raise OSError("PRIVATE")

    monkeypatch.setattr(harness_module, "print", fail_print, raising=False)
    raw = json.dumps(summary_report()).encode()
    failure = harness_module.sanitized_first_failure_record(raw, "journey-274", 0)
    harness_module.emit_failure_summary(
        raw,
        failure,
        {"buildModeIdentity": "LIVE_DEMO", "frontendManifestDigest": "a" * 64},
    )
    assert len(calls) == 2
    assert (
        calls[1]
        == harness_module.SUMMARY_PREFIX + '{"diagnosticState":"DIAGNOSTIC_GAP"}'
    )
    assert "PRIVATE" not in str(calls)


def test_summary_encoded_content_passes_existing_scanner(tmp_path):
    summary = make_summary(summary_report())
    encoded = harness_module.encode_failure_summary(summary)
    assert len((harness_module.SUMMARY_PREFIX + encoded).encode()) <= 4096
    artifact = tmp_path / "summary.json"
    artifact.write_text(encoded)
    minimum_disclosure.scan_generated_artifacts([artifact])


def test_summary_flaky_and_malformed_counts():
    report = summary_report()
    test = report["suites"][0]["specs"][0]["tests"][0]
    test.update(status="flaky", results=[{"status": "failed"}, {"status": "passed"}])
    report["stats"].update(unexpected=0, flaky=1)
    assert harness_module.summary_counts(report)["flaky"] == 1
    assert harness_module.summary_counts(report)["executed"] == 1
    test["results"] = [{"status": "skipped"}]
    assert all(v is None for v in harness_module.summary_counts(report).values())


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_installed_json_reporter_serializes_synthetic_steps():
    # Exercise the installed serializer, without loading tests or a browser.
    if not (
        MODULE_PATH.parents[2]
        / "console/frontend/node_modules/playwright/lib/runner/index.js"
    ).is_file():
        pytest.skip("installed frontend dependencies required for serializer probe")
    script = """
const path='./console/frontend/node_modules/playwright/lib/runner/index.js';
const {runnerReporters}=require(path);
(async()=>{
 const config={configDir:process.cwd(),config:{tags:[],reporter:[['json']]}};
 const [r]=await runnerReporters.createReporters(config,'test');
 const values=['PRIMARY_HOME_DESKTOP_NAVIGATE','WAVE3B_11_RESTART_READINESS',
   'UNIFIED_07_EMPLOYEE_MANAGEMENT']
   .map(title=>r._serializeTestStep({title,duration:12,
     error:{message:'SYNTHETIC'},steps:[]}));
 console.log(JSON.stringify(values));
})();
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=MODULE_PATH.parents[2],
        capture_output=True,
        check=True,
    )
    value = json.loads(result.stdout)
    assert value == [
        {
            "title": title,
            "duration": 12,
            "error": {"message": "SYNTHETIC"},
        }
        for title in (
            "PRIMARY_HOME_DESKTOP_NAVIGATE",
            "WAVE3B_11_RESTART_READINESS",
            "UNIFIED_07_EMPLOYEE_MANAGEMENT",
        )
    ]


def primary_step_report():
    report = summary_report()
    report["suites"][0]["file"] = "platform-support-surfaces.spec.ts"
    report["suites"][0]["specs"][0]["title"] = (
        "keeps all nineteen primary surfaces responsive and restores heading focus"
    )
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result.update(
        duration=5008,
        steps=[
            {"title": "PRIMARY_WORK_DESKTOP_NAVIGATE", "duration": 8},
            {"title": "PRIMARY_WORK_DESKTOP_HEADING_VISIBLE", "duration": 1},
            {
                "title": "PRIMARY_WORK_DESKTOP_HEADING_FOCUSED",
                "duration": 4999,
                "error": {"message": "PRIVATE locator URL"},
            },
        ],
    )
    return report


def test_step_failure_and_last_completion_are_distinct():
    summary = make_summary(primary_step_report())
    diagnostic = summary["stepDiagnostic"]
    assert diagnostic["failedStep"]["stepId"] == "PRIMARY_WORK_DESKTOP_HEADING_FOCUSED"
    assert (
        diagnostic["lastCompletedStep"]["stepId"]
        == "PRIMARY_WORK_DESKTOP_HEADING_VISIBLE"
    )
    assert diagnostic["completedStepCount"] == 2
    assert diagnostic["elapsedMs"] == 5008
    assert diagnostic["timeoutKind"] == "UNKNOWN"
    assert "PRIVATE" not in harness_module.encode_failure_summary(summary)


def wave_3b_step_report():
    report = summary_report("timedOut")
    report["suites"][0]["file"] = "wave-3b-product-technical-evidence.spec.ts"
    report["suites"][0]["specs"][0]["title"] = (
        "proves all twelve Wave 3B real-service browser journeys"
    )
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result.update(
        duration=240_000,
        steps=[
            {"title": title, "duration": 1}
            for title in list(harness_module.WAVE_3B_STEP_IDS)[
                : list(harness_module.WAVE_3B_STEP_IDS).index("WAVE3B_12_OPEN_EVIDENCE")
                + 1
            ]
        ]
        + [
            {
                "title": "WAVE3B_12_CLOSE_FOCUS_CHECK",
                "duration": 5000,
                "error": {"message": "PRIVATE locator state"},
            }
        ],
    )
    return report


def test_wave_3b_steps_are_static_sanitized_and_distinguish_failure():
    summary = make_summary(wave_3b_step_report(), restart_count=4)
    diagnostic = summary["stepDiagnostic"]
    assert diagnostic["failedStep"] == {
        "routeKey": "EVIDENCE",
        "viewportKey": "MOBILE",
        "stepId": "WAVE3B_12_CLOSE_FOCUS_CHECK",
        "actionClass": "FOCUS_CHECK",
        "elapsedMs": 5000,
    }
    assert diagnostic["lastCompletedStep"]["stepId"] == "WAVE3B_12_OPEN_EVIDENCE"
    assert diagnostic["completedStepCount"] == (
        list(harness_module.WAVE_3B_STEP_IDS).index("WAVE3B_12_OPEN_EVIDENCE") + 1
    )
    assert diagnostic["elapsedMs"] == 240_000
    assert diagnostic["timeoutKind"] == "SCENARIO"
    assert summary["actionClass"] == "FOCUS_CHECK"
    assert summary["restartCountClass"] == "ONE_OR_MORE"
    assert summary["restartCountScope"] == "SUITE_CUMULATIVE"
    encoded = harness_module.encode_failure_summary(summary)
    assert "PRIVATE" not in encoded
    assert "locator" not in encoded


def test_wave_3b_conflict_recovery_uses_exact_static_top_level_steps():
    source = (
        MODULE_PATH.parents[2]
        / "console/frontend/tests/e2e/wave-3b-product-technical-evidence.spec.ts"
    ).read_text(encoding="utf-8")
    titles = re.findall(r'await test\.step\("(WAVE3B_08_[A-Z_]+)"', source)
    expected = [
        title
        for title in harness_module.WAVE_3B_STEP_IDS
        if title.startswith("WAVE3B_08_")
    ]
    assert titles == expected
    assert expected == [
        "WAVE3B_08_NAVIGATION",
        "WAVE3B_08_MAKE_STALE",
        "WAVE3B_08_CONFLICT_WRITE",
        "WAVE3B_08_ERROR_UI",
        "WAVE3B_08_AUTHORITATIVE_READBACK",
        "WAVE3B_08_EXPLICIT_RECOVERY",
        "WAVE3B_08_FINAL_ASSERTION",
    ]
    assert "test.setTimeout(240_000)" in source
    assert "waitForTimeout(" not in source


def test_wave_3b_conflict_write_failure_is_bounded_and_distinct():
    report = wave_3b_step_report()
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    conflict_index = list(harness_module.WAVE_3B_STEP_IDS).index(
        "WAVE3B_08_CONFLICT_WRITE"
    )
    result["steps"] = result["steps"][: conflict_index + 1]
    result["steps"][-1].update(
        duration=5000, error={"message": "PRIVATE response and URL"}
    )
    summary = make_summary(report)
    diagnostic = summary["stepDiagnostic"]
    assert diagnostic["failedStep"] == {
        "routeKey": "WORKFLOWS",
        "viewportKey": "DESKTOP",
        "stepId": "WAVE3B_08_CONFLICT_WRITE",
        "actionClass": "CONFLICT_WRITE",
        "elapsedMs": 5000,
    }
    assert diagnostic["lastCompletedStep"]["stepId"] == "WAVE3B_08_MAKE_STALE"
    assert "PRIVATE" not in harness_module.encode_failure_summary(summary)


def unified_step_report():
    report = summary_report("timedOut")
    report["suites"][0]["file"] = "unified-product-assembly.spec.ts"
    report["suites"][0]["specs"][0]["title"] = (
        "proves the complete durable unified-product browser journey"
    )
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result.update(
        duration=7000,
        steps=[
            {"title": "UNIFIED_01_PROBLEM_GAP", "duration": 100},
            {
                "title": "UNIFIED_02_AGENT_PUBLISH",
                "duration": 5000,
                "error": {"message": "PRIVATE selector and URL"},
            },
        ],
    )
    return report


def test_unified_source_uses_exact_static_top_level_steps_without_retry_controls():
    source = (
        MODULE_PATH.parents[2]
        / "console/frontend/tests/e2e/unified-product-assembly.spec.ts"
    ).read_text(encoding="utf-8")
    titles = re.findall(r'await test\.step\("([A-Z0-9_]+)"', source)
    assert titles == list(harness_module.UNIFIED_PRODUCT_STEP_IDS)
    assert "test.setTimeout(180_000)" in source
    assert "test.slow(" not in source
    assert "test.fixme(" not in source
    assert "waitForTimeout(" not in source


def append_failed_report(target, source):
    target["suites"].extend(source["suites"])
    target["stats"]["unexpected"] += source["stats"]["unexpected"]


def test_first_unified_uses_only_its_exact_failed_result_steps():
    report = unified_step_report()
    append_failed_report(report, wave_3b_step_report())
    summary = make_summary(report)
    assert summary["scenarioId"] == "UNIFIED_PRODUCT_ASSEMBLY_DURABLE_JOURNEY"
    assert summary["stepDiagnostic"]["failedStep"]["stepId"] == (
        "UNIFIED_02_AGENT_PUBLISH"
    )
    assert "WAVE3B" not in harness_module.encode_failure_summary(summary)


def test_first_wave_uses_only_its_exact_failed_result_steps():
    report = wave_3b_step_report()
    append_failed_report(report, unified_step_report())
    summary = make_summary(report)
    assert summary["scenarioId"] == "WAVE_3B_REAL_SERVICE_JOURNEYS"
    assert summary["stepDiagnostic"]["failedStep"]["stepId"] == (
        "WAVE3B_12_CLOSE_FOCUS_CHECK"
    )
    assert "UNIFIED_02" not in harness_module.encode_failure_summary(summary)


def test_same_spec_passing_project_does_not_replace_failed_result():
    report = unified_step_report()
    report["suites"][0]["specs"][0]["tests"].append(
        {
            "status": "expected",
            "projectName": "other",
            "results": [{"status": "passed"}],
        }
    )
    report["stats"]["expected"] = 1
    summary = make_summary(report)
    assert summary["stepDiagnostic"]["failedStep"]["stepId"] == (
        "UNIFIED_02_AGENT_PUBLISH"
    )


@pytest.mark.parametrize(
    "ambiguity", ["failed_test", "duplicate_title", "multi_result"]
)
def test_ambiguous_failure_context_omits_steps(ambiguity):
    report = unified_step_report()
    spec = report["suites"][0]["specs"][0]
    if ambiguity == "failed_test":
        spec["tests"].append(
            {"status": "unexpected", "results": [{"status": "failed"}]}
        )
        report["stats"]["unexpected"] = 2
    elif ambiguity == "duplicate_title":
        report["suites"].append(json.loads(json.dumps(report["suites"][0])))
        report["stats"]["unexpected"] = 2
    else:
        spec["tests"][0]["results"].append({"status": "passed"})
    raw = json.dumps(report).encode()
    context = harness_module.first_failure_context(report)
    failure = harness_module.sanitized_first_failure_record(
        raw, "journey-281", 0, failure_context=context
    )
    summary = harness_module.build_failure_summary(
        raw,
        failure,
        {"buildModeIdentity": "LIVE_DEMO", "frontendManifestDigest": "a" * 64},
        context,
    )
    assert context is None
    assert failure["firstFailureAssertionId"] == "NOT_RETAINED"
    assert "stepDiagnostic" not in summary
    assert "PRIVATE" not in harness_module.encode_failure_summary(summary)


@pytest.mark.parametrize("raw", [b"not-json PRIVATE", b'{"stats":{"unexpected":1}}'])
def test_missing_or_damaged_report_omits_steps(raw):
    parsed = harness_module._browser_json(raw)
    context = harness_module.first_failure_context(parsed) if parsed else None
    failure = harness_module.sanitized_first_failure_record(
        b'{"stats":{"unexpected":1}}',
        "journey-281",
        0,
        failure_context=context,
    )
    summary = harness_module.build_failure_summary(
        raw,
        failure,
        {"buildModeIdentity": "LIVE_DEMO", "frontendManifestDigest": "a" * 64},
        context,
    )
    assert "stepDiagnostic" not in summary
    assert "PRIVATE" not in harness_module.encode_failure_summary(summary)


def test_wave_3b_step_identity_and_action_fail_closed():
    report = wave_3b_step_report()
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result["steps"][10]["title"] = "WAVE3B_PRIVATE_DYNAMIC"
    assert "stepDiagnostic" not in make_summary(report)

    summary = make_summary(wave_3b_step_report())
    summary["stepDiagnostic"]["failedStep"]["actionClass"] = "PRIVATE"
    with pytest.raises(ValueError):
        harness_module.encode_failure_summary(summary)


@pytest.mark.parametrize("mutation", ["unknown", "elapsed", "scenario", "no_failure"])
def test_step_diagnostic_fail_closed(mutation):
    report = primary_step_report()
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    if mutation == "unknown":
        result["steps"][0]["title"] = "PRIVATE_DYNAMIC"
        assert "stepDiagnostic" not in make_summary(report)
    elif mutation == "elapsed":
        result["duration"] = "PRIVATE"
        assert make_summary(report)["stepDiagnostic"]["elapsedMs"] is None
    elif mutation == "scenario":
        result["status"] = "timedOut"
        assert make_summary(report)["stepDiagnostic"]["timeoutKind"] == "SCENARIO"
    else:
        result["steps"].pop()
        assert make_summary(report)["stepDiagnostic"]["failedStep"] is None


def test_step_fields_are_closed_and_bounded():
    value = make_summary(primary_step_report())
    value["stepDiagnostic"]["failedStep"]["url"] = "PRIVATE"
    with pytest.raises(ValueError):
        harness_module.encode_failure_summary(value)


def make_release(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    package = release / "agent_console"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app=FastAPI()\n"
        "@app.get('/healthz')\n"
        "def health(): return {'status':'ok'}\n",
        encoding="utf-8",
    )
    for path in (package / "__init__.py", package / "app.py"):
        path.chmod(0o444)
    package.chmod(0o555)
    release.chmod(0o555)
    return release


def args(release: Path, runtime: Path, port: int) -> Namespace:
    return Namespace(
        release_root=release,
        runtime_dir=runtime,
        backend_host="127.0.0.1",
        backend_port=port,
        postgres_url="postgresql://postgres@127.0.0.1:55432/test",
        qdrant_url="http://127.0.0.1:56333",
        python_path=".",
        journey_id="s5-impl-075-test-journey",
    )


def sentinel(release: Path, port: int, token: str) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPYCACHEPREFIX=str(release.parent / f"cache-{token}"),
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_console.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--header",
            f"X-Sentinel:{token}",
        ],
        cwd=release,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)
    assert process.poll() is None
    return process


def identity(process: subprocess.Popen[bytes], port: int) -> tuple[int, str, int, int]:
    started = subprocess.run(
        ["ps", "-p", str(process.pid), "-o", "lstart="],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz") as response:
        health = response.status
    return process.pid, started, port, health


def test_old_pattern_has_controlled_collision_without_signalling() -> None:
    old = (
        Path(__file__).parents[1]
        / "console/frontend/tests/e2e/knowledge-workbench.spec.ts"
    ).read_text()
    historical = 'execFileSync("p' + 'kill", ["-f", "uvicorn agent_console.app:app"])'
    assert historical not in old
    prefix = "python -m uvicorn agent_console.app:app"
    commands = [
        f"{prefix} --port 18000 --header X-Sentinel:public",
        f"{prefix} --port 18001 --header X-Sentinel:staging",
        f"{prefix} --port 18002 --header X-Sentinel:test",
    ]
    assert sum("uvicorn agent_console.app:app" in command for command in commands) == 3


def test_occupied_port_fails_closed(tmp_path: Path) -> None:
    release = make_release(tmp_path)
    port = free_port()
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", port))
        with pytest.raises(RuntimeError, match="occupied by an unowned process"):
            Harness(args(release, tmp_path / "runtime", port)).start()


def test_three_services_restart_and_cleanup_are_isolated_and_immutable(
    tmp_path: Path,
) -> None:
    release = make_release(tmp_path)
    before = release_manifest(release)
    public_port, staging_port, test_port = free_port(), free_port(), free_port()
    public = sentinel(release, public_port, "public")
    staging = sentinel(release, staging_port, "staging")
    harness = Harness(args(release, tmp_path / "runtime", test_port))
    try:
        harness.start()
        public_identity = identity(public, public_port)
        staging_identity = identity(staging, staging_port)
        test_pid = harness.child.pid
        harness.restart()
        assert harness.child.pid != test_pid
        assert identity(public, public_port) == public_identity
        assert identity(staging, staging_port) == staging_identity
        harness.stop()
        assert public.poll() is None
        assert staging.poll() is None
        assert release_manifest(release) == before
        assert (tmp_path / "runtime/release-manifest-before.json").is_file()
        assert not list(release.rglob("__pycache__"))
        assert not list(release.rglob("*.pyc"))
        assert all(
            not path.stat().st_mode & stat.S_IWUSR
            for path in (release, *release.rglob("*"))
        )
    finally:
        harness.stop()
        public.terminate()
        staging.terminate()
        public.wait(timeout=5)
        staging.wait(timeout=5)


def test_authorized_harness_paths_have_no_broad_process_matcher() -> None:
    root = Path(__file__).parents[1]
    paths = [
        root / "scripts/acceptance",
        root / "console/frontend/tests",
        root / ".github/workflows/ci.yml",
    ]
    prohibited = ("p" + "kill", "kill" + "all", "p" + "grep", "pid" + "of")
    for path in paths:
        files = path.rglob("*") if path.is_dir() else [path]
        for file in files:
            if file.is_file():
                text = file.read_text(encoding="utf-8", errors="ignore").lower()
                assert all(term not in text for term in prohibited), (file, prohibited)


def test_minimum_disclosure_extraction_is_allowlisted_and_fail_closed() -> None:
    record = {
        "schemaVersion": 1,
        "acceptanceState": "PASSED",
        "backendPid": 123,
        "backendStartTimeNs": 456,
        "backendRestartCount": 2,
        "releaseEntryCount": 42,
        "releaseManifestBeforeDigest": "a" * 64,
        "releaseManifestAfterDigest": "a" * 64,
        "journeyId": "s5-impl-075-test-journey",
        "phase": "BROWSER_EXECUTION",
        "assertionCategory": "BROWSER_ACCEPTANCE",
        "statusCode": 0,
        "exceptionClass": "NONE",
        "correlationDigest": "b" * 64,
        "restartRelation": "NO_RESTART",
        "completedAt": "2026-09-01T00:00:00+00:00",
        "sourceText": "must never be emitted",
    }
    result = minimum_disclosure.extract_allowlisted(
        record, set(minimum_disclosure.EVIDENCE_FIELDS)
    )
    assert set(result) == minimum_disclosure.EVIDENCE_FIELDS
    assert "sourceText" not in result
    with pytest.raises(minimum_disclosure.DisclosureViolation):
        minimum_disclosure.extract_allowlisted(record, {"sourceText"})


@pytest.mark.parametrize(
    "prohibited",
    [
        "supplier source_text must not escape",
        "bounded-test-key",
        "DATABASE_URL=unavailable",
        "postgresql://user@database.example/test",
        '{"vector":[0.1,0.2]}',
        '{"payload":{"content":"synthetic source"}}',
        "S5_PLANNING_API_KEY=placeholder-key",
        'request_body={"supplier":"ACME"}',
        "runtime_setting=VITE_MODE:live",
        "instruction_content=classify the supplied complaint",
        "/Users/operator/private/browser/error-context.md",
    ],
)
def test_generated_artifact_scan_rejects_disclosure(
    tmp_path: Path, prohibited: str
) -> None:
    artifact = tmp_path / "browser.log"
    artifact.write_text(prohibited, encoding="utf-8")
    with pytest.raises(minimum_disclosure.DisclosureViolation) as error:
        minimum_disclosure.scan_generated_artifacts([tmp_path])
    assert prohibited not in str(error.value)


def test_generated_trace_scan_rejects_compressed_payload_content(
    tmp_path: Path,
) -> None:
    trace = tmp_path / "trace.zip"
    with zipfile.ZipFile(trace, "w") as archive:
        archive.writestr("trace.network", '{"payload":{"content":"private"}}')
    with pytest.raises(minimum_disclosure.DisclosureViolation):
        minimum_disclosure.scan_generated_artifacts([trace])


def test_clean_generated_evidence_contains_only_correlation_fields(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "acceptance-evidence.json"
    evidence.write_text(
        '{"acceptanceState":"PASSED","backendPid":123,'
        '"completedAt":"2026-09-01T00:00:00+00:00",'
        '"releaseEntryCount":42}',
        encoding="utf-8",
    )
    minimum_disclosure.scan_generated_artifacts([evidence])


def browser_report(
    *failures: tuple[object, ...], unexpected: int | None = None
) -> bytes:
    specs = []
    for failure in failures:
        _file_name, title, message, *structured = failure
        status = "timedOut" if "timeout" in message.lower() else "failed"
        result = {"status": status, "errors": [{"message": message}]}
        if structured:
            result["structuredHttpStatus"] = structured[0]
        if len(structured) > 1:
            result["operationId"] = structured[1]
        specs.append(
            {
                "title": title,
                "tests": [
                    {
                        "status": "unexpected",
                        "results": [result],
                    }
                ],
            }
        )
    return json.dumps(
        {
            "stats": {
                "expected": 3,
                "unexpected": len(failures) if unexpected is None else unexpected,
            },
            "suites": [{"file": failures[0][0] if failures else "", "specs": specs}],
        }
    ).encode()


def test_successful_browser_report_has_no_first_failure_record() -> None:
    report = json.dumps(
        {"stats": {"expected": 3, "unexpected": 0}, "suites": []}
    ).encode()
    assert (
        harness_module.sanitized_first_failure_record(report, "journey-086", 0) is None
    )


def test_first_failure_is_stable_and_deterministic_without_raw_message() -> None:
    report = browser_report(
        (
            "agent-workbench.spec.ts",
            "publishes an exact reviewed revision through the real Workbench",
            "expect(locator('#private')).toBeVisible() token=secret",
        ),
        (
            "agent-workbench.spec.ts",
            "creates a governed draft through the guided Builder",
            "second assertion",
        ),
    )
    record = harness_module.sanitized_first_failure_record(report, "journey-086", 0)
    assert (
        record["firstFailureAssertionId"] == "AGENT_WORKBENCH_PUBLISH_REVIEWED_REVISION"
    )
    assert record["failureSubtype"] == "SELECTOR_STATE_MISMATCH"
    assert record["unexpectedAssertionCount"] == 2
    assert "private" not in json.dumps(record)
    assert "secret" not in json.dumps(record)


@pytest.mark.parametrize(
    ("message", "category", "subtype", "http"),
    [
        ("Timeout 30000ms exceeded", "BROWSER_TIMEOUT", "TIMEOUT", "NONE"),
        (
            "HTTP response status 503",
            "BROWSER_ASSERTION",
            "APPLICATION_STATE_MISMATCH",
            "UNKNOWN",
        ),
        (
            "page.goto navigation failed",
            "BROWSER_NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NONE",
        ),
        (
            "unknown opaque exception",
            "BROWSER_ASSERTION",
            "APPLICATION_STATE_MISMATCH",
            "UNKNOWN",
        ),
    ],
)
def test_first_failure_closed_classification(message, category, subtype, http) -> None:
    report = browser_report(
        (
            "agent-workbench.spec.ts",
            "creates a governed draft through the guided Builder",
            message,
        )
    )
    record = harness_module.sanitized_first_failure_record(report, "journey-086", 1)
    assert (
        record["failureCategory"],
        record["failureSubtype"],
        record["httpStatusCategory"],
    ) == (category, subtype, http)


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (100, "HTTP_1XX"),
        (199, "HTTP_1XX"),
        (200, "HTTP_2XX"),
        (299, "HTTP_2XX"),
        (300, "HTTP_3XX"),
        (399, "HTTP_3XX"),
        (400, "HTTP_4XX"),
        (499, "HTTP_4XX"),
        (500, "HTTP_5XX"),
        (599, "HTTP_5XX"),
    ],
)
def test_structured_integer_http_status_maps_to_category(status, category) -> None:
    report = browser_report(
        (
            "agent-workbench.spec.ts",
            "creates a governed draft through the guided Builder",
            "opaque failure",
            status,
        )
    )
    record = harness_module.sanitized_first_failure_record(report, "journey-088", 0)
    assert record["httpStatusSourceClass"] == "STRUCTURED_RESPONSE_STATUS"
    assert record["httpStatusCategory"] == category
    assert str(status) not in json.dumps(record)


@pytest.mark.parametrize("status", ["503", True, 503.0, 99, 600])
def test_invalid_structured_http_status_is_rejected(status) -> None:
    report = browser_report(
        (
            "agent-workbench.spec.ts",
            "creates a governed draft through the guided Builder",
            "opaque failure",
            status,
        )
    )
    with pytest.raises(ValueError, match="structured HTTP status"):
        harness_module.sanitized_first_failure_record(report, "journey-088", 0)


def test_numbers_in_text_exit_code_and_assertion_count_never_make_http_claim() -> None:
    report = browser_report(
        (
            "agent-workbench.spec.ts",
            "creates a governed draft through the guided Builder",
            "HTTP response status 503; exit code 404; assertion count 500",
        ),
        unexpected=599,
    )
    record = harness_module.sanitized_first_failure_record(report, "journey-088", 0)
    assert record["httpStatusSourceClass"] == "NO_STRUCTURED_HTTP_STATUS"
    assert record["httpStatusCategory"] in {"NONE", "UNKNOWN"}


@pytest.mark.parametrize(
    "operation_id",
    sorted(harness_module.KNOWLEDGE_WORKBENCH_OPERATION_IDS),
)
def test_knowledge_lifecycle_operation_ids_are_closed_and_stable(operation_id) -> None:
    report = browser_report(
        (
            "knowledge-workbench.spec.ts",
            KNOWLEDGE_LIFECYCLE_TITLE,
            "opaque failure",
            None,
            operation_id,
        )
    )
    record = harness_module.sanitized_first_failure_record(report, "journey-088", 0)
    assert record["firstFailureOperationId"] == operation_id


def test_first_failed_operation_is_deterministic_and_only_one_is_retained() -> None:
    report = json.loads(
        browser_report(
            (
                "knowledge-workbench.spec.ts",
                KNOWLEDGE_LIFECYCLE_TITLE,
                "opaque failure",
            )
        )
    )
    result = report["suites"][0]["specs"][0]["tests"][0]["results"][0]
    result["operations"] = [
        {"operationId": "KNOWLEDGE_INDEX_RETRIEVE", "status": "failed"},
        {"operationId": "KNOWLEDGE_UPDATE", "status": "failed"},
    ]
    record = harness_module.sanitized_first_failure_record(
        json.dumps(report).encode(), "journey-088", 0
    )
    assert record["firstFailureOperationId"] == "KNOWLEDGE_INDEX_RETRIEVE"
    assert "KNOWLEDGE_UPDATE" not in json.dumps(record)


@pytest.mark.parametrize(
    "operation_id",
    [
        None,
        "FREE_FORM_OPERATION",
        "https://example.test/path",
        "#selector",
        "/route",
        "token=secret",
    ],
)
def test_missing_or_unsafe_knowledge_operation_fails_closed(operation_id) -> None:
    failure = [
        "knowledge-workbench.spec.ts",
        KNOWLEDGE_LIFECYCLE_TITLE,
        "opaque failure",
        None,
        operation_id,
    ]
    record = harness_module.sanitized_first_failure_record(
        browser_report(tuple(failure)), "journey-088", 0
    )
    assert record["firstFailureOperationId"] == "NOT_RETAINED"
    assert record["failureCategory"] == "BROWSER_DIAGNOSTIC_GAP"


def test_schema_versions_have_exact_distinct_fields_and_reject_mixing() -> None:
    record = harness_module.sanitized_first_failure_record(
        browser_report(
            (
                "agent-workbench.spec.ts",
                "creates a governed draft through the guided Builder",
                "opaque failure",
            )
        ),
        "journey-088",
        0,
    )
    assert record["schemaVersion"] == 2
    assert set(record) == harness_module.FIRST_FAILURE_FIELDS
    version_one = {
        key: value
        for key, value in record.items()
        if key not in {"firstFailureOperationId", "httpStatusSourceClass"}
    }
    version_one["schemaVersion"] = 1
    digest_source = {
        key: value for key, value in version_one.items() if key != "correlationDigest"
    }
    version_one["correlationDigest"] = hashlib.sha256(
        json.dumps(digest_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert set(harness_module.validate_first_failure_record(version_one)) == (
        harness_module.FIRST_FAILURE_V1_FIELDS
    )
    for mixed in (
        {**record, "schemaVersion": 1},
        {**version_one, "schemaVersion": 2},
        {**record, "schemaVersion": 99},
    ):
        with pytest.raises(ValueError):
            harness_module.validate_first_failure_record(mixed)


def test_missing_assertion_id_fails_closed_to_diagnostic_gap() -> None:
    report = browser_report(("unknown.spec.ts", "free form test", "password=private"))
    record = harness_module.sanitized_first_failure_record(report, "journey-086", 0)
    assert record["firstFailureAssertionId"] == "NOT_RETAINED"
    assert record["failureCategory"] == "BROWSER_DIAGNOSTIC_GAP"
    assert "private" not in json.dumps(record)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(extraField="forbidden"),
        lambda value: value.update(firstFailureAssertionId="../../private"),
        lambda value: value.update(firstFailureAssertionId="UNVERSIONED_IDENTIFIER"),
        lambda value: value.update(journeyId="https://example.test/path?token=secret"),
        lambda value: value.update(journeyId="secret-value"),
        lambda value: value.update(completedAssertionCount=-1),
        lambda value: value.update(completedAssertionCount=100_001),
        lambda value: value.update(failureSubtype="raw assertion message"),
        lambda value: value.update(exceptionClass="/tmp/error-context.md"),
        lambda value: value.update(httpStatusCategory="screenshot.png"),
        lambda value: value.update(httpStatusSourceClass="FREE_FORM"),
        lambda value: value.update(firstFailureOperationId="https://example.test"),
        lambda value: value.update(
            httpStatusCategory="HTTP_5XX",
            httpStatusSourceClass="NO_STRUCTURED_HTTP_STATUS",
        ),
    ],
)
def test_first_failure_schema_rejects_extra_raw_and_unbounded_values(mutation) -> None:
    report = browser_report(
        (
            "agent-workbench.spec.ts",
            "creates a governed draft through the guided Builder",
            "expect(value)",
        )
    )
    record = harness_module.sanitized_first_failure_record(report, "journey-086", 0)
    mutation(record)
    with pytest.raises(ValueError):
        harness_module.validate_first_failure_record(record)


def test_build_mode_missing_or_incorrect_fails_closed(tmp_path: Path) -> None:
    frontend = tmp_path / "dist"
    frontend.mkdir()
    (frontend / "index.html").write_text("immutable", encoding="utf-8")
    identity = tmp_path / "build-identity.json"
    with pytest.raises(build_preflight.BuildPreflightError):
        build_preflight.verify_build_identity(frontend, identity)
    with pytest.raises(build_preflight.BuildPreflightError):
        build_preflight.record_build_identity(frontend, identity, "synthetic")


class FakePostgresConnection:
    def __init__(self, identity: tuple[str, str]) -> None:
        self.identity = identity
        self.statements: list[object] = []
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement: object):
        self.statements.append(statement)
        return self

    def fetchone(self):
        if len(self.statements) == 1:
            return self.identity
        return ("CREATED",)

    def rollback(self) -> None:
        self.rolled_back = True


def test_exact_postgres_validation_role_migration_read_write_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakePostgresConnection(("browser_validation", "browser_validation"))
    monkeypatch.setattr(harness_module.psycopg, "connect", lambda _url: connection)
    harness_module.verify_postgres_role_readiness(
        "postgresql://redacted", "browser_validation"
    )
    assert len(connection.statements) == 8
    assert connection.rolled_back


def test_incorrect_postgres_validation_role_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakePostgresConnection(("postgres", "postgres"))
    monkeypatch.setattr(harness_module.psycopg, "connect", lambda _url: connection)
    with pytest.raises(RuntimeError, match="role identity mismatch"):
        harness_module.verify_postgres_role_readiness(
            "postgresql://redacted", "browser_validation"
        )


def test_missing_postgres_validation_grants_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakePostgresConnection(("browser_validation", "browser_validation"))

    def fail_on_schema(statement: object):
        connection.statements.append(statement)
        if len(connection.statements) == 2:
            raise PermissionError("prohibited detail")
        return connection

    monkeypatch.setattr(connection, "execute", fail_on_schema)
    monkeypatch.setattr(harness_module.psycopg, "connect", lambda _url: connection)
    with pytest.raises(RuntimeError, match="role readiness failed") as error:
        harness_module.verify_postgres_role_readiness(
            "postgresql://redacted", "browser_validation"
        )
    assert "prohibited detail" not in str(error.value)


def test_live_build_identity_is_external_digest_bound_and_sanitized(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    frontend = release / "console/frontend/dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("immutable", encoding="utf-8")
    identity = tmp_path / "runtime/build-identity.json"
    identity.parent.mkdir()
    build_preflight.record_build_identity(frontend, identity, "live")
    assert not identity.is_relative_to(release)
    record = build_preflight.verify_build_identity(frontend, identity)
    assert set(record) == build_preflight.BUILD_IDENTITY_FIELDS
    assert record["buildModeIdentity"] == build_preflight.APPROVED_BUILD_MODE
    minimum_disclosure.scan_generated_artifacts([identity])
    (frontend / "index.html").write_text("changed", encoding="utf-8")
    with pytest.raises(build_preflight.BuildPreflightError):
        build_preflight.verify_build_identity(frontend, identity)


def test_raw_playwright_retention_is_disabled() -> None:
    config = (
        Path(__file__).parents[1] / "console/frontend/playwright.config.ts"
    ).read_text(encoding="utf-8")
    assert 'trace: "off"' in config
    assert 'screenshot: "off"' in config
    assert 'video: "off"' in config
    assert "retain-on-failure" not in config


def test_recursive_plain_and_compressed_diagnostics_scan(tmp_path: Path) -> None:
    nested = tmp_path / "diagnostics/nested"
    nested.mkdir(parents=True)
    (nested / "acceptance.json").write_text(
        '{"journeyId":"journey-075","phase":"BROWSER_EXECUTION",'
        '"assertionCategory":"BROWSER_ACCEPTANCE","statusCode":1,'
        '"exceptionClass":"BROWSER_COMMAND_FAILED",'
        '"correlationDigest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        '"restartRelation":"NO_RESTART",'
        '"completedAt":"2026-09-02T00:00:00+00:00"}',
        encoding="utf-8",
    )
    with zipfile.ZipFile(nested / "sanitized.zip", "w") as archive:
        archive.writestr(
            "diagnostic.json",
            '{"journeyId":"journey-075","exceptionClass":"ASSERTION_FAILURE"}',
        )
    minimum_disclosure.scan_generated_artifacts([tmp_path])


def test_attempt_05_categories_are_negative_controls_for_old_scanner(
    tmp_path: Path,
) -> None:
    old_patterns = tuple(
        minimum_disclosure._FORBIDDEN_TEXT[index] for index in (0, 1, 2, 3, 5, 6)
    )
    controls = [
        'request_body={"supplier":"ACME"}',
        "runtime_setting=VITE_MODE:live",
        "instruction_content=classify the supplied complaint",
        "/Users/operator/private/browser/error-context.md",
    ]
    for index, control in enumerate(controls):
        assert not any(pattern.search(control) for pattern in old_patterns)
        artifact = tmp_path / f"negative-control-{index}.txt"
        artifact.write_text(control, encoding="utf-8")
        with pytest.raises(minimum_disclosure.DisclosureViolation):
            minimum_disclosure.scan_artifact(artifact)


def test_validation_helpers_prohibit_broad_file_dump_commands() -> None:
    root = Path(__file__).parents[1]
    files = [
        *sorted((root / "scripts/acceptance").glob("*")),
        root / ".github/workflows/ci.yml",
    ]
    command_names = "|".join(("s" + "ed", "c" + "at", "h" + "ead", "t" + "ail"))
    prohibited = re.compile(rf"(?m)^\s*(?:{command_names})\s")
    for file in files:
        if file.is_file():
            text = file.read_text(encoding="utf-8", errors="ignore").lower()
            assert prohibited.search(text) is None, file


def test_harness_connects_digital_employee_authority_to_validated_postgres() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"EXECUTION_DATABASE_URL": self.args.postgres_url' in source
