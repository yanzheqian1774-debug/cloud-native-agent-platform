"""One clarification successor, new admission, unchanged planning context/budget."""

from .authority_contracts import AuthorityError
from .context_call_admission import active, lock
from .task_delegation import digest


def validated_predecessor(experience, service, c, context, source, request, target):
    predecessor = request.get("predecessor_invocation_id")
    if predecessor is None:
        return None
    scope = (context.scope.tenant_id, context.scope.security_domain)
    lock(c, "f3-planning-successor:" + digest([*scope, predecessor]))
    previous = c.execute(
        "SELECT a.*,i.actor_id,i.record AS invocation,r.record AS result "
        "FROM authorization_admin.context_call_requests a "
        "JOIN workflow_planning.invocations i ON i.namespace=a.tenant_id "
        "AND i.security_domain=a.security_domain "
        "AND i.invocation_id=a.first_invocation_id "
        "JOIN workflow_planning.invocation_results r ON r.namespace=i.namespace "
        "AND r.security_domain=i.security_domain AND r.invocation_id=i.invocation_id "
        "WHERE a.tenant_id=%s AND a.security_domain=%s "
        "AND a.first_invocation_id=%s AND a.record->>'phase'='planning'",
        (*scope, predecessor),
    ).fetchone()
    if not previous:
        raise AuthorityError("CONTEXT_ADMISSION_CLARIFICATION_REQUIRED")
    experience.require(service, c, context, previous)
    old = previous["invocation"]["target"]
    if (
        previous["actor_id"] != context.principal_id
        or previous["record"].get("source_context_id") != source["context_id"]
        or previous["result"].get("technical_status") != "SUCCEEDED"
        or previous["result"].get("kind") != "NEEDS_CLARIFICATION"
        or target.get("predecessor_invocation_id") != predecessor
        or target["problem"] != old["problem"]
        or target["suggestion_context_id"] != old["suggestion_context_id"]
        or target.get("source_proposal") != old.get("source_proposal")
        or target.get("request_revision") != old.get("request_revision", 1) + 1
        or target["request_revision"] > 8
    ):
        raise AuthorityError("CONTEXT_ADMISSION_CLARIFICATION_REQUIRED")
    if c.execute(
        "SELECT 1 FROM draft_provider_budget.reservations r "
        "LEFT JOIN draft_provider_budget.settlements s "
        "USING(namespace,security_domain,ledger_id,reservation_id) "
        "WHERE r.namespace=%s AND r.security_domain=%s AND r.invocation_id=%s "
        "AND s.reservation_id IS NULL",
        (*scope, predecessor),
    ).fetchone():
        raise AuthorityError("CONTEXT_ADMISSION_OUTCOME_UNKNOWN")
    return previous


def successor(experience, service, c, context, source, request, target, expires):
    previous = validated_predecessor(
        experience, service, c, context, source, request, target
    )
    if previous is None:
        return target["suggestion_context_id"], expires
    scope = (context.scope.tenant_id, context.scope.security_domain)
    predecessor = request["predecessor_invocation_id"]
    if c.execute(
        "SELECT 1 FROM authorization_admin.context_call_requests "
        "WHERE tenant_id=%s AND security_domain=%s "
        "AND record->>'phase'='planning' "
        "AND record->'target'->>'predecessor_invocation_id'=%s",
        (*scope, predecessor),
    ).fetchone():
        raise AuthorityError("CONTEXT_ADMISSION_SUCCESSOR_ALREADY_PREPARED")
    decision = active(c, previous, service.configuration)
    return (
        "f3-planning-continuation:" + digest([*scope, target["invocation_id"]]),
        min(expires, decision["expires_at"]),
    )
