"""Model provider factory."""

import os

from agent_runtime.providers.base import ModelProvider
from agent_runtime.providers.mock import MockModelProvider
from agent_runtime.providers.openai_compatible import (
    OpenAICompatibleModelProvider,
)


def create_model_provider() -> ModelProvider:
    """Create the configured model provider."""

    provider = os.getenv("MODEL_PROVIDER", "mock")

    if provider == "mock":
        return MockModelProvider()

    if provider == "openai-compatible":
        return OpenAICompatibleModelProvider()

    raise ValueError(f"Unsupported model provider: {provider}")
