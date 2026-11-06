"""Finite own-call READ metadata and own grant-key GET; no authorization writes."""

from .authority_contracts import AuthorityError, ExactGrant


def current(admin, context, members):
    now = admin.clock()
    try:
        revoked = any(
            admin.authorization.has_dynamic_revocation(
                context, m, now=now, recovery_epoch=admin.recovery_epoch
            )
            for m in members
        )
        allowed = all(
            admin.authorization.has_current_grant(
                context,
                m,
                now=now,
                generation=admin.generation.generation,
                recovery_epoch=admin.recovery_epoch,
            )
            for m in members
        )
        return "REVOKED" if revoked else "EFFECTIVE" if allowed else "NOT_EFFECTIVE"
    except AuthorityError:
        return "UNAVAILABLE"


def read_targets(admin, context, metadata):
    root, invocation = metadata["problemId"], metadata["invocationId"]
    groups = []
    for kind, purpose, members in [
        (
            "PLANNING",
            "WORKBENCH_PLANNING",
            (ExactGrant("PLAN", "READ", "plan:prepared:" + root),),
        ),
        (
            "USAGE",
            "PROVIDER_USAGE_REVIEW",
            (
                ExactGrant(
                    "RESOURCE_USE",
                    "READ",
                    "resource-use:contextual-resource-use:" + invocation,
                ),
                ExactGrant(
                    "EVIDENCE",
                    "READ_MEASUREMENT",
                    "evidence-reference:provider-usage:planning:" + invocation,
                ),
            ),
        ),
    ]:
        history = admin.repository.exact_read_history(context, members)
        effective = current(admin, context, members)
        try:
            admin._validate_requestable(purpose, members)
            requestable = effective not in {"REVOKED", "UNAVAILABLE"}
        except AuthorityError:
            requestable = False
        eligibility = (
            "REVOKED"
            if effective == "REVOKED"
            else "AUTHORITY_UNAVAILABLE"
            if effective == "UNAVAILABLE"
            else "REQUESTABLE"
            if requestable
            else "NOT_REQUESTABLE"
        )
        if requestable:
            with admin.repository.connection_scope() as connection:
                requestable = admin.target_validator is not None and all(
                    admin.target_validator.is_known_exact_target(
                        context, m, connection=connection
                    )
                    for m in members
                )
            if not requestable:
                eligibility = "TARGET_UNAVAILABLE"
        granted = [h["previouslyGranted"] for h in history]
        groups.append(
            {
                "kind": kind,
                "purpose": purpose,
                "requestedGrants": [
                    {"owner": m.owner, "action": m.action, "resource": m.exact_resource}
                    for m in members
                ],
                "history": history,
                "classification": "RENEWAL"
                if all(granted)
                else "FIRST_READ"
                if not any(granted)
                else "MIXED",
                "currentRead": effective,
                "requestable": requestable,
                "eligibilityReason": eligibility,
            }
        )
    return {
        "schemaVersion": "planning-exact-read-targets.v1",
        **metadata,
        "applicant": {
            "principalId": context.principal_id,
            "tenantId": context.scope.tenant_id,
            "securityDomain": context.scope.security_domain,
        },
        "groups": groups,
        "checkedAt": admin.clock(),
        "authorizationGranted": False,
    }


def recover_request(admin, context, key):
    admin._validate_idempotency_key(key)
    request = admin.repository.recover_read_request(context, key)
    allowed = {
        "WORKBENCH_PLANNING": {("PLAN", "READ", "plan:prepared:")},
        "PROVIDER_USAGE_REVIEW": {
            ("RESOURCE_USE", "READ", "resource-use:contextual-resource-use:"),
            (
                "EVIDENCE",
                "READ_MEASUREMENT",
                "evidence-reference:provider-usage:planning:",
            ),
        },
    }
    patterns = allowed.get(request.purpose, set())
    if (
        not patterns
        or not request.members
        or len(request.members) > 2
        or any(
            not any(
                m.owner == o and m.action == a and m.exact_resource.startswith(p)
                for o, a, p in patterns
            )
            for m in request.members
        )
    ):
        raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
    decision = admin.repository.read_request_decision(request.request_id)
    exact = current(admin, context, request.members)
    state = request.status.value
    if state == "APPROVED":
        now = admin.clock()
        state = (
            "REVOKED"
            if exact == "REVOKED"
            else "UNAVAILABLE"
            if decision is None
            else "EXPIRED"
            if decision["expiresAt"] is None or now >= decision["expiresAt"]
            else "NOT_YET_EFFECTIVE"
            if decision["notBefore"] and now < decision["notBefore"]
            else "EFFECTIVE"
            if exact == "EFFECTIVE"
            else "NOT_EFFECTIVE"
            if exact == "NOT_EFFECTIVE"
            else "UNAVAILABLE"
        )
    return {
        "schemaVersion": "exact-read-request-recovery.v1",
        "requestKey": key,
        "requestId": request.request_id,
        "state": request.status.value,
        "accessState": state,
        "currentExactRead": exact,
        "aggregateVersion": request.aggregate_version,
        "submittedAt": request.created_at,
        "purpose": request.purpose,
        "applicant": {
            "principalId": request.subject_principal_id,
            "tenantId": request.scope.tenant_id,
            "securityDomain": request.scope.security_domain,
        },
        "requestedGrants": [
            {"owner": m.owner, "action": m.action, "resource": m.exact_resource}
            for m in request.members
        ],
        "decision": decision,
        "checkedAt": admin.clock(),
    }
