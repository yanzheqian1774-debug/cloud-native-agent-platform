"""Team owner selection reuses account identity without granting authority."""

from types import SimpleNamespace as S
from unittest.mock import Mock

import pytest
from agent_console import workbench_team_people as module
from agent_console.team_definition import TeamDefinitionError


def setup(monkeypatch, admin=True):
    scope = S(tenant_id="tenant", security_domain="domain")
    binding = S(
        credential_id="local-account:bob",
        grant_source_id="grant:bob",
        username="bob",
        principal_id="human:bob",
        scope=scope,
    )
    generation = S(
        generation=18, local_accounts=(binding,), credential_revocation_tombstones=set()
    )
    row = dict(
        account_id=binding.credential_id,
        username="bob",
        principal_id="human:bob",
        tenant_id="tenant",
        security_domain="domain",
        status="ENABLED",
    )
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = [row]
    call = S(
        context=S(principal_id="human:alice", scope=scope),
        connection=connection,
        policy_generation=18,
        authority=S(adapter=S(authorization=S(generation=generation))),
    )
    monkeypatch.setattr(module, "for_call", lambda _: admin)
    return call, generation, row


def test_admin_can_select_current_same_scope_account_without_secret_projection(
    monkeypatch,
):
    call, _, _ = setup(monkeypatch)
    items = module.candidates(call)
    assert items[1] == {
        "principalId": "human:bob",
        "label": "bob",
        "source": "LOCAL_TEST_ACCOUNT",
    }
    assert all(set(item) == {"principalId", "label", "source"} for item in items)
    module.validate_owner(call, "human:bob", "human:alice")
    assert "FOR SHARE" in call.connection.execute.call_args.args[0]


def test_ordinary_caller_cannot_enumerate_or_assign_other_account(monkeypatch):
    call, _, _ = setup(monkeypatch, admin=False)
    assert [x["principalId"] for x in module.candidates(call)] == ["human:alice"]
    call.connection.execute.assert_not_called()
    with pytest.raises(TeamDefinitionError, match="TEAM_OWNER_UNAVAILABLE"):
        module.validate_owner(call, "human:bob", "human:alice")


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "DISABLED"),
        ("status", "REVOKED"),
        ("tenant_id", "other"),
        ("security_domain", "other"),
        ("principal_id", "human:other"),
        ("username", "renamed"),
    ],
)
def test_stale_or_foreign_selection_rejected(monkeypatch, field, value):
    call, _, row = setup(monkeypatch)
    row[field] = value
    with pytest.raises(TeamDefinitionError, match="TEAM_OWNER_UNAVAILABLE"):
        module.validate_owner(call, "human:bob", "human:alice")


def test_tombstones_and_generation_change_are_not_current_candidates(monkeypatch):
    call, generation, _ = setup(monkeypatch)
    generation.credential_revocation_tombstones.add("grant:bob")
    assert len(module.candidates(call)) == 1
    call.connection.execute.assert_not_called()
    generation.generation = 19
    with pytest.raises(TeamDefinitionError, match="TEAM_OWNER_SOURCE_CHANGED"):
        module.candidates(call)


def test_historical_owner_can_be_retained_without_reactivating_identity(monkeypatch):
    call, _, _ = setup(monkeypatch, admin=False)
    module.validate_owner(call, "human:historical", "human:historical")
    call.connection.execute.assert_not_called()
