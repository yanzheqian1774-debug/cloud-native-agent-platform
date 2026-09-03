#!/usr/bin/env python3
"""Deterministic, fail-closed v0.2.2 release rehearsal runner."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import pwd
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

import continuity_monitor  # noqa: E402
import release_contract_v2 as contract_v2  # noqa: E402
from browser_build_preflight import (  # noqa: E402
    record_build_identity,
    verify_build_identity,
)
from isolated_browser_harness import (  # noqa: E402
    release_manifest,
    validate_first_failure_record,
)
from minimum_disclosure import scan_generated_artifacts  # noqa: E402

SCHEMA_VERSION = 1
HISTORICAL_SCHEMA_1_ATTEMPTS = frozenset(
    {f"v0.2.2-attempt-{number:02d}" for number in range(1, 6)}
)
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
    "continuity-monitor-start",
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
MODE_NORMALIZATION_FIELDS = frozenset(
    {
        "entryCount",
        "writableBeforeCount",
        "writableAfterCount",
        "executablePreservedCount",
        "unsupportedEntryCount",
        "correlationDigest",
    }
)
SYMLINK_CLASSIFICATIONS = frozenset(
    {
        "CANDIDATE_INTERNAL_SYMLINK",
        "SYMLINK_CANONICAL_ESCAPE",
        "BROKEN_SYMLINK",
        "SYMLINK_LOOP",
        "UNSUPPORTED_SYMLINK_TARGET",
        "SYMLINK_CANONICALIZATION_ERROR",
    }
)
SYMLINK_EVIDENCE_FIELDS = frozenset(
    {
        "symlinkCount",
        "classification",
        "manifestDigest",
        "correlationDigest",
        "stage",
        "state",
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
        "BROWSER_HTTP_ERROR",
        "BROWSER_NAVIGATION_ERROR",
        "BROWSER_PROCESS_ERROR",
        "BROWSER_DIAGNOSTIC_GAP",
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


def _read_json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        return contract_v2.load_json_exact(path.read_bytes())
    except (OSError, contract_v2.ContractV2Error) as exc:
        raise RunnerError("CONTRACT", f"{label} is unavailable or invalid") from exc


def load_schema_2_entry_gate(
    path: Path,
    *,
    workspace: Path,
    declared_instance_digest: str,
    declared_schema_blob: str,
    declared_evidence_envelope_digest: str,
    evidence_envelope_path: Path,
    product_ci_observation_path: Path,
    tool_ci_observation_path: Path,
) -> dict[str, Any]:
    """Validate every external trust input before constructing a Runner."""
    try:
        data = path.read_bytes()
        if contract_v2.contract_instance_digest(data) != declared_instance_digest:
            contract_v2.fail("Contract instance digest mismatch")
        contract = contract_v2.validate_contract(contract_v2.load_json_exact(data))
        contract_v2.validate_frozen_product(contract)
        contract_v2.verify_git_provenance(contract, workspace)
        tool = contract["acceptanceToolProvenance"]
        schema_path = "scripts/acceptance/release_contract.v2.schema.json"
        actual_schema_blob = contract_v2._git(
            ["rev-parse", f"{tool['sourceSha']}:{schema_path}"], workspace
        )
        if actual_schema_blob != declared_schema_blob:
            contract_v2.fail("approved Contract schema blob mismatch")
        product_observed = _read_json_file(
            product_ci_observation_path, "product CI observation"
        )
        tool_observed = _read_json_file(tool_ci_observation_path, "tool CI observation")
        contract_v2.validate_observed_ci(
            contract["productProvenance"]["exactSourceCi"],
            product_observed,
            "product CI",
        )
        contract_v2.validate_observed_ci(
            tool["exactMainCi"], tool_observed, "acceptance-tool CI"
        )
        envelope_data = evidence_envelope_path.read_bytes()
        if (
            contract_v2.contract_instance_digest(envelope_data)
            != declared_evidence_envelope_digest
        ):
            contract_v2.fail("Evidence envelope digest mismatch")
        envelope = contract_v2.load_json_exact(envelope_data)
        contract_v2.validate_evidence_envelope(
            envelope,
            contract_data=data,
            schema_blob=declared_schema_blob,
            pairing=contract["approvedPairing"]["pairingDigest"],
            observed_ci=tool_observed,
        )
        return contract
    except (OSError, contract_v2.ContractV2Error) as exc:
        raise RunnerError(
            "PROVENANCE", "schema-2 entry gate rejected provenance"
        ) from exc


def adapt_schema_2_for_runner(
    contract: dict[str, Any],
    *,
    workspace: Path,
    runtime_root: Path,
    browser_executable: Path,
    browser_executable_digest: str,
) -> dict[str, Any]:
    """Map validated v2 environment-neutral fields into the legacy executor."""
    profile = contract["executionProfile"]
    product = contract["productProvenance"]
    tool = contract["acceptanceToolProvenance"]
    return {
        "schemaVersion": 1,
        "product": {"sourceSha": product["sourceSha"], "treeSha": product["treeSha"]},
        "acceptanceToolSourceSha": tool["sourceSha"],
        "build": {
            "mode": profile["mode"],
            "frontendManifestPath": product["frontendManifest"]["path"],
            "frontendManifestDigest": product["frontendManifest"][
                "sha256"
            ].removeprefix("sha256:"),
        },
        "images": profile["images"],
        "ports": profile["ports"],
        "identity": {"runtimeRoot": str(runtime_root), "workspaceRoot": str(workspace)},
        "validationRolePolicy": profile["validationRolePolicy"],
        "pythonInterpreter": profile["pythonInterpreter"],
        "applicationSourceDirectories": profile["applicationSourceDirectories"],
        "diagnosticRetentionPolicy": profile["diagnosticRetentionPolicy"],
        "migrations": {
            key: value.removeprefix("sha256:")
            for key, value in profile["migrations"].items()
        },
        "browser": {
            "command": profile["browser"]["command"],
            "journeyId": profile["browser"]["journeyId"],
            "executablePath": str(browser_executable),
            "executableDigest": browser_executable_digest,
        },
        "continuitySentinels": [],
        "continuityMonitor": profile["continuityMonitor"],
    }


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


def manifest_digest(manifest: dict[str, dict[str, str | int]]) -> str:
    return digest_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    )


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
    exact_dual_provenance: bool = False
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
    candidate_source_dir: Path | None = None
    candidate_mount_owned: bool = False
    validation_uid: int | None = None
    validation_gid: int | None = None
    build_identity_path: Path | None = None
    candidate_before: dict[str, dict[str, str | int]] | None = None
    candidate_mounted_after: dict[str, dict[str, str | int]] | None = None
    candidate_unmounted_after: dict[str, dict[str, str | int]] | None = None
    candidate_executables: set[str] = field(default_factory=set)
    mode_normalization_evidence: dict[str, int | str] | None = None
    symlink_classification_evidence: dict[str, int | str] | None = None
    sentinel_before: dict[str, tuple[str, int]] = field(default_factory=dict)
    continuity_process: subprocess.Popen[bytes] | None = None
    continuity_runtime: Path | None = None
    continuity_evidence: Path | None = None
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
        if self.exact_dual_provenance:
            exact = run_command(["git", "rev-parse", "HEAD"], self.workspace)
            if (
                exact.returncode
                or exact.stdout.decode().strip()
                != self.contract["acceptanceToolSourceSha"]
            ):
                fail("PROVENANCE", "acceptance tooling exact identity mismatch")
        else:
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
                fail(
                    "PROVENANCE",
                    "acceptance tooling is older than the contract minimum",
                )

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
        self.candidate_source_dir = self.runtime_dir / "candidate-source"
        self.candidate_source_dir.mkdir(mode=0o700)
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
                bundle.extractall(self.candidate_source_dir, filter="data")
        except (OSError, tarfile.TarError) as exc:
            raise RunnerError("CANDIDATE", "candidate presentation failed") from exc
        archive_path.unlink()
        if not self.exact_dual_provenance:
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
            mounted_candidate = self.runtime_dir / "candidate"
            explicit = (
                f"{mounted_candidate}/scripts/acceptance/static_proxy_server.py "
                f"--root {mounted_candidate}/console/frontend/dist"
            )
            if config.count(relative) != 1:
                fail("PROVENANCE", "acceptance configuration command is ambiguous")
            (self.candidate_source_dir / config_path).write_text(
                config.replace(relative, explicit), encoding="utf-8"
            )
        manifest = (
            self.candidate_source_dir / self.contract["build"]["frontendManifestPath"]
        )
        if (
            not manifest.is_file()
            or digest_bytes(manifest.read_bytes())
            != self.contract["build"]["frontendManifestDigest"]
        ):
            fail("PROVENANCE", "candidate frontend manifest identity mismatch")

    def build_candidate(self) -> None:
        assert self.candidate_source_dir is not None and self.runtime_dir is not None
        frontend = self.candidate_source_dir / "console/frontend"
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
        uid, gid = self.select_validation_identity()
        self.normalize_candidate_modes(uid, gid)
        self.candidate_before = release_manifest(self.candidate_source_dir)
        self.present_read_only_candidate()

    def candidate_entries(self) -> list[Path]:
        assert self.candidate_source_dir is not None and self.runtime_dir is not None
        expected = self.runtime_dir / "candidate-source"
        if self.candidate_source_dir != expected:
            fail("OWNERSHIP", "candidate source is not runner-owned")
        self.verify_runtime_owned()
        entries = [self.candidate_source_dir]

        def traversal_failed(_error: OSError) -> None:
            fail(
                "CANDIDATE",
                "candidate traversal failed",
                "MODE_NORMALIZATION_TRAVERSAL_FAILED",
            )

        try:
            for directory, names, files in os.walk(
                self.candidate_source_dir,
                topdown=True,
                onerror=traversal_failed,
                followlinks=False,
            ):
                base = Path(directory)
                entries.extend(base / name for name in sorted((*names, *files)))
        except RunnerError:
            raise
        except (OSError, RuntimeError) as exc:
            raise RunnerError(
                "CANDIDATE",
                "candidate traversal failed",
                "MODE_NORMALIZATION_TRAVERSAL_FAILED",
            ) from exc
        return entries

    def write_mode_normalization_evidence(
        self,
        *,
        entry_count: int,
        writable_before: int,
        writable_after: int,
        executable_preserved: int,
        unsupported: int,
    ) -> None:
        correlation = digest_bytes(
            (
                f"{self.token}:candidate-mode-normalization:{entry_count}:"
                f"{writable_before}:{writable_after}:{executable_preserved}:"
                f"{unsupported}"
            ).encode()
        )
        evidence: dict[str, int | str] = {
            "entryCount": entry_count,
            "writableBeforeCount": writable_before,
            "writableAfterCount": writable_after,
            "executablePreservedCount": executable_preserved,
            "unsupportedEntryCount": unsupported,
            "correlationDigest": correlation,
        }
        if set(evidence) != MODE_NORMALIZATION_FIELDS:
            fail("INTERNAL", "mode-normalization evidence schema violation")
        self.mode_normalization_evidence = evidence
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.with_suffix(".candidate-mode-normalization.json").write_text(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def verify_candidate_mode_normalization(self) -> None:
        entries = self.candidate_entries()
        writable_after = 0
        executable_preserved = 0
        unsupported = 0
        for path in entries:
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise RunnerError(
                    "CANDIDATE",
                    "candidate traversal failed",
                    "MODE_NORMALIZATION_TRAVERSAL_FAILED",
                ) from exc
            mode = stat.S_IMODE(metadata.st_mode)
            if stat.S_ISLNK(metadata.st_mode):
                continue
            if mode & 0o222:
                writable_after += 1
            relative = path.relative_to(self.candidate_source_dir).as_posix()
            if stat.S_ISDIR(metadata.st_mode):
                expected = 0o555
            elif stat.S_ISREG(metadata.st_mode):
                expected = 0o555 if relative in self.candidate_executables else 0o444
                executable_preserved += relative in self.candidate_executables
            else:
                unsupported += 1
                continue
            if mode != expected:
                fail(
                    "CANDIDATE",
                    "candidate mode normalization verification failed",
                    "MODE_NORMALIZATION_VERIFICATION_FAILED",
                )
        if unsupported:
            fail(
                "CANDIDATE",
                "candidate contains an unsupported entry type",
                "MODE_NORMALIZATION_UNSUPPORTED_ENTRY",
            )
        if writable_after:
            fail(
                "CANDIDATE",
                "candidate contains a writable entry after normalization",
                "MODE_NORMALIZATION_WRITABLE_REMAINS",
            )
        if executable_preserved != len(self.candidate_executables):
            fail(
                "CANDIDATE",
                "required candidate executable mode was not preserved",
                "MODE_NORMALIZATION_EXECUTABLE_REMOVED",
            )

    def _resolve_symlink_target(self, path: Path) -> Path:
        raw_target = Path(os.readlink(path))
        unresolved = (
            raw_target if raw_target.is_absolute() else path.parent / raw_target
        )
        return unresolved.resolve(strict=True)

    def _classify_symlink(self, path: Path, canonical_root: Path) -> str:
        try:
            canonical_target = self._resolve_symlink_target(path)
        except FileNotFoundError:
            return "BROKEN_SYMLINK"
        except RuntimeError:
            return "SYMLINK_LOOP"
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                return "SYMLINK_LOOP"
            return "SYMLINK_CANONICALIZATION_ERROR"
        try:
            canonical_target.relative_to(canonical_root)
        except ValueError:
            return "SYMLINK_CANONICAL_ESCAPE"
        try:
            target_metadata = canonical_target.stat()
        except OSError:
            return "SYMLINK_CANONICALIZATION_ERROR"
        if not (
            stat.S_ISREG(target_metadata.st_mode)
            or stat.S_ISDIR(target_metadata.st_mode)
        ):
            return "UNSUPPORTED_SYMLINK_TARGET"
        return "CANDIDATE_INTERNAL_SYMLINK"

    def write_symlink_classification_evidence(
        self,
        *,
        symlink_count: int,
        classification: str,
        state: str,
    ) -> None:
        if classification not in SYMLINK_CLASSIFICATIONS or state not in {
            "PASS",
            "FAIL",
        }:
            fail("INTERNAL", "symlink classification evidence schema violation")
        assert self.candidate_source_dir is not None
        candidate_manifest_digest = manifest_digest(
            release_manifest(self.candidate_source_dir)
        )
        correlation = digest_bytes(
            (
                f"{self.token}:candidate-symlink-classification:{symlink_count}:"
                f"{classification}:{candidate_manifest_digest}:{state}"
            ).encode()
        )
        evidence: dict[str, int | str] = {
            "symlinkCount": symlink_count,
            "classification": classification,
            "manifestDigest": candidate_manifest_digest,
            "correlationDigest": correlation,
            "stage": "candidate-presentation",
            "state": state,
        }
        if set(evidence) != SYMLINK_EVIDENCE_FIELDS:
            fail("INTERNAL", "symlink classification evidence schema violation")
        self.symlink_classification_evidence = evidence
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.with_suffix(".candidate-symlinks.json").write_text(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def reject_symlink_classification(
        self, classification: str, symlink_count: int
    ) -> NoReturn:
        self.write_symlink_classification_evidence(
            symlink_count=symlink_count,
            classification=classification,
            state="FAIL",
        )
        fail(
            "CANDIDATE",
            "candidate symlink classification failed",
            classification,
        )

    def normalize_candidate_modes(self, uid: int, gid: int) -> None:
        assert self.candidate_source_dir is not None
        entries = self.candidate_entries()
        try:
            root = self.candidate_source_dir.resolve(strict=True)
        except OSError as exc:
            raise RunnerError(
                "CANDIDATE",
                "candidate root canonicalization failed",
                "SYMLINK_CANONICALIZATION_ERROR",
            ) from exc
        writable_before = 0
        unsupported = 0
        regular_files: list[Path] = []
        directories: list[Path] = []
        symlinks: list[Path] = []
        self.candidate_executables.clear()
        try:
            for path in entries:
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    symlinks.append(path)
                elif stat.S_ISDIR(metadata.st_mode):
                    directories.append(path)
                    writable_before += bool(metadata.st_mode & 0o222)
                elif stat.S_ISREG(metadata.st_mode):
                    regular_files.append(path)
                    writable_before += bool(metadata.st_mode & 0o222)
                    if metadata.st_nlink != 1:
                        fail(
                            "CANDIDATE",
                            "candidate regular file has an unsafe hard link",
                            "MODE_NORMALIZATION_HARDLINK_REJECTED",
                        )
                    if metadata.st_mode & 0o111:
                        self.candidate_executables.add(
                            path.relative_to(self.candidate_source_dir).as_posix()
                        )
                else:
                    unsupported += 1
            for path in symlinks:
                classification = self._classify_symlink(path, root)
                if classification != "CANDIDATE_INTERNAL_SYMLINK":
                    self.reject_symlink_classification(classification, len(symlinks))
        except RunnerError:
            raise
        except (OSError, RuntimeError) as exc:
            raise RunnerError(
                "CANDIDATE",
                "candidate traversal failed",
                "MODE_NORMALIZATION_TRAVERSAL_FAILED",
            ) from exc
        if symlinks:
            self.write_symlink_classification_evidence(
                symlink_count=len(symlinks),
                classification="CANDIDATE_INTERNAL_SYMLINK",
                state="PASS",
            )
        if unsupported:
            self.write_mode_normalization_evidence(
                entry_count=len(entries),
                writable_before=writable_before,
                writable_after=writable_before,
                executable_preserved=0,
                unsupported=unsupported,
            )
            fail(
                "CANDIDATE",
                "candidate contains an unsupported entry type",
                "MODE_NORMALIZATION_UNSUPPORTED_ENTRY",
            )
        try:
            for path in (*directories, *regular_files, *symlinks):
                os.chown(path, uid, gid, follow_symlinks=False)
            for path in (*directories, *regular_files, *symlinks):
                metadata = path.lstat()
                if (metadata.st_uid, metadata.st_gid) != (uid, gid):
                    fail(
                        "OWNERSHIP",
                        "candidate entry ownership mismatch",
                        "MODE_NORMALIZATION_OWNERSHIP_MISMATCH",
                    )
            for path in regular_files:
                relative = path.relative_to(self.candidate_source_dir).as_posix()
                path.chmod(0o555 if relative in self.candidate_executables else 0o444)
            for path in sorted(
                directories, key=lambda item: len(item.parts), reverse=True
            ):
                path.chmod(0o555)
        except RunnerError:
            raise
        except (OSError, PermissionError) as exc:
            raise RunnerError(
                "CANDIDATE",
                "candidate mode normalization failed",
                "MODE_NORMALIZATION_CHMOD_FAILED",
            ) from exc
        self.verify_candidate_mode_normalization()
        self.write_mode_normalization_evidence(
            entry_count=len(entries),
            writable_before=writable_before,
            writable_after=0,
            executable_preserved=len(self.candidate_executables),
            unsupported=0,
        )

    def select_validation_identity(self) -> tuple[int, int]:
        if os.geteuid() != 0:
            fail(
                "CANDIDATE",
                "filesystem read-only presentation authority is unavailable",
                "READ_ONLY_MOUNT_MISSING",
            )
        try:
            identity = pwd.getpwnam("nobody")
        except KeyError as exc:
            raise RunnerError(
                "CANDIDATE",
                "unprivileged validation identity is unavailable",
                "VALIDATION_IDENTITY_MISMATCH",
            ) from exc
        if identity.pw_uid == 0 or identity.pw_gid == 0:
            fail(
                "CANDIDATE",
                "root denial-probe identity is forbidden",
                "ROOT_PROBE_FORBIDDEN",
            )
        self.validation_uid, self.validation_gid = identity.pw_uid, identity.pw_gid
        return identity.pw_uid, identity.pw_gid

    def verify_mount_target_owned(self) -> None:
        if self.runtime_dir is None or self.candidate_dir is None:
            fail("OWNERSHIP", "candidate mount ownership is unavailable")
        expected = self.runtime_dir / "candidate"
        if not self.candidate_mount_owned or self.candidate_dir != expected:
            fail("OWNERSHIP", "candidate mount target is not runner-owned")
        self.verify_runtime_owned()

    def mount_options(self) -> set[str]:
        assert self.candidate_dir is not None
        result = run_command(
            [
                "findmnt",
                "--noheadings",
                "--output",
                "TARGET,VFS-OPTIONS",
                "--target",
                str(self.candidate_dir),
            ],
            self.workspace,
        )
        if result.returncode:
            fail(
                "CANDIDATE",
                "read-only candidate mount is missing",
                "READ_ONLY_MOUNT_MISSING",
            )
        try:
            target, options = result.stdout.decode().strip().split(maxsplit=1)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RunnerError(
                "CANDIDATE",
                "read-only candidate mount verification failed",
                "READ_ONLY_MOUNT_VERIFICATION_FAILED",
            ) from exc
        if Path(target) != self.candidate_dir:
            fail(
                "CANDIDATE",
                "read-only candidate mount verification failed",
                "READ_ONLY_MOUNT_VERIFICATION_FAILED",
            )
        return set(options.split(","))

    def present_read_only_candidate(self) -> None:
        assert self.runtime_dir is not None and self.candidate_source_dir is not None
        uid, gid = self.select_validation_identity()
        if (
            shutil.which("mount") is None
            or shutil.which("umount") is None
            or shutil.which("findmnt") is None
            or shutil.which("setpriv") is None
        ):
            fail(
                "CANDIDATE",
                "filesystem read-only presentation tooling is unavailable",
                "READ_ONLY_MOUNT_MISSING",
            )
        self.candidate_dir = self.runtime_dir / "candidate"
        self.candidate_dir.mkdir(mode=0o700)
        mounted = run_command(
            [
                "mount",
                "--bind",
                str(self.candidate_source_dir),
                str(self.candidate_dir),
            ],
            self.workspace,
        )
        if mounted.returncode:
            fail(
                "CANDIDATE",
                "filesystem read-only presentation could not be created",
                "READ_ONLY_MOUNT_MISSING",
            )
        self.candidate_mount_owned = True
        remounted = run_command(
            ["mount", "-o", "remount,bind,ro", str(self.candidate_dir)],
            self.workspace,
        )
        if remounted.returncode:
            fail(
                "CANDIDATE",
                "read-only candidate mount verification failed",
                "READ_ONLY_MOUNT_VERIFICATION_FAILED",
            )
        if "ro" not in self.mount_options():
            fail(
                "CANDIDATE",
                "candidate presentation is mode-bit-only or writable",
                "MODE_BITS_ONLY_NOT_ENFORCED",
            )
        source_stat = self.candidate_source_dir.stat()
        target_stat = self.candidate_dir.stat()
        if (
            (source_stat.st_dev, source_stat.st_ino)
            != (target_stat.st_dev, target_stat.st_ino)
            or (source_stat.st_uid, source_stat.st_gid) != (uid, gid)
            or (target_stat.st_uid, target_stat.st_gid) != (uid, gid)
        ):
            fail(
                "CANDIDATE",
                "candidate mount source and target ownership mismatch",
                "READ_ONLY_MOUNT_VERIFICATION_FAILED",
            )
        probe_runtime = self.runtime_dir / "validation-runtime"
        probe_runtime.mkdir(mode=0o700)
        os.chown(probe_runtime, uid, gid)
        mounted = release_manifest(self.candidate_dir)
        if mounted != self.candidate_before:
            fail("CANDIDATE", "mounted candidate manifest equality failed")

    def denial_probes(self) -> None:
        assert self.candidate_dir is not None and self.runtime_dir is not None
        if self.validation_uid in {None, 0} or self.validation_gid in {None, 0}:
            fail(
                "CANDIDATE",
                "root denial-probe identity is forbidden",
                "ROOT_PROBE_FORBIDDEN",
            )
        if "ro" not in self.mount_options():
            fail(
                "CANDIDATE",
                "read-only candidate mount is missing",
                "READ_ONLY_MOUNT_MISSING",
            )
        prefix = [
            "setpriv",
            f"--reuid={self.validation_uid}",
            f"--regid={self.validation_gid}",
            "--clear-groups",
        ]
        identity = run_command([*prefix, "id", "-u"], self.workspace)
        if identity.returncode or identity.stdout.decode().strip() != str(
            self.validation_uid
        ):
            fail(
                "CANDIDATE",
                "validation identity mismatch",
                "VALIDATION_IDENTITY_MISMATCH",
            )
        ordinary = run_command(
            [*prefix, "sh", "-c", ": > ordinary-write-denied"], self.candidate_dir
        )
        if ordinary.returncode == 0:
            fail(
                "CANDIDATE",
                "ordinary candidate write was not denied",
                "WRITE_UNEXPECTEDLY_SUCCEEDED",
            )
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
                *prefix,
                str(configured),
                "-c",
                "open('bytecode-write-denied.pyc','wb').write(b'x')",
            ],
            self.candidate_dir,
            environment,
        )
        if probe.returncode == 0:
            fail(
                "CANDIDATE",
                "Python bytecode write was not denied",
                "BYTECODE_UNEXPECTEDLY_SUCCEEDED",
            )
        cache = self.runtime_dir / "validation-runtime"
        external = run_command(
            [
                *prefix,
                str(configured),
                "-c",
                "open('authorized-cache','wb').write(b'x')",
            ],
            cache,
            {"PATH": os.environ.get("PATH", "")},
        )
        if external.returncode or not (cache / "authorized-cache").is_file():
            fail(
                "CANDIDATE",
                "authorized external runtime is not writable",
                "VALIDATION_IDENTITY_MISMATCH",
            )
        self.candidate_mounted_after = release_manifest(self.candidate_dir)
        if self.candidate_mounted_after != self.candidate_before:
            fail("CANDIDATE", "mounted candidate manifest equality failed")

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

    def start_server_local_continuity_monitor(self) -> None:
        self.ensure_runtime()
        assert self.runtime_dir is not None
        monitor_runtime = self.runtime_dir / "continuity-monitor"
        monitor_runtime.mkdir(mode=0o700)
        contract_path = self.runtime_dir / "continuity-contract.json"
        contract_path.write_text(
            json.dumps(
                self.contract["continuityMonitor"],
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        contract_path.chmod(0o400)
        read_fd, write_fd = os.pipe()
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "continuity_monitor.py"),
                    "--workspace",
                    str(self.workspace),
                    "--runtime",
                    str(monitor_runtime),
                    "--contract",
                    str(contract_path),
                    "--token-fd",
                    str(read_fd),
                ],
                cwd=self.workspace,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                pass_fds=(read_fd,),
                start_new_session=True,
            )
            os.close(read_fd)
            read_fd = -1
            os.write(write_fd, (self.token + "\n").encode())
        except OSError as exc:
            raise RunnerError(
                "OWNERSHIP", "continuity monitor could not start"
            ) from exc
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            os.close(write_fd)
        evidence = monitor_runtime / "evidence.jsonl"
        expected = continuity_monitor.ownership_digest(self.workspace, self.token)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                fail("CANDIDATE", "continuity monitor exited before readiness")
            if evidence.is_file():
                try:
                    first = json.loads(
                        evidence.read_text(encoding="utf-8").splitlines()[0]
                    )
                except (OSError, IndexError, json.JSONDecodeError):
                    pass
                else:
                    if (
                        first.get("phase") == "START"
                        and first.get("workspaceOwnershipDigest") == expected
                    ):
                        self.continuity_process = process
                        self.continuity_runtime = monitor_runtime
                        self.continuity_evidence = evidence
                        return
            time.sleep(0.05)
        process.terminate()
        process.wait(timeout=5)
        fail("CANDIDATE", "continuity monitor readiness deadline expired")

    def stop_and_validate_server_local_continuity_monitor(self) -> None:
        if (
            self.continuity_process is None
            or self.continuity_runtime is None
            or self.continuity_evidence is None
        ):
            fail("OWNERSHIP", "owned continuity monitor is unavailable")
        expected = continuity_monitor.ownership_digest(self.workspace, self.token)
        try:
            first = json.loads(
                self.continuity_evidence.read_text(encoding="utf-8").splitlines()[0]
            )
        except (OSError, IndexError, json.JSONDecodeError) as exc:
            raise RunnerError(
                "OWNERSHIP", "continuity ownership evidence is unavailable"
            ) from exc
        if first.get("workspaceOwnershipDigest") != expected:
            fail("OWNERSHIP", "foreign continuity monitor cannot be stopped")
        stop = self.continuity_runtime / "stop"
        fd = os.open(stop, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        os.close(fd)
        try:
            self.continuity_process.wait(
                timeout=self.contract["continuityMonitor"]["intervalSeconds"] + 10
            )
        except subprocess.TimeoutExpired as exc:
            raise RunnerError(
                "RESOURCE", "continuity monitor stop deadline expired"
            ) from exc
        if self.continuity_process.returncode != 0:
            fail("CANDIDATE", "continuity monitor exited unexpectedly")
        data = self.continuity_evidence.read_bytes()
        continuity_monitor.validate_evidence(data, expected_ownership_digest=expected)
        preserved = self.output.with_name(self.output.name + ".continuity.jsonl")
        fd = os.open(
            preserved, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400
        )
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        self.continuity_process = None

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
        failure_record = self.capture_browser_first_failure()
        if result.returncode:
            if failure_record is not None:
                fail(
                    str(failure_record["failureCategory"]),
                    "browser Harness reported a sanitized first failure",
                )
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

    def capture_browser_first_failure(self) -> dict[str, object] | None:
        assert self.runtime_dir is not None
        source = self.runtime_dir / "browser-runtime/browser-first-failure.json"
        if not source.exists():
            return None
        try:
            record = validate_first_failure_record(
                json.loads(source.read_text(encoding="utf-8"))
            )
            scan_generated_artifacts([source])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise RunnerError(
                "BROWSER_DIAGNOSTIC_GAP",
                "browser first-failure evidence failed closed validation",
            ) from exc
        destination = self.output.with_suffix(".browser-first-failure.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(record, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return record

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
        self.candidate_mounted_after = after
        if after != self.candidate_before:
            fail("CANDIDATE", "candidate manifest equality failed")
        if any(
            path.name == "__pycache__" or path.suffix == ".pyc"
            for path in self.candidate_dir.rglob("*")
        ):
            fail("CANDIDATE", "candidate cache contamination detected")

    def unmount_candidate(self) -> None:
        if self.candidate_dir is None or not self.candidate_mount_owned:
            return
        self.verify_mount_target_owned()
        if self.candidate_mounted_after is None:
            self.candidate_mounted_after = release_manifest(self.candidate_dir)
        result = run_command(["umount", str(self.candidate_dir)], self.workspace)
        if result.returncode:
            fail("OWNERSHIP", "owned candidate mount could not be unmounted")
        self.candidate_mount_owned = False
        assert self.candidate_source_dir is not None
        self.candidate_unmounted_after = release_manifest(self.candidate_source_dir)
        if self.candidate_unmounted_after != self.candidate_before:
            fail("CANDIDATE", "underlying candidate changed after unmount")

    def write_candidate_manifests(self) -> None:
        if not all(
            (
                self.candidate_before,
                self.candidate_mounted_after,
                self.candidate_unmounted_after,
            )
        ):
            return
        path = self.output.with_suffix(".candidate-manifests.json")
        path.write_text(
            json.dumps(
                {
                    "preMountDigest": manifest_digest(self.candidate_before),
                    "mountedPostProbeDigest": manifest_digest(
                        self.candidate_mounted_after
                    ),
                    "unmountedPostProbeDigest": manifest_digest(
                        self.candidate_unmounted_after
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    def cleanup(self) -> None:
        continuity_error: RunnerError | None = None
        if self.runtime_dir is not None:
            self.verify_runtime_owned()
        if self.continuity_process is not None:
            if self.continuity_process.poll() is None:
                try:
                    self.stop_and_validate_server_local_continuity_monitor()
                except RunnerError as exc:
                    if self.continuity_process.poll() is None:
                        raise
                    self.continuity_process = None
                    continuity_error = exc
            else:
                self.continuity_process = None
                continuity_error = RunnerError(
                    "OWNERSHIP", "continuity monitor cleanup found an unexpected exit"
                )
        for credential in tuple(self.credential_files):
            credential.unlink(missing_ok=True)
            self.credential_files.discard(credential)
        for name in tuple(self.owned_containers):
            self.verify_owned(name)
            self.docker(["rm", "--force", name], "OWNERSHIP")
            self.owned_containers.remove(name)
        if self.runtime_dir is not None:
            self.unmount_candidate()
            self.write_candidate_manifests()
            shutil.rmtree(self.runtime_dir)
            if self.runtime_dir.exists():
                fail("OWNERSHIP", "owned runtime cleanup could not be verified")
        if continuity_error is not None:
            raise continuity_error

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
                if self.exact_dual_provenance and self.mode != "micro-postgres":
                    self.stage(
                        "continuity-monitor-start",
                        self.start_server_local_continuity_monitor,
                    )
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
                    if not self.exact_dual_provenance:
                        self.continuity_before()
                    self.stage("candidate-presentation", self.present_candidate)
                    self.stage("live-demo-build-identity", self.build_candidate)
                    self.stage("write-bytecode-denial", self.denial_probes)
                    self.stage("browser-harness", self.browser_harness)
                    self.stage("sanitized-diagnostics", self.verify_diagnostics)
                    self.stage("nondisclosure-scan", self.verify_diagnostics)
                    self.stage("manifest-immutability", self.verify_candidate_manifest)
                    self.stage(
                        "continuity-monitoring",
                        self.stop_and_validate_server_local_continuity_monitor
                        if self.exact_dual_provenance
                        else self.continuity_after,
                    )
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
    parser.add_argument("--attempt-id")
    parser.add_argument("--contract-instance-sha256")
    parser.add_argument("--contract-schema-blob")
    parser.add_argument("--evidence-envelope", type=Path)
    parser.add_argument("--evidence-envelope-sha256")
    parser.add_argument("--product-ci-observation", type=Path)
    parser.add_argument("--tool-ci-observation", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--browser-executable", type=Path)
    parser.add_argument("--browser-executable-digest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw = contract_v2.load_json_exact(args.contract.read_bytes())
        if raw.get("schemaVersion") == 1:
            if args.attempt_id not in HISTORICAL_SCHEMA_1_ATTEMPTS:
                fail(
                    "CONTRACT",
                    "schema 1 is restricted to historical attempts 01 through 05",
                )
            contract = load_contract(args.contract)
            exact_v2 = False
        elif raw.get("schemaVersion") == 2:
            required = (
                args.contract_instance_sha256,
                args.contract_schema_blob,
                args.evidence_envelope,
                args.evidence_envelope_sha256,
                args.product_ci_observation,
                args.tool_ci_observation,
                args.runtime_root,
                args.browser_executable,
                args.browser_executable_digest,
            )
            if any(value is None for value in required):
                fail("CONTRACT", "schema-2 external trust inputs are required")
            workspace = Path.cwd().resolve()
            v2 = load_schema_2_entry_gate(
                args.contract,
                workspace=workspace,
                declared_instance_digest=args.contract_instance_sha256,
                declared_schema_blob=args.contract_schema_blob,
                declared_evidence_envelope_digest=args.evidence_envelope_sha256,
                evidence_envelope_path=args.evidence_envelope,
                product_ci_observation_path=args.product_ci_observation,
                tool_ci_observation_path=args.tool_ci_observation,
            )
            contract = adapt_schema_2_for_runner(
                v2,
                workspace=workspace,
                runtime_root=args.runtime_root,
                browser_executable=args.browser_executable,
                browser_executable_digest=args.browser_executable_digest,
            )
            exact_v2 = True
        else:
            fail("CONTRACT", "release contract schema version is unsupported")
    except (OSError, contract_v2.ContractV2Error):
        print("release runner failed: CONTRACT", file=sys.stderr)
        return 2
    except RunnerError as exc:
        print(f"release runner failed: {exc.category}", file=sys.stderr)
        return 2
    return Runner(
        contract,
        args.mode,
        args.evidence,
        args.fault,
        exact_dual_provenance=exact_v2,
    ).run()


if __name__ == "__main__":
    raise SystemExit(main())
