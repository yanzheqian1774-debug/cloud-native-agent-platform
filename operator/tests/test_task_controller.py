from unittest.mock import Mock, patch

import httpx
import kopf
import pytest
from agent_operator.errors import TaskExecutionError
from agent_operator.retry import RetryExhaustedError
from agent_operator.task_controller import (
    build_agent_service_url,
    create_task,
    invoke_agent,
)


@pytest.fixture(autouse=True)
def mock_task_status_writer():
    with patch(
        "agent_operator.task_controller.patch_task_status"
    ) as mock_status_writer:
        yield mock_status_writer


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
        name="test-task",
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
    assert status_patch.status["attempts"] == 1
    assert status_patch.status["reason"] is None
    assert status_patch.status["message"] is None
    assert status_patch.status["retryable"] is None

    mock_invoke_agent.assert_called_once()

    call_kwargs = mock_invoke_agent.call_args.kwargs

    assert call_kwargs["agent_name"] == "researcher-agent"
    assert call_kwargs["namespace"] == "agent-workloads"
    assert call_kwargs["prompt"] == "research this topic"

    assert 0 < call_kwargs["timeout_seconds"] <= 60


@patch("agent_operator.task_controller.invoke_agent")
def test_create_task_sets_failed_status(
    mock_invoke_agent,
) -> None:
    mock_invoke_agent.side_effect = TaskExecutionError(
        reason="AuthenticationError",
        message="unauthorized",
        retryable=False,
    )

    status_patch = kopf.Patch()

    create_task(
        name="test-task",
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
    assert status_patch.status["reason"] == "AuthenticationError"
    assert status_patch.status["retryable"] is False
    assert status_patch.status["result"] is None
    assert status_patch.status["attempts"] == 1


@patch("agent_operator.task_controller.httpx.post")
def test_invoke_agent_classifies_http_error(mock_post) -> None:
    request = httpx.Request(
        "POST",
        "http://agent/v1/invoke",
    )

    mock_post.side_effect = httpx.ConnectError(
        "runtime unavailable",
        request=request,
    )

    try:
        invoke_agent(
            agent_name="researcher-agent",
            namespace="agent-workloads",
            prompt="hello",
            timeout_seconds=30,
        )
    except TaskExecutionError as exc:
        assert exc.reason == "NetworkError"
        assert exc.retryable is True
    else:
        raise AssertionError("TaskExecutionError was not raised")


@patch("agent_operator.task_controller.httpx.post")
def test_invoke_agent_rejects_invalid_response(mock_post) -> None:
    response = Mock()
    response.json.return_value = {
        "unexpected": "value",
    }

    mock_post.return_value = response

    try:
        invoke_agent(
            agent_name="researcher-agent",
            namespace="agent-workloads",
            prompt="hello",
            timeout_seconds=30,
        )
    except TaskExecutionError as exc:
        assert exc.reason == "InvalidResponse"
        assert exc.retryable is False
    else:
        raise AssertionError("TaskExecutionError was not raised")


@patch("agent_operator.retry.time.sleep")
@patch("agent_operator.task_controller.invoke_agent")
def test_create_task_retries_retryable_error_then_succeeds(
    mock_invoke_agent,
    mock_sleep,
) -> None:
    mock_invoke_agent.side_effect = [
        TaskExecutionError(
            reason="UpstreamUnavailable",
            message="temporarily unavailable",
            retryable=True,
        ),
        "TASK_OK",
    ]

    status_patch = kopf.Patch()

    create_task(
        name="test-task",
        spec={
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "hello",
            },
        },
        namespace="agent-workloads",
        patch=status_patch,
    )

    assert status_patch.status["phase"] == "Succeeded"
    assert status_patch.status["result"] == "TASK_OK"
    assert status_patch.status["attempts"] == 2
    assert status_patch.status["reason"] is None
    assert status_patch.status["message"] is None
    assert status_patch.status["retryable"] is None
    assert mock_invoke_agent.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("agent_operator.retry.time.sleep")
