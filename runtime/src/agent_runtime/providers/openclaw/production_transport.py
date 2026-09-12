"""Production transport for one externally owned exact-version OpenClaw Gateway."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from agent_runtime.providers.openclaw.compatibility import EXACT_TARGET
from agent_runtime.providers.openclaw.models import (
    ExactTarget,
    ExecutionObservation,
    ExecutionRequest,
    OpenClawError,
    ReasonCode,
    RuntimeBinding,
    RuntimeObservation,
)

_CLIENT_CONFIG_TOKEN = "${OPENCLAW_GATEWAY_TOKEN}"
_MAX_RESPONSE_BYTES = 1_048_576
_AGENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")


class SecretReferenceResolver(Protocol):
    """Resolve one already-authorized opaque Secret Reference at call time."""

    def resolve(self, reference: str) -> str: ...


@dataclass(frozen=True, slots=True)
class EnvironmentSecretReferenceResolver:
    """Consume the existing Kubernetes secretKeyRef-to-env projection."""

    reference: str
    environment_name: str = "OPENCLAW_GATEWAY_TOKEN"
    environment: Mapping[str, str] | None = None

    def resolve(self, reference: str) -> str:
        if reference != self.reference or not reference.startswith("secret-ref:"):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        source = os.environ if self.environment is None else self.environment
        value = source.get(self.environment_name, "")
        if not isinstance(value, str) or not value.strip():
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        return value


@dataclass(frozen=True, slots=True)
class OpenClawProductionConfig:
    """Strict private bootstrap input; contains references and paths, never secrets."""

    manifest_path: Path
    package_lock_path: Path
    node_executable: Path
    openclaw_entrypoint: Path
    client_config_path: Path
    client_state_dir: Path
    agent_id: str
    agent_workspace: Path
    gateway_secret_reference: str
    timeout_seconds: float = 10.0
    freshness_seconds: int = 30


class CommandRunner(Protocol):
    def __call__(
        self, argv: tuple[str, ...], env: Mapping[str, str], timeout: float
    ) -> subprocess.CompletedProcess[str]: ...


def _run_command(
    argv: tuple[str, ...], env: Mapping[str, str], timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=dict(env),
    )


class OpenClawProductionTransport:
    """Fixed Gateway RPCs with exact target, identity, isolation and shape checks."""

    def __init__(
        self,
        config: OpenClawProductionConfig,
        credentials: SecretReferenceResolver,
        *,
        runner: CommandRunner = _run_command,
    ) -> None:
        self._config = config
        self._credentials = credentials
        self._runner = runner
        self._gateway_url: str | None = None

    def preflight(self) -> ExactTarget:
        manifest = self._read_json(self._config.manifest_path)
        self._validate_manifest(manifest)
        self._validate_isolation_and_client_config()
        self._validate_node()
        locked = self._read_json(self._config.package_lock_path)
        package = self._locked_package(locked)
        version = self._required_text(package, "version")
        integrity = self._required_text(package, "integrity")
        if version != EXACT_TARGET.version:
            raise OpenClawError(ReasonCode.VERSION_UNSUPPORTED.value)
        if integrity != EXACT_TARGET.package_integrity:
            raise OpenClawError(ReasonCode.PACKAGE_INTEGRITY_MISMATCH.value)
        version_output = self._run_local(("--version",))
        match = re.search(r"OpenClaw\s+(\S+)\s+\(([0-9a-f]{7,40})\)", version_output)
        if match is None:
            raise OpenClawError(ReasonCode.VERSION_UNSUPPORTED.value)
        executable_version, commit = match.groups()
        if version != executable_version or not EXACT_TARGET.tag_commit.startswith(
            commit
        ):
            raise OpenClawError(ReasonCode.VERSION_UNSUPPORTED.value)
        self._require_ready_gateway()
        self._require_agent_workspace()
        return ExactTarget(version, EXACT_TARGET.tag_commit, integrity)

    def start(self, binding: RuntimeBinding) -> RuntimeObservation:
        raise OpenClawError(ReasonCode.RUNTIME_LIFECYCLE_UNSUPPORTED.value)

    def observe_runtime(
        self, binding: RuntimeBinding
    ) -> tuple[RuntimeObservation, ...]:
        raise OpenClawError(ReasonCode.RUNTIME_LIFECYCLE_UNSUPPORTED.value)

    def stop(self, binding: RuntimeBinding) -> RuntimeObservation:
        raise OpenClawError(ReasonCode.RUNTIME_LIFECYCLE_UNSUPPORTED.value)

    def replace(self, binding: RuntimeBinding) -> RuntimeObservation:
        raise OpenClawError(ReasonCode.RUNTIME_LIFECYCLE_UNSUPPORTED.value)

    def execute(self, request: ExecutionRequest) -> ExecutionObservation:
        raise OpenClawError(ReasonCode.EXECUTION_UNSUPPORTED.value)

    def observe_execution(
        self, request: ExecutionRequest
    ) -> tuple[ExecutionObservation, ...]:
        raise OpenClawError(ReasonCode.EXECUTION_UNSUPPORTED.value)

    def _validate_manifest(self, manifest: object) -> None:
        if not isinstance(manifest, dict):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        expected = {
            "provider": "openclaw",
            "runtime_exact_version": EXACT_TARGET.version,
            "runtime_tag_commit": EXACT_TARGET.tag_commit,
            "npm_integrity": EXACT_TARGET.package_integrity,
            "profile": "external-single-gateway-isolated-agent-workspace",
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                code = (
                    ReasonCode.PACKAGE_INTEGRITY_MISMATCH
                    if key == "npm_integrity"
                    else ReasonCode.VERSION_UNSUPPORTED
                    if key in {"runtime_exact_version", "runtime_tag_commit"}
                    else ReasonCode.CONFIGURATION_MISSING
                )
                raise OpenClawError(code.value)

    def _validate_isolation_and_client_config(self) -> None:
        cfg = self._config
        for path in (
            cfg.manifest_path,
            cfg.package_lock_path,
            cfg.node_executable,
            cfg.openclaw_entrypoint,
            cfg.client_config_path,
            cfg.client_state_dir,
            cfg.agent_workspace,
        ):
            if not path.is_absolute() or not path.exists():
                raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        if not cfg.client_state_dir.is_dir() or not cfg.agent_workspace.is_dir():
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        state = cfg.client_state_dir.resolve()
        workspace = cfg.agent_workspace.resolve()
        config_path = cfg.client_config_path.resolve()
        if (
            state == workspace
            or state in workspace.parents
            or workspace in state.parents
        ):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        if config_path == workspace or workspace in config_path.parents:
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        if not _AGENT_ID.fullmatch(cfg.agent_id):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        if not cfg.gateway_secret_reference.startswith("secret-ref:"):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        document = self._read_json(cfg.client_config_path)
        if not isinstance(document, dict) or set(document) != {"gateway"}:
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        gateway = document.get("gateway")
        if not isinstance(gateway, dict) or set(gateway) != {"mode", "remote"}:
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        remote = gateway.get("remote")
        if (
            gateway.get("mode") != "remote"
            or not isinstance(remote, dict)
            or set(remote) != {"url", "token"}
            or remote.get("token") != _CLIENT_CONFIG_TOKEN
        ):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        url = remote.get("url")
        if not isinstance(url, str):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"ws", "wss"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        self._gateway_url = url

    def _validate_node(self) -> None:
        output = self._run_process((str(self._config.node_executable), "--version"), {})
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", output.strip())
        if match is None or not self._node_supported(tuple(map(int, match.groups()))):
            raise OpenClawError(ReasonCode.NODE_VERSION_UNSUPPORTED.value)

    @staticmethod
    def _node_supported(version: tuple[int, int, int]) -> bool:
        major, minor, patch = version
        return (
            (major == 22 and (minor, patch) >= (22, 3))
            or (major == 24 and (minor, patch) >= (15, 0))
            or (major == 25 and (minor, patch) >= (9, 0))
            or major > 25
        )

    @staticmethod
    def _locked_package(lock: object) -> dict[str, object]:
        if not isinstance(lock, dict) or lock.get("lockfileVersion") != 3:
            raise OpenClawError(ReasonCode.PACKAGE_INTEGRITY_MISMATCH.value)
        packages = lock.get("packages")
        package = (
            packages.get("node_modules/openclaw")
            if isinstance(packages, dict)
            else None
        )
        if not isinstance(package, dict):
            raise OpenClawError(ReasonCode.PACKAGE_INTEGRITY_MISMATCH.value)
        return package

    def _run_local(self, arguments: tuple[str, ...]) -> str:
        return self._run_process(
            (
                str(self._config.node_executable),
                str(self._config.openclaw_entrypoint),
                *arguments,
            ),
            {},
        )

    def _rpc(self, method: str, params: dict[str, object]) -> dict[str, object]:
        allowed = {
            "health",
            "status",
            "agents.list",
        }
        if method not in allowed:
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
        token = self._credentials.resolve(self._config.gateway_secret_reference)
        try:
            output = self._run_process(
                (
                    str(self._config.node_executable),
                    str(self._config.openclaw_entrypoint),
                    "gateway",
                    "call",
                    method,
                    "--params",
                    json.dumps(params, sort_keys=True, separators=(",", ":")),
                    "--json",
                    "--timeout",
                    str(max(1, int(self._config.timeout_seconds * 1000))),
                ),
                {
                    "OPENCLAW_STATE_DIR": str(self._config.client_state_dir),
                    "OPENCLAW_CONFIG_PATH": str(self._config.client_config_path),
                    "OPENCLAW_GATEWAY_TOKEN": token,
                },
            )
        finally:
            token = ""
        try:
            value = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value) from None
        if not isinstance(value, dict):
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
        return value

    def _run_process(self, argv: tuple[str, ...], extra_env: Mapping[str, str]) -> str:
        env = {"LANG": "C.UTF-8", **extra_env}
        try:
            result = self._runner(argv, env, self._config.timeout_seconds)
        except (OSError, subprocess.TimeoutExpired):
            raise OpenClawError(ReasonCode.GATEWAY_UNAVAILABLE.value) from None
        output = result.stdout or ""
        error = result.stderr or ""
        if len(output.encode()) > _MAX_RESPONSE_BYTES or len(error.encode()) > (
            _MAX_RESPONSE_BYTES
        ):
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
        if result.returncode != 0:
            normalized = f"{output}\n{error}".lower()
            if any(word in normalized for word in ("auth", "token", "password")):
                code = ReasonCode.GATEWAY_AUTHENTICATION_FAILED
            elif any(
                word in normalized
                for word in (
                    "econnrefused",
                    "gateway not connected",
                    "timed out",
                    "timeout",
                    "transport",
                )
            ):
                code = ReasonCode.GATEWAY_UNAVAILABLE
            elif "config" in normalized:
                code = ReasonCode.CONFIGURATION_MISSING
            else:
                code = ReasonCode.GATEWAY_PROTOCOL_ERROR
            raise OpenClawError(code.value)
        return output.strip()

    def _require_ready_gateway(self) -> str:
        health = self._rpc("health", {})
        status = self._rpc("status", {})
        if status.get("runtimeVersion") != EXACT_TARGET.version:
            raise OpenClawError(ReasonCode.VERSION_UNSUPPORTED.value)
        event_loop = health.get("eventLoop")
        if not isinstance(event_loop, dict) or event_loop.get("degraded") is not False:
            raise OpenClawError(ReasonCode.GATEWAY_UNAVAILABLE.value)
        if self._gateway_url is None:
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
        return "gateway-" + sha256(self._gateway_url.encode()).hexdigest()[:24]

    def _require_agent_workspace(self) -> None:
        value = self._rpc("agents.list", {})
        agents = value.get("agents")
        if not isinstance(agents, list):
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
        matches = [
            item
            for item in agents
            if isinstance(item, dict) and item.get("id") == self._config.agent_id
        ]
        if len(matches) != 1:
            raise OpenClawError(ReasonCode.OBSERVATION_MISSING.value)
        workspace = matches[0].get("workspace")
        if not isinstance(workspace, str):
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
        if Path(workspace).resolve() != self._config.agent_workspace.resolve():
            raise OpenClawError(ReasonCode.IDENTITY_MISMATCH.value)

    @staticmethod
    def _read_json(path: Path) -> object:
        try:
            if path.stat().st_size > _MAX_RESPONSE_BYTES:
                raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value)
            return json.loads(path.read_text())
        except OpenClawError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise OpenClawError(ReasonCode.CONFIGURATION_MISSING.value) from None

    @staticmethod
    def _required_text(value: Mapping[str, object], key: str) -> str:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip() or len(item.encode()) > 512:
            raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
        return item
