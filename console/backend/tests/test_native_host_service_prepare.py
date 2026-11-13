"""Offline configuration inherits current scope; never connects or activates."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from agent_operator import native_host_service_prepare as module
from agent_operator.native_host_service_prepare import prepare
from test_owned_business_policy import document


@pytest.fixture
def prepared_inputs(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("offline preparation must not connect")

    monkeypatch.setattr(psycopg, "connect", forbidden)
    policy = document()
    policy.update(
        enabled=True, expiresAt=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    )
    owned = tmp_path / "owned.json"
    owned.write_text(json.dumps(policy))
    owned.chmod(0o600)
    monkeypatch.setenv("OWNED_BUSINESS_ADMISSION_POLICY", str(owned))
    for name in (
        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
        "NATIVE_DISPATCH_CONTINUATION_POLICY",
    ):
        path = tmp_path / (name + ".json")
        path.write_text('{"controlled":true}')
        path.chmod(0o600)
        monkeypatch.setenv(name, str(path))
    monkeypatch.delenv("NATIVE_LOOP_RUNTIME_FILE", raising=False)
    loaded = Path(module.__file__).resolve()
    root = loaded.parents[3]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": str(root),
                "sourceHashes": {
                    str(loaded.relative_to(root)): hashlib.sha256(
                        loaded.read_bytes()
                    ).hexdigest()
                },
            }
        )
    )
    return (
        owned,
        policy,
        manifest,
        tmp_path / "state",
        tmp_path / "output" / "service.json",
    )


def test_offline_default_disabled_inherits_scope_and_does_not_change_policy(
    prepared_inputs,
):
    owned, policy, manifest, state, output = prepared_inputs
    before = owned.read_bytes()
    result = prepare(manifest, state, output)
    saved = json.loads(output.read_text())
    assert result["enabled"] is saved["enabled"] is False
    assert (saved["namespace"], saved["securityDomain"], saved["principalId"]) == (
        policy["tenantId"],
        policy["securityDomain"],
        policy["subjectId"],
    )
    assert not state.exists()  # No service process or process directory created.
    assert owned.read_bytes() == before
    assert "authorizationResources" not in saved
    assert "scopes" not in saved and "allowanceId" not in saved
    with pytest.raises(FileExistsError):
        prepare(manifest, state, output, enabled=True)


def test_expired_authority_is_not_extended_to_make_service_start(prepared_inputs):
    owned, policy, manifest, state, output = prepared_inputs
    policy["expiresAt"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    owned.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match="CURRENT_OWNED_POLICY_REQUIRED"):
        prepare(manifest, state, output, enabled=True)
    assert not output.exists()
