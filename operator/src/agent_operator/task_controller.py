"""Task controller for AgentOS."""

from datetime import UTC, datetime
from typing import Any

import httpx
import kopf


def utc_now() -> str:
    """Return the current UTC time in Kubernetes-compatible format."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_agent_service_url(
    agent_name: str,
    namespace: str,
) -> str:
    """Build the stable in-cluster Agent Runtime invoke endpoint."""

    return f"http://{agent_name}.{namespace}.svc.cluster.local:8080/v1/invoke"


def invoke_agent(
    agent_name: str,
    namespace: str,
    prompt: str,
    timeout_seconds: int,
) -> str:
    """Invoke an Agent Runtime through its Kubernetes Service."""

    response = httpx.post(
        build_agent_service_url(
            agent_name=agent_name,
            namespace=namespace,
        ),
        json={
            "input": prompt,
        },
        timeout=float(timeout_seconds),
    )

    response.raise_for_status()

    payload = response.json()

    return payload["output"]


@kopf.on.create("agentos.io", "v1alpha1", "tasks")
def create_task(
    spec: dict[str, Any],
    namespace: str,
    patch: kopf.Patch,
    **_: Any,
) -> None:
    """Execute a newly created Task."""

    agent_name = spec["agentRef"]["name"]
    prompt = spec["input"]["prompt"]
    timeout_seconds = spec.get("timeoutSeconds", 300)

    patch.status["phase"] = "Running"
    patch.status["startedAt"] = utc_now()

    try:
        result = invoke_agent(
            agent_name=agent_name,
            namespace=namespace,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        patch.status["phase"] = "Failed"
        patch.status["message"] = str(exc)
        patch.status["completedAt"] = utc_now()
        return

    patch.status["result"] = result
    patch.status["phase"] = "Succeeded"
    patch.status["completedAt"] = utc_now()
