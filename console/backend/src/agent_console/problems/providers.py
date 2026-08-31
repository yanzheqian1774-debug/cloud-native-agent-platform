# ruff: noqa: RUF001
"""Console-local model provider ports and authenticated adapters."""

from __future__ import annotations

import json
import math
import os
from typing import Any, Protocol

import httpx

PLANNING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "classification": {"type": "string"},
        "summary": {"type": "string"},
        "needs_clarification": {"type": "boolean"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "purpose": {"type": "string"},
                },
                "required": ["title", "purpose"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["classification", "summary", "needs_clarification", "tasks"],
    "additionalProperties": False,
}


class ProblemPlanningError(ValueError):
    """Controlled, credential-free planning failure."""

    def __init__(self, reason: str, status: int = 422) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class PlanningProposalPort(Protocol):
    provider_id: str
    model: str

    def propose(
        self, problem: str, context: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


class EmbeddingPort(Protocol):
    provider_id: str
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _endpoint(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ProblemPlanningError("PROVIDER_CONFIGURATION_MISSING", 503)
    return value


def _planning_timeout_seconds() -> float:
    raw_value = os.getenv("S5_PLANNING_TIMEOUT_SECONDS")
    if raw_value is None:
        return 30.0
    value = raw_value.strip()
    if not value:
        raise ProblemPlanningError("PROVIDER_CONFIGURATION_INVALID", 503)
    try:
        timeout = float(value)
    except ValueError:
        raise ProblemPlanningError("PROVIDER_CONFIGURATION_INVALID", 503) from None
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise ProblemPlanningError("PROVIDER_CONFIGURATION_INVALID", 503)
    return timeout


def _provider_request(
    client: httpx.Client,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        value = response.json()
    except (httpx.HTTPError, ValueError):
        raise ProblemPlanningError("CONTROLLED_PROVIDER_UNAVAILABLE", 503) from None
    if not isinstance(value, dict):
        raise ProblemPlanningError("CONTROLLED_PROVIDER_INVALID_RESPONSE", 503)
    return value


def _validate_proposal(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "classification",
        "summary",
        "needs_clarification",
        "tasks",
    }:
        raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503)
    if not isinstance(value["classification"], str) or not value["classification"]:
        raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503)
    if not isinstance(value["summary"], str) or not value["summary"]:
        raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503)
    if not isinstance(value["needs_clarification"], bool):
        raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503)
    tasks = value["tasks"]
    if not isinstance(tasks, list):
        raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503)
    for task in tasks:
        if (
            not isinstance(task, dict)
            or set(task) != {"title", "purpose"}
            or not isinstance(task["title"], str)
            or not task["title"]
            or not isinstance(task["purpose"], str)
            or not task["purpose"]
        ):
            raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503)
    return value


def _validate_vectors(value: object, expected: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != expected:
        raise ProblemPlanningError("EMBEDDING_PROVIDER_INVALID", 503)
    vectors: list[list[float]] = []
    dimension: int | None = None
    for raw_vector in value:
        if not isinstance(raw_vector, list) or not raw_vector:
            raise ProblemPlanningError("EMBEDDING_PROVIDER_INVALID", 503)
        vector = []
        for item in raw_vector:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ProblemPlanningError("EMBEDDING_PROVIDER_INVALID", 503)
            vector.append(float(item))
        dimension = dimension or len(vector)
        if len(vector) != dimension:
            raise ProblemPlanningError("EMBEDDING_PROVIDER_INVALID", 503)
        vectors.append(vector)
    return vectors


class _ConfiguredProvider:
    def __init__(
        self, provider_id: str, model: str, client: httpx.Client | None
    ) -> None:
        self.provider_id = provider_id
        self.model = model
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0))


class OllamaPlanningProvider(_ConfiguredProvider):
    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__(
            "ollama",
            os.getenv("S5_IMPL_041_PLANNING_MODEL", "qwen3:8B"),
            client,
        )
        self.base_url = os.getenv(
            "S5_IMPL_041_OLLAMA_URL", "http://127.0.0.1:11434"
        ).rstrip("/")

    def propose(self, problem: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        value = _provider_request(
            self._client,
            _endpoint(self.base_url, "api/chat"),
            {
                "model": self.model,
                "stream": False,
                "think": False,
                "format": PLANNING_SCHEMA,
                "messages": _planning_messages(problem, context),
                "options": {
                    "temperature": 0,
                    "seed": 41,
                    "num_ctx": 2048,
                    "num_predict": 400,
                },
            },
        )
        try:
            content = json.loads(value["message"]["content"])
        except (KeyError, TypeError, json.JSONDecodeError):
            raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503) from None
        return _validate_proposal(content)


