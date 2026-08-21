"""Experimental Hermes-only provider prototype."""

import json
import subprocess
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

    def provision(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
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
                self.image,
                "gateway",
                "run",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def invoke(self, request: RuntimeRequest) -> RuntimeResult:
        payload = self._request(
            "/v1/chat/completions",
            method="POST",
            body={
                "model": "hermes-agent",
                "messages": [{"role": "user", "content": request.input}],
                "stream": False,
            },
        )
        output = payload["choices"][0]["message"]["content"]
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
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)
