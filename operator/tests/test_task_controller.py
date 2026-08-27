from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import kopf
import pytest
from agent_gateway.capability import ProviderResponse
from agent_operator.errors import TaskExecutionError
from agent_operator.execution_coordinator import ExecutionClassification
from agent_operator.retry import RetryExhaustedError
from agent_operator.task_controller import (
    build_agent_service_url,
    create_task,
    invoke_agent,
    task_evidence_subject,
)

TASK_META = {
    "name": "test-task",
    "namespace": "agent-workloads",
    "uid": "task-uid-001",
    "labels": {
        "agentos.io/workflow": "workflow-001",
        "agentos.io/workflow-task": "test-task",
    },
    "ownerReferences": [
        {
            "apiVersion": "agentos.io/v1alpha1",
            "kind": "Workflow",
            "name": "workflow-001",
            "uid": "workflow-uid-001",
            "controller": True,
        }
    ],
}
AGENT_BODY = {
    "metadata": {
        "name": "researcher-agent",
        "namespace": "agent-workloads",
        "uid": "agent-uid-001",
        "creationTimestamp": "2026-08-24T00:00:00Z",
    },
    "spec": {"runtime": {"type": "native"}},
}


@pytest.fixture(autouse=True)
def mock_task_status_writer():
    with (
        patch("agent_operator.task_controller.patch_task_status") as mock_status_writer,
        patch(
            "agent_operator.task_controller.load_agent_definition",
            return_value=[AGENT_BODY],
        ),
    ):
        yield mock_status_writer


def succeeded_outcome(result: str):
    return SimpleNamespace(
        classification=ExecutionClassification.SUCCEEDED,
        result=result,
        diagnostic="TASK_RUNTIME_SUCCEEDED",
    )


@pytest.fixture
def mock_execution_coordinator():
    coordinator = Mock()
    coordinator.execute.return_value = succeeded_outcome("research result")
    with patch(
        "agent_operator.task_controller.build_default_coordinator",
        return_value=coordinator,
    ):
        yield coordinator


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


def test_create_task_sets_succeeded_status(
    mock_execution_coordinator,
) -> None:
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
        meta=TASK_META,
    )

    assert status_patch.status["phase"] == "Succeeded"
    assert status_patch.status["result"] == "research result"
    assert status_patch.status["startedAt"]
    assert status_patch.status["completedAt"]
    assert status_patch.status["attempts"] == 1
    assert status_patch.status["reason"] is None
    assert status_patch.status["message"] is None
    assert status_patch.status["retryable"] is None

    mock_execution_coordinator.execute.assert_called_once()
    call_kwargs = mock_execution_coordinator.execute.call_args.kwargs
    assert call_kwargs["input_text"] == "research this topic"
    assert call_kwargs["context"].envelope.definition_ref.name == "researcher-agent"
    assert (
        call_kwargs["context"].evidence_subject.workflow_identity == "workflow-uid-001"
    )
    assert call_kwargs["context"].evidence_subject.task_identity == "task-uid-001"


def test_standalone_task_has_no_evidence_subject() -> None:
    metadata = {key: TASK_META[key] for key in ("name", "namespace", "uid")}
    assert task_evidence_subject(metadata=metadata, namespace="agent-workloads") is None


def test_contradictory_workflow_identity_fails_closed() -> None:
    metadata = {
        **TASK_META,
        "ownerReferences": [
            {**TASK_META["ownerReferences"][0], "name": "different-workflow"}
        ],
    }
    with pytest.raises(ValueError, match="EVIDENCE_SUBJECT_IDENTITY_CONFLICT"):
        task_evidence_subject(metadata=metadata, namespace="agent-workloads")


def test_default_task_path_consumes_native_and_requested_capability() -> None:
    agent = {
        **AGENT_BODY,
        "spec": {
            "runtime": {"type": "native"},
            "model": {"provider": "mock", "name": "mock-model"},
            "capabilities": ["customer-lookup"],
        },
    }
    status_patch = kopf.Patch()
    with (
        patch(
            "agent_operator.task_controller.load_agent_definition",
            return_value=[agent],
        ),
        patch(
            "agent_operator.execution_coordinator.DeterministicSyntheticTransport.send",
            return_value=ProviderResponse(200, {"accepted": True}),
        ) as capability_send,
    ):
        create_task(
            name="test-task",
            spec={
                "agentRef": {"name": "researcher-agent"},
                "input": {"prompt": "research this topic"},
            },
            namespace="agent-workloads",
            patch=status_patch,
            meta=TASK_META,
        )

    assert status_patch.status["phase"] == "Succeeded"
    assert status_patch.status["result"] == "mock response: research this topic"
    assert status_patch.status["attempts"] == 1
    capability_send.assert_called_once()
    provider_request = capability_send.call_args.args[0]
    assert provider_request.execution_identity.value


