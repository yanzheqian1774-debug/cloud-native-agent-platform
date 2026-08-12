from unittest.mock import Mock, patch

import httpx
import kopf
from agent_operator.task_controller import (
    build_agent_service_url,
    create_task,
    invoke_agent,
)


def test_build_agent_service_url() -> None:
    url = build_agent_service_url(
        agent_name="researcher-agent",
        namespace="agent-workloads",
    )

    assert url == (
        "http://researcher-agent.agent-workloads.svc.cluster.local:8080/v1/invoke"
    )


@patch("agent_operator.task_controller.httpx.post")
def test_invoke_agent(mock_post) -> None:
    response = Mock()
    response.json.return_value = {
        "output": "task result",
    }

    mock_post.return_value = response

    result = invoke_agent(
        agent_name="researcher-agent",
        namespace="agent-workloads",
        prompt="hello",
        timeout_seconds=30,
    )

    assert result == "task result"

    response.raise_for_status.assert_called_once()

    mock_post.assert_called_once_with(
        ("http://researcher-agent.agent-workloads.svc.cluster.local:8080/v1/invoke"),
        json={
            "input": "hello",
        },
        timeout=30.0,
    )


@patch("agent_operator.task_controller.invoke_agent")
def test_create_task_sets_succeeded_status(
    mock_invoke_agent,
) -> None:
    mock_invoke_agent.return_value = "research result"

    status_patch = kopf.Patch()

    create_task(
        spec={
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "research this topic",
            },
            "timeoutSeconds": 60,
        },
        namespace="agent-workloads",
        patch=status_patch,
    )

    assert status_patch.status["phase"] == "Succeeded"
    assert status_patch.status["result"] == "research result"
    assert status_patch.status["startedAt"]
    assert status_patch.status["completedAt"]

    mock_invoke_agent.assert_called_once_with(
        agent_name="researcher-agent",
        namespace="agent-workloads",
        prompt="research this topic",
        timeout_seconds=60,
    )


@patch("agent_operator.task_controller.invoke_agent")
def test_create_task_sets_failed_status(
    mock_invoke_agent,
) -> None:
    mock_invoke_agent.side_effect = httpx.ConnectError("runtime unavailable")

    status_patch = kopf.Patch()

    create_task(
        spec={
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "research this topic",
            },
        },
        namespace="agent-workloads",
        patch=status_patch,
    )

    assert status_patch.status["phase"] == "Failed"
    assert "runtime unavailable" in status_patch.status["message"]
    assert status_patch.status["startedAt"]
    assert status_patch.status["completedAt"]
