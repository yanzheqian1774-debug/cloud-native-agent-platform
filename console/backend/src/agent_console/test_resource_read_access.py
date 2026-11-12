"""Exact catalog snapshot checks and transaction-bound, audited READ decisions."""

from datetime import timedelta

from .authority_contracts import AuthorityError, ExactGrant, GrantRequestStatus
from .grant_administration_application import GrantDecisionCommand, GrantRequestCommand
from .read_access_recovery import current
from .resource_automation import bound_grants
from .resource_use_domain import canonical_digest
from .test_resource_read_policy import COLLECTIONS
from .workbench_prepared_resources import OWNERS, PREFIXES, TABLES


def snapshot_matches(connection, context, target):
    scope = (context.scope.tenant_id, context.scope.security_domain)
    if target.digest is None:
        return COLLECTIONS.get((target.owner, target.action)) == target.resource
    for kind, (table, column) in TABLES.items():
        if target.owner != OWNERS[kind] or target.action != "READ_RESOURCE":
            continue
        row = connection.execute(
            f"SELECT r->>'digest' digest FROM {table} t "
            "CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r "
            f"WHERE namespace=%s AND security_domain=%s AND %s || {column} "
            "|| ':' || (r->>'revisionId')=%s"
            + (" AND kind=%s" if kind in {"skill", "mcp"} else ""),
            (
                *scope,
                PREFIXES[kind] + "prepared-resource:",
                target.resource,
                *([kind] if kind in {"skill", "mcp"} else []),
            ),
        ).fetchone()
        if row and row["digest"].removeprefix("sha256:") == target.digest:
            return True
    definitions = {
        "EMPLOYEE": (
            "digital_employee_definition.revisions",
            "definition_id",
            "employee:",
        ),
        "BUSINESS_CAPABILITY": (
            "business_capability.revisions",
            "capability_id",
            "business-capability:",
        ),
        "TOOL": ("tool_definition.revisions", "tool_id", ""),
        "MODEL_GOVERNANCE": (
            "model_governance.model_revisions",
            "model_id",
            "model:revision:",
        ),
    }
    if target.owner in definitions:
        table, column, prefix = definitions[target.owner]
        suffix = " || ':' || digest" if target.owner == "MODEL_GOVERNANCE" else ""
        row = connection.execute(
            f"SELECT digest FROM {table} WHERE namespace=%s AND security_domain=%s "
            f"AND %s || {column} || ':' || revision_id{suffix}=%s",
            (*scope, prefix, target.resource),
        ).fetchone()
        return bool(row and row["digest"].removeprefix("sha256:") == target.digest)
    if target.owner == "WORKFLOW":
        row = connection.execute(
            "SELECT r->>'digest' digest FROM workflow_definition.definitions t "
            "CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r "
            "WHERE namespace=%s AND security_domain=%s AND 'workflow:' || "
            "workflow_definition_id || ':' || (r->>'revisionId')=%s",
            (*scope, target.resource),
        ).fetchone()
        return bool(row and row["digest"].removeprefix("sha256:") == target.digest)
    return False


def was_denied(connection, context, grant):
    return (
        connection.execute(
            "SELECT 1 FROM authorization_admin.grant_requests r JOIN "
            "authorization_admin.grant_request_members m USING(request_id) "
            "WHERE r.tenant_id=%s AND r.security_domain=%s "
            "AND r.subject_principal_id=%s "
            "AND r.state='REJECTED' AND m.owner=%s AND m.action=%s "
            "AND m.exact_resource=%s LIMIT 1",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                grant.owner,
                grant.action,
                grant.exact_resource,
            ),
        ).fetchone()
        is not None
    )


