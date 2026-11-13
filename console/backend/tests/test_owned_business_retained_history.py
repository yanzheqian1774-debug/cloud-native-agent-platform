"""Policy versions retain exact history without retaining execution authority."""

import json
from copy import deepcopy

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_retained_history import configured_paths
from agent_console.owned_business_work_reader import OwnedBusinessWorkReader
from test_owned_business_policy import document


def write(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


def policies(tmp_path):
    old = document()
    old["enabled"] = True
    new = {**old, "policyVersion": "2", "expiresAt": "2026-12-12T23:30:12Z"}
    return write(tmp_path / "old.json", old), write(tmp_path / "new.json", new), old


def test_retention_default_off_and_explicit_exact_version(tmp_path):
    old, new, _ = policies(tmp_path)
    assert not OwnedBusinessWorkReader(new, None, 33, 1).retained_history
    reader = OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old])
    assert len(reader.retained_history) == 1
    retained = next(iter(reader.retained_history.values()))
    assert retained.path == str(old) and not retained.retained_history
    assert retained.policy.expiresAt < reader.policy.expiresAt


@pytest.mark.parametrize(
    "value", ["{}", '"/private/a"', '["relative"]', '["/a","/a"]', "[false]", "broken"]
)
def test_configuration_rejects_unbounded_or_ambiguous_paths(value):
    with pytest.raises(AuthorityError, match="RETAINED_HISTORY_INVALID"):
        configured_paths(value)


@pytest.mark.parametrize(
    "field", ["subjectId", "accountId", "allowanceId", "ledgerId", "rootPolicyDigest"]
)
def test_retention_cannot_mix_another_perimeter(tmp_path, field):
    old, new, value = policies(tmp_path)
    value[field] = "f" * 64 if field.endswith("Digest") else "other"
    write(old, value)
    expected = (
        "POLICY_INVALID"
        if field in {"subjectId", "accountId", "ledgerId"}
        else "RETAINED_HISTORY_INVALID"
    )
    with pytest.raises(AuthorityError, match=expected):
        OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old])


def test_retention_cannot_add_source_or_duplicate_digest(tmp_path):
    old, new, value = policies(tmp_path)
    changed = deepcopy(value)
    changed["scopes"][0]["sourceContentDigest"] = "f" * 64
    write(old, changed)
    with pytest.raises(AuthorityError, match="RETAINED_HISTORY_INVALID"):
        OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old])
    write(old, value)
    copy = write(tmp_path / "duplicate.json", value)
    with pytest.raises(AuthorityError, match="RETAINED_HISTORY_INVALID"):
        OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old, copy])
