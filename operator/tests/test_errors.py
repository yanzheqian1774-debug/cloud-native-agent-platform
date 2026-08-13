import httpx
from agent_operator.errors import classify_http_error


def make_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "POST",
        "http://agent/v1/invoke",
    )
    response = httpx.Response(
        status_code,
        request=request,
    )

    return httpx.HTTPStatusError(
        "upstream error",
        request=request,
        response=response,
    )


def test_classify_rate_limit_error() -> None:
    error = classify_http_error(make_status_error(429))

    assert error.reason == "RateLimited"
    assert error.retryable is True


def test_classify_upstream_unavailable_error() -> None:
    error = classify_http_error(make_status_error(503))

    assert error.reason == "UpstreamUnavailable"
    assert error.retryable is True


def test_classify_authentication_error() -> None:
    error = classify_http_error(make_status_error(401))

    assert error.reason == "AuthenticationError"
    assert error.retryable is False


def test_classify_timeout_error() -> None:
    error = classify_http_error(
        httpx.ReadTimeout(
            "read timed out",
            request=httpx.Request(
                "POST",
                "http://agent/v1/invoke",
            ),
        )
    )

    assert error.reason == "UpstreamTimeout"
    assert error.retryable is True


def test_classify_network_error() -> None:
    error = classify_http_error(
        httpx.ConnectError(
            "connection failed",
            request=httpx.Request(
                "POST",
                "http://agent/v1/invoke",
            ),
        )
    )

    assert error.reason == "NetworkError"
    assert error.retryable is True
