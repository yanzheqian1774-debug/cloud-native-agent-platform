from __future__ import annotations

import importlib.util
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
