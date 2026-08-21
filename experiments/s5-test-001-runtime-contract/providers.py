"""Experimental runtime-specific Provider implementations."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from runtime_contract import (
    ExecutionHandle,
    ExecutionOutcome,
    ExecutionRequest,
    Observation,
    OutcomeKind,
    RuntimeBinding,
    RuntimeDescriptor,
    Submission,
    TruthValue,
)


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


class HermesProvider:
    descriptor = RuntimeDescriptor(
        runtime_id="hermes",
        provider_id="experimental.hermes",
        version="0.20.4",
        interaction_modes=("inline_outcome",),
        ownership_modes=("managed", "external"),
        artifact={
            "image": "nousresearch/hermes-agent:v2026.8.18",
            "digest": (
                "sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32"
                "bc763ccf6"
            ),
            "architecture": "linux/arm64",
        },
    )

    def __init__(
        self,
        binding: RuntimeBinding,
        *,
        name: str,
        data_dir: Path,
        gateway_key: str,
        model_key: str,
        host_port: int = 18680,
    ) -> None:
        self.binding = binding
        self.name = name
        self.data_dir = data_dir
        self.gateway_key = gateway_key
        self.model_key = model_key
        self.host_port = host_port

    def configure(self) -> None:
        env = {**os.environ, "KIMI_CN_API_KEY": self.model_key}
        base = ["docker", "run", "--rm", "-v", f"{self.data_dir}:/opt/data"]
        image = self._image()
        for path, value in (
            ("model.provider", "kimi-coding-cn"),
            ("model.default", "kimi-k3"),
        ):
            subprocess.run(
                [*base, image, "hermes", "config", "set", path, value],
                check=True,
                capture_output=True,
                text=True,
            )
        subprocess.run(
            [
                *base,
                "-e",
                "KIMI_CN_API_KEY",
                image,
                "sh",
                "-c",
                (
                    "umask 077; printf 'KIMI_CN_API_KEY=%s\\n' "
                    '"$KIMI_CN_API_KEY" > /opt/data/.env; '
                    "chown hermes:hermes /opt/data/.env"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def start(self) -> None:
        environment = {**os.environ, "API_SERVER_KEY": self.gateway_key}
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                self.name,
                "-p",
                f"127.0.0.1:{self.host_port}:8642",
                "-v",
                f"{self.data_dir}:/opt/data",
                "-e",
                "HERMES_HOME=/opt/data",
                "-e",
                "API_SERVER_ENABLED=true",
                "-e",
                "API_SERVER_HOST=0.0.0.0",
                "-e",
                "API_SERVER_KEY",
                self._image(),
                "gateway",
                "run",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )

    def wait_available(self, timeout_seconds: int = 180) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if any(
                o.name == "RuntimeAvailable" and o.value is TruthValue.TRUE
                for o in self.observe()
            ):
                return True
            time.sleep(0.5)
        return False

    def observe(self) -> tuple[Observation, ...]:
        observed = _now_ms()
        running = self._container_running()
        try:
            health = self._request("/health")
            runtime = health.get("status") == "ok"
        except (OSError, urllib.error.URLError, TimeoutError):
            runtime = False
        return (
            Observation(
                "InfrastructureAvailable",
                TruthValue.TRUE if running else TruthValue.FALSE,
                "managed container state",
                observed,
            ),
            Observation(
                "RuntimeAvailable",
                TruthValue.TRUE if runtime else TruthValue.FALSE,
                "Hermes health interaction",
                observed,
            ),
            Observation(
                "DependencyReady",
                TruthValue.UNKNOWN,
                "health cannot establish model inference",
                observed,
            ),
        )

    def sanitized_preflight(self) -> dict[str, object]:
        """Inspect active resolution without returning any credential material."""
        resolver = """
import json
import os
from pathlib import Path
from hermes_cli.config import load_config_readonly, load_env
from hermes_cli.runtime_provider import resolve_runtime_provider

