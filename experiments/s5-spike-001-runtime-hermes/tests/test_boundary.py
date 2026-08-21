import json
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
    assert provider.last_invocation_evidence == {
        "http_status": 200,
        "runtime_id": None,
        "runtime_model": None,
        "finish_reason": None,
        "usage": None,
    }


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


def test_checkpoint_b_manifest_is_spike_isolated() -> None:
    manifest = (SPIKE / "manifests" / "checkpoint-b-kubernetes.yaml").read_text()
    assert "namespace: s5-spike-001" in manifest
    assert 's5-spike-001: "true"' in manifest
    assert "agentos.io" not in manifest
    assert "kind: Deployment" in manifest
    assert "emptyDir: {}" in manifest


def test_model_credential_is_inherited_by_name(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KIMI_CN_API_KEY", "test-only-value")
    calls = []

    def capture(command, **kwargs):
        calls.append(command)

    monkeypatch.setattr("provider.hermes.subprocess.run", capture)
    provider = HermesProvider(
        "test",
        "image",
        tmp_path,
        "gateway-key",
        8642,
        inference_provider="kimi-coding-cn",
        model="kimi-k3",
        model_credential_env="KIMI_CN_API_KEY",
    )
    provider.provision()
    command = calls[0]
    assert "KIMI_CN_API_KEY" in command
    assert "test-only-value" not in command


def test_provider_configures_non_secret_model_selection(monkeypatch, tmp_path) -> None:
    calls = []

    def capture(command, **kwargs):
        calls.append(command)

    monkeypatch.setattr("provider.hermes.subprocess.run", capture)
    provider = HermesProvider(
        "test",
        "image",
        tmp_path,
        "gateway-key",
        8642,
        inference_provider="kimi-coding-cn",
        model="kimi-k3",
    )
    provider.configure()
    assert calls[0][-4:] == ["config", "set", "model.provider", "kimi-coding-cn"]
    assert calls[1][-4:] == ["config", "set", "model.default", "kimi-k3"]


def test_temporary_credential_binding_does_not_put_value_in_argv(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("KIMI_CN_API_KEY", "test-only-value")
    calls = []

    def capture(command, **kwargs):
        calls.append(command)

    monkeypatch.setattr("provider.hermes.subprocess.run", capture)
    provider = HermesProvider(
        "test",
        "image",
        tmp_path,
        "gateway-key",
        8642,
        model_credential_env="KIMI_CN_API_KEY",
    )
    provider.bind_model_credential()
    command = calls[0]
    assert "KIMI_CN_API_KEY" in command
    assert not any("test-only-value" in argument for argument in command)
    assert "chown hermes:hermes /opt/data/.env" in command[-1]


def test_sanitized_preflight_never_returns_credential_value(
    monkeypatch, tmp_path
) -> None:
    secret = "test-only-value"

    def capture(command, **kwargs):
        assert secret not in command

        class Result:
            stdout = json.dumps(
                {
                    "active_home": "/opt/data",
                    "configured_provider": "kimi-coding-cn",
                    "configured_model": "kimi-k3",
                    "resolved_provider": "kimi-coding-cn",
                    "resolved_model": "kimi-k3",
                    "credential_present": True,
                    "credential_key_present": True,
                    "credential_assignment_nonempty": True,
                    "env_mode": "0600",
                    "env_owner_uid": 1000,
                    "env_readable": True,
                    "multiplex_profiles": False,
                }
            )

        return Result()

    monkeypatch.setattr("provider.hermes.subprocess.run", capture)
    provider = HermesProvider("test", "image", tmp_path, "gateway-key", 8642)
    result = provider.sanitized_preflight()
    assert result["credential_present"] is True
    assert secret not in json.dumps(result)
