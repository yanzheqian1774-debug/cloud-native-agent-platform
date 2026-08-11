"""Kubernetes resource builders for Agent workloads."""

from typing import Any


def build_agent_deployment(
    name: str,
    namespace: str,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Build a Kubernetes Deployment for an Agent."""

    replicas = spec.get("replicas", 1)

    labels = {
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/managed-by": "agent-operator",
        "agentos.io/agent": name,
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": replicas,
            "selector": {
                "matchLabels": {
                    "agentos.io/agent": name,
                }
            },
            "template": {
                "metadata": {
                    "labels": labels,
                },
                "spec": {
                    "containers": [
                        {
                            "name": "agent",
                            "image": "nginx:1.27-alpine",
                            "imagePullPolicy": "IfNotPresent",
                        }
                    ]
                },
            },
        },
    }
