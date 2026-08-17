from unittest.mock import Mock, patch

import kopf
import pytest
from agent_operator.workflow_controller import (
    create_workflow,
    ensure_workflow_task,
    get_workflow,
    list_workflow_task_phases,
    list_workflow_task_states,
    reconcile_workflow,
    reconcile_workflow_for_task,
    resolve_task_prompt,
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


@patch("agent_operator.workflow_controller.list_workflow_task_states")
@patch("agent_operator.workflow_controller.ensure_workflow_task")
def test_create_workflow_creates_only_root_tasks(
    mock_ensure_workflow_task,
    mock_list_workflow_task_states,
) -> None:
    mock_list_workflow_task_states.return_value = {}

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

    mock_ensure_workflow_task.assert_called_once_with(
        workflow_name="research-workflow",
        namespace="agent-workloads",
        task_spec=spec["tasks"][0],
        owner=body,
    )

    assert status_patch.status["phase"] == "Running"
    assert status_patch.status["taskCount"] == 4


@patch("agent_operator.workflow_controller.list_workflow_task_states")
@patch("agent_operator.workflow_controller.ensure_workflow_task")
def test_create_workflow_creates_multiple_root_tasks(
    mock_ensure_workflow_task,
    mock_list_workflow_task_states,
) -> None:
    mock_list_workflow_task_states.return_value = {}
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


@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_list_workflow_task_phases_returns_phases_by_workflow_task_name(
    mock_load_kubernetes_config,
    mock_custom_objects_api,
) -> None:
    api = mock_custom_objects_api.return_value

    api.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "labels": {
                        "agentos.io/workflow": "research-workflow",
                        "agentos.io/workflow-task": "research",
                    }
                },
                "status": {
                    "phase": "Succeeded",
                },
            },
            {
                "metadata": {
                    "labels": {
                        "agentos.io/workflow": "research-workflow",
                        "agentos.io/workflow-task": "market",
                    }
                },
                "status": {
                    "phase": "Running",
                },
            },
        ]
    }

    phases = list_workflow_task_phases(
        workflow_name="research-workflow",
        namespace="agent-workloads",
    )

    assert phases == {
        "research": "Succeeded",
        "market": "Running",
    }

    api.list_namespaced_custom_object.assert_called_once_with(
        group="agentos.io",
        version="v1alpha1",
        namespace="agent-workloads",
        plural="tasks",
        label_selector="agentos.io/workflow=research-workflow",
    )


@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_list_workflow_task_phases_treats_existing_task_without_status_as_pending(
    mock_load_kubernetes_config,
    mock_custom_objects_api,
) -> None:
    api = mock_custom_objects_api.return_value

    api.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "labels": {
                        "agentos.io/workflow": "research-workflow",
                        "agentos.io/workflow-task": "research",
                    }
                }
            }
        ]
    }

    phases = list_workflow_task_phases(
        workflow_name="research-workflow",
        namespace="agent-workloads",
    )

    assert phases == {
        "research": "Pending",
    }


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_creates_tasks_after_dependencies_succeed(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "research": {
            "phase": "Succeeded",
            "result": None,
        },
    }

    mock_ensure_workflow_task.return_value = True

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

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 2

    created_task_names = {
        call.kwargs["task_spec"]["name"]
        for call in mock_ensure_workflow_task.call_args_list
    }

    assert created_task_names == {
        "market",
        "technology",
    }


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_does_not_wait_for_running_sibling(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    """A running sibling must not block another ready sibling."""

    mock_list_workflow_task_states.return_value = {
        "research": {
            "phase": "Succeeded",
            "result": None,
        },
        "market": {
            "phase": "Running",
            "result": None,
        },
    }

    mock_ensure_workflow_task.return_value = True

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

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 1

    mock_ensure_workflow_task.assert_called_once()

    created_task_spec = mock_ensure_workflow_task.call_args.kwargs["task_spec"]

    assert created_task_spec["name"] == "technology"


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_waits_for_all_dependencies(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "research": {
            "phase": "Succeeded",
            "result": None,
        },
        "market": {
            "phase": "Succeeded",
            "result": None,
        },
        "technology": {
            "phase": "Running",
            "result": None,
        },
    }

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

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 0
    mock_ensure_workflow_task.assert_not_called()


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_creates_fan_in_task_when_all_dependencies_succeed(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    """A fan-in task becomes runnable after every dependency succeeds."""

    mock_list_workflow_task_states.return_value = {
        "research": {
            "phase": "Succeeded",
            "result": None,
        },
        "market": {
            "phase": "Succeeded",
            "result": None,
        },
        "technology": {
            "phase": "Succeeded",
            "result": None,
        },
    }

    mock_ensure_workflow_task.return_value = True

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

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 1

    mock_ensure_workflow_task.assert_called_once()

    created_task_spec = mock_ensure_workflow_task.call_args.kwargs["task_spec"]

    assert created_task_spec["name"] == "report"


@patch("agent_operator.workflow_controller.reconcile_workflow")
@patch("agent_operator.workflow_controller.get_workflow")
def test_reconcile_workflow_for_task_reconciles_after_success(
    mock_get_workflow,
    mock_reconcile_workflow,
) -> None:
    workflow = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "research-workflow",
            "namespace": "agent-workloads",
            "uid": "workflow-uid",
        },
        "spec": {
            "tasks": [
                workflow_task("research"),
                workflow_task("market", ["research"]),
            ]
        },
    }

    mock_get_workflow.return_value = workflow

    task_body = {
        "metadata": {
            "labels": {
                "agentos.io/workflow": "research-workflow",
                "agentos.io/workflow-task": "research",
            }
        }
    }

    reconcile_workflow_for_task(
        body=task_body,
        namespace="agent-workloads",
        new_phase="Succeeded",
    )

    mock_get_workflow.assert_called_once_with(
        workflow_name="research-workflow",
        namespace="agent-workloads",
    )

    mock_reconcile_workflow.assert_called_once_with(
        spec=workflow["spec"],
        name="research-workflow",
        namespace="agent-workloads",
        body=workflow,
    )


