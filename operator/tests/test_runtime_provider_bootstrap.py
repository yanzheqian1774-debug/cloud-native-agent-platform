import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_operator import main
from agent_operator.runtime_provider_bootstrap import (
    BOOTSTRAP_ENVIRONMENT,
    RuntimeProviderBootstrapError,
    assemble_production_runtime_provider,
)
from agent_operator.runtime_provider_factory import RuntimeProviderKind
from agent_runtime.providers.openclaw import EXACT_TARGET
from agent_runtime.providers.openclaw.models import ReasonCode


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value))


def _bootstrap_fixture(tmp_path: Path) -> tuple[Path, Path]:
    profile_path = tmp_path / "runtime-profile.json"
    bootstrap_path = tmp_path / "bootstrap.json"
    revision = {
        "revisionId": "runtime-profile-revision-1",
        "state": "PUBLISHED",
        "content": {
            "provider": "OPENCLAW",
            "openClawPackageRef": "declaration-only:openclaw-package",
            "secretReferences": ["secret-ref:openclaw-gateway"],
        },
    }
    _write_json(
        profile_path,
        {
            "profile": {
                "profileId": "runtime-profile-1",
                "lifecycleState": "PUBLISHED",
                "publishedRevisionId": revision["revisionId"],
                "revisions": [revision],
            }
        },
    )
    _write_json(
        bootstrap_path,
        {
            "schemaVersion": "s5-v023-openclaw-bootstrap/v1",
            "runtimeProfilePath": str(profile_path),
            "targetManifestPath": str(tmp_path / "target.json"),
            "packageLockPath": str(tmp_path / "package-lock.json"),
            "nodeExecutable": str(tmp_path / "node"),
            "openClawEntrypoint": str(tmp_path / "openclaw.mjs"),
            "clientConfigPath": str(tmp_path / "client.json"),
            "clientStateDir": str(tmp_path / "client-state"),
            "agentId": "platform-agent",
            "agentWorkspace": str(tmp_path / "agent-workspace"),
            "gatewaySecretReference": "secret-ref:openclaw-gateway",
            "timeoutSeconds": 10,
            "freshnessSeconds": 30,
        },
    )
    return bootstrap_path, profile_path


def test_assembly_uses_published_profile_and_explicit_openclaw_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap_path, _ = _bootstrap_fixture(tmp_path)
    captured = {}

    class Transport:
        def __init__(self, config, credentials):
            captured["config"] = config
            captured["credentials"] = credentials

        def preflight(self):
            return EXACT_TARGET

    monkeypatch.setattr(
        "agent_operator.runtime_provider_bootstrap.OpenClawProductionTransport",
        Transport,
    )

    adapter = assemble_production_runtime_provider(
        bootstrap_path,
        environment={"OPENCLAW_GATEWAY_TOKEN": "fixture-token"},
    )

    assert adapter.provider_kind is RuntimeProviderKind.OPENCLAW
    assert captured["config"].gateway_secret_reference == (
        "secret-ref:openclaw-gateway"
    )
    assert (
        captured["credentials"].resolve("secret-ref:openclaw-gateway")
        == "fixture-token"
    )


@pytest.mark.parametrize("mutation", ["unpublished", "secret-mismatch"])
def test_assembly_rejects_unpublished_or_unprojected_profile_identity(
    tmp_path: Path, mutation: str
) -> None:
    bootstrap_path, profile_path = _bootstrap_fixture(tmp_path)
    if mutation == "unpublished":
        profile = json.loads(profile_path.read_text())
        profile["profile"]["lifecycleState"] = "DRAFT"
        _write_json(profile_path, profile)
    else:
        bootstrap = json.loads(bootstrap_path.read_text())
        bootstrap["gatewaySecretReference"] = "secret-ref:another-secret"
        _write_json(bootstrap_path, bootstrap)

    with pytest.raises(
        RuntimeProviderBootstrapError,
        match=ReasonCode.CONFIGURATION_MISSING.value,
    ):
        assemble_production_runtime_provider(
            bootstrap_path,
            environment={"OPENCLAW_GATEWAY_TOKEN": "fixture-token"},
        )


def test_operator_startup_executes_configured_production_assembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap_path, _ = _bootstrap_fixture(tmp_path)
    adapter = SimpleNamespace(provider_kind=RuntimeProviderKind.OPENCLAW)
    assemble = Mock(return_value=adapter)
    logger = Mock()
    monkeypatch.setenv(BOOTSTRAP_ENVIRONMENT, str(bootstrap_path))
    monkeypatch.setattr(main, "assemble_production_runtime_provider", assemble)

    main.startup(logger)

    assemble.assert_called_once_with(bootstrap_path)
    assert main.PRODUCTION_RUNTIME_ADAPTER is adapter
    logger.info.assert_called_once_with(
        "Enterprise Agent OS operator starting; runtime provider=openclaw"
    )
