"""Task controller for AgentOS."""

from datetime import UTC, datetime
from typing import Any

import httpx
import kopf
from kubernetes import client, config

from agent_operator.errors import TaskExecutionError, classify_http_error
from agent_operator.retry import RetryExhaustedError, execute_with_retry


def utc_now() -> str:
    """Return the current UTC time in Kubernetes-compatible format."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def patch_task_status(
    *,
    name: str,
    namespace: str,
    status: dict[str, object],
) -> None:
    """Persist Task status immediately to the Kubernetes API."""

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    api = client.CustomObjectsApi()

    api.patch_namespaced_custom_object_status(
        group="agentos.io",
        version="v1alpha1",
        namespace=namespace,
        plural="tasks",
        name=name,
        body={"status": status},
    )


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
    timeout_seconds: float,
) -> str:
    """Invoke an Agent Runtime through its Kubernetes Service."""

    try:
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

    except httpx.HTTPError as exc:
        raise classify_http_error(exc) from exc

    try:
        payload = response.json()
        return payload["output"]

    except (KeyError, ValueError, TypeError) as exc:
        raise TaskExecutionError(
            reason="InvalidResponse",
            message=f"invalid Agent Runtime response: {exc}",
            retryable=False,
        ) from exc


@kopf.on.create("agentos.io", "v1alpha1", "tasks")
def create_task(
    spec: dict[str, Any],
    name: str,
    namespace: str,
    patch: kopf.Patch,
    **_: Any,
) -> None:
    """Execute a newly created Task."""

    agent_name = spec["agentRef"]["name"]
    prompt = spec["input"]["prompt"]
    timeout_seconds = spec.get("timeoutSeconds", 300)

    started_at = utc_now()

    patch_task_status(
        name=name,
        namespace=namespace,
        status={
            "phase": "Running",
            "startedAt": started_at,
            "completedAt": None,
            "attempts": 0,
            "result": None,
            "reason": None,
            "message": None,
            "retryable": None,
        },
    )

    patch.status["startedAt"] = started_at

    def operation(remaining_seconds: float) -> str:
        return invoke_agent(
            agent_name=agent_name,
            namespace=namespace,
            prompt=prompt,
            timeout_seconds=remaining_seconds,
        )

    try:
        result, attempts = execute_with_retry(
            operation,
            timeout_seconds=float(timeout_seconds),
        )

    except RetryExhaustedError as exc:
        if exc.error.reason == "ExecutionTimeout":
            patch.status["phase"] = "TimedOut"
        else:
            patch.status["phase"] = "Failed"

        patch.status["result"] = None
        patch.status["reason"] = exc.error.reason
        patch.status["message"] = exc.error.message
        patch.status["retryable"] = exc.error.retryable
        patch.status["attempts"] = exc.attempts
        patch.status["completedAt"] = utc_now()
        return

    patch.status["phase"] = "Succeeded"
    patch.status["result"] = result
    patch.status["reason"] = None
    patch.status["message"] = None
    patch.status["retryable"] = None
    patch.status["attempts"] = attempts
    patch.status["completedAt"] = utc_now()
