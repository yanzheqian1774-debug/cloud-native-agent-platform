from unittest.mock import Mock, patch

import kopf
import pytest
from agent_operator.workflow_controller import (
    build_skipped_task_status,
    create_workflow,
    ensure_workflow_task,
    get_workflow,
    list_workflow_task_phases,
    list_workflow_task_states,
    patch_workflow_task_statuses,
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


def test_build_skipped_task_status_uses_dependency_failed_reason() -> None:
    status = build_skipped_task_status(
        task_name="reviewer",
        dependencies=("builder", "tester"),
        task_phases={
            "builder": "Failed",
            "tester": "Running",
        },
    )

    assert status == {
        "phase": "Skipped",
        "reason": "DependencyFailed",
        "message": (
            "Task 'reviewer' skipped because required dependencies "
            "cannot succeed: builder (Failed)"
        ),
    }


def test_build_skipped_task_status_uses_dependency_skipped_reason() -> None:
    status = build_skipped_task_status(
        task_name="publish",
        dependencies=("reviewer",),
        task_phases={
            "reviewer": "Skipped",
        },
    )

    assert status == {
        "phase": "Skipped",
        "reason": "DependencySkipped",
        "message": (
            "Task 'publish' skipped because required dependencies "
            "cannot succeed: reviewer (Skipped)"
        ),
    }


@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_patch_workflow_task_statuses_patches_changed_status(
    mock_load_kubernetes_config,
    mock_custom_objects_api,
) -> None:
    api = mock_custom_objects_api.return_value

    changed = patch_workflow_task_statuses(
        workflow_name="engineering-workflow",
        namespace="agent-workloads",
        body={
            "status": {
                "tasks": {},
            }
        },
        task_statuses={
            "reviewer": {
                "phase": "Skipped",
                "reason": "DependencyFailed",
                "message": "blocked",
            }
        },
    )

    assert changed is True

    mock_load_kubernetes_config.assert_called_once()

    api.patch_namespaced_custom_object_status.assert_called_once_with(
        group="agentos.io",
        version="v1alpha1",
        namespace="agent-workloads",
        plural="workflows",
        name="engineering-workflow",
        body={
            "status": {
                "tasks": {
                    "reviewer": {
                        "phase": "Skipped",
                        "reason": "DependencyFailed",
                        "message": "blocked",
                    }
                }
            }
        },
    )


@patch("agent_operator.workflow_controller.client.CustomObjectsApi")
@patch("agent_operator.workflow_controller.load_kubernetes_config")
def test_patch_workflow_task_statuses_is_noop_when_unchanged(
    mock_load_kubernetes_config,
    mock_custom_objects_api,
) -> None:
    status = {
        "phase": "Skipped",
        "reason": "DependencyFailed",
        "message": "blocked",
    }

    changed = patch_workflow_task_statuses(
        workflow_name="engineering-workflow",
        namespace="agent-workloads",
        body={
            "status": {
                "tasks": {
                    "reviewer": status,
                }
            }
        },
        task_statuses={
            "reviewer": status,
        },
    )

    assert changed is False

    mock_load_kubernetes_config.assert_not_called()
    mock_custom_objects_api.assert_not_called()


@patch("agent_operator.workflow_controller.patch_workflow_task_statuses")
@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_skips_failed_descendant_without_creating_task(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
    mock_patch_workflow_task_statuses,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "architect": {
            "phase": "Succeeded",
            "result": "architecture",
        },
        "builder": {
            "phase": "Failed",
            "result": None,
        },
        "tester": {
            "phase": "Running",
            "result": None,
        },
    }

    body = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "engineering-workflow",
            "namespace": "agent-workloads",
            "uid": "workflow-uid",
        },
        "status": {
            "phase": "Running",
            "taskCount": 4,
        },
    }

    spec = {
        "tasks": [
            workflow_task("architect"),
            workflow_task("builder", ["architect"]),
            workflow_task("tester", ["architect"]),
            workflow_task("reviewer", ["builder", "tester"]),
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="engineering-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 0

    mock_ensure_workflow_task.assert_not_called()

    mock_patch_workflow_task_statuses.assert_called_once()

    statuses = mock_patch_workflow_task_statuses.call_args.kwargs["task_statuses"]

    assert statuses["reviewer"]["phase"] == "Skipped"
    assert statuses["reviewer"]["reason"] == "DependencyFailed"


@patch("agent_operator.workflow_controller.patch_workflow_task_statuses")
@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_propagates_skips_transitively(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
    mock_patch_workflow_task_statuses,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "architect": {
            "phase": "Failed",
            "result": None,
        },
    }

    body = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "engineering-workflow",
            "namespace": "agent-workloads",
            "uid": "workflow-uid",
        },
    }

    spec = {
        "tasks": [
            workflow_task("architect"),
            workflow_task("builder", ["architect"]),
            workflow_task("reviewer", ["builder"]),
            workflow_task("publish", ["reviewer"]),
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="engineering-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 0
    mock_ensure_workflow_task.assert_not_called()

    statuses = mock_patch_workflow_task_statuses.call_args.kwargs["task_statuses"]

    assert statuses["builder"]["phase"] == "Skipped"
    assert statuses["builder"]["reason"] == "DependencyFailed"

    assert statuses["reviewer"]["phase"] == "Skipped"
    assert statuses["reviewer"]["reason"] == "DependencySkipped"

    assert statuses["publish"]["phase"] == "Skipped"
    assert statuses["publish"]["reason"] == "DependencySkipped"


@patch("agent_operator.workflow_controller.patch_workflow_task_statuses")
@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_preserves_independent_sibling(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
    mock_patch_workflow_task_statuses,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "root": {
            "phase": "Succeeded",
            "result": None,
        },
        "failed-branch": {
            "phase": "Failed",
            "result": None,
        },
    }

    mock_ensure_workflow_task.return_value = True

    body = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "parallel-workflow",
            "namespace": "agent-workloads",
            "uid": "workflow-uid",
        },
    }

    spec = {
        "tasks": [
            workflow_task("root"),
            workflow_task("failed-branch", ["root"]),
            workflow_task("independent-branch", ["root"]),
            workflow_task("failed-descendant", ["failed-branch"]),
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="parallel-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 1

    created_task = mock_ensure_workflow_task.call_args.kwargs["task_spec"]["name"]

    assert created_task == "independent-branch"

    statuses = mock_patch_workflow_task_statuses.call_args.kwargs["task_statuses"]

    assert statuses["failed-descendant"]["phase"] == "Skipped"


@patch("agent_operator.workflow_controller.patch_workflow_task_statuses")
@patch("agent_operator.workflow_controller.ensure_workflow_task")
@patch("agent_operator.workflow_controller.list_workflow_task_states")
def test_reconcile_workflow_respects_existing_skipped_status(
    mock_list_workflow_task_states,
    mock_ensure_workflow_task,
    mock_patch_workflow_task_statuses,
) -> None:
    mock_list_workflow_task_states.return_value = {
        "root": {
            "phase": "Failed",
            "result": None,
        },
    }

    body = {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": "engineering-workflow",
            "namespace": "agent-workloads",
            "uid": "workflow-uid",
        },
        "status": {
            "tasks": {
                "child": {
                    "phase": "Skipped",
                    "reason": "DependencyFailed",
                    "message": "already skipped",
                }
            }
        },
    }

    spec = {
        "tasks": [
            workflow_task("root"),
            workflow_task("child", ["root"]),
            workflow_task("grandchild", ["child"]),
        ]
    }

    created = reconcile_workflow(
        spec=spec,
        name="engineering-workflow",
        namespace="agent-workloads",
        body=body,
    )

    assert created == 0
    mock_ensure_workflow_task.assert_not_called()

    statuses = mock_patch_workflow_task_statuses.call_args.kwargs["task_statuses"]

    assert "child" not in statuses
    assert statuses["grandchild"]["phase"] == "Skipped"
    assert statuses["grandchild"]["reason"] == "DependencySkipped"


@patch("agent_operator.workflow_controller.reconcile_workflow")
@patch("agent_operator.workflow_controller.get_workflow")
def test_reconcile_workflow_for_task_reconciles_failed_phase(
    mock_get_workflow,
    mock_reconcile_workflow,
) -> None:
    workflow = {
        "metadata": {
            "name": "engineering-workflow",
        },
        "spec": {
            "tasks": [
                workflow_task("builder"),
            ]
        },
    }

    mock_get_workflow.return_value = workflow

    reconcile_workflow_for_task(
        body={
            "metadata": {
                "labels": {
                    "agentos.io/workflow": "engineering-workflow",
                }
            }
        },
        namespace="agent-workloads",
        new_phase="Failed",
    )

    mock_get_workflow.assert_called_once_with(
        workflow_name="engineering-workflow",
        namespace="agent-workloads",
    )

    mock_reconcile_workflow.assert_called_once_with(
        spec=workflow["spec"],
        name="engineering-workflow",
        namespace="agent-workloads",
        body=workflow,
    )


@patch("agent_operator.workflow_controller.reconcile_workflow")
@patch("agent_operator.workflow_controller.get_workflow")
def test_reconcile_workflow_for_task_reconciles_timed_out_phase(
    mock_get_workflow,
    mock_reconcile_workflow,
) -> None:
    workflow = {
        "metadata": {
            "name": "engineering-workflow",
        },
        "spec": {
            "tasks": [
                workflow_task("tester"),
            ]
        },
    }

    mock_get_workflow.return_value = workflow

    reconcile_workflow_for_task(
        body={
            "metadata": {
                "labels": {
                    "agentos.io/workflow": "engineering-workflow",
                }
            }
        },
        namespace="agent-workloads",
        new_phase="TimedOut",
    )

    mock_get_workflow.assert_called_once()

    mock_reconcile_workflow.assert_called_once()


@patch("agent_operator.workflow_controller.reconcile_workflow")
@patch("agent_operator.workflow_controller.get_workflow")
def test_reconcile_workflow_for_task_ignores_running_phase(
    mock_get_workflow,
    mock_reconcile_workflow,
) -> None:
    reconcile_workflow_for_task(
        body={
            "metadata": {
                "labels": {
                    "agentos.io/workflow": "engineering-workflow",
                }
            }
        },
        namespace="agent-workloads",
        new_phase="Running",
    )

    mock_get_workflow.assert_not_called()
    mock_reconcile_workflow.assert_not_called()
