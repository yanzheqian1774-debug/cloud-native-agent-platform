from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
GOOGLE_APT_INDEX = (
    "https://dl.google.com/linux/chrome-stable/deb/dists/stable/"
    "main/binary-amd64/Packages.gz"
)


def browser_job() -> dict[str, object]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["agent-workbench-browser"]


def named_step(name: str) -> dict[str, object]:
    return next(step for step in browser_job()["steps"] if step["name"] == name)


@dataclass(frozen=True)
class InstallResult:
    completed: subprocess.CompletedProcess[str]
    attempts: int
    sleeps: list[str]
    trace: list[str]


def write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def run_install_step(
    tmp_path: Path,
    outcomes: list[tuple[int, str]],
    *,
    fail_tee: bool = False,
) -> InstallResult:
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    scenario = tmp_path / "scenario"
    scenario.mkdir()
    trace = tmp_path / "trace"
    counter = tmp_path / "counter"
    sleeps = tmp_path / "sleeps"

    for attempt, (exit_code, output) in enumerate(outcomes, start=1):
        (scenario / f"{attempt}.exit").write_text(str(exit_code), encoding="utf-8")
        (scenario / f"{attempt}.log").write_text(output, encoding="utf-8")

    write_executable(
        mock_bin / "npm",
        """#!/usr/bin/env bash
echo "npm $*" >>"$INSTALL_TRACE"
exit 0
""",
    )
    write_executable(
        mock_bin / "npx",
        """#!/usr/bin/env bash
echo "npx $*" >>"$INSTALL_TRACE"
attempt=0
if [ -f "$INSTALL_COUNTER" ]; then
  attempt="$(<"$INSTALL_COUNTER")"
fi
attempt="$((attempt + 1))"
echo "$attempt" >"$INSTALL_COUNTER"
scenario="$INSTALL_SCENARIO/$attempt"
if [ ! -f "$scenario.exit" ]; then
  echo "unexpected extra install attempt" >&2
  exit 99
fi
command cat "$scenario.log"
exit "$(<"$scenario.exit")"
""",
    )
    write_executable(
        mock_bin / "sleep",
        """#!/usr/bin/env bash
echo "$1" >>"$INSTALL_SLEEPS"
""",
    )
    if fail_tee:
        write_executable(mock_bin / "tee", "#!/usr/bin/env bash\nexit 74\n")

    install_step = named_step("Install frontend and Chromium")
    completed = subprocess.run(
        ["bash", "-e", "-c", install_step["run"]],
        cwd=ROOT / install_step["working-directory"],
        env={
            **os.environ,
            "PATH": f"{mock_bin}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
            "INSTALL_TRACE": str(trace),
            "INSTALL_COUNTER": str(counter),
            "INSTALL_SCENARIO": str(scenario),
            "INSTALL_SLEEPS": str(sleeps),
        },
        capture_output=True,
        check=False,
        text=True,
    )
    attempt_count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
    sleep_values = (
        sleeps.read_text(encoding="utf-8").splitlines() if sleeps.exists() else []
    )
    trace_values = trace.read_text(encoding="utf-8").splitlines()
    return InstallResult(completed, attempt_count, sleep_values, trace_values)


def apt_hash_failure(*additional_lines: str) -> str:
    return "\n".join(
        (
            f"E: Failed to fetch {GOOGLE_APT_INDEX}  Hash Sum mismatch",
            "E: Some index files failed to download. They have been ignored, "
            "or old ones used instead.",
            "Failed to install browsers",
            "Error: Installation process exited with code: 100",
            *additional_lines,
            "",
        )
    )


def test_workflow_runs_locked_install_once_on_success(tmp_path: Path) -> None:
    step = named_step("Install frontend and Chromium")
    assert step["timeout-minutes"] == 5

    result = run_install_step(tmp_path, [(0, "Chromium installed\n")])

    assert result.completed.returncode == 0
    assert result.attempts == 1
    assert result.sleeps == []
    assert result.trace == [
        "npm ci",
        "npx playwright install --with-deps chromium",
    ]
    assert "attempt=1/3 exit_code=0 error_category=none" in result.completed.stdout


def test_known_google_apt_hash_failure_retries_with_short_backoff(
    tmp_path: Path,
) -> None:
    result = run_install_step(
        tmp_path,
        [(1, apt_hash_failure()), (1, apt_hash_failure()), (0, "installed\n")],
    )

    assert result.completed.returncode == 0
    assert result.attempts == 3
    assert result.sleeps == ["30", "60"]
    assert (
        result.completed.stdout.count(
            "error_category=google_apt_index_hash_sum_mismatch"
        )
        == 2
    )
    assert "attempt=3/3 exit_code=0 error_category=none" in result.completed.stdout


def test_known_google_apt_hash_failure_fails_closed_after_three_attempts(
    tmp_path: Path,
) -> None:
    result = run_install_step(tmp_path, [(1, apt_hash_failure())] * 3)

    assert result.completed.returncode == 1
    assert result.attempts == 3
    assert result.sleeps == ["30", "60"]
    assert "attempt=3/3 exit_code=1" in result.completed.stdout


@pytest.mark.parametrize(
    ("exit_code", "output", "category"),
    [
        (
            23,
            apt_hash_failure("Error: disk full"),
            "mixed_playwright_install_failure",
        ),
        (
            17,
            "Get:1 https://dl.google.com/linux/chrome-stable/deb Packages\n"
            "E: Failed to fetch https://mirror.invalid/Packages.gz  "
            "Hash Sum mismatch\n",
            "playwright_install_failure_unclassified",
        ),
        (
            42,
            "unexpected installer failure\n",
            "playwright_install_failure_unclassified",
        ),
    ],
)
def test_non_allowed_install_failures_do_not_retry(
    tmp_path: Path,
    exit_code: int,
    output: str,
    category: str,
) -> None:
    result = run_install_step(tmp_path, [(exit_code, output)])

    assert result.completed.returncode == exit_code
    assert result.attempts == 1
    assert result.sleeps == []
    assert f"attempt=1/3 exit_code={exit_code} error_category={category}" in (
        result.completed.stdout
    )


def test_install_log_write_failure_stops_without_retry(tmp_path: Path) -> None:
    result = run_install_step(tmp_path, [(1, "")], fail_tee=True)

    assert result.completed.returncode == 74
    assert result.attempts == 1
    assert result.sleeps == []
    assert "error_category=install_log_write_failure" in result.completed.stdout


def test_diagnostics_are_required_only_after_browser_execution() -> None:
    browser_step = named_step("Run real browser acceptance")
    artifact_step = named_step("Retain sanitized browser diagnostics")
    assert browser_step["id"] == "browser_acceptance"
    assert artifact_step["with"]["if-no-files-found"] == "error"

    condition = artifact_step["if"]
    retained_outcomes = set(
        re.findall(r"steps\.browser_acceptance\.outcome == '([^']+)'", condition)
    )

    assert retained_outcomes == {"success", "failure", "cancelled"}
    assert {
        outcome: outcome in retained_outcomes
        for outcome in ("success", "failure", "cancelled", "skipped", "")
    } == {
        "success": True,
        "failure": True,
        "cancelled": True,
        "skipped": False,
        "": False,
    }
    assert "always()" in condition
    assert "continue-on-error" not in artifact_step