@patch("agent_operator.workflow_controller.get_workflow")
def test_reconcile_workflow_for_task_ignores_non_success_phase(
    mock_get_workflow,
) -> None:
    reconcile_workflow_for_task(
        body={
            "metadata": {
                "labels": {
                    "agentos.io/workflow": "research-workflow",
                }
            }
        },
        namespace="agent-workloads",
        new_phase="Running",
    )

    mock_get_workflow.assert_not_called()


@patch("agent_operator.workflow_controller.get_workflow")
def test_reconcile_workflow_for_task_ignores_standalone_task(
    mock_get_workflow,
) -> None:
    reconcile_workflow_for_task(
        body={"metadata": {"labels": {}}},
        namespace="agent-workloads",
        new_phase="Succeeded",
    )

    mock_get_workflow.assert_not_called()


@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_get_workflow_reads_workflow_resource(
    mock_load_kubernetes_config,
    mock_custom_objects_api,
) -> None:
    api = mock_custom_objects_api.return_value

    expected = {
        "metadata": {
            "name": "research-workflow",
        },
        "spec": {
            "tasks": [],
        },
    }

    api.get_namespaced_custom_object.return_value = expected

    result = get_workflow(
        workflow_name="research-workflow",
        namespace="agent-workloads",
    )

    assert result == expected

    api.get_namespaced_custom_object.assert_called_once_with(
        group="agentos.io",
        version="v1alpha1",
        namespace="agent-workloads",
        plural="workflows",
        name="research-workflow",
    )


def test_resolve_task_prompt_returns_original_prompt_without_sources() -> None:
    task_spec = {
        "input": {
            "prompt": "Analyze market.",
        }
    }

    result = resolve_task_prompt(
        task_spec=task_spec,
        task_results={},
    )

    assert result == "Analyze market."


def test_resolve_task_prompt_preserves_source_order() -> None:
    task_spec = {
        "input": {
            "prompt": "Write report.",
            "from": [
                {"task": "market"},
                {"task": "technology"},
            ],
        }
    }

    result = resolve_task_prompt(
        task_spec=task_spec,
        task_results={
            "technology": "Technology result",
            "market": "Market result",
        },
    )

    assert result.index("[market]") < result.index("[technology]")


def test_list_workflow_task_states_returns_phase_and_result() -> None:
    response = {
        "items": [
            {
                "metadata": {
                    "labels": {
                        "agentos.io/workflow-task": "research",
                    }
                },
                "status": {
                    "phase": "Succeeded",
                    "result": "Research result",
                },
            },
            {
                "metadata": {
                    "labels": {
                        "agentos.io/workflow-task": "market",
                    }
                },
                "status": {
                    "phase": "Running",
                },
            },
        ]
    }

    with (
        patch("agent_operator.workflow_controller.load_kubernetes_config"),
        patch(
            "agent_operator.workflow_controller.client.CustomObjectsApi"
        ) as api_class,
    ):
        api = api_class.return_value
        api.list_namespaced_custom_object.return_value = response

        states = list_workflow_task_states(
            workflow_name="research-workflow",
            namespace="agent-workloads",
        )

    assert states == {
        "research": {
            "phase": "Succeeded",
            "result": "Research result",
        },
        "market": {
            "phase": "Running",
            "result": None,
        },
    }

    api.list_namespaced_custom_object.assert_called_once_with(
        group="agentos.io",
        version="v1alpha1",
        namespace="agent-workloads",
        plural="tasks",
        label_selector="agentos.io/workflow=research-workflow",
    )


