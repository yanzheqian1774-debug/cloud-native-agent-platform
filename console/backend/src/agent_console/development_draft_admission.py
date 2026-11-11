"""D12 policy admission for a current administrator's own new draft context."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .development_administrator import for_service
from .task_delegation import digest


def admit(service, connection, context, row):
    from .context_call_admission import active, latest, lock

    grants = service.delegation.grants
    if not for_service(grants, context, connection):
        return False
    if (
        row["subject_id"] != context.principal_id
        or row["record"].get("phase") not in {"understanding", "planning"}
        or not row["record"].get("development_administrator")
        or row["record"]["configuration"] != service.configuration
    ):
        raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
    lock(connection, row["context_id"])
    previous = latest(connection, row["context_id"])
    if previous:
        if connection.execute(
            "SELECT 1 FROM authorization_admin.context_call_revocations "
            "WHERE admission_id=%s",
            (previous["admission_id"],),
        ).fetchone():
            raise AuthorityError("CONTEXT_ADMISSION_REQUIRED")
        try:
            active(connection, row, service.configuration)
            return True
        except AuthorityError as exc:
            if exc.reason_code != "CONTEXT_ADMISSION_REQUIRED":
                raise
    now = datetime.now(UTC)
    ordinal = previous["ordinal"] + 1 if previous else 1
    record = {
        "type": "DEVELOPMENT_ADMINISTRATOR",
        "policy": "D12",
        "actor": context.principal_id,
        "request": row["record"],
        "request_digest": row["digest"],
        "ledger_policy_rows_unchanged": True,
        "development_call_cap": row["record"].get("development_call_cap"),
        "understanding_cost_cap_unchanged": True,
        "predecessor_id": previous["admission_id"] if previous else None,
    }
    connection.execute(
        "INSERT INTO authorization_admin.context_call_decisions VALUES"
        "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            "development-context:" + uuid4().hex,
            row["context_id"],
            ordinal,
            "policy:development-administrator:D12",
            context.principal_id,
            grants.generation.generation,
            grants.recovery_epoch,
            f"d12:{row['context_id']}:{ordinal}",
            digest(record),
            Jsonb(record),
            now,
            now + timedelta(minutes=5),
        ),
    )
    service.repository._audit(
        connection,
        event_type="CONTEXT_CALL_ADMISSION",
        actor_id=context.principal_id,
        outcome="APPROVED",
        reason="D12_CAPABILITY_SHARED_PLANNING_BUDGET"
        if row["record"].get("capability_source")
        else "D12_CURRENT_ROLE_EXISTING_DRAFT_BUDGET",
        occurred_at=now,
        scope=context.scope,
        subject_id=row["context_id"],
        generation=grants.generation.generation,
        recovery_epoch=grants.recovery_epoch,
    )
    return True


def bind_created_object(service, legacy):
    """Refresh a current role's lease atomically with linking its successful draft."""

    def bind(connection, context, owner, result, **kwargs):
        invocation_id = kwargs.get("draft_invocation_id")
        if (
            owner == "BUSINESS_PROBLEM"
            and invocation_id
            and for_service(service.delegation.grants, context, connection)
        ):
            row = connection.execute(
                "SELECT r.* FROM authorization_admin.context_call_requests r "
                "JOIN draft_assistance.invocation_versions v ON "
                "r.context_id=v.record->>'contextId' "
                "WHERE v.namespace=%s AND v.security_domain=%s "
                "AND v.invocation_id=%s AND r.subject_id=%s "
                "ORDER BY v.aggregate_version DESC LIMIT 1",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    invocation_id,
                    context.principal_id,
                ),
            ).fetchone()
            if row and row["record"].get("development_administrator"):
                admit(service, connection, context, row)
        return legacy(connection, context, owner, result, **kwargs)

    return bind
