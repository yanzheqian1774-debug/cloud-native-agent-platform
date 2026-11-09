from types import SimpleNamespace

from agent_console.readonly_continuation import resource_policy_digest
from agent_console.resource_policy_contract import DevelopmentAdministratorReview


def test_preparation_lookup_matches_current_role_generation_not_legacy_policy():
    automation = SimpleNamespace(policy=SimpleNamespace(digest="legacy-policy"))
    call = SimpleNamespace(
        context=SimpleNamespace(principal_id="human:development-admin"),
        policy_generation=18,
    )
    prepared = DevelopmentAdministratorReview("human:development-admin", 18, "a" * 64)
    assert resource_policy_digest(automation, call, True) == prepared.policy_digest
    assert resource_policy_digest(automation, call, False) == "legacy-policy"
    call.policy_generation = 19
    assert resource_policy_digest(automation, call, True) != prepared.policy_digest
    call.context.principal_id = "human:other"
    assert resource_policy_digest(automation, call, True) != prepared.policy_digest
