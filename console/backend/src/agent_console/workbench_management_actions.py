"""Read-only management action observations, never command authorizations."""

from .authority_contracts import AuthorityError, ExactGrant


def projection(call, actions, *, target=None):
    names = tuple(actions)
    unavailable = False
    try:
        allowed = call.authority.current_action_grants(
            tuple(actions[name][0] for name in names)
        )
        if len(allowed) != len(names):
            unavailable = True
    except AuthorityError as exc:
        if str(exc) != "AUTHORIZATION_STATE_UNAVAILABLE":
            raise
        unavailable = True
    if unavailable:
        names = ()
        allowed = ()
    return {
        "status": "UNAVAILABLE" if unavailable else "AVAILABLE",
        "subjectId": call.context.principal_id,
        "tenantId": call.context.scope.tenant_id,
        "securityDomain": call.context.scope.security_domain,
        "generation": call.authority.generation,
        "recoveryEpoch": call.authority.adapter.controller.readiness.recovery_epoch,
        "readAt": call.authority.adapter.clock().isoformat(),
        "target": target,
        "actions": {
            name: {
                "authorized": bool(allowed[i]),
                "lifecycleEligible": actions[name][1],
            }
            for i, name in enumerate(names)
        },
        "authorityGranted": False,
        "executionStarted": False,
    }


def collection_projection(call, owner):
    return projection(
        call,
        {"CREATE": (ExactGrant(owner, "CREATE", owner.lower() + ":collection"), True)},
    )


def employee_projection(call, definition, *, successor_available):
    identity = definition["employeeDefinitionId"]
    lifecycle = definition.get("lifecycleState")
    actions = {
        "CREATE": (
            ExactGrant("EMPLOYEE", "CREATE", "employee:collection"),
            successor_available,
        )
    }
    for action, state in (
        ("VALIDATE", "DRAFT"),
        ("APPROVE", "VALIDATED"),
        ("PUBLISH", "APPROVED"),
    ):
        actions[action] = (
            ExactGrant("EMPLOYEE", action, f"employee:{identity}:aggregate"),
            lifecycle == state,
        )
    return projection(
        call,
        actions,
        target={
            key: definition[key]
            for key in (
                "employeeDefinitionId",
                "employeeDefinitionRevisionId",
                "employeeDefinitionDigest",
                "aggregateVersion",
            )
        },
    )
