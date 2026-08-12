"""Mock model provider."""

from agent_runtime.providers.base import ModelProvider


class MockModelProvider(ModelProvider):
    """Deterministic provider used for tests and local development."""

    def generate(self, prompt: str) -> str:
        return f"mock response: {prompt}"
