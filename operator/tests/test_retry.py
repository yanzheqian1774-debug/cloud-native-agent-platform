from unittest.mock import Mock, call, patch

import pytest
from agent_operator.errors import TaskExecutionError
from agent_operator.retry import RetryExhaustedError, execute_with_retry


def test_execute_with_retry_succeeds_first_attempt() -> None:
    operation = Mock(return_value="result")

    result, attempts = execute_with_retry(
        operation,
        timeout_seconds=30,
        initial_backoff_seconds=0,
    )

    assert result == "result"
    assert attempts == 1
    operation.assert_called_once()


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_retries_retryable_error(mock_sleep) -> None:
    operation = Mock(
        side_effect=[
            TaskExecutionError(
                reason="UpstreamUnavailable",
                message="temporarily unavailable",
                retryable=True,
            ),
            "result",
        ]
    )

    result, attempts = execute_with_retry(
        operation,
        timeout_seconds=30,
    )

    assert result == "result"
    assert attempts == 2
    assert operation.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_uses_exponential_backoff(mock_sleep) -> None:
    operation = Mock(
        side_effect=[
            TaskExecutionError(
                reason="UpstreamUnavailable",
                message="temporarily unavailable",
                retryable=True,
            ),
            TaskExecutionError(
                reason="UpstreamUnavailable",
                message="temporarily unavailable",
                retryable=True,
            ),
            "result",
        ]
    )

    result, attempts = execute_with_retry(
        operation,
        timeout_seconds=30,
    )

    assert result == "result"
    assert attempts == 3

    assert mock_sleep.call_args_list == [
        call(1.0),
        call(2.0),
    ]


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_stops_on_non_retryable_error(mock_sleep) -> None:
    operation = Mock(
        side_effect=TaskExecutionError(
            reason="AuthenticationError",
            message="unauthorized",
            retryable=False,
        )
    )

    with pytest.raises(RetryExhaustedError) as exc_info:
        execute_with_retry(
            operation,
            timeout_seconds=30,
        )

    assert exc_info.value.error.reason == "AuthenticationError"
    assert exc_info.value.attempts == 1
    assert operation.call_count == 1
    mock_sleep.assert_not_called()


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_stops_after_max_attempts(mock_sleep) -> None:
    operation = Mock(
        side_effect=TaskExecutionError(
            reason="UpstreamUnavailable",
            message="temporarily unavailable",
            retryable=True,
        )
    )

    with pytest.raises(RetryExhaustedError) as exc_info:
        execute_with_retry(
            operation,
            timeout_seconds=30,
        )

    assert exc_info.value.error.reason == "UpstreamUnavailable"
    assert exc_info.value.attempts == 3
    assert operation.call_count == 3

    assert mock_sleep.call_args_list == [
        call(1.0),
        call(2.0),
    ]


def test_execute_with_retry_rejects_invalid_max_attempts() -> None:
    operation = Mock(return_value="result")

    with pytest.raises(ValueError, match="max_attempts must be at least 1"):
        execute_with_retry(
            operation,
            timeout_seconds=30,
            max_attempts=0,
        )

    operation.assert_not_called()


@patch("agent_operator.retry.time.monotonic")
def test_execute_with_retry_times_out_before_first_attempt(
    mock_monotonic,
) -> None:
    mock_monotonic.side_effect = [
        100.0,
        131.0,
    ]

    operation = Mock()

    with pytest.raises(RetryExhaustedError) as exc_info:
        execute_with_retry(
            operation,
            timeout_seconds=30,
        )

    assert exc_info.value.error.reason == "ExecutionTimeout"
    assert exc_info.value.error.retryable is False
    assert exc_info.value.attempts == 0
    operation.assert_not_called()


@patch("agent_operator.retry.time.sleep")
@patch("agent_operator.retry.time.monotonic")
def test_execute_with_retry_times_out_before_backoff(
    mock_monotonic,
    mock_sleep,
) -> None:
    mock_monotonic.side_effect = [
        100.0,
        100.0,
        129.5,
    ]

    operation = Mock(
        side_effect=TaskExecutionError(
            reason="UpstreamUnavailable",
            message="temporarily unavailable",
            retryable=True,
        )
    )

    with pytest.raises(RetryExhaustedError) as exc_info:
        execute_with_retry(
            operation,
            timeout_seconds=30,
        )

    assert exc_info.value.error.reason == "ExecutionTimeout"
    assert exc_info.value.attempts == 1
    assert operation.call_count == 1
    mock_sleep.assert_not_called()


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_uses_longer_backoff_for_rate_limit(mock_sleep) -> None:
    operation = Mock(
        side_effect=[
            TaskExecutionError(
                reason="RateLimited",
                message="too many requests",
                retryable=True,
            ),
            TaskExecutionError(
                reason="RateLimited",
                message="too many requests",
                retryable=True,
            ),
            "result",
        ]
    )

    result, attempts = execute_with_retry(
        operation,
        timeout_seconds=60,
    )

    assert result == "result"
    assert attempts == 3
    assert operation.call_count == 3

    assert mock_sleep.call_args_list == [
        call(5.0),
        call(10.0),
    ]


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_preserves_larger_configured_rate_limit_backoff(
    mock_sleep,
) -> None:
    operation = Mock(
        side_effect=[
            TaskExecutionError(
                reason="RateLimited",
                message="too many requests",
                retryable=True,
            ),
            "result",
        ]
    )

    result, attempts = execute_with_retry(
        operation,
        timeout_seconds=60,
        initial_backoff_seconds=10.0,
    )

    assert result == "result"
    assert attempts == 2
    mock_sleep.assert_called_once_with(10.0)


@patch("agent_operator.retry.time.sleep")
def test_execute_with_retry_keeps_default_backoff_for_other_errors(
    mock_sleep,
) -> None:
    operation = Mock(
        side_effect=[
            TaskExecutionError(
                reason="UpstreamUnavailable",
                message="temporarily unavailable",
                retryable=True,
            ),
            TaskExecutionError(
                reason="UpstreamUnavailable",
                message="temporarily unavailable",
                retryable=True,
            ),
            "result",
        ]
    )

    result, attempts = execute_with_retry(
        operation,
        timeout_seconds=60,
    )

    assert result == "result"
    assert attempts == 3

    assert mock_sleep.call_args_list == [
        call(1.0),
        call(2.0),
    ]


@patch("agent_operator.retry.time.sleep")
@patch("agent_operator.retry.time.monotonic")
def test_execute_with_retry_rate_limit_respects_execution_deadline(
    mock_monotonic,
    mock_sleep,
) -> None:
    mock_monotonic.side_effect = [
        100.0,
        100.0,
        127.0,
    ]

    operation = Mock(
        side_effect=TaskExecutionError(
            reason="RateLimited",
            message="too many requests",
            retryable=True,
        )
    )

    with pytest.raises(RetryExhaustedError) as exc_info:
        execute_with_retry(
            operation,
            timeout_seconds=30,
        )

    assert exc_info.value.error.reason == "ExecutionTimeout"
    assert exc_info.value.attempts == 1
    assert operation.call_count == 1
    mock_sleep.assert_not_called()
