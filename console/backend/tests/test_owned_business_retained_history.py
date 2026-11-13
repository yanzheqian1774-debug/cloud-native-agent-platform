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


def typed_policies(tmp_path):
    from agent_console.owned_business_policy import OwnedBusinessPolicy

    old, new, value = policies(tmp_path)
    digest = OwnedBusinessPolicy.load(old).digest
    changed = json.loads(new.read_text())
    changed.update(
        schemaVersion="owned-business-admission.v2",
        retainedReadPolicyDigests=[digest],
        adoptionPolicyDigest="f" * 64,
    )
    for field in ("skills", "employees"):
        changed["scopes"][0][field][0]["revision_id"] += ":typed"
    write(new, changed)
    return old, new, value


def test_v2_exact_old_policy_constructs_read_only_reader_without_changing_v1(tmp_path):
    from agent_console.owned_business_policy import OwnedBusinessPolicy
    from agent_console.resource_use_domain import canonical_digest

    old, new, _ = typed_policies(tmp_path)
    policy = OwnedBusinessPolicy.load(old)
    assert policy.digest == canonical_digest(policy.model_dump(mode="json"))
    assert "retainedReadPolicyDigests" not in policy.model_dump()
    reader = OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old])
    retained = reader.retained_history[policy.digest]
    assert retained.policy == policy
    with pytest.raises(AuthorityError, match="HISTORY_ONLY"):
        retained.work(None, None, None)
    with pytest.raises(AuthorityError, match="HISTORY_ONLY"):
        retained.planning_basis(None, None, None)


@pytest.mark.parametrize("kind", ["missing", "wrong", "duplicate", "unknown-schema"])
def test_v2_requires_complete_explicit_pins(tmp_path, kind):
    old, new, _ = typed_policies(tmp_path)
    current = json.loads(new.read_text())
    paths = [old]
    if kind == "missing":
        paths = []
    elif kind == "wrong":
        current["retainedReadPolicyDigests"] = ["0" * 64]
    elif kind == "duplicate":
        current["retainedReadPolicyDigests"] *= 2
    else:
        current["schemaVersion"] = "owned-business-admission.v3"
    write(new, current)
    with pytest.raises(AuthorityError):
        OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=paths)


@pytest.mark.parametrize(
    "field",
    [
        "authorizationBasisDigest",
        "agents",
        "runtimes",
        "operations",
        "sourceContentDigest",
        "documentRules",
        "capability",
        "scopeId",
    ],
)
def test_v2_pin_cannot_relax_business_perimeter(tmp_path, field):
    old, new, _ = typed_policies(tmp_path)
    current = json.loads(new.read_text())
    scope = current["scopes"][0]
    if field in {"authorizationBasisDigest", "sourceContentDigest"}:
        scope[field] = "0" * 64
    elif field in {"agents", "runtimes"}:
        scope[field][0]["revision_id"] += ":other"
    elif field == "operations":
        scope[field] = ["other"]
    elif field == "documentRules":
        scope[field]["scope"] = "other"
    elif field == "capability":
        scope[field] = scope["agents"][0]
    else:
        scope[field] = "other"
    write(new, current)
    with pytest.raises(AuthorityError, match="RETAINED_HISTORY_INVALID"):
        OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old])


def test_v1_digest_matches_pre_successor_base_faef():
    from agent_console.owned_business_policy import OwnedBusinessPolicy

    assert OwnedBusinessPolicy.model_validate(document()).digest == (
        "3c906dc081bd69b91293b2505e3a8143e8df9a5dd344729ea9c616866d0a5e83"
    )


@pytest.mark.parametrize(
    "field",
    ["rootPolicyDigest", "rootUnderstandingPolicyDigest", "allowanceId", "policyId"],
)
def test_v2_pins_do_not_relax_root_or_budget_identity(tmp_path, field):
    old, new, _ = typed_policies(tmp_path)
    current = json.loads(new.read_text())
    current[field] = "0" * 64 if field.endswith("Digest") else "other"
    write(new, current)
    with pytest.raises(AuthorityError, match="RETAINED_HISTORY_INVALID"):
        OwnedBusinessWorkReader(new, None, 33, 1, retained_history_paths=[old])
