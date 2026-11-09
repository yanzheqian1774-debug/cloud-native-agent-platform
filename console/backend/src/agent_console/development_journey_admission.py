# ruff: noqa: E501 -- Exact parameterized owner SQL.
"""Current development-role planning, bounded on the original shared ledger."""

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .context_call_admission import lock, request_row
from .development_administrator import for_service
from .task_delegation import digest

# Same aggregate ceilings as existing development planning; unknowns remain charged.
CALL_CAP = 100
COST_CAP = 50_000_000


def prepare(service, c, context, request, record):
    if not for_service(service.delegation.grants, context, c):
        return None
    scope = (context.scope.tenant_id, context.scope.security_domain)
    source = c.execute(
        "SELECT r.* FROM authorization_admin.context_call_requests r JOIN "
        "authorization_admin.context_call_objects o USING(context_id) "
        "WHERE o.tenant_id=%s AND o.security_domain=%s AND o.owner='BUSINESS_PROBLEM' "
        "AND o.resource_id=%s AND r.subject_id=%s",
        (*scope, request.target.problem.resource_id, context.principal_id),
    ).fetchone()
    if not source or not source["record"].get("development_administrator"):
        raise AuthorityError("DEVELOPMENT_JOURNEY_OWN_DRAFT_REQUIRED")
    key = (*scope, context.principal_id, request.idempotency_key)
    lock(c, "planning:" + digest(key))
    old = c.execute(
        "SELECT * FROM authorization_admin.planning_call_preparations "
        "WHERE tenant_id=%s AND security_domain=%s AND subject_id=%s AND request_key=%s",
        key,
    ).fetchone()
    if old:
        if old["input_commitment"] != record["target"]["input_commitment"]:
            raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
        row = request_row(c, old["context_id"])
        from .development_draft_admission import admit

        admit(service, c, context, row)
        return service._projection(c, row, old["record"])
    account = c.execute(
        "SELECT a.* FROM browser_identity.local_accounts a JOIN "
        "browser_identity.local_account_sessions s USING(account_id) "
        "WHERE s.session_id=%s AND a.revision=s.account_revision AND a.status='ENABLED' FOR SHARE OF a",
        (context.session_id_or_service_credential_id,),
    ).fetchone()
    if not account:
        raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
    identity = record["target"]["suggestion_context_id"]
    payload = dict(
        task_id="D13-CONVERSATION-JOURNEY",
        phase="planning",
        synthetic_only=True,
        development_administrator=True,
        development_journey=True,
        context_id=identity,
        first_invocation_id=record["target"]["invocation_id"],
        source_context_id=source["context_id"],
        configuration=service.configuration,
        subject_id=context.principal_id,
        account_id=account["account_id"],
        account_revision=account["revision"],
        target=record["target"],
        cumulative_call_cap=CALL_CAP,
        total_cost_cap_microusd=COST_CAP,
        maximum_new_calls=1,
    )
    c.execute(
        "INSERT INTO authorization_admin.context_call_requests "
        "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,first_invocation_id,record,digest) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            identity,
            *scope,
            context.principal_id,
            account["account_id"],
            account["revision"],
            record["target"]["invocation_id"],
            Jsonb(payload),
            digest(payload),
        ),
    )
    saved = {
        **record,
        "request": request.model_dump(mode="json"),
        "bounded_new_calls": 1,
    }
    c.execute(
        "INSERT INTO authorization_admin.planning_call_preparations VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (*key, identity, record["target"]["input_commitment"], Jsonb(saved)),
    )
    row = request_row(c, identity)
    from .development_draft_admission import admit

    admit(service, c, context, row)
    return service._projection(c, row, saved)
