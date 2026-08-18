from unittest.mock import Mock, patch

import httpx
from agent_runtime.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz() -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_runtime_info(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_NAME", "researcher")
    monkeypatch.setenv("MODEL_NAME", "mock-model")
    monkeypatch.setenv("AGENT_ROLE", "researcher")
    monkeypatch.setenv("AGENT_DISPLAY_NAME", "Research Agent")

    response = client.get("/v1/info")

    assert response.status_code == 200
    assert response.json()["agent"] == "researcher"
    assert response.json()["model"] == "mock-model"
    assert response.json()["role"] == "researcher"
    assert response.json()["display_name"] == "Research Agent"


def test_mock_invoke(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_NAME", "researcher")
    monkeypatch.setenv("MODEL_NAME", "mock-model")
    monkeypatch.setenv("MODEL_PROVIDER", "mock")

    response = client.post(
        "/v1/invoke",
        json={"input": "hello"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["agent"] == "researcher"
    assert body["model"] == "mock-model"
    assert body["output"] == "mock response: hello"


@patch("agent_runtime.main.create_model_provider")
def test_invoke_preserves_provider_rate_limit(
    mock_create_model_provider,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_NAME", "researcher")
    monkeypatch.setenv("MODEL_NAME", "test-model")

    request = httpx.Request(
        "POST",
        "https://api.example.com/v1/chat/completions",
    )
    provider_response = httpx.Response(
        429,
        request=request,
    )

    provider = Mock()
    provider.generate.side_effect = httpx.HTTPStatusError(
        "rate limited",
        request=request,
        response=provider_response,
    )

    mock_create_model_provider.return_value = provider

    response = client.post(
        "/v1/invoke",
        json={"input": "hello"},
    )

    assert response.status_code == 429
    assert response.json() == {
        "detail": "model provider returned HTTP 429",
    }

    provider.generate.assert_called_once_with("hello")


@patch("agent_runtime.main.create_model_provider")
def test_invoke_preserves_provider_unavailable_status(
    mock_create_model_provider,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_NAME", "researcher")
    monkeypatch.setenv("MODEL_NAME", "test-model")

    request = httpx.Request(
        "POST",
        "https://api.example.com/v1/chat/completions",
    )
    provider_response = httpx.Response(
        503,
        request=request,
    )

    provider = Mock()
    provider.generate.side_effect = httpx.HTTPStatusError(
        "provider unavailable",
        request=request,
        response=provider_response,
    )

    mock_create_model_provider.return_value = provider

    response = client.post(
        "/v1/invoke",
        json={"input": "hello"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "model provider returned HTTP 503",
    }
