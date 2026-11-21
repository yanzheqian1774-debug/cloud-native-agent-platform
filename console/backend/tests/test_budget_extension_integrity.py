"""Typed audit-column and private deployment-file boundaries, no database."""

import json
from types import SimpleNamespace

import pytest
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.draft_provider_budget_postgres import _digest
from agent_console.provider_budget_extension import (
    Selection,
    _validate_activation,
    configure_from_environment,
)


def selection():
    return Selection(
        schemaVersion="provider-budget-extension-selection.v1",
        namespace="n",
        securityDomain="d",
        ledgerId="l",
        allowanceId="a",
        extensionId="e",
        extensionDigest="a" * 64,
        authorizationEvidenceDigest="b" * 64,
    )


@pytest.mark.parametrize(
    "mutation", ["schema", "command", "allowance", "extension", "extra", "selection"]
)
def test_activation_corruption_rejected_even_with_rehashed_record(mutation):
    selected = selection()
    record = {
        "schemaVersion": "provider-budget-extension-activation.v1",
        "selection": selected.model_dump(mode="json"),
        "commandId": "one",
    }
    row = {
        "allowance_id": "a",
        "extension_id": "e",
        "command_id": "one",
        "record": record,
        "digest": _digest(record),
    }
    _validate_activation(
        row, selected, SimpleNamespace(allowanceId="a", extensionId="e")
    )
    if mutation == "schema":
        record["schemaVersion"] = "not-activation"
    elif mutation == "command":
        row["command_id"] = "two"
    elif mutation == "allowance":
        row["allowance_id"] = "other"
    elif mutation == "extension":
        row["extension_id"] = "other"
    elif mutation == "extra":
        record["pretendHumanReviewed"] = True
    else:
        record["selection"]["authorizationEvidenceDigest"] = "c" * 64
    row["digest"] = _digest(record)
    with pytest.raises(DraftAssistanceError):
        _validate_activation(
            row, selected, SimpleNamespace(allowanceId="a", extensionId="e")
        )


@pytest.mark.parametrize("mutation", ["mode", "symlink", "owner", "duplicate"])
def test_private_file_failure_precedes_any_database_access(
    tmp_path, monkeypatch, mutation
):
    import os

    target = tmp_path / "selection.json"
    target.write_text(json.dumps(selection().model_dump(mode="json")))
    target.chmod(0o600)
    if mutation == "mode":
        target.chmod(0o644)
    elif mutation == "symlink":
        link = tmp_path / "linked.json"
        link.symlink_to(target)
        target = link
    elif mutation == "owner":
        uid = os.getuid()
        monkeypatch.setattr(os, "getuid", lambda: uid + 1)
    else:
        target.write_text('{"extensionId":"one","extensionId":"two"}')

    def forbidden():
        pytest.fail("must reject before reading database")

    owner = SimpleNamespace(_connection=forbidden)
    with pytest.raises(DraftAssistanceError, match="CONFIGURATION_INVALID"):
        configure_from_environment(
            owner, {"PROVIDER_BUDGET_EXTENSION_POLICY": str(target)}
        )
    assert not hasattr(owner, "budget_extension")
