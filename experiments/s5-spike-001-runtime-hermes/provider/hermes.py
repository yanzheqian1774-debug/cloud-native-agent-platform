"""Experimental Hermes-only provider prototype."""

import json
import os
import subprocess
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from harness.runtime_boundary import (
    RuntimeHealth,
    RuntimeRequest,
    RuntimeResult,
    RuntimeState,
)


@dataclass
class HermesProvider:
    """Keep all Hermes semantics on the provider side of the boundary."""

    name: str
    image: str
    data_dir: Path
    api_key: str
    host_port: int
    inference_provider: str | None = None
    model: str | None = None
    model_credential_env: str | None = None
    last_invocation_evidence: dict | None = None

    def configure(self) -> None:
        """Persist only non-secret Hermes model selection in spike storage."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        settings = []
        if self.inference_provider:
            settings.append(("model.provider", self.inference_provider))
        if self.model:
            settings.append(("model.default", self.model))
        for key, value in settings:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{self.data_dir}:/opt/data",
                    self.image,
                    "config",
                    "set",
                    key,
                    value,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

    def bind_model_credential(self) -> None:
        """Write the credential only into disposable runtime storage."""
        if not self.model_credential_env:
            return
        if not os.environ.get(self.model_credential_env):
            raise ValueError("model credential environment variable is absent")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        variable = self.model_credential_env
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{self.data_dir}:/opt/data",
                "-e",
                variable,
                self.image,
                "sh",
                "-lc",
                (
                    "umask 077; "
                    f'printf "{variable}=%s\\n" "${variable}" > /opt/data/.env; '
                    "chown hermes:hermes /opt/data/.env"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def provision(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            self.name,
            "--label",
            "s5-spike-001=true",
            "-v",
            f"{self.data_dir}:/opt/data",
            "-p",
            f"127.0.0.1:{self.host_port}:8642",
            "-e",
            "API_SERVER_ENABLED=true",
            "-e",
            "API_SERVER_HOST=0.0.0.0",
            "-e",
            f"API_SERVER_KEY={self.api_key}",
        ]
        if self.inference_provider:
            command.extend(
                ["-e", f"HERMES_INFERENCE_PROVIDER={self.inference_provider}"]
            )
        if self.model:
            command.extend(["-e", f"HERMES_MODEL={self.model}"])
        if self.model_credential_env:
            if not os.environ.get(self.model_credential_env):
                raise ValueError("model credential environment variable is absent")
            # Pass only the environment-variable name. Docker inherits its value
            # from this process without putting the credential in argv.
            command.extend(["-e", self.model_credential_env])
        command.extend([self.image, "gateway", "run"])
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

    def sanitized_preflight(self) -> dict:
        """Resolve active Hermes configuration without exposing credentials."""
        resolver = textwrap.dedent(
            """
            import json
            import os
            import stat
            from pathlib import Path

            from hermes_cli.config import load_config
            from hermes_cli.env_loader import load_hermes_dotenv
            from hermes_cli.runtime_provider import resolve_runtime_provider

            home = Path(os.environ.get("HERMES_HOME", ""))
            load_hermes_dotenv(hermes_home=home)
            cfg = load_config()
            model = cfg.get("model", {})
            provider = model.get("provider", "") if isinstance(model, dict) else ""
            default = (
                model.get("default", "") if isinstance(model, dict) else str(model)
            )
            runtime = resolve_runtime_provider(
                requested=provider,
                target_model=default,
            )
            env_path = home / ".env"
            lines = env_path.read_text().splitlines()
            gateway = cfg.get("gateway", {})
            result = {
                "active_home": str(home),
                "configured_provider": provider,
                "configured_model": default,
                "resolved_provider": runtime.get("provider"),
                "resolved_model": default,
                "credential_present": bool(runtime.get("api_key")),
                "credential_key_present": any(
                    line.startswith("KIMI_CN_API_KEY=") for line in lines
                ),
                "credential_assignment_nonempty": any(
                    line.startswith("KIMI_CN_API_KEY=")
                    and bool(line.split("=", 1)[1])
                    for line in lines
                ),
                "env_mode": format(stat.S_IMODE(env_path.stat().st_mode), "04o"),
                "env_owner_uid": env_path.stat().st_uid,
                "env_readable": os.access(env_path, os.R_OK),
                "multiplex_profiles": bool(gateway.get("multiplex_profiles", False))
                if isinstance(gateway, dict)
                else False,
            }
            print(json.dumps(result))
            """
        )
        result = subprocess.run(
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
        return json.loads(result.stdout)

    def invoke(self, request: RuntimeRequest) -> RuntimeResult:
        payload = self._request(
            "/v1/chat/completions",
            method="POST",
            body={
                "model": "hermes-agent",
                "messages": [{"role": "user", "content": request.input}],
                "stream": False,
            },
            timeout=180,
        )
        output = payload["choices"][0]["message"]["content"]
        choice = payload["choices"][0]
        self.last_invocation_evidence = {
            "http_status": 200,
            "runtime_id": payload.get("id"),
            "runtime_model": payload.get("model"),
            "finish_reason": choice.get("finish_reason"),
            "usage": payload.get("usage"),
        }
        return RuntimeResult(output=output, correlation_id=request.correlation_id)

    def health(self) -> RuntimeHealth:
        try:
            live = self._request("/health")
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            return RuntimeHealth(
                state=RuntimeState.UNAVAILABLE,
                infrastructure_available=self._container_running(),
                runtime_available=False,
                dependency_available=None,
                task_ready=False,
                detail=type(exc).__name__,
            )

        if live.get("status") != "ok":
            return RuntimeHealth(
                state=RuntimeState.DEGRADED,
                infrastructure_available=self._container_running(),
                runtime_available=True,
                dependency_available=None,
                task_ready=None,
                detail="unexpected liveness payload",
            )

        try:
            detailed = self._request("/health/detailed")
        except (OSError, urllib.error.URLError, TimeoutError):
            return RuntimeHealth(
                state=RuntimeState.DEGRADED,
                infrastructure_available=self._container_running(),
                runtime_available=True,
                dependency_available=None,
                task_ready=None,
                detail="liveness passed; detailed readiness unavailable",
            )

        ready = detailed.get("status") == "ok"
        # Live A.2 evidence showed model.status=ok with no configured inference
        # provider. Detailed health can establish API/runtime readiness, but it
        # cannot establish dependency or task readiness by itself.
        return RuntimeHealth(
            state=RuntimeState.READY if ready else RuntimeState.DEGRADED,
            infrastructure_available=self._container_running(),
            runtime_available=True,
            dependency_available=False if not ready else None,
            task_ready=False if not ready else None,
            detail="runtime readiness mapped; task readiness requires invocation",
        )

    def cleanup(self) -> None:
        subprocess.run(
            ["docker", "rm", "-f", self.name],
            check=False,
            capture_output=True,
            text=True,
        )

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
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.host_port}{path}",
            method=method,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
