"""Owner-authorized adaptive readback without settlement or new model calls."""

from .plan_suggestion_domain import PlanningError
from .planning_adaptive import child_key, projection


def read_chain(service, principal, root_key):
    scope = service.application.scope(principal)
    root = service.invocations.find_request(scope, principal.principal_id, root_key)
    if root is None:
        raise PlanningError("PLANNING_NOT_FOUND")
    first = service.read(principal, root, settle_receipt=False)
    document = first["invocation"].get("request", {})
    if document.get("idempotency_key") != root_key:
        raise PlanningError("PLANNING_CHAIN_MISMATCH")
    limits = document.get("adaptive_loop")
    count = limits.get("maximum_attempts") if isinstance(limits, dict) else 1
    if type(count) is not int or not 1 <= count <= 4:
        raise PlanningError("PLANNING_CHAIN_LIMIT_INVALID")
    chain = [first]
    for ordinal in range(1, count):
        key = child_key(root_key, ordinal)
        identity = service.invocations.find_request(scope, principal.principal_id, key)
        if identity is None:
            break
        value = service.read(principal, identity, settle_receipt=False)
        request = value["invocation"].get("request", {})
        previous = chain[-1]["invocation"]["target"]["invocation_id"]
        if (
            request.get("idempotency_key") != key
            or request.get("predecessor_invocation_id") != previous
            or request.get("target") != document.get("target")
            or value["invocation"]["target"].get("problem")
            != first["invocation"]["target"].get("problem")
        ):
            raise PlanningError("PLANNING_CHAIN_MISMATCH")
        chain.append(value)
    return {
        "rootRequestKey": root_key,
        "rootInvocationId": root,
        "value": projection(chain, limits, "READ_ONLY_RECOVERY") if limits else first,
    }
