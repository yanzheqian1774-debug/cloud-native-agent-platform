"""Error model for AgentOS task execution."""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TaskExecutionError(Exception):
    """Structured error raised during Task execution."""

    reason: str
    message: str
    retryable: bool

    def __str__(self) -> str:
        return self.message


def execution_timeout_error() -> TaskExecutionError:
    """Return the terminal error for an exhausted Task execution budget."""

    return TaskExecutionError(
        reason="ExecutionTimeout",
        message="task execution deadline exceeded",
        retryable=False,
    )


def classify_http_error(exc: httpx.HTTPError) -> TaskExecutionError:
    """Convert an HTTPX error into AgentOS task execution semantics."""

    if isinstance(exc, httpx.TimeoutException):
        return TaskExecutionError(
            reason="UpstreamTimeout",
            message=str(exc),
            retryable=True,
        )

    if isinstance(exc, httpx.NetworkError):
        return TaskExecutionError(
            reason="NetworkError",
            message=str(exc),
            retryable=True,
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code

        if status_code == 429:
            return TaskExecutionError(
                reason="RateLimited",
                message=str(exc),
                retryable=True,
            )

        if status_code in {502, 503, 504}:
            return TaskExecutionError(
                reason="UpstreamUnavailable",
                message=str(exc),
                retryable=True,
            )

        if status_code == 400:
            return TaskExecutionError(
                reason="InvalidRequest",
                message=str(exc),
                retryable=False,
            )

        if status_code == 401:
            return TaskExecutionError(
                reason="AuthenticationError",
                message=str(exc),
                retryable=False,
            )

        if status_code == 403:
            return TaskExecutionError(
                reason="AuthorizationError",
                message=str(exc),
                retryable=False,
            )

        if status_code == 404:
            return TaskExecutionError(
                reason="AgentNotFound",
                message=str(exc),
                retryable=False,
            )

    return TaskExecutionError(
        reason="InternalError",
        message=str(exc),
        retryable=False,
    )