def test_ambiguous_capability_declaration_fails_before_running_or_invocation(
    mock_task_status_writer,
) -> None:
    agent = {
        **AGENT_BODY,
        "spec": {
            "runtime": {"type": "native"},
            "model": {"provider": "mock", "name": "mock-model"},
            "capabilities": ["customer-lookup", "document-read"],
        },
    }
    status_patch = kopf.Patch()
    with (
        patch(
            "agent_operator.task_controller.load_agent_definition",
            return_value=[agent],
        ),
        patch(
            "agent_operator.task_controller.build_default_coordinator"
        ) as coordinator_factory,
    ):
        create_task(
            name="test-task",
            spec={
                "agentRef": {"name": "researcher-agent"},
                "input": {"prompt": "research this topic"},
            },
            namespace="agent-workloads",
            patch=status_patch,
            meta=TASK_META,
        )

    mock_task_status_writer.assert_not_called()
    coordinator_factory.assert_not_called()
    assert status_patch.status["phase"] == "Failed"
    assert status_patch.status["reason"] == "InvalidLegacyIdentityEvidence"
    assert status_patch.status["attempts"] == 0


def test_create_task_sets_failed_status(
    mock_execution_coordinator,
) -> None:
    mock_execution_coordinator.execute.side_effect = TaskExecutionError(
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
        meta=TASK_META,
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


@pytest.mark.parametrize(
    "transport_error",
    [
        httpx.ReadTimeout("read timed out"),
        httpx.WriteTimeout("write timed out"),
        httpx.ReadError("read failed"),
        httpx.WriteError("write failed"),
        httpx.RemoteProtocolError("protocol failed"),
    ],
)
@patch("agent_operator.task_controller.httpx.post")
def test_invoke_agent_suppresses_retry_for_indeterminate_transport_failure(
    mock_post,
    transport_error,
) -> None:
    mock_post.side_effect = transport_error
    with pytest.raises(TaskExecutionError) as exc_info:
        invoke_agent(
            agent_name="researcher-agent",
            namespace="agent-workloads",
            prompt="hello",
            timeout_seconds=30,
        )
    assert exc_info.value.reason == "ExecutionOutcomeUnknown"
    assert exc_info.value.retryable is False


def test_indeterminate_transport_failure_is_not_retried(
    mock_execution_coordinator,
) -> None:
    mock_execution_coordinator.execute.side_effect = TaskExecutionError(
        reason="ExecutionOutcomeUnknown",
        message="Runtime outcome unknown",
        retryable=False,
    )
    status_patch = kopf.Patch()
    create_task(
        spec={
            "agentRef": {"name": "researcher-agent"},
            "input": {"prompt": "hello"},
        },
        name="test-task",
        namespace="agent-workloads",
        patch=status_patch,
        meta=TASK_META,
    )
    mock_execution_coordinator.execute.assert_called_once()
    assert status_patch.status["phase"] == "Failed"
    assert status_patch.status["reason"] == "ExecutionOutcomeUnknown"
    assert status_patch.status["retryable"] is False
    assert status_patch.status["attempts"] == 1


@patch("agent_operator.retry.time.sleep")
def test_create_task_retries_retryable_error_then_succeeds(
    mock_sleep,
    mock_execution_coordinator,
) -> None:
    mock_execution_coordinator.execute.side_effect = [
        TaskExecutionError(
            reason="UpstreamUnavailable",
            message="temporarily unavailable",
            retryable=True,
        ),
        succeeded_outcome("TASK_OK"),
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
        meta=TASK_META,
    )

    assert status_patch.status["phase"] == "Succeeded"
    assert status_patch.status["result"] == "TASK_OK"
    assert status_patch.status["attempts"] == 2
    assert status_patch.status["reason"] is None
    assert status_patch.status["message"] is None
    assert status_patch.status["retryable"] is None
    assert mock_execution_coordinator.execute.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("agent_operator.retry.time.sleep")
def test_create_task_fails_after_retry_exhaustion(
    mock_sleep,
    mock_execution_coordinator,
) -> None:
    mock_execution_coordinator.execute.side_effect = TaskExecutionError(
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
        meta=TASK_META,
    )

    assert status_patch.status["phase"] == "Failed"
    assert status_patch.status["reason"] == "UpstreamUnavailable"
    assert status_patch.status["retryable"] is True
    assert status_patch.status["result"] is None
    assert status_patch.status["attempts"] == 3
    assert mock_execution_coordinator.execute.call_count == 3
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
        meta=TASK_META,
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
        meta=TASK_META,
    )

    assert mock_execute_with_retry.call_args.kwargs["timeout_seconds"] == 45.0


def test_create_task_persists_running_status_before_execution(
    mock_task_status_writer,
    mock_execution_coordinator,
) -> None:
    status_patch = kopf.Patch()
    call_order = []

    mock_task_status_writer.side_effect = lambda **_: call_order.append("running")

    def invoke_side_effect(**_):
        call_order.append("invoke")
        return succeeded_outcome("task result")

    mock_execution_coordinator.execute.side_effect = invoke_side_effect
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
        meta={**TASK_META, "name": "running-task"},
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


