"""Enterprise Agent OS Kubernetes operator."""

import os
from threading import Event, Thread
from typing import Any

import kopf
from kubernetes import client, config

import agent_operator.task_controller
import agent_operator.workflow_controller  # noqa: F401
from agent_operator.native_dispatch_reconciler import (
    NativeDispatchAssembly,
    build_native_dispatch_from_environment,
)
from agent_operator.resources import (
    build_agent_deployment,
    build_agent_service,
)

API_GROUP = "agentos.io"
API_VERSION = "v1alpha1"
RESOURCE = "agents"
_native_dispatch_assembly: NativeDispatchAssembly | None = None
_native_dispatch_stop = Event()
_native_dispatch_thread: Thread | None = None


def _run_native_dispatch(logger: Any, interval: float) -> None:
    if _native_dispatch_assembly is None:
        return
    while not _native_dispatch_stop.is_set():
        try:
            result = _native_dispatch_assembly.worker.run_once()
            if result.state != "IDLE":
                logger.info(
                    "Native dispatch reconciliation: state=%s command=%s",
                    result.state,
                    result.command_id,
                )
        except Exception:
            logger.exception("Native dispatch reconciliation failed")
        _native_dispatch_stop.wait(interval)


@kopf.on.startup()
def startup(logger: Any, **_: Any) -> None:
    """Log operator startup."""
    global _native_dispatch_assembly, _native_dispatch_thread
    logger.info("Enterprise Agent OS operator starting")
    _native_dispatch_assembly = build_native_dispatch_from_environment()
    if _native_dispatch_assembly is None:
        return
    interval = float(os.environ.get("NATIVE_DISPATCH_POLL_SECONDS", "1"))
    if not 0.1 <= interval <= 60:
        raise ValueError("NATIVE_DISPATCH_POLL_SECONDS_INVALID")
    _native_dispatch_stop.clear()
    _native_dispatch_thread = Thread(
        target=_run_native_dispatch,
        args=(logger, interval),
        name="native-dispatch-worker",
        daemon=True,
    )
    _native_dispatch_thread.start()


@kopf.on.cleanup()
def cleanup(**_: Any) -> None:
    """Stop the Native dispatch loop and release PostgreSQL pools."""
    global _native_dispatch_assembly, _native_dispatch_thread
    _native_dispatch_stop.set()
    if _native_dispatch_thread is not None:
        _native_dispatch_thread.join(timeout=5)
        _native_dispatch_thread = None
    if _native_dispatch_assembly is not None:
        _native_dispatch_assembly.close()
        _native_dispatch_assembly = None


@kopf.on.create("agentos.io", "v1alpha1", "agents")
def create_agent(
    spec: dict[str, Any],
    name: str,
    namespace: str,
    patch: kopf.Patch,
    body: dict[str, Any],
    **_: Any,
) -> None:
    create_deployment(
        name=name,
        namespace=namespace,
        spec=spec,
        owner=body,
    )
    create_service(
        name=name,
        namespace=namespace,
        owner=body,
    )

    patch.status["phase"] = "Pending"
    patch.status["readyReplicas"] = 0


@kopf.on.update("agentos.io", "v1alpha1", "agents")
def update_agent(
    spec: dict[str, Any],
    name: str,
    namespace: str,
    patch: kopf.Patch,
    **_: Any,
) -> None:
    """Reconcile mutable Deployment state when an Agent spec changes."""

    reconcile_agent_deployment(
        name=name,
        namespace=namespace,
        spec=spec,
    )


@kopf.on.delete(API_GROUP, API_VERSION, RESOURCE)
def delete_agent(
    name: str,
    namespace: str,
    logger: Any,
    **_: Any,
) -> None:
    """Handle Agent deletion."""

    logger.info("Agent deleted: %s/%s", namespace, name)


def create_deployment(
    name: str,
    namespace: str,
    spec: dict[str, Any],
    owner: dict[str, Any] | None = None,
) -> None:
    deployment = build_agent_deployment(
        name=name,
        namespace=namespace,
        spec=spec,
    )

    if owner is not None:
        kopf.adopt(deployment, owner=owner)

    load_kubernetes_config()

    apps_api = client.AppsV1Api()

    apps_api.create_namespaced_deployment(
        namespace=namespace,
        body=deployment,
    )


def create_service(
    name: str,
    namespace: str,
    owner: dict[str, Any] | None = None,
) -> None:
    service = build_agent_service(
        name=name,
        namespace=namespace,
    )

    if owner is not None:
        kopf.adopt(service, owner=owner)

    load_kubernetes_config()

    core_api = client.CoreV1Api()

    core_api.create_namespaced_service(
        namespace=namespace,
        body=service,
    )


def load_kubernetes_config() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def get_deployment_ready_replicas(
    name: str,
    namespace: str,
) -> int:
    load_kubernetes_config()

    apps_api = client.AppsV1Api()

    deployment = apps_api.read_namespaced_deployment(
        name=name,
        namespace=namespace,
    )

    return deployment.status.ready_replicas or 0


@kopf.timer(
    "agentos.io",
    "v1alpha1",
    "agents",
    interval=5.0,
)
def reconcile_agent_status(
    spec: dict[str, Any],
    name: str,
    namespace: str,
    patch: kopf.Patch,
    **_: Any,
) -> None:
    desired_replicas = spec.get("replicas", 1)

    try:
        ready_replicas = get_deployment_ready_replicas(
            name=name,
            namespace=namespace,
        )
    except client.ApiException as exc:
        if exc.status == 404:
            patch.status["phase"] = "Pending"
            patch.status["readyReplicas"] = 0
            return
        raise

    patch.status["readyReplicas"] = ready_replicas

    if ready_replicas >= desired_replicas:
        patch.status["phase"] = "Running"
    elif ready_replicas > 0:
        patch.status["phase"] = "Provisioning"
    else:
        patch.status["phase"] = "Pending"


def reconcile_agent_deployment(
    name: str,
    namespace: str,
    spec: dict[str, Any],
) -> None:
    """Reconcile mutable Deployment state from the Agent desired spec."""

    desired = build_agent_deployment(
        name=name,
        namespace=namespace,
        spec=spec,
    )

    desired_spec = desired["spec"]

    patch_body = {
        "spec": {
            "replicas": desired_spec["replicas"],
            "template": desired_spec["template"],
        }
    }

    load_kubernetes_config()

    apps_api = client.AppsV1Api()

    apps_api.patch_namespaced_deployment(
        name=name,
        namespace=namespace,
        body=patch_body,
    )
