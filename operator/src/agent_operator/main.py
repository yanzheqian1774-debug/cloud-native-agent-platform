"""Enterprise Agent OS Kubernetes operator."""

from typing import Any

import kopf
from kubernetes import client, config

import agent_operator.task_controller  # noqa: F401
from agent_operator.resources import (
    build_agent_deployment,
    build_agent_service,
)

API_GROUP = "agentos.io"
API_VERSION = "v1alpha1"
RESOURCE = "agents"


@kopf.on.startup()
def startup(logger: Any, **_: Any) -> None:
    """Log operator startup."""
    logger.info("Enterprise Agent OS operator starting")


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
    replicas = spec.get("replicas", 1)

    update_deployment_replicas(
        name=name,
        namespace=namespace,
        replicas=replicas,
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


def update_deployment_replicas(
    name: str,
    namespace: str,
    replicas: int,
) -> None:
    load_kubernetes_config()

    apps_api = client.AppsV1Api()

    apps_api.patch_namespaced_deployment(
        name=name,
        namespace=namespace,
        body={
            "spec": {
                "replicas": replicas,
            }
        },
    )