@patch("agent_operator.task_controller.invoke_agent")
def test_create_task_fails_after_retry_exhaustion(
    mock_invoke_agent,
    mock_sleep,
) -> None:
    mock_invoke_agent.side_effect = TaskExecutionError(
        reason="UpstreamUnavailable",
        message="temporarily unavailable",
        retryable=True,
    )

    status_patch = kopf.Patch()

    create_task(
        name="test-task",
        spec={
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "hello",
            },
        },
        namespace="agent-workloads",
        patch=status_patch,
    )

    assert status_patch.status["phase"] == "Failed"
    assert status_patch.status["reason"] == "UpstreamUnavailable"
    assert status_patch.status["retryable"] is True
    assert status_patch.status["result"] is None
    assert status_patch.status["attempts"] == 3
    assert mock_invoke_agent.call_count == 3
    assert mock_sleep.call_count == 2


@patch("agent_operator.task_controller.execute_with_retry")
def test_create_task_sets_timed_out_status(
    mock_execute_with_retry,
) -> None:
    mock_execute_with_retry.side_effect = RetryExhaustedError(
        error=TaskExecutionError(
            reason="ExecutionTimeout",
            message="task execution deadline exceeded",
            retryable=False,
        ),
        attempts=1,
    )

    status_patch = kopf.Patch()

    create_task(
        name="test-task",
        spec={
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "hello",
            },
            "timeoutSeconds": 30,
        },
        namespace="agent-workloads",
        patch=status_patch,
    )

    assert status_patch.status["phase"] == "TimedOut"
    assert status_patch.status["reason"] == "ExecutionTimeout"
    assert status_patch.status["retryable"] is False
    assert status_patch.status["result"] is None
    assert status_patch.status["attempts"] == 1
    assert status_patch.status["startedAt"]
    assert status_patch.status["completedAt"]


@patch("agent_operator.task_controller.execute_with_retry")
def test_create_task_passes_execution_timeout_to_retry(
    mock_execute_with_retry,
) -> None:
    mock_execute_with_retry.return_value = ("TASK_OK", 1)

    status_patch = kopf.Patch()

    create_task(
        name="test-task",
        spec={
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "hello",
            },
            "timeoutSeconds": 45,
        },
        namespace="agent-workloads",
        patch=status_patch,
    )

    assert mock_execute_with_retry.call_args.kwargs["timeout_seconds"] == 45.0


def test_create_task_persists_running_status_before_execution(
    mock_task_status_writer,
) -> None:
    status_patch = kopf.Patch()
    call_order = []

    mock_task_status_writer.side_effect = lambda **_: call_order.append("running")

    def invoke_side_effect(**_):
        call_order.append("invoke")
        return "task result"

    with patch(
        "agent_operator.task_controller.invoke_agent",
        side_effect=invoke_side_effect,
    ):
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
            name="running-task",
            namespace="agent-workloads",
            patch=status_patch,
        )

    assert call_order == [
        "running",
        "invoke",
    ]

    call = mock_task_status_writer.call_args.kwargs

    assert call["name"] == "running-task"
    assert call["namespace"] == "agent-workloads"
    assert call["status"]["phase"] == "Running"
    assert call["status"]["attempts"] == 0
    assert call["status"]["startedAt"]
    assert call["status"]["completedAt"] is None
    assert call["status"]["result"] is None
    assert call["status"]["reason"] is None
    assert call["status"]["message"] is None
    assert call["status"]["retryable"] is None


@patch("agent_operator.task_controller.httpx.post")
def test_invoke_agent_classifies_rate_limit_response(mock_post) -> None:
    request = httpx.Request(
        "POST",
        "http://researcher-agent.agent-workloads.svc.cluster.local:8080/v1/invoke",
    )
    response = httpx.Response(
        429,
        request=request,
    )

    mock_post.return_value = response

    with pytest.raises(TaskExecutionError) as exc_info:
        invoke_agent(
            agent_name="researcher-agent",
            namespace="agent-workloads",
            prompt="hello",
            timeout_seconds=30,
        )

    assert exc_info.value.reason == "RateLimited"
    assert exc_info.value.retryable is True
