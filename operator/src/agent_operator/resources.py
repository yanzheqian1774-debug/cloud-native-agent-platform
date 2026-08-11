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
                            "image": "enterprise-agent-runtime:v0.1",
                            "imagePullPolicy": "IfNotPresent",
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": 8080,
                                    "protocol": "TCP",
                                }
                            ],
                            "env": [
                                {
                                    "name": "AGENT_NAME",
                                    "value": name,
                                },
                                {
                                    "name": "AGENT_NAMESPACE",
                                    "value": namespace,
                                },
                                {
                                    "name": "AGENT_RUNTIME",
                                    "value": spec["runtime"]["type"],
                                },
                                {
                                    "name": "MODEL_PROVIDER",
                                    "value": spec["model"]["provider"],
                                },
                                {
                                    "name": "MODEL_NAME",
                                    "value": spec["model"]["name"],
                                },
                            ],
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/healthz",
                                    "port": 8080,
                                },
                                "initialDelaySeconds": 2,
                                "periodSeconds": 10,
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/readyz",
                                    "port": 8080,
                                },
                                "initialDelaySeconds": 2,
                                "periodSeconds": 5,
                            },
                        }
                    ]
                },
            },
        },
    }
