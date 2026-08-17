from unittest.mock import patch

import kopf
from agent_operator.main import (
    create_agent,
    reconcile_agent_deployment,
    reconcile_agent_status,
    update_agent,
)


@patch(
    "agent_operator.main.get_deployment_ready_replicas",
    return_value=1,
)
def test_reconcile_agent_status_sets_running(
    mock_ready_replicas,
) -> None:
    status_patch = kopf.Patch()

    reconcile_agent_status(
        spec={"replicas": 1},
        name="test-agent",
        namespace="agent-workloads",
        patch=status_patch,
    )

    mock_ready_replicas.assert_called_once()

    assert status_patch.status["readyReplicas"] == 1
    assert status_patch.status["phase"] == "Running"


@patch("agent_operator.main.create_service")
@patch("agent_operator.main.create_deployment")
def test_create_agent_sets_pending_status(
    mock_create_deployment,
    mock_create_service,
) -> None:
    status_patch = kopf.Patch()
    spec = {
        "runtime": {"type": "native"},
        "model": {
            "provider": "mock",
            "name": "mock-model",
        },
        "replicas": 1,
    }

    body = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": "test-agent",
            "namespace": "agent-workloads",
            "uid": "test-uid",
        },
    }

    create_agent(
        name="test-agent",
        namespace="agent-workloads",
        patch=status_patch,
        spec=spec,
        body=body,
    )

    mock_create_deployment.assert_called_once_with(
        name="test-agent",
        namespace="agent-workloads",
        spec=spec,
        owner=body,
    )

    mock_create_service.assert_called_once_with(
        name="test-agent",
        namespace="agent-workloads",
        owner=body,
    )

    assert status_patch.status["phase"] == "Pending"
    assert status_patch.status["readyReplicas"] == 0


@patch("agent_operator.main.reconcile_agent_deployment")
def test_update_agent_reconciles_deployment(
    mock_reconcile_agent_deployment,
) -> None:
    status_patch = kopf.Patch()

    spec = {
        "replicas": 2,
        "runtime": {
            "type": "native",
        },
        "model": {
            "provider": "openai-compatible",
            "name": "kimi-k3",
            "baseUrl": "https://api.moonshot.cn/v1",
            "secretRef": {
                "name": "model-credentials",
                "key": "api-key",
            },
        },
        "identity": {
            "role": "architect",
            "displayName": "Engineering Architect",
        },
        "instructions": {
            "systemPrompt": "You are an engineering architect.",
        },
    }

    update_agent(
        spec=spec,
        name="test-agent",
        namespace="agent-workloads",
        patch=status_patch,
    )

    mock_reconcile_agent_deployment.assert_called_once_with(
        name="test-agent",
        namespace="agent-workloads",
        spec=spec,
    )


@patch("agent_operator.main.client.AppsV1Api")
@patch("agent_operator.main.load_kubernetes_config")
def test_reconcile_agent_deployment_patches_mutable_desired_state(
    mock_load_kubernetes_config,
    mock_apps_api,
) -> None:
    spec = {
        "replicas": 2,
        "runtime": {
            "type": "native",
        },
        "model": {
            "provider": "openai-compatible",
            "name": "kimi-k3",
            "baseUrl": "https://api.moonshot.cn/v1",
            "secretRef": {
                "name": "model-credentials",
                "key": "api-key",
            },
        },
        "identity": {
            "role": "architect",
            "displayName": "Engineering Architect",
        },
        "instructions": {
            "systemPrompt": "You are an engineering architect.",
        },
    }

    apps_api = mock_apps_api.return_value

    reconcile_agent_deployment(
        name="test-agent",
        namespace="agent-workloads",
        spec=spec,
    )

    mock_load_kubernetes_config.assert_called_once()

    apps_api.patch_namespaced_deployment.assert_called_once()

    call = apps_api.patch_namespaced_deployment.call_args

    assert call.kwargs["name"] == "test-agent"
    assert call.kwargs["namespace"] == "agent-workloads"

    body = call.kwargs["body"]

    assert body["spec"]["replicas"] == 2

    template = body["spec"]["template"]
    container = template["spec"]["containers"][0]

    env_by_name = {item["name"]: item for item in container["env"]}

    assert env_by_name["MODEL_PROVIDER"]["value"] == "openai-compatible"
    assert env_by_name["MODEL_NAME"]["value"] == "kimi-k3"
    assert env_by_name["MODEL_BASE_URL"]["value"] == "https://api.moonshot.cn/v1"

    assert env_by_name["MODEL_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "model-credentials",
        "key": "api-key",
    }

    assert env_by_name["AGENT_ROLE"]["value"] == "architect"
    assert env_by_name["AGENT_DISPLAY_NAME"]["value"] == "Engineering Architect"
    assert (
        env_by_name["AGENT_SYSTEM_PROMPT"]["value"]
        == "You are an engineering architect."
    )

    # Immutable Deployment fields must not be part of the update patch.
    assert "selector" not in body["spec"]
