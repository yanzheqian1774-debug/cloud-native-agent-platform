#!/usr/bin/env python3
"""Deterministic, fail-closed v0.2.2 release rehearsal runner."""

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
import tarfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from browser_build_preflight import (  # noqa: E402
    record_build_identity,
    verify_build_identity,
)
from isolated_browser_harness import (  # noqa: E402
    assert_immutable,
    release_manifest,
)
from minimum_disclosure import scan_generated_artifacts  # noqa: E402

SCHEMA_VERSION = 1
MODES = frozenset(
    {
        "preflight",
        "micro-postgres",
        "readiness-rehearsal",
        "private-acceptance-precheck",
    }
)
STAGES = (
    "provenance",
    "locked-frontend-build",
    "live-demo-build-identity",
    "docker-preflight",
    "postgres-start",
    "postgres-provision",
    "migrations-readiness",
    "qdrant-health",
    "candidate-presentation",
    "write-bytecode-denial",
    "candidate-resolution",
    "browser-harness",
    "sanitized-diagnostics",
    "nondisclosure-scan",
    "manifest-immutability",
    "continuity-monitoring",
    "owned-cleanup",
)
RECORD_FIELDS = frozenset(
    {
        "schemaVersion",
        "stageId",
        "state",
        "timestamp",
        "exitCode",
        "errorCategory",
        "errorCode",
        "correlationDigest",
        "completedAt",
    }
)
ERROR_CATEGORIES = frozenset(
    {
        "NONE",
        "CONTRACT",
        "PROVENANCE",
        "INTERPRETER",
        "DOCKER_DAEMON",
        "IMAGE",
        "NAME_CONFLICT",
        "PORT_CONFLICT",
        "MOUNT",
        "PERMISSION",
        "RESOURCE",
        "CONFIGURATION",
        "POSTGRES",
        "QDRANT",
        "CANDIDATE",
        "BROWSER",
        "BROWSER_ASSERTION",
        "BROWSER_TIMEOUT",
        "BROWSER_CONNECTION",
        "BROWSER_SERVER",
        "BROWSER_INVOCATION",
        "BROWSER_PERMISSION",
        "BROWSER_LAUNCH",
        "BROWSER_PREFLIGHT_BUILD",
        "BROWSER_PREFLIGHT_POSTGRES",
        "BROWSER_PREFLIGHT_CANDIDATE",
        "BROWSER_PREFLIGHT_BACKEND",
        "BROWSER_ARGUMENTS",
        "BROWSER_ARGUMENTS_REQUIRED",
        "BROWSER_ARGUMENTS_UNKNOWN",
        "BROWSER_ARGUMENTS_CREDENTIAL_MODE",
        "BROWSER_ARGUMENTS_VALUE",
        "BROWSER_MODULE",
        "BROWSER_MODULE_DEPENDENCY",
        "BROWSER_MODULE_PERMISSION",
        "BROWSER_MODULE_FILE",
        "BROWSER_MODULE_SYNTAX",
        "BROWSER_MODULE_PSYCOPG",
        "BROWSER_MODULE_BUILD_PREFLIGHT",
        "BROWSER_MODULE_DISCLOSURE",
        "DISCLOSURE",
        "OWNERSHIP",
        "INTERNAL",
    }
)
TOP_FIELDS = frozenset(
    {
        "schemaVersion",
        "product",
        "acceptanceToolSourceSha",
        "build",
        "images",
        "ports",
        "identity",
        "validationRolePolicy",
        "pythonInterpreter",
        "applicationSourceDirectories",
        "diagnosticRetentionPolicy",
        "migrations",
        "browser",
        "continuitySentinels",
    }
)
PRODUCT_FIELDS = frozenset({"sourceSha", "treeSha"})
BUILD_FIELDS = frozenset({"mode", "frontendManifestPath", "frontendManifestDigest"})
IMAGE_FIELDS = frozenset({"postgres", "qdrant"})
PORT_FIELDS = frozenset({"postgres", "qdrant", "backend", "frontend"})
IDENTITY_FIELDS = frozenset({"runtimeRoot", "workspaceRoot"})
ROLE_FIELDS = frozenset({"administrativeRole", "validationRole", "database"})
DIAGNOSTIC_FIELDS = frozenset(
    {"retainRaw", "retainSanitized", "scanCompressed", "disposeBrowserArtifacts"}
)
BROWSER_FIELDS = frozenset(
    {"command", "journeyId", "executablePath", "executableDigest"}
)
SENTINEL_FIELDS = frozenset({"name", "healthUrl", "pid", "startTime"})
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]{0,62}\Z")
IMAGE = re.compile(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}\Z")
FAULTS = frozenset(
    {
        "name-conflict",
        "port-conflict",
        "missing-image",
        "invalid-mount",
        "permission-failure",
        "daemon-unavailable",
        "storage-resource-failure",
        "invalid-configuration",
    }
)


class RunnerError(RuntimeError):
    def __init__(self, category: str, safe_message: str, code: str | None = None):
        super().__init__(safe_message)
        self.category = category if category in ERROR_CATEGORIES else "INTERNAL"
        self.code = code


def fail(category: str, message: str, code: str | None = None) -> NoReturn:
    raise RunnerError(category, message, code)


