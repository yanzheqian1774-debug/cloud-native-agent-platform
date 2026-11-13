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