def prepare(policy, grants, context, connection, key):
    """Caller owns transaction. Original keys recover decisions, never renew expiry."""
    grants._validate_idempotency_key(key)
    issuer, lifetime = policy.authenticate(grants, context)
    bound = bound_grants(grants, connection)
    eligible, results = [], []
    # No authority write before every configured snapshot is checked.
    for target in policy.targets:
        grant = target.grant
        if not snapshot_matches(connection, context, target):
            raise AuthorityError("TEST_READ_POLICY_SNAPSHOT_CHANGED")
        if (
            not bound.target_validator
            or not bound.target_validator.is_known_exact_target(
                context, grant, connection=connection
            )
        ):
            raise AuthorityError("TEST_READ_POLICY_TARGET_UNAVAILABLE")
        state = current(bound, context, (grant,))
        if state == "UNAVAILABLE":
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")
        if state == "REVOKED" or was_denied(connection, context, grant):
            results.append(
                {
                    "resource": target.resource,
                    "state": "REVOKED" if state == "REVOKED" else "DENIED",
                }
            )
        else:
            eligible.append((target, state))
    for target, state in eligible:
        request_key = "test-read:" + canonical_digest(
            [policy.digest, key, target.model_dump(mode="json")]
        )
        try:
            request = bound.repository.recover_read_request(context, request_key)
        except AuthorityError as exc:
            if exc.reason_code != "GRANT_REQUEST_NOT_FOUND":
                raise
            if state == "EFFECTIVE":
                results.append({"resource": target.resource, "state": state})
                continue
            request = bound.submit_request(
                context,
                GrantRequestCommand(target.purpose, (target.grant,), request_key),
            )
        if request.status == GrantRequestStatus.REJECTED:
            results.append({"resource": target.resource, "state": "DENIED"})
            continue
        expiry = min(
            lifetime, request.created_at + timedelta(seconds=policy.grantTTLSeconds)
        )
        if request.status == GrantRequestStatus.APPROVED:
            receipt = bound.repository.read_request_decision(request.request_id)
            if receipt is None or receipt["expiresAt"] is None:
                raise AuthorityError("TEST_READ_POLICY_RECEIPT_UNAVAILABLE")
            expiry = receipt["expiresAt"]
        elif expiry > grants.clock():
            bound.decide_request(
                issuer,
                GrantDecisionCommand(
                    request.request_id,
                    True,
                    "TEST_RESOURCE_READ",
                    "POLICY",
                    "test-resource-read:"
                    + policy.policyId
                    + ":"
                    + policy.policyVersion
                    + ":"
                    + policy.digest,
                    None,
                    expiry,
                    "test-read-decision:"
                    + canonical_digest([request_key, request.request_id]),
                    expected_version=1,
                ),
            )
        results.append(
            {
                "resource": target.resource,
                "state": "EXPIRED" if expiry <= grants.clock() else "APPROVED",
                "requestId": request.request_id,
                "expiresAt": expiry.isoformat(),
            }
        )
    return {
        "policyVersion": policy.policyVersion,
        "policyDigest": policy.digest,
        "items": results,
    }


def operations(policy, grants):
    """Install only when an operator supplied the policy; disabled remains denied."""
    from pydantic import BaseModel, ConfigDict, Field

    from .workbench_bff import PREFIX, WorkbenchOperation

    class PrepareTestRead(BaseModel):
        model_config = ConfigDict(extra="forbid")
        idempotencyKey: str = Field(min_length=1, max_length=160)

    def handle(call):
        return prepare(
            policy,
            grants,
            call.context,
            call.connection,
            call.payload["idempotencyKey"],
        )

    def status(call):
        if not policy.enabled or call.context.principal_id not in policy.subjects:
            return {"available": False}
        policy.authenticate(grants, call.context)
        return {
            "available": True,
            "policyDigest": policy.digest,
            "policyVersion": policy.policyVersion,
            "expiresAt": policy.expiresAt.isoformat(),
        }

    return (
        WorkbenchOperation(
            "READ_TEST_RESOURCE_READ_STATUS",
            "GET",
            PREFIX + "/test-resource-access/status",
            None,
            None,
            lambda *_: (
                ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
            ),
            status,
        ),
        WorkbenchOperation(
            "PREPARE_TEST_RESOURCE_READ",
            "POST",
            PREFIX + "/test-resource-access/prepare",
            PrepareTestRead,
            None,
            lambda *_: (
                ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
            ),
            handle,
        ),
    )