def _exact(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        fail("CONTRACT", f"{label} has missing, duplicate, or unknown fields")
    return value


def load_contract(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        pairs: list[tuple[str, Any]] = []

        def object_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            keys = [key for key, _ in items]
            if len(keys) != len(set(keys)):
                fail("CONTRACT", "release contract contains a duplicate field")
            pairs.extend(items)
            return dict(items)

        value = json.loads(text, object_pairs_hook=object_pairs)
    except RunnerError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerError(
            "CONTRACT", "release contract is unavailable or malformed"
        ) from exc
    contract = _exact(value, TOP_FIELDS, "release contract")
    product = _exact(contract["product"], PRODUCT_FIELDS, "product")
    build = _exact(contract["build"], BUILD_FIELDS, "build")
    images = _exact(contract["images"], IMAGE_FIELDS, "images")
    ports = _exact(contract["ports"], PORT_FIELDS, "ports")
    identity = _exact(contract["identity"], IDENTITY_FIELDS, "identity")
    roles = _exact(
        contract["validationRolePolicy"], ROLE_FIELDS, "validation role policy"
    )
    diagnostics = _exact(
        contract["diagnosticRetentionPolicy"], DIAGNOSTIC_FIELDS, "diagnostic policy"
    )
    migrations = contract["migrations"]
    browser = _exact(contract["browser"], BROWSER_FIELDS, "browser")
    if contract["schemaVersion"] != SCHEMA_VERSION:
        fail("CONTRACT", "release contract schema version is unsupported")
    for value in (
        product["sourceSha"],
        product["treeSha"],
        contract["acceptanceToolSourceSha"],
    ):
        if not isinstance(value, str) or not GIT_SHA.fullmatch(value):
            fail("CONTRACT", "release contract contains a malformed Git identity")
    if not isinstance(build["frontendManifestDigest"], str) or not DIGEST.fullmatch(
        build["frontendManifestDigest"]
    ):
        fail("CONTRACT", "release contract contains a malformed digest")
    if build["mode"] != "LIVE_DEMO" or not isinstance(
        build["frontendManifestPath"], str
    ):
        fail("CONTRACT", "release build identity is unsafe")
    for value in images.values():
        if not isinstance(value, str) or not IMAGE.fullmatch(value):
            fail("CONTRACT", "container image is not digest pinned")
    port_values = list(ports.values())
    if any(
        type(port) is not int or not 1024 <= port <= 65535 for port in port_values
    ) or len(set(port_values)) != len(port_values):
        fail("CONTRACT", "isolated port allocation is malformed or duplicated")
    for value in roles.values():
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            fail("CONTRACT", "validation role policy contains an unsafe identifier")
    workspace = Path(identity["workspaceRoot"])
    runtime = Path(identity["runtimeRoot"])
    if (
        not workspace.is_absolute()
        or not runtime.is_absolute()
        or runtime == workspace
        or workspace in runtime.parents
    ):
        fail("CONTRACT", "runtime/workspace identity is unsafe")
    interpreter = contract["pythonInterpreter"]
    if (
        not isinstance(interpreter, str)
        or not interpreter
        or Path(interpreter).name.startswith("python") is False
    ):
        fail("CONTRACT", "candidate interpreter is malformed")
    sources = contract["applicationSourceDirectories"]
    if (
        not isinstance(sources, list)
        or not sources
        or len(sources) != len(set(sources))
    ):
        fail("CONTRACT", "application source directories are malformed or duplicated")
    if any(
        not isinstance(item, str)
        or Path(item).is_absolute()
        or ".." in Path(item).parts
        for item in sources
    ):
        fail("CONTRACT", "application source directory is unsafe")
    expected_policy = {
        "retainRaw": False,
        "retainSanitized": True,
        "scanCompressed": True,
        "disposeBrowserArtifacts": True,
    }
    if diagnostics != expected_policy:
        fail("CONTRACT", "diagnostic retention policy is unsafe")
    expected_migrations = {f"{version:04d}" for version in range(1, 8)}
    if not isinstance(migrations, dict) or set(migrations) != expected_migrations:
        fail("CONTRACT", "migration identity set is incomplete or unknown")
    if any(
        not isinstance(value, str) or not DIGEST.fullmatch(value)
        for value in migrations.values()
    ):
        fail("CONTRACT", "migration identity is malformed")
    command = browser["command"]
    expected_command = [
        "npm",
        "--prefix",
        "console/frontend",
        "run",
        "test:e2e",
        "--",
        "--workers",
        "1",
        "--retries",
        "0",
        "--forbid-only",
        "--reporter",
        "json",
    ]
    if (
        command != expected_command
        or browser["journeyId"] != "s5-impl-078-release-rehearsal"
    ):
        fail("CONTRACT", "browser command contract is malformed")
    executable = Path(browser["executablePath"])
    if (
        not executable.is_absolute()
        or not isinstance(browser["executableDigest"], str)
        or not DIGEST.fullmatch(browser["executableDigest"])
    ):
        fail("CONTRACT", "browser executable identity is malformed")
    sentinels = contract["continuitySentinels"]
    if not isinstance(sentinels, list) or len(sentinels) > 2:
        fail("CONTRACT", "continuity sentinel contract is malformed")
    names: set[str] = set()
    for sentinel_value in sentinels:
        sentinel = _exact(sentinel_value, SENTINEL_FIELDS, "continuity sentinel")
        if (
            sentinel["name"] not in {"public", "staging"}
            or sentinel["name"] in names
            or not isinstance(sentinel["healthUrl"], str)
            or not sentinel["healthUrl"].startswith("http://127.0.0.1:")
            or type(sentinel["pid"]) is not int
            or sentinel["pid"] <= 1
            or not isinstance(sentinel["startTime"], str)
            or not sentinel["startTime"]
        ):
            fail("CONTRACT", "continuity sentinel identity is unsafe")
        names.add(sentinel["name"])
    return contract


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    timeout: float = 120,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            input=stdin,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("RESOURCE", "bounded command deadline expired") from exc
    except (OSError, PermissionError) as exc:
        raise RunnerError(
            "CONFIGURATION",
            "required executable could not be started",
            getattr(exc, "errno", None) and str(exc.errno),
        ) from exc


@dataclass
class Runner:
    contract: dict[str, Any]
    mode: str
    output: Path
    fault: str | None = None
    token: str = field(default_factory=lambda: secrets.token_hex(16))
    records: list[dict[str, Any]] = field(default_factory=list)
    owned_containers: set[str] = field(default_factory=set)
    credential_files: set[Path] = field(default_factory=set)
    validation_password: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    administrative_password: str = field(
        default_factory=lambda: secrets.token_urlsafe(24)
    )
    runtime_dir: Path | None = None
    candidate_dir: Path | None = None
    build_identity_path: Path | None = None
    candidate_before: dict[str, dict[str, str | int]] | None = None
    sentinel_before: dict[str, tuple[str, int]] = field(default_factory=dict)
    chromium_path: Path | None = None

    @property
    def workspace(self) -> Path:
        return Path(self.contract["identity"]["workspaceRoot"]).resolve()

    def emit(
        self,
        stage: str,
        state: str,
        started: str,
        exit_code: int,
        category: str = "NONE",
        code: str | None = None,
    ) -> None:
        completed = datetime.now(UTC).isoformat()
        correlation = digest_bytes(
            f"{self.token}:{stage}:{state}:{exit_code}:{category}:{code or ''}".encode()
        )
        record = {
            "schemaVersion": SCHEMA_VERSION,
            "stageId": stage,
            "state": state,
            "timestamp": started,
            "exitCode": exit_code,
            "errorCategory": category,
            "errorCode": code,
            "correlationDigest": correlation,
            "completedAt": completed,
        }
        if set(record) != RECORD_FIELDS:
            fail("INTERNAL", "stage record schema violation")
        self.records.append(record)

    def stage(self, name: str, action: Callable[[], None]) -> None:
        started = datetime.now(UTC).isoformat()
        try:
            action()
        except RunnerError as exc:
            self.emit(name, "FAILED", started, 2, exc.category, exc.code)
            raise
        except KeyboardInterrupt as exc:
            self.emit(name, "FAILED", started, 130, "CONFIGURATION", None)
            raise RunnerError("CONFIGURATION", "stage was interrupted") from exc
        except Exception as exc:
            self.emit(
                name,
                "FAILED",
                started,
                2,
                "INTERNAL",
                str(getattr(exc, "errno", "")) or None,
            )
            raise RunnerError(
                "INTERNAL", "stage failed with sanitized internal error"
            ) from exc
        self.emit(name, "PASSED", started, 0)

    def skip(self, name: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.emit(name, "NOT_APPLICABLE", now, 0)

    def provenance(self) -> None:
        product = self.contract["product"]
        result = run_command(
            ["git", "rev-parse", f"{product['sourceSha']}^{{tree}}"], self.workspace
        )
        if result.returncode or result.stdout.decode().strip() != product["treeSha"]:
            fail(
                "PROVENANCE", "candidate provenance does not match the release contract"
            )
        minimum = run_command(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                self.contract["acceptanceToolSourceSha"],
                "HEAD",
            ],
            self.workspace,
        )
        if minimum.returncode:
            fail("PROVENANCE", "acceptance tooling is older than the contract minimum")

    def frontend_lock(self) -> None:
        build = self.contract["build"]
        path = (self.workspace / build["frontendManifestPath"]).resolve()
        if (
            self.workspace not in path.parents
            or not path.is_file()
            or digest_bytes(path.read_bytes()) != build["frontendManifestDigest"]
        ):
            fail("PROVENANCE", "frontend manifest identity mismatch")

    def ensure_runtime(self) -> None:
        if self.runtime_dir is not None:
            return
        runtime_root = Path(self.contract["identity"]["runtimeRoot"])
        runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.runtime_dir = runtime_root / self.token
        self.runtime_dir.mkdir(mode=0o700)
        marker = self.runtime_dir / "ownership.json"
        marker.write_text(
            json.dumps({"schemaVersion": 1, "ownershipToken": self.token}),
            encoding="utf-8",
        )
        marker.chmod(0o600)

    def verify_runtime_owned(self) -> None:
        if self.runtime_dir is None:
            fail("OWNERSHIP", "runtime ownership identity is unavailable")
        marker = self.runtime_dir / "ownership.json"
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RunnerError(
                "OWNERSHIP", "runtime ownership identity is invalid"
            ) from exc
        if value != {"schemaVersion": 1, "ownershipToken": self.token}:
            fail("OWNERSHIP", "runtime ownership identity mismatch")

    def interpreter(self) -> None:
        configured = (self.workspace / self.contract["pythonInterpreter"]).absolute()
        if not configured.is_file() or not os.access(configured, os.X_OK):
            fail("INTERPRETER", "candidate Python interpreter is unavailable")
        result = run_command(
            [
                str(configured),
                "-c",
                "import json,sys;print(json.dumps([sys.executable,sys.prefix]))",
            ],
            self.workspace,
        )
        try:
            executable, prefix = json.loads(result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise RunnerError(
                "INTERPRETER", "candidate Python interpreter identity mismatch"
            ) from exc
        if (
            result.returncode
            or Path(executable) != configured
            or Path(prefix) != configured.parent.parent
        ):
            fail("INTERPRETER", "candidate Python interpreter identity mismatch")
        for source in self.contract["applicationSourceDirectories"]:
            if not (self.workspace / source).is_dir():
                fail(
                    "CANDIDATE", "approved application source directory is unavailable"
                )

    def port_preflight(self) -> None:
        for port in self.contract["ports"].values():
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError as exc:
                    fail(
                        "PORT_CONFLICT", "isolated port is unavailable", str(exc.errno)
                    )

    def docker(
        self, args: list[str], category: str = "CONFIGURATION"
    ) -> subprocess.CompletedProcess[bytes]:
        if self.fault == "daemon-unavailable":
            fail("DOCKER_DAEMON", "Docker daemon is unavailable")
        result = run_command(["docker", *args], self.workspace)
        if result.returncode:
            mapping = {
                "missing-image": "IMAGE",
                "name-conflict": "NAME_CONFLICT",
                "invalid-mount": "MOUNT",
                "permission-failure": "PERMISSION",
                "storage-resource-failure": "RESOURCE",
                "invalid-configuration": "CONFIGURATION",
            }
            fail(mapping.get(self.fault or "", category), "Docker operation failed")
        return result

    def docker_preflight(self) -> None:
        self.docker(["info", "--format", "{{.ServerVersion}}"], "DOCKER_DAEMON")
        if self.fault == "port-conflict":
            fail("PORT_CONFLICT", "isolated port is unavailable")
        for image in self.contract["images"].values():
            target = (
                "missing.invalid@sha256:" + "0" * 64
                if self.fault == "missing-image"
                else image
            )
            inspected = self.docker(
                ["image", "inspect", target, "--format", "{{index .RepoDigests 0}}"],
                "IMAGE",
            )
            if inspected.stdout.decode().strip() != image:
                fail("IMAGE", "container image digest mismatch")
        self.port_preflight()
        runtime = Path(self.contract["identity"]["runtimeRoot"])
        if (
            self.fault == "invalid-mount"
            or runtime == self.workspace
            or self.workspace in runtime.parents
        ):
            fail("MOUNT", "runtime mount source is unsafe")
        usage = shutil.disk_usage(runtime.parent)
        if self.fault == "storage-resource-failure" or usage.free < 512 * 1024 * 1024:
            fail("RESOURCE", "runtime storage is insufficient")

    def container_name(self, service: str) -> str:
        return f"s5-impl-078-{service}-{self.token[:12]}"

    def verify_owned(self, name: str) -> None:
        if name not in self.owned_containers:
            fail("OWNERSHIP", "cleanup target is not runner-owned")
        result = self.docker(
            [
                "inspect",
                name,
                "--format",
                '{{index .Config.Labels "io.agent-platform.release-owner"}}',
            ],
            "OWNERSHIP",
        )
        if result.stdout.decode().strip() != self.token:
            fail("OWNERSHIP", "cleanup target ownership mismatch")

    def postgres_start(self) -> None:
        name = self.container_name("postgres")
        if self.fault == "name-conflict":
            name = "s5-impl-078-forced-conflict"
        roles = self.contract["validationRolePolicy"]
        port = self.contract["ports"]["postgres"]
        self.ensure_runtime()
        assert self.runtime_dir is not None
        environment_file = self.runtime_dir / "postgres.env"
        descriptor = os.open(
            environment_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"POSTGRES_DB={roles['database']}\n")
            stream.write(f"POSTGRES_PASSWORD={self.administrative_password}\n")
        self.credential_files.add(environment_file)
        pgpass = self.runtime_dir / "pgpass"
        descriptor = os.open(pgpass, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(
                f"127.0.0.1:5432:{roles['database']}:"
                f"{roles['administrativeRole']}:{self.administrative_password}\n"
            )
            stream.write(
                f"127.0.0.1:5432:{roles['database']}:"
                f"{roles['validationRole']}:{self.validation_password}\n"
            )
        self.credential_files.add(pgpass)
        args = [
            "run",
            "--detach",
            "--name",
            name,
            "--label",
            f"io.agent-platform.release-owner={self.token}",
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--env-file",
            str(environment_file),
            "--mount",
            f"type=bind,src={self.runtime_dir},dst=/runner-secrets,readonly",
            self.contract["images"]["postgres"],
        ]
        self.docker(args, "POSTGRES")
        self.owned_containers.add(name)
        for _ in range(60):
            ready = run_command(
                [
                    "docker",
                    "exec",
                    "--env",
                    "PGPASSFILE=/runner-secrets/pgpass",
                    name,
                    "psql",
                    "--no-psqlrc",
                    "--host",
                    "127.0.0.1",
                    "--username",
                    roles["administrativeRole"],
                    "--dbname",
                    roles["database"],
                    "--tuples-only",
                    "--command",
                    "SELECT 1",
                ],
                self.workspace,
                timeout=5,
            )
            if ready.returncode == 0:
                return
            time.sleep(0.25)
        fail("POSTGRES", "PostgreSQL readiness deadline expired")

    def pg(self, sql: str, user: str | None = None) -> None:
        name = self.container_name("postgres")
        roles = self.contract["validationRolePolicy"]
        if name not in self.owned_containers:
            name = next(iter(self.owned_containers))
        command = [
            "exec",
            "-i",
        ]
        command.extend(
            [
                "--env",
                "PGPASSFILE=/runner-secrets/pgpass",
            ]
        )
        command.extend(
            [
                name,
                "psql",
                "--no-psqlrc",
                "--set",
                "ON_ERROR_STOP=1",
                "--username",
                user or roles["administrativeRole"],
                "--dbname",
                roles["database"],
            ]
        )
        command[command.index("--username") : command.index("--username")] = [
            "--host",
            "127.0.0.1",
        ]
        result = (
            self.docker(command, "POSTGRES")
            if not sql
            else run_command(["docker", *command], self.workspace, stdin=sql.encode())
        )
        if result.returncode:
            code = None
            match = re.search(rb"SQLSTATE[ =:]+([0-9A-Z]{5})", result.stderr)
            if match:
                code = match.group(1).decode()
            fail("POSTGRES", "PostgreSQL stage failed", code)

    def postgres_provision(self) -> None:
        roles = self.contract["validationRolePolicy"]
        role = roles["validationRole"]
        if not IDENTIFIER.fullmatch(role):
            fail("CONTRACT", "validation role identifier is unsafe")
        database = roles["database"]
        self.pg(
            f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{self.validation_password}';\n"
            f'GRANT CONNECT, CREATE ON DATABASE "{database}" TO "{role}";\n'
        )

    def postgres_readiness(self) -> None:
        role = self.contract["validationRolePolicy"]["validationRole"]
        self.pg(
            "SELECT current_user;\n"
            f'CREATE SCHEMA release_runner_probe AUTHORIZATION "{role}";\n'
            "CREATE TABLE release_runner_probe.item("
            "id integer primary key, state text);\n"
            "INSERT INTO release_runner_probe.item VALUES (1,'created');\n"
            "SELECT state FROM release_runner_probe.item WHERE id=1;\n"
            "UPDATE release_runner_probe.item SET state='updated' WHERE id=1;\n"
            "DELETE FROM release_runner_probe.item WHERE id=1;\n"
            "DROP SCHEMA release_runner_probe CASCADE;\n"
            f'BEGIN; CREATE SCHEMA rollback_probe AUTHORIZATION "{role}"; ROLLBACK;\n'
            "DO $$ BEGIN IF to_regnamespace('rollback_probe') IS NOT NULL THEN "
            "RAISE EXCEPTION 'rollback verification failed'; END IF; END $$;\n",
            role,
        )

    def apply_migrations(self) -> None:
        role = self.contract["validationRolePolicy"]["validationRole"]
        migration_root = self.workspace / "console/backend/migrations"
        for version in range(1, 8):
            prefix = f"{version:04d}_"
            matches = sorted(migration_root.glob(f"{prefix}*.sql"))
            if len(matches) != 1:
                fail("POSTGRES", "migration source identity is ambiguous")
            data = matches[0].read_bytes()
            if digest_bytes(data) != self.contract["migrations"][f"{version:04d}"]:
                fail("PROVENANCE", "migration checksum identity mismatch")
            self.pg(data.decode("utf-8"), role)
        self.postgres_readiness()

    def qdrant_start(self) -> None:
        self.ensure_runtime()
        assert self.runtime_dir is not None
        storage = self.runtime_dir / "qdrant-storage"
        storage.mkdir(mode=0o700)
        name = self.container_name("qdrant")
        port = self.contract["ports"]["qdrant"]
        self.docker(
            [
                "run",
                "--detach",
                "--name",
                name,
                "--label",
                f"io.agent-platform.release-owner={self.token}",
                "--publish",
                f"127.0.0.1:{port}:6333",
                "--mount",
                f"type=bind,src={storage},dst=/qdrant/storage",
                self.contract["images"]["qdrant"],
            ],
            "QDRANT",
        )
        self.owned_containers.add(name)
        url = f"http://127.0.0.1:{port}/healthz"
        for _ in range(80):
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.25)
        fail("QDRANT", "Qdrant readiness deadline expired")

    def present_candidate(self) -> None:
        self.ensure_runtime()
        assert self.runtime_dir is not None
        self.candidate_dir = self.runtime_dir / "candidate"
        self.candidate_dir.mkdir(mode=0o700)
        source = self.contract["product"]["sourceSha"]
        archive = run_command(
            ["git", "archive", "--format=tar", source], self.workspace
        )
        if archive.returncode:
            fail("PROVENANCE", "candidate source archive is unavailable")
        archive_path = self.runtime_dir / "candidate.tar"
        archive_path.write_bytes(archive.stdout)
        try:
            with tarfile.open(archive_path) as bundle:
                bundle.extractall(self.candidate_dir, filter="data")
        except (OSError, tarfile.TarError) as exc:
            raise RunnerError("CANDIDATE", "candidate presentation failed") from exc
        archive_path.unlink()
        config_path = "console/frontend/playwright.config.ts"
        overlay = run_command(
            [
                "git",
                "show",
                f"{self.contract['acceptanceToolSourceSha']}:{config_path}",
            ],
            self.workspace,
        )
        if overlay.returncode:
            fail("PROVENANCE", "acceptance configuration overlay is unavailable")
        config = overlay.stdout.decode("utf-8")
        relative = "../../scripts/acceptance/static_proxy_server.py --root dist"
        explicit = (
            f"{self.candidate_dir}/scripts/acceptance/static_proxy_server.py "
            f"--root {self.candidate_dir}/console/frontend/dist"
        )
        if config.count(relative) != 1:
            fail("PROVENANCE", "acceptance configuration command is ambiguous")
        (self.candidate_dir / config_path).write_text(
            config.replace(relative, explicit), encoding="utf-8"
        )
        manifest = self.candidate_dir / self.contract["build"]["frontendManifestPath"]
        if (
            not manifest.is_file()
            or digest_bytes(manifest.read_bytes())
            != self.contract["build"]["frontendManifestDigest"]
        ):
            fail("PROVENANCE", "candidate frontend manifest identity mismatch")

    def build_candidate(self) -> None:
        assert self.candidate_dir is not None and self.runtime_dir is not None
        frontend = self.candidate_dir / "console/frontend"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.runtime_dir / "npm-home"),
            "npm_config_cache": str(self.runtime_dir / "npm-cache"),
            "VITE_SUPPLIER_QUALITY_DEMO_MODE": "live",
            "VITE_BACKEND_URL": f"http://127.0.0.1:{self.contract['ports']['backend']}",
        }
        for command in (
            ["npm", "ci"],
            ["npm", "run", "build"],
        ):
            result = run_command(command, frontend, environment, timeout=300)
            if result.returncode:
                fail("CANDIDATE", "locked frontend build failed")
        self.chromium_path = Path(self.contract["browser"]["executablePath"]).resolve()
        if (
            not self.chromium_path.is_file()
            or not os.access(self.chromium_path, os.X_OK)
            or digest_bytes(self.chromium_path.read_bytes())
            != self.contract["browser"]["executableDigest"]
        ):
            fail("CANDIDATE", "browser executable identity mismatch")
        browser_probe = run_command(
            [
                "node",
                "-e",
                "const {chromium}=require('@playwright/test');"
                "chromium.launch({executablePath:process.argv[1]}).then("
                "async b=>{await b.close()}).catch(()=>process.exit(2))",
                str(self.chromium_path),
            ],
            frontend,
            environment,
            timeout=60,
        )
        if browser_probe.returncode:
            fail("CANDIDATE", "browser executable launch probe failed")
        self.build_identity_path = self.runtime_dir / "build-identity.json"
        record_build_identity(frontend / "dist", self.build_identity_path, "live")
        verify_build_identity(frontend / "dist", self.build_identity_path)
        for path in sorted(self.candidate_dir.rglob("*"), reverse=True):
            if not path.is_symlink():
                executable = path.stat().st_mode & 0o111
                path.chmod(0o555 if path.is_dir() or executable else 0o444)
        self.candidate_dir.chmod(0o555)
        self.candidate_before = release_manifest(self.candidate_dir)
        assert_immutable(self.candidate_dir)

    def denial_probes(self) -> None:
        assert self.candidate_dir is not None and self.runtime_dir is not None
        ordinary = self.candidate_dir / "ordinary-write-denied"
        try:
            descriptor = os.open(ordinary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except PermissionError:
            pass
        else:
            os.close(descriptor)
            ordinary.unlink(missing_ok=True)
            fail("CANDIDATE", "ordinary candidate write was not denied")
        configured = (self.workspace / self.contract["pythonInterpreter"]).absolute()
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.pathsep.join(
                str(self.candidate_dir / item)
                for item in self.contract["applicationSourceDirectories"]
            ),
        }
        probe = run_command(
            [
                str(configured),
                "-c",
                "open('bytecode-write-denied.pyc','wb').write(b'x')",
            ],
            self.candidate_dir,
            environment,
        )
        if probe.returncode == 0:
            (self.candidate_dir / "bytecode-write-denied.pyc").unlink(missing_ok=True)
            fail("CANDIDATE", "Python bytecode write was not denied")

    def sentinel_snapshot(self) -> dict[str, tuple[str, int]]:
        result: dict[str, tuple[str, int]] = {}
        for sentinel in self.contract["continuitySentinels"]:
            process = run_command(
                ["ps", "-p", str(sentinel["pid"]), "-o", "lstart="], self.workspace
            )
            if (
                process.returncode
                or process.stdout.decode().strip() != sentinel["startTime"]
            ):
                fail("CANDIDATE", "continuity sentinel process identity drifted")
            try:
                with urllib.request.urlopen(
                    sentinel["healthUrl"], timeout=1
                ) as response:
                    status = response.status
            except (OSError, urllib.error.URLError) as exc:
                raise RunnerError(
                    "CANDIDATE", "continuity sentinel is unhealthy"
                ) from exc
            if status != 200:
                fail("CANDIDATE", "continuity sentinel is unhealthy")
            result[sentinel["name"]] = (sentinel["startTime"], status)
        return result

    def continuity_before(self) -> None:
        self.sentinel_before = self.sentinel_snapshot()

    def continuity_after(self) -> None:
        if self.sentinel_snapshot() != self.sentinel_before:
            fail("CANDIDATE", "continuity sentinel correlation drifted")

    def browser_harness(self) -> None:
        assert self.candidate_dir is not None
        assert self.runtime_dir is not None
        assert self.build_identity_path is not None
        verify_build_identity(
            self.candidate_dir / "console/frontend/dist", self.build_identity_path
        )
        configured = (self.workspace / self.contract["pythonInterpreter"]).absolute()
        runtime = self.runtime_dir / "browser-runtime"
        postgres_port = self.contract["ports"]["postgres"]
        qdrant_port = self.contract["ports"]["qdrant"]
        role = self.contract["validationRolePolicy"]["validationRole"]
        database = self.contract["validationRolePolicy"]["database"]
        postgres_url_file = self.runtime_dir / "postgres-url"
        descriptor = os.open(
            postgres_url_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(
                f"postgresql://{role}:{self.validation_password}@"
                f"127.0.0.1:{postgres_port}/{database}"
            )
        self.credential_files.add(postgres_url_file)
        command = [
            str(configured),
            str(self.workspace / "scripts/acceptance/isolated_browser_harness.py"),
            "--release-root",
            str(self.candidate_dir),
            "--runtime-dir",
            str(runtime),
            "--backend-host",
            "127.0.0.1",
            "--backend-port",
            str(self.contract["ports"]["backend"]),
            "--frontend-port",
            str(self.contract["ports"]["frontend"]),
            "--postgres-url-file",
            str(postgres_url_file),
            "--postgres-validation-role",
            role,
            "--qdrant-url",
            f"http://127.0.0.1:{qdrant_port}",
            "--build-mode-identity",
            str(self.build_identity_path),
            "--journey-id",
            self.contract["browser"]["journeyId"],
            "--python-path",
            os.pathsep.join(self.contract["applicationSourceDirectories"]),
            "--",
            *self.contract["browser"]["command"],
        ]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.runtime_dir / "npm-home"),
            "npm_config_cache": str(self.runtime_dir / "npm-cache"),
        }
        if self.chromium_path is None:
            fail("BROWSER", "browser executable identity is unavailable")
        environment["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = str(self.chromium_path)
        result = run_command(command, self.workspace, environment, timeout=900)
        if result.returncode:
            argument = re.search(
                rb"harness argument failure: "
                rb"(REQUIRED|UNKNOWN|CREDENTIAL_MODE|VALUE)",
                result.stderr,
            )
            module_error = re.search(
                rb"(ModuleNotFoundError|ImportError|PermissionError|"
                rb"FileNotFoundError|SyntaxError)",
                result.stderr,
            )
            match = re.search(
                rb"browser acceptance failed: "
                rb"(LAUNCH|TIMEOUT|ASSERTION|CONNECTION|SERVER|"
                rb"INVOCATION|PERMISSION|EMPTY|COMMAND)",
                result.stderr,
            )
            if module_error:
                label = module_error.group(1)
                if b"psycopg" in result.stderr:
                    category = "BROWSER_MODULE_PSYCOPG"
                elif b"browser_build_preflight" in result.stderr:
                    category = "BROWSER_MODULE_BUILD_PREFLIGHT"
                elif b"minimum_disclosure" in result.stderr:
                    category = "BROWSER_MODULE_DISCLOSURE"
                else:
                    category = {
                        b"ModuleNotFoundError": "BROWSER_MODULE_DEPENDENCY",
                        b"ImportError": "BROWSER_MODULE_DEPENDENCY",
                        b"PermissionError": "BROWSER_MODULE_PERMISSION",
                        b"FileNotFoundError": "BROWSER_MODULE_FILE",
                        b"SyntaxError": "BROWSER_MODULE_SYNTAX",
                    }[label]
                detail = "browser Harness module startup failed"
            elif argument:
                label = argument.group(1).decode()
                category = f"BROWSER_ARGUMENTS_{label}"
                detail = "browser Harness arguments failed"
            elif match:
                category = match.group(1).decode() if match else "COMMAND"
                detail = f"browser command failed: {category}"
                category = {
                    "ASSERTION": "BROWSER_ASSERTION",
                    "TIMEOUT": "BROWSER_TIMEOUT",
                    "CONNECTION": "BROWSER_CONNECTION",
                    "SERVER": "BROWSER_SERVER",
                    "INVOCATION": "BROWSER_INVOCATION",
                    "PERMISSION": "BROWSER_PERMISSION",
                    "LAUNCH": "BROWSER_LAUNCH",
                }.get(category, "BROWSER")
            else:
                phases = re.findall(
                    rb"harness phase: "
                    rb"(MODULE|ARGUMENTS|BUILD_IDENTITY|POSTGRES_ROLE|CANDIDATE|"
                    rb"BACKEND|BROWSER_COMMAND)",
                    result.stderr,
                )
                phase = phases[-1].decode() if phases else "NONE"
                category = {
                    "MODULE": "BROWSER_ARGUMENTS",
                    "ARGUMENTS": "BROWSER_PREFLIGHT_BUILD",
                    "BUILD_IDENTITY": "BROWSER_PREFLIGHT_POSTGRES",
                    "POSTGRES_ROLE": "BROWSER_PREFLIGHT_CANDIDATE",
                    "CANDIDATE": "BROWSER_PREFLIGHT_BACKEND",
                    "BACKEND": "BROWSER",
                    "BROWSER_COMMAND": "BROWSER",
                    "NONE": "BROWSER_MODULE",
                }[phase]
                detail = "browser Harness preflight failed"
            fail(category, detail)

    def verify_diagnostics(self) -> None:
        assert self.runtime_dir is not None and self.build_identity_path is not None
        browser_runtime = self.runtime_dir / "browser-runtime"
        raw = browser_runtime / "playwright-output"
        if raw.exists():
            fail("DISCLOSURE", "raw browser artifacts were retained")
        scan_generated_artifacts(
            [self.build_identity_path, browser_runtime / "acceptance-evidence.json"]
        )
        source = browser_runtime / "acceptance-evidence.json"
        if source.is_file():
            destination = self.output.with_suffix(".browser.json")
            destination.write_bytes(source.read_bytes())

    def verify_candidate_manifest(self) -> None:
        assert self.candidate_dir is not None and self.candidate_before is not None
        after = release_manifest(self.candidate_dir)
        if after != self.candidate_before:
            fail("CANDIDATE", "candidate manifest equality failed")
        assert_immutable(self.candidate_dir)
        if any(
            path.name == "__pycache__" or path.suffix == ".pyc"
            for path in self.candidate_dir.rglob("*")
        ):
            fail("CANDIDATE", "candidate cache contamination detected")

    def cleanup(self) -> None:
        if self.runtime_dir is not None:
            self.verify_runtime_owned()
        for credential in tuple(self.credential_files):
            credential.unlink(missing_ok=True)
            self.credential_files.discard(credential)
        for name in tuple(self.owned_containers):
            self.verify_owned(name)
            self.docker(["rm", "--force", name], "OWNERSHIP")
            self.owned_containers.remove(name)
        if self.runtime_dir is not None:
            if self.candidate_dir is not None and self.candidate_dir.exists():
                for path in (self.candidate_dir, *self.candidate_dir.rglob("*")):
                    if not path.is_symlink():
                        path.chmod(path.stat().st_mode | stat.S_IWUSR)
            shutil.rmtree(self.runtime_dir)

    def write_evidence(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.records, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def run(self) -> int:
        failure: RunnerError | None = None
        result_code = 0
        try:
            self.stage("provenance", self.provenance)
            self.stage("locked-frontend-build", self.frontend_lock)
            self.stage("candidate-resolution", self.interpreter)
            if self.mode == "preflight":
                for name in STAGES:
                    if (
                        name not in {record["stageId"] for record in self.records}
                        and name != "owned-cleanup"
                    ):
                        self.skip(name)
            else:
                self.stage("docker-preflight", self.docker_preflight)
                self.stage("postgres-start", self.postgres_start)
                self.stage("postgres-provision", self.postgres_provision)
                action = (
                    self.postgres_readiness
                    if self.mode == "micro-postgres"
                    else self.apply_migrations
                )
                self.stage("migrations-readiness", action)
                if self.mode == "micro-postgres":
                    for name in STAGES:
                        if (
                            name not in {record["stageId"] for record in self.records}
                            and name != "owned-cleanup"
                        ):
                            self.skip(name)
                else:
                    self.stage("qdrant-health", self.qdrant_start)
                    self.continuity_before()
                    self.stage("candidate-presentation", self.present_candidate)
                    self.stage("live-demo-build-identity", self.build_candidate)
                    self.stage("write-bytecode-denial", self.denial_probes)
                    self.stage("browser-harness", self.browser_harness)
                    self.stage("sanitized-diagnostics", self.verify_diagnostics)
                    self.stage("nondisclosure-scan", self.verify_diagnostics)
                    self.stage("manifest-immutability", self.verify_candidate_manifest)
                    self.stage("continuity-monitoring", self.continuity_after)
        except RunnerError as exc:
            failure = exc
            result_code = 2
            self.write_evidence()
        finally:
            started = datetime.now(UTC).isoformat()
            try:
                self.cleanup()
                self.emit("owned-cleanup", "PASSED", started, 0)
            except RunnerError as cleanup_error:
                self.emit(
                    "owned-cleanup",
                    "FAILED",
                    started,
                    2,
                    cleanup_error.category,
                    cleanup_error.code,
                )
                if failure is None:
                    failure = cleanup_error
                    result_code = 2
            self.write_evidence()
            if failure:
                print(f"release runner failed: {failure.category}", file=sys.stderr)
        return result_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=sorted(MODES))
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--fault", choices=sorted(FAULTS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_contract(args.contract)
    except RunnerError as exc:
        print(f"release runner failed: {exc.category}", file=sys.stderr)
        return 2
    return Runner(contract, args.mode, args.evidence, args.fault).run()


if __name__ == "__main__":
    raise SystemExit(main())
