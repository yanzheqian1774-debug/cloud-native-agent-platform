"""Contract tests for Console-local Planning and Embedding providers."""

from __future__ import annotations

import json

import httpx
import pytest
from agent_console.problems import (
    OllamaEmbeddingProvider,
    OllamaPlanningProvider,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatiblePlanningProvider,
    ProblemPlanningError,
)
from agent_console.problems.providers import (
    embedding_provider_from_environment,
    planning_provider_from_environment,
)

PROPOSAL = {
    "classification": "SUPPLIER_QUALITY",
    "summary": "形成待审批计划",
    "needs_clarification": False,
    "tasks": [{"title": "核验事实", "purpose": "建立受控事实基础"}],
}


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=0.1)


def configure_public(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "S5_PLANNING_BASE_URL": "https://planning.example/v1/",
        "S5_PLANNING_API_KEY": "planning-secret-marker",
        "S5_PLANNING_MODEL": "planner-model-v1",
        "S5_EMBEDDING_BASE_URL": "https://embedding.example/v1/",
        "S5_EMBEDDING_API_KEY": "embedding-secret-marker",
        "S5_EMBEDDING_MODEL": "embedding-model-v1",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def assert_timeout(client: httpx.Client, seconds: float) -> None:
    assert client.timeout.connect == seconds
    assert client.timeout.read == seconds
    assert client.timeout.write == seconds
    assert client.timeout.pool == seconds


def test_public_planning_timeout_defaults_to_exactly_30_seconds(monkeypatch):
    configure_public(monkeypatch)
    monkeypatch.delenv("S5_PLANNING_TIMEOUT_SECONDS", raising=False)
    provider = OpenAICompatiblePlanningProvider()
    assert_timeout(provider._client, 30.0)


@pytest.mark.parametrize("configured", ["45", "60", "45.5"])
def test_public_planning_timeout_accepts_bounded_seconds(monkeypatch, configured):
    configure_public(monkeypatch)
    monkeypatch.setenv("S5_PLANNING_TIMEOUT_SECONDS", configured)
    provider = OpenAICompatiblePlanningProvider()
    assert_timeout(provider._client, float(configured))


@pytest.mark.parametrize(
    "configured",
    ["", "   ", "not-a-number", "NaN", "inf", "+Infinity", "-inf", "0", "-1", "60.1"],
)
def test_public_planning_timeout_invalid_configuration_fails_closed(
    monkeypatch, configured
):
    configure_public(monkeypatch)
    monkeypatch.setenv("S5_PLANNING_TIMEOUT_SECONDS", configured)
    with pytest.raises(ProblemPlanningError) as caught:
        OpenAICompatiblePlanningProvider()
    assert (caught.value.reason, caught.value.status) == (
        "PROVIDER_CONFIGURATION_INVALID",
        503,
    )
    assert "secret-marker" not in str(caught.value)


def test_public_planning_timeout_invalid_configuration_stays_unavailable(
    monkeypatch,
):
    configure_public(monkeypatch)
    monkeypatch.setenv("S5_PLANNING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("S5_PLANNING_TIMEOUT_SECONDS", "61")
    provider = planning_provider_from_environment()
    with pytest.raises(ProblemPlanningError) as caught:
        provider.propose("problem", [])
    assert (caught.value.reason, caught.value.status) == (
        "PROVIDER_CONFIGURATION_INVALID",
        503,
    )


def test_public_planning_timeout_does_not_change_embedding_or_ollama(monkeypatch):
    configure_public(monkeypatch)
    monkeypatch.setenv("S5_PLANNING_TIMEOUT_SECONDS", "45")
    assert_timeout(OpenAICompatibleEmbeddingProvider()._client, 30.0)
    assert_timeout(OllamaPlanningProvider()._client, 30.0)
    assert_timeout(OllamaEmbeddingProvider()._client, 30.0)


def test_public_planning_contract_auth_endpoint_model_and_schema(monkeypatch):
    configure_public(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://planning.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer planning-secret-marker"
        payload = json.loads(request.content)
        assert payload["model"] == "planner-model-v1"
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(PROPOSAL)}}]},
        )

    provider = OpenAICompatiblePlanningProvider(client(handler))
    assert provider.propose("problem", [{"excerpt": "authorized"}]) == PROPOSAL
    assert provider.provider_id == "openai-compatible"
    assert provider.model == "planner-model-v1"


