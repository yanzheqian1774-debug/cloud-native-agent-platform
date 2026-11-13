"""Exact old policy selection for history only; never admission or dispatch."""

import json
from pathlib import Path

from .authority_contracts import AuthorityError


def require(condition):
    if not condition:
        raise AuthorityError("OWNED_BUSINESS_RETAINED_HISTORY_INVALID")


def configured_paths(value):
    if value is None:
        return ()
    try:
        paths = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise AuthorityError("OWNED_BUSINESS_RETAINED_HISTORY_INVALID") from exc
    require(isinstance(paths, list) and len(paths) <= 8)
    require(all(isinstance(p, str) and Path(p).is_absolute() for p in paths))
    require(len({str(Path(p).resolve()) for p in paths}) == len(paths))
    return tuple(paths)


def perimeter(policy):
    return policy.model_dump(exclude={"policyVersion", "expiresAt", "enabled"})


def successor_perimeter(policy):
    value = perimeter(policy)
    for key in ("schemaVersion", "retainedReadPolicyDigests", "adoptionPolicyDigest"):
        value.pop(key, None)
    for scope in value["scopes"]:
        scope.pop("skills")
        scope.pop("employees")
    return value


def retained_readers(current, paths):
    from .owned_business_work_reader import OwnedBusinessWorkReader

    paths = configured_paths(json.dumps([str(p) for p in paths]))
    from .owned_business_policy import OwnedBusinessPolicyV2

    pins = (
        set(current.policy.retainedReadPolicyDigests)
        if isinstance(current.policy, OwnedBusinessPolicyV2)
        else None
    )
    readers = {}
    for path in paths:
        old = OwnedBusinessWorkReader(
            path,
            current.authorization,
            current.generation,
            current.recovery_epoch,
            _retained_read_only=True,
        )
        require(
            old.policy.enabled
            and (
                perimeter(old.policy) == perimeter(current.policy)
                if pins is None
                else old.policy.digest in pins
                and successor_perimeter(old.policy)
                == successor_perimeter(current.policy)
            )
            and old.policy.expiresAt <= current.policy.expiresAt
            and old.policy.digest != current.policy.digest
            and old.policy.digest not in readers
        )
        readers[old.policy.digest] = old
    require(pins is None or set(readers) == pins)
    return readers


def select_reader(current, c, context, problem):
    # Selection is not proof of access. The existing selected reader validates
    # original owner, full revision/digest, source and current revocation again.
    from .owned_business_postgres import saved

    bound = c.execute(
        "SELECT invocation_id FROM authorization_admin.context_call_objects "
        "WHERE tenant_id=%s AND security_domain=%s AND owner='BUSINESS_PROBLEM' "
        "AND resource_id=%s",
        (context.scope.tenant_id, context.scope.security_domain, problem.resource_id),
    ).fetchone()
    if bound is None:
        return None
    row = saved(c, context, bound["invocation_id"])
    return current.retained_history.get(row["record"]["policyDigest"]) if row else None
