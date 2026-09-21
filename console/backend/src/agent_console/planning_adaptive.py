"""Finite planning orchestration over the existing immutable invocation ledger.

There is no recovery dispatch on GET or duplicate root submission. A caller may
explicitly start another bounded round; UNKNOWN is never an automatic edge.
"""

from dataclasses import asdict, dataclass
from time import monotonic

from .business_problem_domain import canonical_digest
from .plan_suggestion_domain import PlanningError


@dataclass(frozen=True)
class AdaptiveLimits:
    maximum_attempts: int = 3
    total_seconds: float = 180
    single_seconds: float = 60
    cleanup_seconds: float = 2

    def __post_init__(self):
        if not (
            1 <= self.maximum_attempts <= 4
            and 1 <= self.single_seconds <= 300
            and self.single_seconds <= self.total_seconds <= 900
            and 2 <= self.cleanup_seconds <= 5
        ):
            raise ValueError("PLANNING_LOOP_LIMIT_INVALID")


class LoopCancellation:
    def __init__(self, parent, deadline, clock=monotonic):
        self.parent, self.deadline, self.clock = parent, deadline, clock

    def is_set(self):
        return (
            self.parent is not None and self.parent.is_set()
        ) or self.clock() >= self.deadline


def child_key(root, ordinal):
    return "planning-repair:" + canonical_digest([root, ordinal])


def recovery(service, principal, root_key, first):
    """Read existing successors only; never reconstruct and dispatch a request."""
    chain = [first]
    limits = first["invocation"].get("request", {}).get("adaptive_loop")
    if not limits:
        return first
    for ordinal in range(1, limits["maximum_attempts"]):
        identity = service.invocations.find_request(
            service.application.scope(principal),
            principal.principal_id,
            child_key(root_key, ordinal),
        )
        if identity is None:
            break
        chain.append(service.read(principal, identity))
    return projection(chain, limits, "READ_ONLY_RECOVERY")


def projection(chain, limits, stop):
    last = dict(chain[-1])
    last["adaptive"] = {
        "limits": limits,
        "stop_reason": stop,
        "attempts": [
            {
                "invocation_id": row["invocation"]["target"]["invocation_id"],
                "kind": row["result"].get("kind"),
                "technical_status": row["result"]["technical_status"],
                "diagnostic": row["result"].get("validation_diagnostic"),
            }
            for row in chain
        ],
    }
    return last


def run(service, principal, request, limits, clock=monotonic):
    if request.output_language != "zh-CN" or request.policy is None:
        raise PlanningError("PLANNING_LOOP_REQUIRES_CHINESE_POLICY")
    scope = service.application.scope(principal)
    root = service.invocations.find_request(
        scope, principal.principal_id, request.idempotency_key
    )
    config = {"version": "planning-loop.v1", **asdict(limits)}
    if root:
        prior = service.read(principal, root)
        stored = prior["invocation"].get("request", {})
        # Reuse the originally admitted limits to preserve idempotency across
        # configuration updates; begin performs full input commitment checking.
        first = service.begin(
            principal, request, loop=stored.get("adaptive_loop", config)
        )
        return recovery(service, principal, request.idempotency_key, first)
    started = clock()
    chain = []
    seen = set()
    current = request
    feedback = None
    stop = "ATTEMPT_LIMIT"
    for ordinal in range(limits.maximum_attempts):
        if (
            clock() - started + limits.single_seconds + limits.cleanup_seconds
            > limits.total_seconds
        ):
            stop = "TOTAL_DEADLINE"
            break
        from .responses_deadline import CANCEL

        cancellation = LoopCancellation(
            CANCEL.get(), started + limits.total_seconds, clock
        )
        token = CANCEL.set(cancellation)
        try:
            result = service.begin(principal, current, repair=feedback, loop=config)
        finally:
            CANCEL.reset(token)
        chain.append(result)
        outcome = result["result"]
        if (
            outcome["technical_status"] != "SUCCEEDED"
            or outcome.get("kind") != "INVALID"
        ):
            stop = (
                "AWAIT_CONFIRMATION"
                if outcome.get("proposal")
                else outcome.get("kind") or outcome["technical_status"]
            )
            break
        diagnostic = outcome.get("validation_diagnostic") or {}
        errors = diagnostic.get("locations") or diagnostic.get("issues") or []
        if any(item.get("rule", "").startswith("REPAIR_") for item in errors):
            stop = "PROTECTED_REPAIR_CONFLICT"
            break
        if not errors:
            stop = "NO_SAFE_REPAIR_DIAGNOSTIC"
            break
        fingerprint = canonical_digest(errors)
        if fingerprint in seen:
            stop = "NO_PROGRESS"
            break
        seen.add(fingerprint)
        feedback = {
            "issues": errors,
            "rule_version": "planning-repair.v1",
            "source_invocation": result["invocation"]["target"]["invocation_id"],
        }
        if outcome.get("language_repair_source") is not None:
            feedback["language_repair_source"] = outcome["language_repair_source"]
        current = request.model_copy(
            update={
                "idempotency_key": child_key(request.idempotency_key, ordinal + 1),
                "predecessor_invocation_id": result["invocation"]["target"][
                    "invocation_id"
                ],
            }
        )
    if not chain:
        raise PlanningError("PLANNING_LOOP_DEADLINE_INSUFFICIENT")
    return projection(chain, config, stop)
