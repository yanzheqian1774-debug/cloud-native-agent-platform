from unittest.mock import Mock, patch

import pytest
from agent_runtime.providers.factory import create_model_provider
from agent_runtime.providers.mock import MockModelProvider
from agent_runtime.providers.openai_compatible import (
    OpenAICompatibleModelProvider,
)


def test_create_mock_model_provider(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "mock")

    provider = create_model_provider()

    assert isinstance(provider, MockModelProvider)


def test_mock_model_provider_generate() -> None:
    provider = MockModelProvider()

    assert provider.generate("hello") == "mock response: hello"


def test_create_model_provider_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unsupported model provider"):
        create_model_provider()


def test_create_openai_compatible_provider(monkeypatch) -> None:
    from agent_runtime.providers.openai_compatible import (
        OpenAICompatibleModelProvider,
    )

    monkeypatch.setenv("MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("MODEL_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "test-model")

    provider = create_model_provider()

    assert isinstance(provider, OpenAICompatibleModelProvider)


@patch("agent_runtime.providers.openai_compatible.httpx.post")
def test_openai_compatible_provider_generate(mock_post, monkeypatch) -> None:
    from agent_runtime.providers.openai_compatible import (
        OpenAICompatibleModelProvider,
    )

    monkeypatch.setenv("MODEL_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "test-model")

    response = Mock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "real model response",
                }
            }
        ]
    }

    mock_post.return_value = response

    provider = OpenAICompatibleModelProvider()

    result = provider.generate("hello")

    assert result == "real model response"

    response.raise_for_status.assert_called_once()

    mock_post.assert_called_once_with(
        "https://example.com/v1/chat/completions",
        headers={
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        },
        json={
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
        },
        timeout=60.0,
    )


@patch("agent_runtime.providers.openai_compatible.httpx.post")
def test_openai_compatible_provider_includes_system_prompt(
    mock_post,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MODEL_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv(
        "AGENT_SYSTEM_PROMPT",
        "You are a researcher.",
    )

    response = Mock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "response",
                }
            }
        ]
    }

    mock_post.return_value = response

    provider = OpenAICompatibleModelProvider()

    provider.generate("hello")

    request = mock_post.call_args.kwargs["json"]

    assert request["messages"] == [
        {
            "role": "system",
            "content": "You are a researcher.",
        },
        {
            "role": "user",
            "content": "hello",
        },
    ]