class OllamaEmbeddingProvider(_ConfiguredProvider):
    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__(
            "ollama",
            os.getenv("S5_IMPL_041_EMBEDDING_MODEL", "shaw/dmeta-embedding-zh:latest"),
            client,
        )
        self.base_url = os.getenv(
            "S5_IMPL_041_OLLAMA_URL", "http://127.0.0.1:11434"
        ).rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        value = _provider_request(
            self._client,
            _endpoint(self.base_url, "api/embed"),
            {"model": self.model, "input": texts},
        )
        return _validate_vectors(value.get("embeddings"), len(texts))


class OpenAICompatiblePlanningProvider(_ConfiguredProvider):
    def __init__(self, client: httpx.Client | None = None) -> None:
        model = _required("S5_PLANNING_MODEL")
        timeout = _planning_timeout_seconds()
        planning_client = (
            client
            if client is not None
            else httpx.Client(timeout=httpx.Timeout(timeout))
        )
        super().__init__("openai-compatible", model, planning_client)
        self.base_url = _required("S5_PLANNING_BASE_URL").rstrip("/")
        self._headers = {"Authorization": f"Bearer {_required('S5_PLANNING_API_KEY')}"}

    def propose(self, problem: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        value = _provider_request(
            self._client,
            _endpoint(self.base_url, "chat/completions"),
            {
                "model": self.model,
                "messages": _planning_messages(problem, context),
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "planning_proposal",
                        "strict": True,
                        "schema": PLANNING_SCHEMA,
                    },
                },
            },
            self._headers,
        )
        try:
            content = json.loads(value["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ProblemPlanningError("MODEL_SCHEMA_VALIDATION_FAILED", 503) from None
        return _validate_proposal(content)


class OpenAICompatibleEmbeddingProvider(_ConfiguredProvider):
    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__("openai-compatible", _required("S5_EMBEDDING_MODEL"), client)
        self.base_url = _required("S5_EMBEDDING_BASE_URL").rstrip("/")
        self._headers = {"Authorization": f"Bearer {_required('S5_EMBEDDING_API_KEY')}"}

    def embed(self, texts: list[str]) -> list[list[float]]:
        value = _provider_request(
            self._client,
            _endpoint(self.base_url, "embeddings"),
            {"model": self.model, "input": texts},
            self._headers,
        )
        data = value.get("data")
        if not isinstance(data, list):
            raise ProblemPlanningError("EMBEDDING_PROVIDER_INVALID", 503)
        ordered: list[object] = [None] * len(data)
        for item in data:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("index"), int)
                or item["index"] < 0
                or item["index"] >= len(data)
                or ordered[item["index"]] is not None
            ):
                raise ProblemPlanningError("EMBEDDING_PROVIDER_INVALID", 503)
            ordered[item["index"]] = item.get("embedding")
        return _validate_vectors(ordered, len(texts))


class _UnavailablePlanningProvider:
    provider_id = "unconfigured"
    model = "unconfigured"

    def __init__(self, reason: str = "PROVIDER_CONFIGURATION_MISSING") -> None:
        self.reason = reason

    def propose(self, problem: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        raise ProblemPlanningError(self.reason, 503)


class _UnavailableEmbeddingProvider:
    provider_id = "unconfigured"
    model = "unconfigured"

    def __init__(self, reason: str = "PROVIDER_CONFIGURATION_MISSING") -> None:
        self.reason = reason

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProblemPlanningError(self.reason, 503)


def planning_provider_from_environment() -> PlanningProposalPort:
    provider = os.getenv("S5_PLANNING_PROVIDER", "").strip()
    if provider == "ollama":
        return OllamaPlanningProvider()
    if provider == "openai-compatible":
        try:
            return OpenAICompatiblePlanningProvider()
        except ProblemPlanningError as exc:
            return _UnavailablePlanningProvider(exc.reason)
    if not provider:
        return _UnavailablePlanningProvider()
    return _UnavailablePlanningProvider("PROVIDER_CONFIGURATION_INVALID")


def embedding_provider_from_environment() -> EmbeddingPort:
    provider = os.getenv("S5_EMBEDDING_PROVIDER", "").strip()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    if provider == "openai-compatible":
        try:
            return OpenAICompatibleEmbeddingProvider()
        except ProblemPlanningError as exc:
            return _UnavailableEmbeddingProvider(exc.reason)
    if not provider:
        return _UnavailableEmbeddingProvider()
    return _UnavailableEmbeddingProvider("PROVIDER_CONFIGURATION_INVALID")


def _planning_messages(
    problem: str, context: list[dict[str, Any]]
) -> list[dict[str, str]]:
    prompt = {
        "problem": problem,
        "authorized_context": [item["excerpt"] for item in context],
        "boundary": "只形成待审批计划；禁止执行、创建实例、调用工具或发布资源。",
    }
    return [
        {
            "role": "system",
            "content": (
                "你是受控规划模型。只返回符合 schema 的 JSON；模型输出不授予权威。"
            ),
        },
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ]
