# ruff: noqa: F811 -- Imported isolated owner fixtures.
"""Optional budget selection is a current pinned policy, never ambient authority."""

import hashlib

import pytest
from agent_operator.native_host_service_config import Configuration
from agent_operator.native_host_service_state import write
from test_native_host_service_config import configured  # noqa: F401


def test_budget_extension_default_off_unpinned_and_changed_pin(
    configured,
    monkeypatch,
    tmp_path,
):
    path, value = configured
    Configuration(path).verify()
    extension = tmp_path / "extension.json"
    write(extension, {"controlledSelection": True})
    monkeypatch.setenv("PROVIDER_BUDGET_EXTENSION_POLICY", str(extension))
    with pytest.raises(ValueError, match="POLICY_BINDING"):
        Configuration(path)
    value["policyFiles"]["PROVIDER_BUDGET_EXTENSION_POLICY"] = hashlib.sha256(
        extension.read_bytes()
    ).hexdigest()
    write(path, value)
    loaded = Configuration(path)
    loaded.verify()
    write(extension, {"changed": True})
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        loaded.verify()


def test_cycle_cannot_inherit_unpinned_extension(tmp_path, monkeypatch):
    from agent_console.fixed_work_cycle_configuration import (
        CycleConfiguration,
        FilePin,
    )
    from test_fixed_work_cycle_entry import config

    value = config(tmp_path, enabled=True)
    # File/source inventory checks are independent of this ambient-policy boundary.
    from agent_console import fixed_work_cycle_configuration as module

    monkeypatch.setattr(module, "source_files", lambda _: value.sourceFiles)
    monkeypatch.setattr(FilePin, "verify", lambda self: self.path)
    monkeypatch.setenv("PROVIDER_BUDGET_EXTENSION_POLICY", str(tmp_path / "extra"))
    with pytest.raises(ValueError, match="BUDGET_EXTENSION_UNPINNED"):
        value.verify()
    pinned = CycleConfiguration.model_validate(
        {
            **value.model_dump(),
            "budgetExtension": {"path": tmp_path / "extra", "sha256": "a" * 64},
        }
    )
    pinned.verify()