home = Path(os.environ["HERMES_HOME"])
load_env()
config = load_config_readonly()
model = config.get("model", {})
configured_provider = model.get("provider", "") if isinstance(model, dict) else ""
configured_model = model.get("default", "") if isinstance(model, dict) else str(model)
runtime = resolve_runtime_provider(
    requested=configured_provider,
    target_model=configured_model,
)
print(json.dumps({
    "configured_provider": configured_provider,
    "configured_model": configured_model,
    "resolved_provider": runtime.get("provider"),
    "resolved_model": configured_model,
    "credential_present": bool(runtime.get("api_key")),
    "projection_present": (home / ".env").is_file(),
}))
"""
        completed = subprocess.run(
            [
                "docker",
                "exec",
                "--user",
                "hermes",
                self.name,
                "/opt/hermes/.venv/bin/python",
                "-c",
                resolver,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        allowed = {
            "configured_provider",
            "configured_model",
            "resolved_provider",
            "resolved_model",
            "credential_present",
            "projection_present",
        }
        return {key: payload.get(key) for key in allowed}

    def diagnostic_submit(self, request: ExecutionRequest) -> dict[str, object]:
        """Perform one request and retain only strictly sanitized evidence."""
        started = time.monotonic_ns()
        try:
            payload = self._request(
                "/v1/chat/completions",
                method="POST",
                body={
                    "model": "hermes-agent",
                    "messages": [{"role": "user", "content": request.input_text}],
                    "stream": False,
                },
                timeout=180,
            )
            return {
                "status": 200,
                "body": self._sanitize_diagnostic(json.dumps(payload)),
                "latency_ms": (time.monotonic_ns() - started) // 1_000_000,
            }
        except urllib.error.HTTPError as exc:
            raw = exc.read(16_384).decode("utf-8", errors="replace")
            sanitized = self._sanitize_diagnostic(raw)
            native_id = None
            try:
                error_payload = json.loads(raw)
                if isinstance(error_payload, dict):
                    for key in ("request_id", "error_id", "id"):
                        value = error_payload.get(key)
                        if isinstance(value, str) and value:
                            native_id = self._sanitize_diagnostic(value)
                            break
            except json.JSONDecodeError:
                pass
            return {
                "status": exc.code,
                "reason": self._sanitize_diagnostic(str(exc.reason)),
                "body": sanitized,
                "native_id": native_id,
                "latency_ms": (time.monotonic_ns() - started) // 1_000_000,
            }

    def _sanitize_diagnostic(self, value: str) -> str:
        sanitized = value.replace(self.gateway_key, "[REDACTED]")
        sanitized = sanitized.replace(self.model_key, "[REDACTED]")
        sanitized = re.sub(
            r"(?i)(authorization|api[_-]?key|token|cookie|secret)"
            r"([\"'=:\s]+)[^\s,;\"}]+",
            r"\1\2[REDACTED]",
            sanitized,
        )
        return sanitized[:4096]

    def submit(self, request: ExecutionRequest) -> Submission:
        started = time.monotonic_ns()
        try:
            payload = self._request(
                "/v1/chat/completions",
                method="POST",
                body={
                    "model": "hermes-agent",
                    "messages": [{"role": "user", "content": request.input_text}],
                    "stream": False,
                },
                timeout=180,
            )
            choice = payload["choices"][0]
            output = choice["message"]["content"]
            usage = payload.get("usage")
            total = usage.get("total_tokens") if isinstance(usage, dict) else None
            semantic_success = (
                bool(output and str(output).strip())
                and isinstance(total, int)
                and total > 0
            )
            outcome = ExecutionOutcome(
                kind=OutcomeKind.SUCCESS if semantic_success else OutcomeKind.FAILURE,
                correlation_id=request.correlation_id,
                output=str(output) if output is not None else None,
                runtime_id=self.descriptor.runtime_id,
                provider_id=self.descriptor.provider_id,
                latency_ms=(time.monotonic_ns() - started) // 1_000_000,
                usage=usage if isinstance(usage, dict) else None,
                reason=None
                if semantic_success
                else "non-empty output and authoritative non-zero usage required",
            )
        except Exception as exc:
            outcome = ExecutionOutcome(
                kind=OutcomeKind.FAILURE,
                correlation_id=request.correlation_id,
                output=None,
                runtime_id=self.descriptor.runtime_id,
                provider_id=self.descriptor.provider_id,
                latency_ms=(time.monotonic_ns() - started) // 1_000_000,
                reason=f"runtime execution failed: {type(exc).__name__}",
            )
        return Submission(correlation_id=request.correlation_id, outcome=outcome)

    def await_outcome(
        self, handle: ExecutionHandle, timeout_ms: int
    ) -> ExecutionOutcome:
        raise RuntimeError("inline runtime does not expose a deferred handle")

    def cleanup(self) -> None:
        subprocess.run(
            ["docker", "rm", "-f", self.name],
            check=False,
            capture_output=True,
            text=True,
        )

    def _image(self) -> str:
        return f"nousresearch/hermes-agent@{self.descriptor.artifact['digest']}"

    def _container_running(self) -> bool:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", self.name],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict | None = None,
        timeout: float = 5,
    ) -> dict:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.host_port}{path}",
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.gateway_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)


class OpenClawProvider:
    """Deferred Provider exercised through an injected native evidence client."""

    descriptor = RuntimeDescriptor(
        runtime_id="openclaw",
        provider_id="experimental.openclaw",
        version="2026.7.1-2 (0790d9f)",
        interaction_modes=("deferred_outcome",),
        ownership_modes=("managed", "external"),
        artifact={"distribution": "npm", "architecture": "darwin/arm64"},
    )

    def __init__(
        self, binding: RuntimeBinding, native_call: Callable[[str, dict], dict]
    ) -> None:
        self.binding = binding
        self._native_call = native_call

    def observe(self) -> tuple[Observation, ...]:
        now = _now_ms()
        return (
            Observation(
                "InfrastructureAvailable",
                TruthValue.UNKNOWN,
                "external ownership hides host",
                now,
            ),
            Observation(
                "RuntimeAvailable",
                TruthValue.TRUE,
                "accepted prior real Gateway evidence",
                now,
            ),
            Observation(
                "DependencyReady",
                TruthValue.UNKNOWN,
                "not required for substitutability replay",
                now,
            ),
        )

    def submit(self, request: ExecutionRequest) -> Submission:
        native = self._native_call("submit", {"input": request.input_text})
        return Submission(
            correlation_id=request.correlation_id,
            handle=ExecutionHandle(request.correlation_id, str(native["runId"])),
        )

    def await_outcome(
        self, handle: ExecutionHandle, timeout_ms: int
    ) -> ExecutionOutcome:
        started = time.monotonic_ns()
        native = self._native_call(
            "observe", {"runId": handle.native_reference, "timeoutMs": timeout_ms}
        )
        success = native.get("status") == "ok"
        return ExecutionOutcome(
            kind=OutcomeKind.SUCCESS if success else OutcomeKind.FAILURE,
            correlation_id=handle.correlation_id,
            output=native.get("output") if success else None,
            runtime_id=self.descriptor.runtime_id,
            provider_id=self.descriptor.provider_id,
            latency_ms=(time.monotonic_ns() - started) // 1_000_000,
            reason=None if success else "runtime dependency unavailable",
        )
