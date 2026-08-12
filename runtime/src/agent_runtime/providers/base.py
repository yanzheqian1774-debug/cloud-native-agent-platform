"""Model provider abstractions."""

from abc import ABC, abstractmethod


class ModelProvider(ABC):
    """Base interface for model providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response for a prompt."""
        raise NotImplementedError
