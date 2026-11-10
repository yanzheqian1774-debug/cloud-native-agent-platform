"""Bounded team owner candidates from the existing local account authority."""

from .development_administrator import for_call
from .local_accounts import account_binding_current
from .team_definition import TeamDefinitionError


def candidates(call, *, lock=False):
    """Not a person directory or a grant; expose only existing account labels."""
    actor = call.context.principal_id
    items = {actor: {"principalId": actor, "label": actor, "source": "CURRENT_SESSION"}}
    adapter = getattr(call.authority, "adapter", None)
    if adapter is None:
        return list(items.values())
    generation = adapter.authorization.generation
    if generation.generation != call.policy_generation:
        raise TeamDefinitionError("TEAM_OWNER_SOURCE_CHANGED")
    administrator = for_call(call)
    scope = call.context.scope
    bindings = [
        a
        for a in generation.local_accounts
        if a.scope == scope
        and account_binding_current(generation, a)
        and (administrator or a.principal_id == actor)
    ]
    if not bindings:
        return list(items.values())
    rows = call.connection.execute(
        "SELECT account_id,username,principal_id,tenant_id,security_domain,status "
        "FROM browser_identity.local_accounts WHERE account_id=ANY(%s) "
        "ORDER BY account_id" + (" FOR SHARE" if lock else ""),
        ([a.credential_id for a in bindings],),
    ).fetchall()
    expected = {a.credential_id: a for a in bindings}
    for row in rows:
        binding = expected.get(row["account_id"])
        if (
            binding is None
            or row["status"] != "ENABLED"
            or row["principal_id"] != binding.principal_id
            or row["username"] != binding.username
            or row["tenant_id"] != scope.tenant_id
            or row["security_domain"] != scope.security_domain
        ):
            continue
        items.setdefault(
            binding.principal_id,
            {
                "principalId": binding.principal_id,
                "label": binding.username,
                "source": "LOCAL_TEST_ACCOUNT",
            },
        )
        if binding.principal_id == actor:
            items[actor] = {
                "principalId": actor,
                "label": binding.username,
                "source": "LOCAL_TEST_ACCOUNT",
            }
    return sorted(items.values(), key=lambda item: item["principalId"])


def validate_owner(call, selected, previous):
    # Retaining a historical reference neither reassigns nor activates its account.
    if selected == previous or selected == call.context.principal_id:
        return
    if not any(item["principalId"] == selected for item in candidates(call, lock=True)):
        raise TeamDefinitionError("TEAM_OWNER_UNAVAILABLE")
