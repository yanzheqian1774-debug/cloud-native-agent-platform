from unittest.mock import patch

import kopf
from agent_operator.main import create_agent, reconcile_agent_status, update_agent


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


@patch("agent_operator.main.create_deployment")
def test_create_agent_sets_pending_status(
    mock_create_deployment,
) -> None:
    status_patch = kopf.Patch()

    create_agent(
        spec={
            "runtime": {"type": "native"},
            "model": {
                "provider": "mock",
                "name": "mock-model",
            },
            "replicas": 1,
        },
        body={
            "apiVersion": "agentos.io/v1alpha1",
            "kind": "Agent",
            "metadata": {
                "name": "test-agent",
                "namespace": "agent-workloads",
                "uid": "test-uid",
            },
        },
        name="test-agent",
        namespace="agent-workloads",
        patch=status_patch,
    )

    mock_create_deployment.assert_called_once()

    assert status_patch.status["phase"] == "Pending"
    assert status_patch.status["readyReplicas"] == 0


@patch("agent_operator.main.update_deployment_replicas")
def test_update_agent_reconciles_replicas(
    mock_update_deployment_replicas,
) -> None:
    status_patch = kopf.Patch()

    update_agent(
        spec={
            "replicas": 2,
            "runtime": {"type": "native"},
            "model": {
                "provider": "mock",
                "name": "mock-model",
            },
        },
        name="test-agent",
        namespace="agent-workloads",
        patch=status_patch,
    )

    mock_update_deployment_replicas.assert_called_once_with(
        name="test-agent",
        namespace="agent-workloads",
        replicas=2,
    )