def test_public_embedding_contract_orders_vectors_and_supports_query(monkeypatch):
    configure_public(monkeypatch)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url == "https://embedding.example/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer embedding-secret-marker"
        payload = json.loads(request.content)
        assert payload["model"] == "embedding-model-v1"
        data = [
            {"index": index, "embedding": [float(index), 1.0, 2.0]}
            for index, _ in enumerate(payload["input"])
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    provider = OpenAICompatibleEmbeddingProvider(client(handler))
    assert provider.embed(["document-a", "document-b"]) == [
        [0.0, 1.0, 2.0],
        [1.0, 1.0, 2.0],
    ]
    assert provider.embed(["query"]) == [[0.0, 1.0, 2.0]]
    assert calls == 2


def test_planning_and_embedding_selection_are_independent(monkeypatch):
    monkeypatch.setenv("S5_PLANNING_PROVIDER", "ollama")
    monkeypatch.setenv("S5_EMBEDDING_PROVIDER", "openai-compatible")
    configure_public(monkeypatch)
    assert isinstance(planning_provider_from_environment(), OllamaPlanningProvider)
    assert isinstance(
        embedding_provider_from_environment(), OpenAICompatibleEmbeddingProvider
    )


def test_explicit_ollama_uses_only_legacy_local_configuration(monkeypatch):
    monkeypatch.setenv("S5_IMPL_041_OLLAMA_URL", "http://ollama.local/")
    monkeypatch.setenv("S5_IMPL_041_PLANNING_MODEL", "local-planner")
    monkeypatch.setenv("S5_IMPL_041_EMBEDDING_MODEL", "local-embedding")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if request.url.path == "/api/chat":
            assert payload["model"] == "local-planner"
            return httpx.Response(
                200, json={"message": {"content": json.dumps(PROPOSAL)}}
            )
        assert request.url.path == "/api/embed"
        assert payload["model"] == "local-embedding"
        return httpx.Response(200, json={"embeddings": [[1.0, 2.0]]})

    transport_client = client(handler)
    assert OllamaPlanningProvider(transport_client).propose("p", []) == PROPOSAL
    assert OllamaEmbeddingProvider(transport_client).embed(["q"]) == [[1.0, 2.0]]


@pytest.mark.parametrize(
    ("missing", "constructor"),
    [
        ("S5_PLANNING_API_KEY", OpenAICompatiblePlanningProvider),
        ("S5_PLANNING_BASE_URL", OpenAICompatiblePlanningProvider),
        ("S5_PLANNING_MODEL", OpenAICompatiblePlanningProvider),
        ("S5_EMBEDDING_API_KEY", OpenAICompatibleEmbeddingProvider),
        ("S5_EMBEDDING_BASE_URL", OpenAICompatibleEmbeddingProvider),
        ("S5_EMBEDDING_MODEL", OpenAICompatibleEmbeddingProvider),
    ],
)
def test_public_configuration_is_required_and_secret_free(
    monkeypatch, missing, constructor
):
    configure_public(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(ProblemPlanningError) as caught:
        constructor()
    assert caught.value.status == 503
    assert caught.value.reason == "PROVIDER_CONFIGURATION_MISSING"
    assert "secret-marker" not in str(caught.value)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_provider_http_failures_are_controlled_and_credentials_are_redacted(
    monkeypatch, status
):
    configure_public(monkeypatch)
    provider = OpenAICompatiblePlanningProvider(
        client(lambda request: httpx.Response(status, text="planning-secret-marker"))
    )
    with pytest.raises(ProblemPlanningError) as caught:
        provider.propose("problem", [])
    assert caught.value.reason == "CONTROLLED_PROVIDER_UNAVAILABLE"
    assert caught.value.status == 503
    assert "planning-secret-marker" not in str(caught.value)


def test_timeout_malformed_json_and_malformed_content_fail_closed(monkeypatch):
    configure_public(monkeypatch)
    calls = 0

    def timeout(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("planning-secret-marker", request=request)

    providers = [
        OpenAICompatiblePlanningProvider(client(timeout)),
        OpenAICompatiblePlanningProvider(
            client(lambda request: httpx.Response(200, content=b"not-json"))
        ),
        OpenAICompatiblePlanningProvider(
            client(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": "{}"}}]}
                )
            )
        ),
    ]
    for provider in providers:
        with pytest.raises(ProblemPlanningError) as caught:
            provider.propose("problem", [])
        assert caught.value.status == 503
        assert "secret-marker" not in str(caught.value)
    assert calls == 1


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"index": 0, "embedding": []}],
        [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [1.0, 2.0]}],
        [{"index": 0, "embedding": [True]}],
        [{"index": 1, "embedding": [1.0]}],
    ],
)
def test_embedding_count_dimension_and_shape_validation(monkeypatch, data):
    configure_public(monkeypatch)
    provider = OpenAICompatibleEmbeddingProvider(
        client(lambda request: httpx.Response(200, json={"data": data}))
    )
    with pytest.raises(ProblemPlanningError) as caught:
        provider.embed(["one", "two"])
    assert caught.value.reason == "EMBEDDING_PROVIDER_INVALID"


def test_missing_or_invalid_provider_does_not_fall_back_to_ollama(monkeypatch):
    monkeypatch.delenv("S5_PLANNING_PROVIDER", raising=False)
    missing = planning_provider_from_environment()
    with pytest.raises(ProblemPlanningError) as caught:
        missing.propose("problem", [])
    assert caught.value.reason == "PROVIDER_CONFIGURATION_MISSING"

    monkeypatch.setenv("S5_PLANNING_PROVIDER", "unknown")
    invalid = planning_provider_from_environment()
    with pytest.raises(ProblemPlanningError) as caught:
        invalid.propose("problem", [])
    assert caught.value.reason == "PROVIDER_CONFIGURATION_INVALID"
