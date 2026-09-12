"""Production bootstrap for one explicitly selected Runtime Profile provider."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from agent_runtime.providers.openclaw import (
    EnvironmentSecretReferenceResolver,
    OpenClawProductionConfig,
    OpenClawProductionTransport,
    OpenClawRuntimeProvider,
)
from agent_runtime.providers.openclaw.models import ReasonCode

from agent_operator.openclaw_runtime_adapter import OpenClawRuntimeApplicationAdapter
from agent_operator.runtime_provider_factory import (
    RuntimeApplicationAdapter,
    RuntimeProviderFactory,
)

BOOTSTRAP_ENVIRONMENT = "AGENT_RUNTIME_PROVIDER_BOOTSTRAP_FILE"
_SCHEMA = "s5-v023-openclaw-bootstrap/v1"
_MAX_DOCUMENT_BYTES = 1_048_576
_GATEWAY_SECRET_REFERENCE = "secret-ref:openclaw-gateway"
_FIELDS = {
    "schemaVersion",
    "runtimeProfilePath",
    "targetManifestPath",
    "packageLockPath",
    "nodeExecutable",
    "openClawEntrypoint",
    "clientConfigPath",
    "clientStateDir",
    "agentId",
    "agentWorkspace",
    "gatewaySecretReference",
    "timeoutSeconds",
    "freshnessSeconds",
}


class RuntimeProviderBootstrapError(ValueError):
    """Stable configuration failure without raw document or secret disclosure."""


def assemble_production_runtime_provider(
    bootstrap_path: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> RuntimeApplicationAdapter:
    """Build and preflight exactly one provider selected by a published profile."""
    document = _read_object(bootstrap_path)
    if set(document) != _FIELDS or document.get("schemaVersion") != _SCHEMA:
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    profile = _published_profile(_absolute_path(document, "runtimeProfilePath"))
    content = profile["content"]
    if content.get("provider") != "OPENCLAW":
        raise RuntimeProviderBootstrapError("RUNTIME_PROVIDER_UNKNOWN")
    package_ref = content.get("openClawPackageRef")
    if not isinstance(package_ref, str) or not package_ref.strip():
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    secret_reference = _text(document, "gatewaySecretReference")
    secret_references = content.get("secretReferences")
    if (
        secret_reference != _GATEWAY_SECRET_REFERENCE
        or not isinstance(secret_references, list)
        or secret_references.count(secret_reference) != 1
    ):
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    timeout = document.get("timeoutSeconds")
    freshness = document.get("freshnessSeconds")
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not 0 < timeout <= 60
        or not isinstance(freshness, int)
        or isinstance(freshness, bool)
        or not 1 <= freshness <= 300
    ):
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    config = OpenClawProductionConfig(
        manifest_path=_absolute_path(document, "targetManifestPath"),
        package_lock_path=_absolute_path(document, "packageLockPath"),
        node_executable=_absolute_path(document, "nodeExecutable"),
        openclaw_entrypoint=_absolute_path(document, "openClawEntrypoint"),
        client_config_path=_absolute_path(document, "clientConfigPath"),
        client_state_dir=_absolute_path(document, "clientStateDir"),
        agent_id=_text(document, "agentId"),
        agent_workspace=_absolute_path(document, "agentWorkspace"),
        gateway_secret_reference=secret_reference,
        timeout_seconds=float(timeout),
        freshness_seconds=freshness,
    )
    resolver = EnvironmentSecretReferenceResolver(
        secret_reference,
        environment=os.environ if environment is None else environment,
    )
    provider = OpenClawRuntimeProvider(OpenClawProductionTransport(config, resolver))
    try:
        provider.preflight()
    except ValueError as exc:
        raise RuntimeProviderBootstrapError(str(exc)) from None
    openclaw = OpenClawRuntimeApplicationAdapter(provider)
    return RuntimeProviderFactory(openclaw=openclaw).create(("openclaw",))


def _published_profile(path: Path) -> dict[str, object]:
    document = _read_object(path)
    profile = document.get("profile")
    if not isinstance(profile, dict):
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    published_id = profile.get("publishedRevisionId")
    revisions = profile.get("revisions")
    if (
        profile.get("lifecycleState") != "PUBLISHED"
        or not isinstance(published_id, str)
        or not isinstance(revisions, list)
    ):
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    matches = [
        item
        for item in revisions
        if isinstance(item, dict)
        and item.get("revisionId") == published_id
        and item.get("state") == "PUBLISHED"
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("content"), dict):
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    return matches[0]


def _read_object(path: Path) -> dict[str, object]:
    try:
        if not path.is_absolute() or path.stat().st_size > _MAX_DOCUMENT_BYTES:
            raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
        value = json.loads(path.read_text())
    except RuntimeProviderBootstrapError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeProviderBootstrapError(
            ReasonCode.CONFIGURATION_MISSING.value
        ) from None
    if not isinstance(value, dict):
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    return value


def _text(document: Mapping[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > 512:
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    return value


def _absolute_path(document: Mapping[str, object], field: str) -> Path:
    path = Path(_text(document, field))
    if not path.is_absolute():
        raise RuntimeProviderBootstrapError(ReasonCode.CONFIGURATION_MISSING.value)
    return path
