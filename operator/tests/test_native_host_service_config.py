"""Pinned deployment configuration only; no production composition is started."""

import hashlib
import json
from pathlib import Path

import pytest
from agent_operator import native_host_service_config as module
from agent_operator.native_host_service_config import Configuration
from agent_operator.native_host_service_state import write


@pytest.fixture
def configured(tmp_path, monkeypatch):
    loaded = Path(module.__file__).resolve()
    root = loaded.parents[3]
    names = (
        "native_host_service.py",
        "native_host_service_config.py",
        "native_host_service_discovery.py",
        "native_host_service_state.py",
        "native_host_service_child.py",
        "native_dispatch_host.py",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": str(root),
                "sourceHashes": {
                    str(loaded.with_name(n).relative_to(root)): hashlib.sha256(
                        loaded.with_name(n).read_bytes()
                    ).hexdigest()
                    for n in names
                },
            }
        )
    )
    policy_files = {}
    for i, name in enumerate(
        (
            "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
            "NATIVE_DISPATCH_CONTINUATION_POLICY",
            "OWNED_BUSINESS_ADMISSION_POLICY",
        )
    ):
        path = tmp_path / f"policy-{i}.json"
        write(path, {"controlled": True})
        monkeypatch.setenv(name, str(path))
        policy_files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in (
        "NATIVE_LOOP_RUNTIME_FILE",
        "NATIVE_DURABLE_WAIT_CONFIGURATION",
        "NATIVE_HOST_SERVICE_LOCK_FD",
        "NATIVE_HOST_SERVICE_READY_FD",
        "NATIVE_HOST_SERVICE_CONTROL_FD",
        "NATIVE_HOST_STARTUP_CONFIGURATION",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NATIVE_DISPATCH_PREPARED_SKILL", "registered-readonly-v1")
    value = {
        "enabled": True,
        "namespace": "ns",
        "securityDomain": "d",
        "principalId": "human:a",
        "stateDirectory": str(tmp_path / "state"),
        "manifestPath": str(manifest),
        "manifestDigest": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "policyFiles": policy_files,
        "maxHosts": 2,
        "maxRestarts": 3,
        "pollSeconds": 1,
        "readinessSeconds": 2,
        "shutdownSeconds": 2,
    }
    config = tmp_path / "service.json"
    write(config, value)
    return config, value


def test_pins_actual_installed_files_and_current_policy(
    configured, monkeypatch, tmp_path
):
    path, _ = configured
    config = Configuration(path)
    config.verify()
    import os

    old = Path(os.environ["OWNED_BUSINESS_ADMISSION_POLICY"])
    old.write_text("changed")
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()


@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", False),
        ("maxHosts", 9),
        ("maxHosts", True),
        ("maxRestarts", 33),
        ("readinessSeconds", 30),
    ],
)
def test_invalid_or_disabled_never_starts(configured, field, value):
    path, config = configured
    config[field] = value
    write(path, config)
    with pytest.raises(ValueError):
        Configuration(path)


def test_ambient_unpinned_runtime_or_nested_launch_rejected(configured, monkeypatch):
    path, _ = configured
    monkeypatch.setenv("NATIVE_LOOP_RUNTIME_FILE", "/not/pinned")
    with pytest.raises(ValueError, match="POLICY_BINDING"):
        Configuration(path)
    monkeypatch.delenv("NATIVE_LOOP_RUNTIME_FILE")
    monkeypatch.setenv("NATIVE_HOST_SERVICE_CONTROL_FD", "9")
    with pytest.raises(ValueError, match="NESTED"):
        Configuration(path)


def test_durable_configuration_is_optional_but_must_be_pinned(
    configured, monkeypatch, tmp_path
):
    path, value = configured
    Configuration(path).verify()
    wait = tmp_path / "wait.json"
    write(wait, {"controlled": True})
    monkeypatch.setenv("NATIVE_DURABLE_WAIT_CONFIGURATION", str(wait))
    with pytest.raises(ValueError, match="POLICY_BINDING"):
        Configuration(path)
    value["policyFiles"]["NATIVE_DURABLE_WAIT_CONFIGURATION"] = hashlib.sha256(
        wait.read_bytes()
    ).hexdigest()
    write(path, value)
    config = Configuration(path)
    config.verify()
    wait.write_text("changed")
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()


@pytest.mark.parametrize("durable", [False, True])
def test_preparation_roundtrip_pins_optional_wait_file(
    configured, monkeypatch, tmp_path, durable
):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from agent_console.owned_business_policy import OwnedBusinessPolicy
    from agent_operator.native_host_service_prepare import prepare

    _, value = configured
    monkeypatch.setattr(
        OwnedBusinessPolicy,
        "load",
        lambda _: SimpleNamespace(
            enabled=True,
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
            tenantId="ns",
            securityDomain="d",
            subjectId="human:a",
            digest="a" * 64,
        ),
    )
    wait = tmp_path / "optional-wait.json"
    if durable:
        write(wait, {"controlled": True})
        monkeypatch.setenv("NATIVE_DURABLE_WAIT_CONFIGURATION", str(wait))
    output = tmp_path / "prepared" / "service.json"
    prepare(value["manifestPath"], tmp_path / "new-state", output, enabled=True)
    config = Configuration(output)
    config.verify()
    assert (
        "NATIVE_DURABLE_WAIT_CONFIGURATION" in config.value["policyFiles"]
    ) is durable
    if durable:
        assert config.value["policyFiles"]["NATIVE_DURABLE_WAIT_CONFIGURATION"] == (
            hashlib.sha256(wait.read_bytes()).hexdigest()
        )
        wait.write_text("changed")
        with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
            config.verify()


def test_optional_ontology_correction_must_be_pinned(configured, monkeypatch, tmp_path):
    path, value = configured
    candidate = tmp_path / "correction.json"
    write(candidate, {"controlled": "correction"})
    monkeypatch.setenv("OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY", str(candidate))
    with pytest.raises(ValueError, match="POLICY_BINDING_REQUIRED"):
        Configuration(path)
    value["policyFiles"]["OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY"] = hashlib.sha256(
        candidate.read_bytes()
    ).hexdigest()
    write(path, value)
    config = Configuration(path)
    config.verify()
    write(candidate, {"controlled": "changed"})
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()
