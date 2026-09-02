#!/usr/bin/env python3
"""Own an isolated real backend while a serialized browser command runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

import psycopg
from browser_build_preflight import verify_build_identity
from minimum_disclosure import (
    EVIDENCE_FIELDS,
    extract_allowlisted,
    scan_generated_artifacts,
)
from psycopg import sql

FIRST_FAILURE_SCHEMA_VERSION = 1
MAX_DIAGNOSTIC_COUNT = 100_000
FIRST_FAILURE_FIELDS = frozenset(
    {
        "schemaVersion",
        "journeyId",
        "runnerPhase",
        "harnessPhase",
        "firstFailureAssertionId",
        "expectedResultClass",
        "observedResultClass",
        "failureCategory",
        "failureSubtype",
        "exceptionClass",
        "httpStatusCategory",
        "correlationDigest",
        "completedJourneyCount",
        "completedAssertionCount",
        "unexpectedAssertionCount",
        "backendStateClass",
        "frontendStateClass",
        "listenerStateClass",
        "restartCountClass",
        "completionState",
    }
)
FIRST_FAILURE_ASSERTION_IDS = {
    (
        "agent-workbench.spec.ts",
        "publishes an exact reviewed revision through the real Workbench",
    ): "AGENT_WORKBENCH_PUBLISH_REVIEWED_REVISION",
    (
        "agent-workbench.spec.ts",
        "creates a governed draft through the guided Builder",
    ): "AGENT_WORKBENCH_CREATE_GOVERNED_DRAFT",
    (
        "knowledge-workbench.spec.ts",
        "completes the real Knowledge lifecycle, retrieval, recovery and purge journey",
    ): "KNOWLEDGE_WORKBENCH_LIFECYCLE",
    (
        "skill-mcp-workbench.spec.ts",
        "publishes, binds and authorizes one bounded real capability test",
    ): "SKILL_MCP_WORKBENCH_PUBLISH_BIND_AUTHORIZE",
    (
        "unified-product-assembly.spec.ts",
        "proves the complete durable unified-product browser journey",
    ): "UNIFIED_PRODUCT_ASSEMBLY_DURABLE_JOURNEY",
    (
        "unified-product-assembly.spec.ts",
        "keeps denial disclosure-safe and responsive navigation accessible",
    ): "UNIFIED_PRODUCT_ASSEMBLY_DISCLOSURE_DENIAL",
    (
        "wave-3b-product-technical-evidence.spec.ts",
        "canonical URL context is deterministic and round-trip stable",
    ): "WAVE_3B_CANONICAL_CONTEXT_ROUND_TRIP",
    (
        "wave-3b-product-technical-evidence.spec.ts",
        "invalid URL context fails closed",
    ): "WAVE_3B_INVALID_CONTEXT_FAIL_CLOSED",
    (
        "wave-3b-product-technical-evidence.spec.ts",
        "proves all twelve Wave 3B real-service browser journeys",
    ): "WAVE_3B_REAL_SERVICE_JOURNEYS",
    (
        "workflow-runtime-workbench.spec.ts",
        "publishes a Runtime Profile then a governed Workflow through real Workbenches",
    ): "WORKFLOW_RUNTIME_PUBLISH_GOVERNED_WORKFLOW",
    (
        "workflow-runtime-workbench.spec.ts",
        "shows controlled empty and validation failure states",
    ): "WORKFLOW_RUNTIME_CONTROLLED_FAILURE_STATES",
    (
        "workflow-runtime-workbench.spec.ts",
        "renders a disclosure-safe denied state",
    ): "WORKFLOW_RUNTIME_DISCLOSURE_DENIAL",
}
FAILURE_CATEGORIES = frozenset(
    {
        "BROWSER_ASSERTION",
        "BROWSER_TIMEOUT",
        "BROWSER_HTTP_ERROR",
        "BROWSER_NAVIGATION_ERROR",
        "BROWSER_PROCESS_ERROR",
        "BROWSER_DIAGNOSTIC_GAP",
    }
)
FAILURE_SUBTYPES = frozenset(
    {
        "ASSERTION_MISMATCH",
        "TIMEOUT",
        "HTTP_ERROR",
        "NAVIGATION_ERROR",
        "SELECTOR_STATE_MISMATCH",
        "APPLICATION_STATE_MISMATCH",
        "PROCESS_EXIT",
        "UNKNOWN",
    }
)
HTTP_STATUS_CATEGORIES = frozenset(
    {
        "NONE",
        "HTTP_1XX",
        "HTTP_2XX",
        "HTTP_3XX",
        "HTTP_4XX",
        "HTTP_5XX",
        "CONNECTION_FAILURE",
        "TIMEOUT",
        "UNKNOWN",
    }
)
EXCEPTION_CLASSES = frozenset(
    {
        "NONE",
        "ASSERTION_ERROR",
        "TIMEOUT_ERROR",
        "HTTP_ERROR",
        "NAVIGATION_ERROR",
        "PROCESS_ERROR",
        "UNKNOWN",
    }
)
_ASSERTION_ID = re.compile(r"[A-Z][A-Z0-9_]{2,95}\Z")


def _browser_json(stdout: bytes) -> dict[str, object] | None:
    try:
        start = stdout.find(b"{")
        end = stdout.rfind(b"}")
        value = json.loads(stdout[start : end + 1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _ordered_specs(suites: object):
    if not isinstance(suites, list):
        return
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        yield from _ordered_specs(suite.get("suites"))
        specs = suite.get("specs")
        if isinstance(specs, list):
            for spec in specs:
                if isinstance(spec, dict):
                    yield suite, spec


def _bounded_count(value: object) -> int:
    return value if type(value) is int and 0 <= value <= MAX_DIAGNOSTIC_COUNT else 0


def _failure_details(text: str, status: str) -> tuple[str, str, str, str]:
    lowered = text.lower()
    if status == "interrupted":
        return "BROWSER_PROCESS_ERROR", "PROCESS_EXIT", "PROCESS_ERROR", "NONE"
    if status == "timedOut" or "timeout" in lowered or "timed out" in lowered:
        return "BROWSER_TIMEOUT", "TIMEOUT", "TIMEOUT_ERROR", "TIMEOUT"
    status_match = re.search(r"(?<!\d)([1-5]\d\d)(?!\d)", text)
    if status_match and (
        "http" in lowered or "status" in lowered or "response" in lowered
    ):
        return (
            "BROWSER_HTTP_ERROR",
            "HTTP_ERROR",
            "HTTP_ERROR",
            f"HTTP_{status_match.group(1)[0]}XX",
        )
    if "net::err_" in lowered or "connection" in lowered:
        return (
            "BROWSER_NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "CONNECTION_FAILURE",
        )
    if "goto" in lowered or "navigation" in lowered:
        return (
            "BROWSER_NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NAVIGATION_ERROR",
            "NONE",
        )
    if (
        "locator" in lowered
        or "selector" in lowered
        or "tobevisible" in lowered
        or "tohave" in lowered
    ):
        return "BROWSER_ASSERTION", "SELECTOR_STATE_MISMATCH", "ASSERTION_ERROR", "NONE"
    if "expect(" in lowered or "assert" in lowered:
        return "BROWSER_ASSERTION", "ASSERTION_MISMATCH", "ASSERTION_ERROR", "NONE"
    return "BROWSER_ASSERTION", "APPLICATION_STATE_MISMATCH", "UNKNOWN", "UNKNOWN"


def sanitized_first_failure_record(
    stdout: bytes, journey_id: str, restart_count: int
) -> dict[str, object] | None:
    report = _browser_json(stdout)
    if report is None:
        return None
    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    unexpected = _bounded_count(stats.get("unexpected"))
    first = None
    for suite, spec in _ordered_specs(report.get("suites")):
        tests = spec.get("tests")
        if not isinstance(tests, list):
            continue
        for test in tests:
            if not isinstance(test, dict):
                continue
            results = test.get("results")
            if test.get("status") == "unexpected" or any(
                isinstance(item, dict)
                and item.get("status") in {"failed", "timedOut", "interrupted"}
                for item in (results if isinstance(results, list) else [])
            ):
                first = (suite, spec, test)
                break
        if first:
            break
    if first is None and unexpected == 0:
        return None
    assertion_id = "NOT_RETAINED"
    category, subtype, exception_class, http_category = (
        "BROWSER_DIAGNOSTIC_GAP",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
    )
    if first is not None:
        suite, spec, test = first
        title = spec.get("title")
        mapped = (
            FIRST_FAILURE_ASSERTION_IDS.get(
                (Path(str(suite.get("file", ""))).name, title)
            )
            if isinstance(title, str)
            else None
        )
        if mapped:
            assertion_id = mapped
        results = test.get("results")
        result = next(
            (
                item
                for item in (results if isinstance(results, list) else [])
                if isinstance(item, dict)
                and item.get("status") in {"failed", "timedOut", "interrupted"}
            ),
            {},
        )
        errors = result.get("errors") if isinstance(result, dict) else []
        transient = " ".join(
            str(item.get("message", "")) for item in errors if isinstance(item, dict)
        )[:65_536]
        category, subtype, exception_class, http_category = _failure_details(
            transient, str(result.get("status", ""))
        )
        if assertion_id == "NOT_RETAINED":
            category, subtype, exception_class, http_category = (
                "BROWSER_DIAGNOSTIC_GAP",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
            )
    completed = _bounded_count(stats.get("expected")) + unexpected
    record: dict[str, object] = {
        "schemaVersion": FIRST_FAILURE_SCHEMA_VERSION,
        "journeyId": journey_id,
        "runnerPhase": "browser-harness",
        "harnessPhase": "BROWSER_COMMAND",
        "firstFailureAssertionId": assertion_id,
        "expectedResultClass": "EXPECTED",
        "observedResultClass": "UNEXPECTED",
        "failureCategory": category,
        "failureSubtype": subtype,
        "exceptionClass": exception_class,
        "httpStatusCategory": http_category,
        "completedJourneyCount": 0,
        "completedAssertionCount": min(completed, MAX_DIAGNOSTIC_COUNT),
        "unexpectedAssertionCount": unexpected,
        "backendStateClass": "RUNNING",
        "frontendStateClass": "UNKNOWN",
        "listenerStateClass": "ACTIVE",
        "restartCountClass": "NONE" if restart_count == 0 else "ONE_OR_MORE",
        "completionState": "FAILED",
    }
    normalized = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["correlationDigest"] = hashlib.sha256(normalized).hexdigest()
    return validate_first_failure_record(record)


def validate_first_failure_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict) or set(record) != FIRST_FAILURE_FIELDS:
        raise ValueError("browser first-failure schema violation")
    if record["schemaVersion"] != FIRST_FAILURE_SCHEMA_VERSION:
        raise ValueError("browser first-failure schema version violation")
    if not isinstance(record["journeyId"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{2,95}", record["journeyId"]
    ):
        raise ValueError("browser first-failure journey identity violation")
    assertion_id = record["firstFailureAssertionId"]
    if assertion_id != "NOT_RETAINED" and (
        not isinstance(assertion_id, str) or not _ASSERTION_ID.fullmatch(assertion_id)
    ):
        raise ValueError("browser first-failure assertion identity violation")
    if (
        assertion_id != "NOT_RETAINED"
        and assertion_id not in FIRST_FAILURE_ASSERTION_IDS.values()
    ):
        raise ValueError("browser first-failure assertion identity is not versioned")
    enum_fields = {
        "runnerPhase": {"browser-harness"},
        "harnessPhase": {"BROWSER_COMMAND"},
        "expectedResultClass": {"EXPECTED"},
        "observedResultClass": {"UNEXPECTED"},
        "failureCategory": FAILURE_CATEGORIES,
        "failureSubtype": FAILURE_SUBTYPES,
        "exceptionClass": EXCEPTION_CLASSES,
        "httpStatusCategory": HTTP_STATUS_CATEGORIES,
        "backendStateClass": {"RUNNING", "STOPPED", "UNKNOWN"},
        "frontendStateClass": {"RUNNING", "STOPPED", "UNKNOWN"},
        "listenerStateClass": {"ACTIVE", "INACTIVE", "UNKNOWN"},
        "restartCountClass": {"NONE", "ONE_OR_MORE", "UNKNOWN"},
        "completionState": {"FAILED"},
    }
    if any(record[name] not in allowed for name, allowed in enum_fields.items()):
        raise ValueError("browser first-failure enum violation")
    for name in (
        "completedJourneyCount",
        "completedAssertionCount",
        "unexpectedAssertionCount",
    ):
        if (
            type(record[name]) is not int
            or not 0 <= record[name] <= MAX_DIAGNOSTIC_COUNT
        ):
            raise ValueError("browser first-failure count violation")
    if not isinstance(record["correlationDigest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", record["correlationDigest"]
    ):
        raise ValueError("browser first-failure digest violation")
    digest_source = {
        key: value for key, value in record.items() if key != "correlationDigest"
    }
    expected_digest = hashlib.sha256(
        json.dumps(digest_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if record["correlationDigest"] != expected_digest:
        raise ValueError("browser first-failure digest mismatch")
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
    if len(encoded) > 4096 or re.search(
        r"(?i)(https?://|[?&][a-z]+=|/Users/|/home/|/tmp/|password|token|secret|trace|screenshot|video|error-context)",
        encoded,
    ):
        raise ValueError("browser first-failure disclosure violation")
    return record


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        if "required" in message:
            category = "REQUIRED"
        elif "unrecognized" in message:
            category = "UNKNOWN"
        elif "credential file mode" in message:
            category = "CREDENTIAL_MODE"
        else:
            category = "VALUE"
        print(f"harness argument failure: {category}", file=sys.stderr)
        super().error("invalid Harness arguments")


def sanitized_browser_failure_class(stdout: bytes, stderr: bytes) -> str:
    try:
        start = stdout.find(b"{")
        end = stdout.rfind(b"}")
        report = json.loads(stdout[start : end + 1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        report = None
    if isinstance(report, dict):
        stats = report.get("stats")
        if isinstance(stats, dict) and stats.get("unexpected", 0) > 0:
            return "ASSERTION"
        if report.get("errors"):
            return "INVOCATION"
    combined = stdout + stderr
    if not combined:
        return "EMPTY"
    if (
        b"npm error" in combined
        or b"Unknown option" in combined
        or b"not found" in combined
        or b"ENOENT" in combined
    ):
        return "INVOCATION"
    if b"EACCES" in combined or b"Permission denied" in combined:
        return "PERMISSION"
    if re.search(rb'"unexpected"\s*:\s*[1-9]', combined) or re.search(
        rb'"status"\s*:\s*"(?:failed|timedOut)"', combined
    ):
        return "ASSERTION"
    patterns = (
        (b"browserType.launch", "LAUNCH"),
        (b"Timed out", "TIMEOUT"),
        (b"TimeoutError", "TIMEOUT"),
        (b"expect(", "ASSERTION"),
        (b"ERR_CONNECTION", "CONNECTION"),
        (b"webServer", "SERVER"),
        (b"Process from config.webServer", "SERVER"),
    )
    return next(
        (category for marker, category in patterns if marker in combined), "COMMAND"
    )


def verify_browser_report(stdout: bytes) -> bool:
    try:
        start = stdout.find(b"{")
        end = stdout.rfind(b"}")
        report = json.loads(stdout[start : end + 1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    stats = report.get("stats") if isinstance(report, dict) else None
    return bool(
        isinstance(stats, dict)
        and type(stats.get("expected")) is int
        and stats["expected"] > 0
        and stats.get("unexpected") == 0
        and stats.get("skipped") == 0
        and stats.get("flaky") == 0
    )


def release_manifest(root: Path) -> dict[str, dict[str, str | int]]:
    result: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        entry: dict[str, str | int] = {"mode": stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            entry.update(type="symlink", target=os.readlink(path))
        elif path.is_dir():
            entry["type"] = "directory"
        elif path.is_file():
            entry.update(
                type="file", sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
        else:
            entry["type"] = "other"
        result[relative] = entry
    return result


def assert_immutable(root: Path) -> None:
    writable = [
        str(path)
        for path in (root, *root.rglob("*"))
        if not path.is_symlink() and path.stat().st_mode & 0o222
    ]
    if writable:
        raise RuntimeError(f"release tree is writable by mode: {writable[0]}")


def endpoint(value: str, name: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https", "postgresql", "postgres"}
        or not parsed.hostname
        or not parsed.port
    ):
        raise ValueError(f"{name} must include an explicit scheme, host and port")
    return value


def verify_postgres_role_readiness(postgres_url: str, expected_role: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", expected_role):
        raise RuntimeError("PostgreSQL validation role identity is invalid")
    schema_name = f"acceptance_preflight_{secrets.token_hex(8)}"
    try:
        with psycopg.connect(postgres_url) as connection:
            identity = connection.execute(
                "SELECT current_user, session_user"
            ).fetchone()
            if identity != (expected_role, expected_role):
                raise RuntimeError("PostgreSQL validation role identity mismatch")
            schema = sql.Identifier(schema_name)
            table = sql.Identifier(schema_name, "migration_read_write_probe")
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            connection.execute(
                sql.SQL(
                    "CREATE TABLE {} (id INTEGER PRIMARY KEY, state TEXT NOT NULL)"
                ).format(table)
            )
            connection.execute(
                sql.SQL("INSERT INTO {} (id, state) VALUES (1, 'CREATED')").format(
                    table
                )
            )
            row = connection.execute(
                sql.SQL("SELECT state FROM {} WHERE id = 1").format(table)
            ).fetchone()
            if row != ("CREATED",):
                raise RuntimeError("PostgreSQL validation role read check failed")
            connection.execute(
                sql.SQL("UPDATE {} SET state = 'UPDATED' WHERE id = 1").format(table)
            )
            connection.execute(sql.SQL("DELETE FROM {} WHERE id = 1").format(table))
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))
            connection.rollback()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("PostgreSQL validation role readiness failed") from exc


class Harness:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.release = args.release_root.resolve()
        self.runtime = args.runtime_dir.resolve()
        self.runtime.mkdir(parents=True, exist_ok=False)
        if self.runtime == self.release or self.release in self.runtime.parents:
            raise RuntimeError("runtime directory must be outside the release")
        self.token = secrets.token_urlsafe(32)
        self.child: subprocess.Popen[bytes] | None = None
        self.child_started_ns = 0
        self.socket_path = self.runtime / "control.sock"
        self.metadata_path = self.runtime / "backend.json"
        caches = [
            path
            for path in self.release.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if caches:
            raise RuntimeError(f"release already contains Python cache: {caches[0]}")
        self.before = release_manifest(self.release)
        self.before_digest = self.manifest_digest(self.before)
        self.restart_count = 0
        (self.runtime / "release-manifest-before.json").write_text(
            json.dumps(self.before, indent=2, sort_keys=True), encoding="utf-8"
        )
        assert_immutable(self.release)

    @property
    def url(self) -> str:
        return f"http://{self.args.backend_host}:{self.args.backend_port}"

    @staticmethod
    def manifest_digest(manifest: dict[str, dict[str, str | int]]) -> str:
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def assert_port_free(self) -> None:
        with socket.socket() as connection_probe:
            connection_probe.settimeout(0.2)
            if (
                connection_probe.connect_ex(
                    (self.args.backend_host, self.args.backend_port)
                )
                == 0
            ):
                raise RuntimeError(
                    "backend port is occupied by an unowned process: "
                    f"{self.args.backend_host}:{self.args.backend_port}"
                )
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((self.args.backend_host, self.args.backend_port))
            except OSError as exc:
                raise RuntimeError(
                    "backend port is occupied by an unowned process: "
                    f"{self.args.backend_host}:{self.args.backend_port}"
                ) from exc

    def write_metadata(self) -> None:
        assert self.child is not None
        payload = {
            "schemaVersion": 1,
            "ownershipToken": self.token,
            "supervisorPid": os.getpid(),
            "backendPid": self.child.pid,
            "backendStartTimeNs": self.child_started_ns,
            "backendHost": self.args.backend_host,
            "backendPort": self.args.backend_port,
            "backendUrl": self.url,
            "releaseRoot": str(self.release),
            "runtimeDir": str(self.runtime),
            "controlSocket": str(self.socket_path),
        }
        temporary = self.metadata_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(self.metadata_path)

    def wait_health(self, expected: bool, timeout: float = 20) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            healthy = False
            try:
                with urllib.request.urlopen(
                    f"{self.url}/healthz", timeout=0.5
                ) as response:
                    healthy = response.status == 200
            except Exception:
                pass
            if healthy is expected:
                return
            time.sleep(0.1)
        raise RuntimeError(f"backend health did not become {expected}")

    def start(self, overrides: dict[str, str] | None = None) -> None:
        self.assert_port_free()
        env = os.environ.copy()
        python_paths = [
            str((self.release / entry).resolve())
            for entry in self.args.python_path.split(os.pathsep)
        ]
        env.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": str(self.runtime / "pycache"),
                "AGENT_DEFINITION_DATABASE_URL": self.args.postgres_url,
                "SKILL_MCP_DATABASE_URL": self.args.postgres_url,
                "KNOWLEDGE_DATABASE_URL": self.args.postgres_url,
                "WORKFLOW_RUNTIME_DATABASE_URL": self.args.postgres_url,
                "KNOWLEDGE_QDRANT_URL": self.args.qdrant_url,
                "S5_IMPL_041_QDRANT_URL": self.args.qdrant_url,
                "S5_HARNESS_OWNERSHIP_TOKEN": self.token,
                "PYTHONPATH": os.pathsep.join(python_paths),
            }
        )
        allowed = {
            "S5_PLANNING_PROVIDER",
            "S5_PLANNING_BASE_URL",
            "S5_PLANNING_API_KEY",
            "S5_PLANNING_MODEL",
            "S5_EMBEDDING_PROVIDER",
            "S5_EMBEDDING_BASE_URL",
            "S5_EMBEDDING_API_KEY",
            "S5_EMBEDDING_MODEL",
        }
        for key, value in (overrides or {}).items():
            if key not in allowed or not isinstance(value, str):
                raise RuntimeError("unsupported backend environment override")
            if key.endswith("BASE_URL"):
                parsed = urlparse(value)
                if (
                    parsed.scheme != "http"
                    or parsed.hostname
                    not in {
                        "127.0.0.1",
                        "localhost",
                    }
                    or not parsed.port
                ):
                    raise RuntimeError("test provider URL must be explicit localhost")
            env[key] = value
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_console.app:app",
            "--host",
            self.args.backend_host,
            "--port",
            str(self.args.backend_port),
            "--header",
            f"X-Harness-Ownership-Token:{self.token}",
        ]
        self.child = subprocess.Popen(
            command,
            cwd=self.release,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.child_started_ns = time.time_ns()
        self.write_metadata()
        self.wait_health(True)

    def verify_owned(self) -> None:
        if self.child is None or self.child.poll() is not None:
            raise RuntimeError("owned backend is not running")
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        expected = (
            self.token,
            self.child.pid,
            str(self.release),
            self.args.backend_port,
        )
        actual = (
            metadata.get("ownershipToken"),
            metadata.get("backendPid"),
            metadata.get("releaseRoot"),
            metadata.get("backendPort"),
        )
        if actual != expected:
            raise RuntimeError("backend ownership metadata mismatch")
        if Path(f"/proc/{self.child.pid}").exists():
            cwd = Path(f"/proc/{self.child.pid}/cwd").resolve()
            command = Path(f"/proc/{self.child.pid}/cmdline").read_bytes().split(b"\0")
            joined = b" ".join(command)
            if (
                cwd != self.release
                or b"uvicorn" not in joined
                or str(self.args.backend_port).encode() not in command
                or self.token.encode() not in joined
            ):
                raise RuntimeError("backend process identity mismatch")
        else:
            command = subprocess.run(
                ["ps", "-p", str(self.child.pid), "-o", "command="],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            cwd = subprocess.run(
                ["lsof", "-a", "-p", str(self.child.pid), "-d", "cwd", "-Fn"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            listener = subprocess.run(
                [
                    "lsof",
                    "-nP",
                    "-a",
                    "-p",
                    str(self.child.pid),
                    f"-iTCP:{self.args.backend_port}",
                    "-sTCP:LISTEN",
                ],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            if (
                "uvicorn" not in command
                or self.token not in command
                or str(self.args.backend_port) not in command
                or f"n{self.release}" not in cwd
                or not listener
            ):
                raise RuntimeError(
                    "backend executable, command, cwd, token, or listener mismatch"
                )

    def stop(self) -> None:
        if self.child is None or self.child.poll() is not None:
            return
        self.verify_owned()
        self.child.terminate()
        try:
            self.child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.verify_owned()
            self.child.kill()
            self.child.wait(timeout=5)
        self.wait_health(False)

    def restart(self, overrides: dict[str, str] | None = None) -> None:
        self.stop()
        self.start(overrides)
        self.restart_count += 1

    def serve(self, ready: threading.Event) -> None:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            server.listen()
            ready.set()
            while True:
                connection, _ = server.accept()
                with connection:
                    request = json.loads(connection.recv(65536))
                    if request.get("ownershipToken") != self.token:
                        response = {"ok": False, "error": "ownership token mismatch"}
                    elif request.get("action") == "restart":
                        try:
                            self.restart(request.get("environment"))
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "status":
                        try:
                            self.verify_owned()
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "stop":
                        try:
                            self.stop()
                            response = {"ok": True}
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif request.get("action") == "start":
                        try:
                            if self.child is not None and self.child.poll() is None:
                                raise RuntimeError("owned backend is already running")
                            self.start(request.get("environment"))
                            response = {
                                "ok": True,
                                "backendPid": self.child.pid,
                                "backendStartTimeNs": self.child_started_ns,
                            }
                        except Exception as exc:
                            response = {"ok": False, "error": str(exc)}
                    else:
                        response = {"ok": False, "error": "unsupported action"}
                    connection.sendall(json.dumps(response).encode())

    def verify_release(self) -> dict[str, dict[str, str | int]]:
        after = release_manifest(self.release)
        (self.runtime / "release-manifest-after.json").write_text(
            json.dumps(after, indent=2, sort_keys=True), encoding="utf-8"
        )
        if after != self.before:
            raise RuntimeError(
                "immutable release content, file modes, or directory modes changed"
            )
        caches = [
            path
            for path in self.release.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if caches:
            raise RuntimeError(f"Python cache appeared inside release: {caches[0]}")
        return after

    def write_minimum_disclosure_evidence(
        self, after: dict[str, dict[str, str | int]], command_result: int
    ) -> Path:
        assert self.child is not None
        record = {
            "schemaVersion": 1,
            "acceptanceState": "PASSED" if command_result == 0 else "FAILED",
            "backendPid": self.child.pid,
            "backendStartTimeNs": self.child_started_ns,
            "backendRestartCount": self.restart_count,
            "releaseEntryCount": len(after),
            "releaseManifestBeforeDigest": self.before_digest,
            "releaseManifestAfterDigest": self.manifest_digest(after),
            "journeyId": self.args.journey_id,
            "phase": "BROWSER_EXECUTION",
            "assertionCategory": "BROWSER_ACCEPTANCE",
            "statusCode": command_result,
            "exceptionClass": (
                "NONE" if command_result == 0 else "BROWSER_COMMAND_FAILED"
            ),
            "correlationDigest": hashlib.sha256(
                (
                    f"{self.args.journey_id}:{command_result}:{self.restart_count}:"
                    f"{self.before_digest}:{self.manifest_digest(after)}"
                ).encode()
            ).hexdigest(),
            "restartRelation": (
                "NO_RESTART"
                if self.restart_count == 0
                else f"OWNED_RESTART_COUNT_{self.restart_count}"
            ),
            "completedAt": datetime.now(UTC).isoformat(),
        }
        evidence = extract_allowlisted(record, set(EVIDENCE_FIELDS))
        path = self.runtime / "acceptance-evidence.json"
        path.write_text(json.dumps(evidence, sort_keys=True), encoding="utf-8")
        return path


def parse_args() -> argparse.Namespace:
    parser = SafeArgumentParser()
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--backend-host", required=True)
    parser.add_argument("--backend-port", required=True, type=int)
    parser.add_argument("--frontend-port", required=True, type=int)
    postgres = parser.add_mutually_exclusive_group(required=True)
    postgres.add_argument("--postgres-url")
    postgres.add_argument("--postgres-url-file", type=Path)
    parser.add_argument("--postgres-validation-role", required=True)
    parser.add_argument("--qdrant-url", required=True)
    parser.add_argument("--build-mode-identity", required=True, type=Path)
    parser.add_argument("--journey-id", required=True)
    parser.add_argument("--python-path", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("a browser command is required after --")
    if args.postgres_url_file is not None:
        if stat.S_IMODE(args.postgres_url_file.stat().st_mode) != 0o600:
            parser.error("PostgreSQL credential file mode must be 0600")
        args.postgres_url = args.postgres_url_file.read_text(encoding="utf-8")
    args.postgres_url = endpoint(args.postgres_url, "PostgreSQL endpoint")
    args.qdrant_url = endpoint(args.qdrant_url, "Qdrant endpoint")
    return args


def main() -> int:
    args = parse_args()
    print("harness phase: ARGUMENTS", file=sys.stderr)
    verify_build_identity(
        args.release_root.resolve() / "console/frontend/dist",
        args.build_mode_identity.resolve(),
    )
    print("harness phase: BUILD_IDENTITY", file=sys.stderr)
    verify_postgres_role_readiness(args.postgres_url, args.postgres_validation_role)
    print("harness phase: POSTGRES_ROLE", file=sys.stderr)
    harness = Harness(args)
    print("harness phase: CANDIDATE", file=sys.stderr)
    command_result = 1
    try:
        harness.start()
        print("harness phase: BACKEND", file=sys.stderr)
        ready = threading.Event()
        threading.Thread(target=harness.serve, args=(ready,), daemon=True).start()
        ready.wait(timeout=5)
        env = os.environ.copy()
        env.update(
            {
                "S5_HARNESS_METADATA": str(harness.metadata_path),
                "S5_HARNESS_OWNERSHIP_TOKEN": harness.token,
                "CONSOLE_BACKEND_URL": harness.url,
                "VITE_BACKEND_URL": harness.url,
                "CONSOLE_FRONTEND_PORT": str(args.frontend_port),
                "KNOWLEDGE_QDRANT_DIRECT_URL": args.qdrant_url,
                "S5_IMMUTABLE_ACCEPTANCE": "1",
                "PLAYWRIGHT_OUTPUT_DIR": str(harness.runtime / "playwright-output"),
                "S5_HARNESS_PYTHON": sys.executable,
            }
        )
        browser_result = subprocess.run(
            args.command,
            cwd=harness.release,
            env=env,
            capture_output=True,
            check=False,
        )
        command_result = browser_result.returncode
        if command_result == 0 and not verify_browser_report(browser_result.stdout):
            command_result = 1
        print("harness phase: BROWSER_COMMAND", file=sys.stderr)
        if command_result:
            category = sanitized_browser_failure_class(
                browser_result.stdout, browser_result.stderr
            )
            print(f"browser acceptance failed: {category}", file=sys.stderr)
            failure = sanitized_first_failure_record(
                browser_result.stdout, args.journey_id, harness.restart_count
            )
            if failure is None:
                failure = sanitized_first_failure_record(
                    json.dumps({"stats": {"unexpected": 1}}).encode(),
                    args.journey_id,
                    harness.restart_count,
                )
            failure_path = harness.runtime / "browser-first-failure.json"
            failure_path.write_text(
                json.dumps(failure, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            scan_generated_artifacts([failure_path])
    finally:
        try:
            harness.stop()
        finally:
            playwright_output = harness.runtime / "playwright-output"
            if playwright_output.exists():
                shutil.rmtree(playwright_output)
            if playwright_output.exists():
                raise RuntimeError("raw browser artifacts were retained")
            after = harness.verify_release()
            evidence = harness.write_minimum_disclosure_evidence(after, command_result)
            scan_generated_artifacts([args.build_mode_identity, evidence])
    return command_result


if __name__ == "__main__":
    print("harness phase: MODULE", file=sys.stderr)
    try:
        raise SystemExit(main())
    except Exception as exc:
        safe_class = (
            "PREFLIGHT_FAILURE"
            if isinstance(exc, (RuntimeError, ValueError))
            else "INTERNAL_FAILURE"
        )
        print(f"isolated browser acceptance failed: {safe_class}", file=sys.stderr)
        raise SystemExit(2) from None