def test_list_workflow_task_states_defaults_missing_status_to_pending() -> None:
    response = {
        "items": [
            {
                "metadata": {
                    "labels": {
                        "agentos.io/workflow-task": "research",
                    }
                },
            }
        ]
    }

    with (
        patch("agent_operator.workflow_controller.load_kubernetes_config"),
        patch(
            "agent_operator.workflow_controller.client.CustomObjectsApi"
        ) as api_class,
    ):
        api = api_class.return_value
        api.list_namespaced_custom_object.return_value = response

        states = list_workflow_task_states(
            workflow_name="research-workflow",
            namespace="agent-workloads",
        )

    assert states == {
        "research": {
            "phase": "Pending",
            "result": None,
        }
    }


def test_list_workflow_task_phases_extracts_phases_from_states() -> None:
    with patch(
        "agent_operator.workflow_controller.list_workflow_task_states"
    ) as list_states:
        list_states.return_value = {
            "research": {
                "phase": "Succeeded",
                "result": "Research result",
            },
            "market": {
                "phase": "Running",
                "result": None,
            },
        }

        phases = list_workflow_task_phases(
            workflow_name="research-workflow",
            namespace="agent-workloads",
        )

    assert phases == {
        "research": "Succeeded",
        "market": "Running",
    }

    list_states.assert_called_once_with(
        workflow_name="research-workflow",
        namespace="agent-workloads",
    )


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_passes_upstream_result_to_downstream_task(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "research": {
            "phase": "Succeeded",
            "result": "Research result",
        },
    }

    mock_ensure_workflow_task.return_value = True

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
            {
                "name": "research",
                "agentRef": {
                    "name": "research-agent",
                },
                "input": {
                    "prompt": "Run research.",
                },
            },
            {
                "name": "market",
                "agentRef": {
                    "name": "market-agent",
                },
                "dependsOn": [
                    "research",
                ],
                "input": {
                    "prompt": "Analyze market.",
                    "from": [
                        {
                            "task": "research",
                        }
                    ],
                },
            },
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 1

    mock_ensure_workflow_task.assert_called_once()

    created_task_spec = mock_ensure_workflow_task.call_args.kwargs["task_spec"]

    assert created_task_spec["name"] == "market"

    assert created_task_spec["input"]["prompt"] == (
        "Analyze market.\n\nPrevious task results:\n\n[research]\nResearch result"
    )

    assert "from" not in (created_task_spec["input"])


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_waits_when_required_result_is_missing(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "research": {
            "phase": "Succeeded",
            "result": None,
        },
    }

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
            {
                "name": "research",
                "agentRef": {
                    "name": "research-agent",
                },
                "input": {
                    "prompt": "Run research.",
                },
            },
            {
                "name": "market",
                "agentRef": {
                    "name": "market-agent",
                },
                "dependsOn": [
                    "research",
                ],
                "input": {
                    "prompt": "Analyze market.",
                    "from": [
                        {
                            "task": "research",
                        }
                    ],
                },
            },
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 0

    mock_ensure_workflow_task.assert_not_called()


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_passes_multiple_results_in_declared_order(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "market": {
            "phase": "Succeeded",
            "result": "Market result",
        },
        "technology": {
            "phase": "Succeeded",
            "result": "Technology result",
        },
    }

    mock_ensure_workflow_task.return_value = True

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
            {
                "name": "market",
                "agentRef": {
                    "name": "market-agent",
                },
                "input": {
                    "prompt": "Market.",
                },
            },
            {
                "name": "technology",
                "agentRef": {
                    "name": "technology-agent",
                },
                "input": {
                    "prompt": "Technology.",
                },
            },
            {
                "name": "report",
                "agentRef": {
                    "name": "report-agent",
                },
                "dependsOn": [
                    "market",
                    "technology",
                ],
                "input": {
                    "prompt": "Write final report.",
                    "from": [
                        {
                            "task": "market",
                        },
                        {
                            "task": "technology",
                        },
                    ],
                },
            },
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 1

    mock_ensure_workflow_task.assert_called_once()

    created_task_spec = mock_ensure_workflow_task.call_args.kwargs["task_spec"]

    prompt = created_task_spec["input"]["prompt"]

    assert "[market]" in prompt
    assert "Market result" in prompt

    assert "[technology]" in prompt
    assert "Technology result" in prompt

    assert prompt.index("[market]") < prompt.index("[technology]")

    assert "from" not in (created_task_spec["input"])


@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_preserves_prompt_without_result_sources(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
) -> None:
    mock_list_workflow_task_states.return_value = {}

    mock_ensure_workflow_task.return_value = True

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
            {
                "name": "research",
                "agentRef": {
                    "name": "research-agent",
                },
                "input": {
                    "prompt": "Run research.",
                },
            },
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="research-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 1

    created_task_spec = mock_ensure_workflow_task.call_args.kwargs["task_spec"]

    assert created_task_spec["input"]["prompt"] == "Run research."

    assert "from" not in (created_task_spec["input"])
