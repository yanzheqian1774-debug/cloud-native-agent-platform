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

    model = spec["model"]

    env = [
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
            "value": model["provider"],
        },
        {
            "name": "MODEL_NAME",
            "value": model["name"],
        },
    ]

    if "baseUrl" in model:
        env.append(
            {
                "name": "MODEL_BASE_URL",
                "value": model["baseUrl"],
            }
        )

    if "secretRef" in model:
        secret_ref = model["secretRef"]

        env.append(
            {
                "name": "MODEL_API_KEY",
                "valueFrom": {
                    "secretKeyRef": {
                        "name": secret_ref["name"],
                        "key": secret_ref["key"],
                    }
                },
            }
        )
    identity = spec.get("identity", {})
    instructions = spec.get("instructions", {})

    if "role" in identity:
        env.append(
            {
                "name": "AGENT_ROLE",
                "value": identity["role"],
            }
        )

    if "displayName" in identity:
        env.append(
            {
                "name": "AGENT_DISPLAY_NAME",
                "value": identity["displayName"],
            }
        )

    if "systemPrompt" in instructions:
        env.append(
            {
                "name": "AGENT_SYSTEM_PROMPT",
                "value": instructions["systemPrompt"],
            }
        )

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
                            "image": spec["runtime"].get(
                                "image",
                                "enterprise-agent-runtime:v0.1-dev",
                            ),
                            "imagePullPolicy": "IfNotPresent",
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": 8080,
                                    "protocol": "TCP",
                                }
                            ],
                            "env": env,
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


def build_agent_service(
    name: str,
    namespace: str,
) -> dict[str, Any]:
    """Build a Kubernetes Service for an Agent runtime."""

    labels = {
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/managed-by": "agent-operator",
        "agentos.io/agent": name,
    }

    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {
                "agentos.io/agent": name,
            },
            "ports": [
                {
                    "name": "http",
                    "port": 8080,
                    "targetPort": 8080,
                    "protocol": "TCP",
                }
            ],
        },
    }


def build_workflow_task(
    *,
    workflow_name: str,
    namespace: str,
    task_spec: dict[str, Any],
) -> dict[str, Any]:
    """Build a Task resource for a Workflow task."""

    task_name = task_spec["name"]

    spec: dict[str, Any] = {
        "agentRef": {
            "name": task_spec["agentRef"]["name"],
        },
        "input": {
            "prompt": task_spec["input"]["prompt"],
        },
    }

    if "timeoutSeconds" in task_spec:
        spec["timeoutSeconds"] = task_spec["timeoutSeconds"]

    return {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Task",
        "metadata": {
            "name": f"{workflow_name}-{task_name}",
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/managed-by": "agent-operator",
                "agentos.io/workflow": workflow_name,
                "agentos.io/workflow-task": task_name,
            },
        },
        "spec": spec,
    }
