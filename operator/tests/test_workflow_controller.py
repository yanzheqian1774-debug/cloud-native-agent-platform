from unittest.mock import Mock, patch

import kopf
import pytest
from agent_operator.workflow_controller import (
    create_workflow,
    ensure_workflow_task,
)
from kubernetes import client


def workflow_task(
    name: str,
    depends_on: list[str] | None = None,
) -> dict:
    task = {
        "name": name,
        "agentRef": {
            "name": f"{name}-agent",
        },
        "input": {
            "prompt": f"run {name}",
        },
    }

    if depends_on is not None:
        task["dependsOn"] = depends_on

    return task


@patch("agent_operator.workflow_controller.ensure_workflow_task")
def test_create_workflow_creates_only_root_tasks(
    mock_ensure_workflow_task,
) -> None:
    status_patch = kopf.Patch()

    body = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "research-workflow",
            "namespace": "agent-workloads",
            "uid": "workflow-uid",
        },
    }

    spec = {
        "tasks": [
            workflow_task("research"),
            workflow_task("market", ["research"]),
            workflow_task("technology", ["research"]),
            workflow_task("report", ["market", "technology"]),
        ]
    }

    create_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
        patch=status_patch,
    )

    assert mock_ensure_workflow_task.call_count == 1

    call = mock_ensure_workflow_task.call_args.kwargs

    assert call["workflow_name"] == "research-workflow"
    assert call["namespace"] == "agent-workloads"
    assert call["task_spec"]["name"] == "research"
    assert call["owner"] == body

    assert status_patch.status["phase"] == "Running"
    assert status_patch.status["taskCount"] == 4


@patch("agent_operator.workflow_controller.ensure_workflow_task")
def test_create_workflow_creates_multiple_root_tasks(
    mock_ensure_workflow_task,
) -> None:
    status_patch = kopf.Patch()

    create_workflow(
        spec={
            "tasks": [
                workflow_task("market"),
                workflow_task("technology"),
                workflow_task("report", ["market", "technology"]),
            ]
        },
        name="parallel-workflow",
        namespace="agent-workloads",
        body={
            "apiVersion": "agentos.io/v1alpha1",
            "kind": "Workflow",
            "metadata": {
                "name": "parallel-workflow",
                "namespace": "agent-workloads",
                "uid": "workflow-uid",
            },
        },
        patch=status_patch,
    )

    assert mock_ensure_workflow_task.call_count == 2

    created_names = {
        call.kwargs["task_spec"]["name"]
        for call in mock_ensure_workflow_task.call_args_list
    }

    assert created_names == {
        "market",
        "technology",
    }


@patch("agent_operator.workflow_controller.ensure_workflow_task")
def test_create_workflow_rejects_invalid_dag(
    mock_ensure_workflow_task,
) -> None:
    status_patch = kopf.Patch()

    with pytest.raises(
        kopf.PermanentError,
        match="workflow contains a dependency cycle",
    ):
        create_workflow(
            spec={
                "tasks": [
                    workflow_task("a", ["b"]),
                    workflow_task("b", ["a"]),
                ]
            },
            name="invalid-workflow",
            namespace="agent-workloads",
            body={
                "metadata": {
                    "name": "invalid-workflow",
                    "namespace": "agent-workloads",
                    "uid": "workflow-uid",
                }
            },
            patch=status_patch,
        )

    mock_ensure_workflow_task.assert_not_called()

    assert status_patch.status["phase"] == "Failed"


@patch("agent_operator.workflow_controller.kopf.adopt")
@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_ensure_workflow_task_creates_task(
    mock_load_config,
    mock_custom_objects_api,
    mock_adopt,
) -> None:
    api = Mock()
    mock_custom_objects_api.return_value = api

    created = ensure_workflow_task(
        workflow_name="research-workflow",
        namespace="agent-workloads",
        task_spec=workflow_task("research"),
        owner={
            "apiVersion": "agentos.io/v1alpha1",
            "kind": "Workflow",
            "metadata": {
                "name": "research-workflow",
                "namespace": "agent-workloads",
                "uid": "workflow-uid",
            },
        },
    )

    assert created is True

    mock_load_config.assert_called_once()
    mock_adopt.assert_called_once()

    api.create_namespaced_custom_object.assert_called_once()

    call = api.create_namespaced_custom_object.call_args.kwargs

    assert call["group"] == "agentos.io"
    assert call["version"] == "v1alpha1"
    assert call["namespace"] == "agent-workloads"
    assert call["plural"] == "tasks"
    assert call["body"]["metadata"]["name"] == "research-workflow-research"


@patch("agent_operator.workflow_controller.kopf.adopt")
@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_ensure_workflow_task_ignores_already_existing_task(
    mock_load_config,
    mock_custom_objects_api,
    mock_adopt,
) -> None:
    api = Mock()
    mock_custom_objects_api.return_value = api

    api.create_namespaced_custom_object.side_effect = client.ApiException(
        status=409,
        reason="AlreadyExists",
    )

    created = ensure_workflow_task(
        workflow_name="research-workflow",
        namespace="agent-workloads",
        task_spec=workflow_task("research"),
        owner={
            "apiVersion": "agentos.io/v1alpha1",
            "kind": "Workflow",
            "metadata": {
                "name": "research-workflow",
                "namespace": "agent-workloads",
                "uid": "workflow-uid",
            },
        },
    )

    assert created is False

    mock_load_config.assert_called_once()
    mock_adopt.assert_called_once()

    api.create_namespaced_custom_object.assert_called_once()


@patch("agent_operator.workflow_controller.kopf.adopt")
@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_ensure_workflow_task_reraises_unexpected_api_error(
    mock_load_config,
    mock_custom_objects_api,
    mock_adopt,
) -> None:
    api = Mock()
    mock_custom_objects_api.return_value = api

    api.create_namespaced_custom_object.side_effect = client.ApiException(
        status=500,
        reason="InternalServerError",
    )

    with pytest.raises(client.ApiException):
        ensure_workflow_task(
            workflow_name="research-workflow",
            namespace="agent-workloads",
            task_spec=workflow_task("research"),
            owner={
                "apiVersion": "agentos.io/v1alpha1",
                "kind": "Workflow",
                "metadata": {
                    "name": "research-workflow",
                    "namespace": "agent-workloads",
                    "uid": "workflow-uid",
                },
            },
        )

    mock_load_config.assert_called_once()
    mock_adopt.assert_called_once()
