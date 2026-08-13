"""Retry utilities for AgentOS task execution."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from agent_operator.errors import TaskExecutionError, execution_timeout_error

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_INITIAL_BACKOFF_SECONDS = 1.0


@dataclass(frozen=True)
class RetryExhaustedError(Exception):
    """Task execution failed after one or more attempts."""

    error: TaskExecutionError
    attempts: int


def execute_with_retry(
    operation: Callable[[float], str],
    *,
    timeout_seconds: float,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    initial_backoff_seconds: float = DEFAULT_INITIAL_BACKOFF_SECONDS,
) -> tuple[str, int]:
    """Execute an operation with retry within a total execution deadline."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than 0")

    deadline = time.monotonic() + timeout_seconds

    for attempt in range(1, max_attempts + 1):
        remaining_seconds = deadline - time.monotonic()

        if remaining_seconds <= 0:
            raise RetryExhaustedError(
                error=execution_timeout_error(),
                attempts=attempt - 1,
            )

        try:
            result = operation(remaining_seconds)
            return result, attempt

        except TaskExecutionError as exc:
            if not exc.retryable or attempt == max_attempts:
                raise RetryExhaustedError(
                    error=exc,
                    attempts=attempt,
                ) from exc

            backoff_seconds = initial_backoff_seconds * (2 ** (attempt - 1))
            remaining_seconds = deadline - time.monotonic()

            if remaining_seconds <= backoff_seconds:
                raise RetryExhaustedError(
                    error=execution_timeout_error(),
                    attempts=attempt,
                ) from exc

            time.sleep(backoff_seconds)

    raise RuntimeError("retry loop exited unexpectedly")