def test_retry_attempts_reuse_one_immutable_execution_context(
    mock_execution_coordinator,
) -> None:
    mock_execution_coordinator.execute.side_effect = [
        TaskExecutionError("NetworkError", "temporary", True),
        succeeded_outcome("TASK_OK"),
    ]
    with patch("agent_operator.retry.time.sleep"):
        create_task(
            spec={
                "agentRef": {"name": "researcher-agent"},
                "input": {"prompt": "hello"},
            },
            name="test-task",
            namespace="agent-workloads",
            patch=kopf.Patch(),
            meta=TASK_META,
        )
    first = mock_execution_coordinator.execute.call_args_list[0].kwargs["context"]
    second = mock_execution_coordinator.execute.call_args_list[1].kwargs["context"]
    assert first is second
    assert first.envelope.execution_identity == second.envelope.execution_identity


@patch("agent_operator.task_controller.invoke_compatible_agent")
def test_running_status_replay_fails_closed_without_duplicate_invocation(
    mock_invoke_compatible,
) -> None:
    status_patch = kopf.Patch()
    create_task(
        spec={
            "agentRef": {"name": "researcher-agent"},
            "input": {"prompt": "hello"},
        },
        name="test-task",
        namespace="agent-workloads",
        patch=status_patch,
        meta=TASK_META,
        status={
            "phase": "Running",
            "attempts": 1,
            "startedAt": "2026-08-24T00:00:00Z",
        },
    )
    mock_invoke_compatible.assert_not_called()
    assert status_patch.status["phase"] == "Failed"
    assert status_patch.status["reason"] == "ExecutionStateUnknown"
    assert status_patch.status["retryable"] is False
    assert status_patch.status["attempts"] == 1


@pytest.mark.parametrize("phase", ["Succeeded", "Failed", "TimedOut"])
@patch("agent_operator.task_controller.invoke_compatible_agent")
def test_terminal_task_replay_is_a_noop(mock_invoke_compatible, phase: str) -> None:
    status_patch = kopf.Patch()
    create_task(
        spec={
            "agentRef": {"name": "researcher-agent"},
            "input": {"prompt": "hello"},
        },
        name="test-task",
        namespace="agent-workloads",
        patch=status_patch,
        meta=TASK_META,
        status={"phase": phase},
    )
    mock_invoke_compatible.assert_not_called()
    assert dict(status_patch.status) == {}


@patch("agent_operator.task_controller.invoke_compatible_agent")
def test_missing_definition_fails_before_running_or_invocation(
    mock_invoke_compatible,
    mock_task_status_writer,
) -> None:
    status_patch = kopf.Patch()
    with patch("agent_operator.task_controller.load_agent_definition", return_value=[]):
        create_task(
            spec={
                "agentRef": {"name": "missing-agent"},
                "input": {"prompt": "hello"},
            },
            name="test-task",
            namespace="agent-workloads",
            patch=status_patch,
            meta=TASK_META,
        )
    mock_task_status_writer.assert_not_called()
    mock_invoke_compatible.assert_not_called()
    assert status_patch.status["phase"] == "Failed"
    assert status_patch.status["reason"] == "AgentDefinitionNotFound"
    assert status_patch.status["attempts"] == 0


@patch("agent_operator.task_controller.invoke_compatible_agent")
def test_running_barrier_write_failure_prevents_runtime_invocation(
    mock_invoke_compatible,
    mock_task_status_writer,
) -> None:
    mock_task_status_writer.side_effect = RuntimeError("status write failed")
    with pytest.raises(RuntimeError, match="status write failed"):
        create_task(
            spec={
                "agentRef": {"name": "researcher-agent"},
                "input": {"prompt": "hello"},
            },
            name="test-task",
            namespace="agent-workloads",
            patch=kopf.Patch(),
            meta=TASK_META,
        )
    mock_invoke_compatible.assert_not_called()


def test_two_handlers_with_stale_status_can_both_invoke_without_distributed_cas(
    mock_execution_coordinator,
) -> None:
    mock_execution_coordinator.execute.side_effect = [
        succeeded_outcome("first"),
        succeeded_outcome("second"),
    ]
    for _ in range(2):
        create_task(
            spec={
                "agentRef": {"name": "researcher-agent"},
                "input": {"prompt": "hello"},
            },
            name="test-task",
            namespace="agent-workloads",
            patch=kopf.Patch(),
            meta=TASK_META,
            status={},
        )
    assert mock_execution_coordinator.execute.call_count == 2
    first = mock_execution_coordinator.execute.call_args_list[0].kwargs["context"]
    second = mock_execution_coordinator.execute.call_args_list[1].kwargs["context"]
    assert first.envelope.execution_identity == second.envelope.execution_identity
