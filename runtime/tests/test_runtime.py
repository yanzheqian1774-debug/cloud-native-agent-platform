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

    response = client.post(
        "/v1/invoke",
        json={"input": "hello"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["agent"] == "researcher"
    assert body["model"] == "mock-model"
    assert body["output"] == "mock response: hello"
