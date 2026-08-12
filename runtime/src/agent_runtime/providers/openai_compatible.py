"""OpenAI-compatible model provider."""

import os

import httpx

from agent_runtime.providers.base import ModelProvider


class OpenAICompatibleModelProvider(ModelProvider):
    """Model provider for OpenAI-compatible chat completion APIs."""

    def __init__(self) -> None:
        self.base_url = os.environ["MODEL_BASE_URL"].rstrip("/")
        self.api_key = os.environ["MODEL_API_KEY"]
        self.model = os.environ["MODEL_NAME"]

    def generate(self, prompt: str) -> str:

        system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
            },
            timeout=60.0,
        )

        response.raise_for_status()

        payload = response.json()

        return payload["choices"][0]["message"]["content"]
