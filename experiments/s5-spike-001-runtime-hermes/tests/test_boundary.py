import sys
from pathlib import Path

SPIKE = Path(__file__).parents[1]
sys.path.insert(0, str(SPIKE))

from harness.runtime_boundary import RuntimeRequest, RuntimeState  # noqa: E402
from provider.hermes import HermesProvider  # noqa: E402


def test_generic_boundary_has_no_hermes_semantics() -> None:
    source = (SPIKE / "harness" / "runtime_boundary.py").read_text()
    assert "hermes" not in source.lower()
    assert "/v1/" not in source
    assert "profile" not in source.lower()


def test_provider_translates_invocation(monkeypatch, tmp_path) -> None:
    provider = HermesProvider("test", "image", tmp_path, "redacted-key", 8642)
    monkeypatch.setattr(
        provider,
        "_request",
        lambda *args, **kwargs: {
            "choices": [{"message": {"content": "provider result"}}]
        },
    )
    result = provider.invoke(RuntimeRequest("hello", "corr-1"))
    assert result.output == "provider result"
    assert result.correlation_id == "corr-1"


def test_provider_distinguishes_container_and_gateway(monkeypatch, tmp_path) -> None:
    provider = HermesProvider("test", "image", tmp_path, "redacted-key", 8642)
    monkeypatch.setattr(provider, "_container_running", lambda: True)

    def unavailable(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(provider, "_request", unavailable)
    health = provider.health()
    assert health.infrastructure_available is True
    assert health.runtime_available is False
    assert health.task_ready is False
    assert health.state is RuntimeState.UNAVAILABLE


def test_detailed_health_does_not_claim_task_readiness(monkeypatch, tmp_path) -> None:
    provider = HermesProvider("test", "image", tmp_path, "redacted-key", 8642)
    monkeypatch.setattr(provider, "_container_running", lambda: True)
    responses = iter([{"status": "ok"}, {"status": "ok"}])
    monkeypatch.setattr(provider, "_request", lambda *args, **kwargs: next(responses))
    health = provider.health()
    assert health.state is RuntimeState.READY
    assert health.runtime_available is True
    assert health.dependency_available is None
    assert health.task_ready is None
