"""Task controller for AgentOS."""

from datetime import UTC, datetime
from typing import Any

import httpx
import kopf
from agent_core.interface_spine.v0_2 import InternalExecutionEnvelope
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from agent_operator.compatibility_interpreter import (
    CompatibilityInterpreterError,
    interpret_legacy_task,
)
from agent_operator.errors import TaskExecutionError, classify_http_error
from agent_operator.execution_coordinator import (
    ExecutionClassification,
    TaskEvidenceSubject,
    TaskExecutionContext,
    build_capability_plan,
    build_default_coordinator,
    build_runtime_configuration,
)
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

    except (
        httpx.ReadError,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
        httpx.WriteError,
        httpx.WriteTimeout,
    ) as exc:
        raise TaskExecutionError(
            reason="ExecutionOutcomeUnknown",
            message=(
                "Runtime transport failed after invocation may have started; "
                "automatic retry was suppressed"
            ),
            retryable=False,
        ) from exc
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


def load_agent_definition(*, name: str, namespace: str) -> list[dict[str, Any]]:
    """Read current same-namespace Agent evidence without changing its API."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    api = client.CustomObjectsApi()
    try:
        body = api.get_namespaced_custom_object(
            group="agentos.io",
            version="v1alpha1",
            namespace=namespace,
            plural="agents",
            name=name,
        )
    except ApiException as exc:
        if exc.status == 404:
            return []
        raise TaskExecutionError(
            reason="AgentLookupFailed",
            message=f"failed to read Agent evidence: {exc.reason}",
            retryable=True,
        ) from exc
    if not isinstance(body, dict):
        raise TaskExecutionError(
            reason="InvalidLegacyIdentityEvidence",
            message="Agent API returned invalid evidence",
            retryable=False,
        )
    return [body]


def task_evidence_subject(
    *, metadata: dict[str, Any], namespace: str
) -> TaskEvidenceSubject | None:
    """Resolve evidence identity from Kubernetes Task and Workflow ownership."""
    task_uid = metadata.get("uid")
    metadata_namespace = metadata.get("namespace")
    labels = metadata.get("labels", {})
    owners = metadata.get("ownerReferences", ())
    workflow_name = (
        labels.get("agentos.io/workflow") if isinstance(labels, dict) else None
    )
    workflow_owners = (
        [
            item
            for item in owners
            if isinstance(item, dict)
            and item.get("apiVersion") == "agentos.io/v1alpha1"
            and item.get("kind") == "Workflow"
            and item.get("controller") is True
        ]
        if isinstance(owners, list)
        else []
    )
    if workflow_name is None and not workflow_owners:
        return None
    if (
        not isinstance(task_uid, str)
        or not task_uid.strip()
        or metadata_namespace != namespace
        or not isinstance(workflow_name, str)
        or not workflow_name.strip()
        or len(workflow_owners) != 1
        or workflow_owners[0].get("name") != workflow_name
        or not isinstance(workflow_owners[0].get("uid"), str)
        or not workflow_owners[0]["uid"].strip()
    ):
        raise ValueError("EVIDENCE_SUBJECT_IDENTITY_CONFLICT")
    return TaskEvidenceSubject(
        namespace=namespace,
        workflow_identity=workflow_owners[0]["uid"],
        task_identity=task_uid,
    )


def invoke_compatible_agent(
    *,
    context: InternalExecutionEnvelope,
    prompt: str,
    timeout_seconds: float,
) -> str:
    """Invoke the unchanged v0.1 endpoint from validated internal context."""
    return invoke_agent(
        agent_name=context.definition_ref.name,
        namespace=context.definition_ref.namespace,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
    )


@kopf.on.create("agentos.io", "v1alpha1", "tasks")
def create_task(
    spec: dict[str, Any],
    name: str,
    namespace: str,
    patch: kopf.Patch,
    meta: dict[str, Any],
    status: dict[str, Any] | None = None,
    **_: Any,
) -> None:
    """Execute a newly created Task."""

    prompt = spec["input"]["prompt"]
    timeout_seconds = spec.get("timeoutSeconds", 300)

    current_phase = (status or {}).get("phase")
    if current_phase in {"Succeeded", "Failed", "TimedOut"}:
        return
    if current_phase == "Running":
        patch.status["phase"] = "Failed"
        patch.status["result"] = None
        patch.status["reason"] = "ExecutionStateUnknown"
        patch.status["message"] = (
            "Task handler replayed after execution started; Runtime outcome is "
            "unknown and duplicate invocation was prevented"
        )
        patch.status["retryable"] = False
        patch.status["attempts"] = (status or {}).get("attempts", 0)
        patch.status["startedAt"] = (status or {}).get("startedAt")
        patch.status["completedAt"] = utc_now()
        return

    agent_name = spec.get("agentRef", {}).get("name")
    try:
        agent_candidates = load_agent_definition(
            name=agent_name,
            namespace=namespace,
        )
        context = interpret_legacy_task(
            task_spec=spec,
            task_metadata=meta,
            namespace=namespace,
            agent_candidates=agent_candidates,
        )
        definition_evidence = agent_candidates[0]
        capability_plan = build_capability_plan(
            definition_evidence=definition_evidence,
            envelope=context,
            input_text=prompt,
        )
        coordinator = build_default_coordinator(
            capability_plan.capability if capability_plan is not None else None
        )
        execution_context = TaskExecutionContext(
            envelope=context,
            runtime_configuration=build_runtime_configuration(
                definition_evidence=definition_evidence,
                namespace=namespace,
                agent_name=agent_name,
            ),
            capability_plan=capability_plan,
            evidence_subject=task_evidence_subject(
                metadata=meta,
                namespace=namespace,
            ),
        )
    except (CompatibilityInterpreterError, ValueError) as exc:
        patch.status["phase"] = "Failed"
        patch.status["result"] = None
        patch.status["reason"] = getattr(exc, "reason", "InvalidLegacyIdentityEvidence")
        patch.status["message"] = str(exc)
        patch.status["retryable"] = False
        patch.status["attempts"] = 0
        patch.status["startedAt"] = None
        patch.status["completedAt"] = utc_now()
        return

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
        del remaining_seconds
        outcome = coordinator.execute(
            context=execution_context,
            input_text=prompt,
        )
        if outcome.classification is ExecutionClassification.SUCCEEDED:
            if outcome.result is None:
                raise TaskExecutionError(
                    reason="InvalidResponse",
                    message="execution completed without a result",
                    retryable=False,
                )
            return outcome.result
        if outcome.classification is ExecutionClassification.DENIED:
            reason = "AuthorizationError"
        elif outcome.classification is ExecutionClassification.UNKNOWN:
            reason = "ExecutionOutcomeUnknown"
        else:
            reason = "InvalidRequest"
        raise TaskExecutionError(
            reason=reason,
            message=f"bounded execution failed: {outcome.diagnostic}",
            retryable=False,
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
