"""D324-5 independent context admission; original ledgers and 323 guard remain.

This is additional admission, never a substitute for exact owner/model Grants.
Only the isolated 324 business principal can create a request. Human approval
pins current account revision and exact configuration for at most eight hours.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .task_delegation import digest

SUBJECT = "human:demo323-requester"
SCOPE = ("s5-323-demo", "isolated-real-demo")


class ContextApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_digest: str = Field(pattern="^[a-f0-9]{64}$")
    expires_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=128)


def available(c):
    return bool(
        c.execute(
            "SELECT to_regclass('authorization_admin.context_call_requests') AS name"
        ).fetchone()["name"]
    )


def lock(c, context_id):
    c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,3240037))", (context_id,)
    )


def request_row(c, context_id):
    return c.execute(
        "SELECT * FROM authorization_admin.context_call_requests WHERE context_id=%s",
        (context_id,),
    ).fetchone()


def old_context(c, context_id):
    return (
        c.execute(
            "SELECT 1 FROM authorization_admin.task_delegations WHERE "
            "root_context_id=%s "
            "UNION ALL SELECT 1 FROM authorization_admin.task_cases WHERE "
            "context_id=%s",
            (context_id, context_id),
        ).fetchone()
        is not None
    )


def latest(c, context_id):
    return c.execute(
        "SELECT * FROM authorization_admin.context_call_decisions "
        "WHERE context_id=%s ORDER BY ordinal DESC LIMIT 1",
        (context_id,),
    ).fetchone()


def active(c, row, configuration):
    # Account is locked before authority/session locks, as in D324-4.
    account = c.execute(
        "SELECT status,revision,principal_id,tenant_id,security_domain FROM "
        "browser_identity.local_accounts WHERE account_id=%s FOR SHARE",
        (row["account_id"],),
    ).fetchone()
    if account != {
        "status": "ENABLED",
        "revision": row["account_revision"],
        "principal_id": row["subject_id"],
        "tenant_id": row["tenant_id"],
        "security_domain": row["security_domain"],
    }:
        raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
    generation = c.execute(
        "SELECT generation,recovery_epoch FROM authorization_admin.active_generation "
        "WHERE singleton=true FOR SHARE"
    ).fetchone()
    decision = latest(c, row["context_id"])
    now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if (
        not decision
        or generation is None
        or now >= decision["expires_at"]
        or any(decision[k] != generation[k] for k in ("generation", "recovery_epoch"))
        or c.execute(
            "SELECT 1 FROM authorization_admin.context_call_revocations WHERE "
            "admission_id=%s",
            (decision["admission_id"],),
        ).fetchone()
    ):
        raise AuthorityError("CONTEXT_ADMISSION_REQUIRED")
    if row["record"]["configuration"] != configuration:
        raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
    return decision


class ContextCallAdmission:
    def __init__(self, delegation, configuration):
        self.delegation = delegation
        self.repository = delegation.repository
        self.configuration = configuration

    def require_dispatch_grants(self, c, context, invocation):
        if request_row(c, invocation.context_id) is None:
            return
        from .draft_assistance_authorization import model_grant, request_grant
        from .local_accounts import current_session_account

        if not current_session_account(
            c, session_id=context.session_id_or_service_credential_id
        ):
            raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
        grants = self.delegation.grants
        if not all(
            grants.authorization.has_current_grants(
                context,
                (request_grant(invocation), model_grant(invocation)),
                now=datetime.now(UTC),
                generation=grants.generation.generation,
                recovery_epoch=grants.recovery_epoch,
                connection=c,
                configure_transaction=False,
            )
        ):
            raise AuthorityError("CONTEXT_ADMISSION_GRANTS_REQUIRED")

    def migrate(self):
        path = self.repository.migration_path.parent / "0037_context_call_admission.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            row = c.execute(
                "SELECT checksum,adapter FROM authorization_admin.schema_migrations "
                "WHERE version=37"
            ).fetchone()
            if row:
                if row != {
                    "checksum": checksum,
                    "adapter": "context-call-admission-v1",
                }:
                    raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
                return
            c.execute(path.read_text())
            c.execute(
                "INSERT INTO "
                "authorization_admin.schema_migrations(version,checksum,adapter) "
                "VALUES(37,%s,'context-call-admission-v1')",
                (checksum,),
            )

    def prepare(self, context, invocation):
        """Create only a request, after the normal owner has created actual IDs."""
        with self.repository.connection_scope() as c:
            if old_context(c, invocation.context_id):
                return False
            if (
                context.principal_id != SUBJECT
                or (context.scope.tenant_id, context.scope.security_domain) != SCOPE
            ):
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            account = c.execute(
                "SELECT a.* FROM browser_identity.local_accounts a JOIN "
                "browser_identity.local_account_sessions s USING(account_id) "
                "WHERE s.session_id=%s AND a.revision=s.account_revision "
                "AND a.status='ENABLED' FOR SHARE OF a",
                (context.session_id_or_service_credential_id,),
            ).fetchone()
            if not account or account["principal_id"] != SUBJECT:
                raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
            lock(c, invocation.context_id)
            row = request_row(c, invocation.context_id)
            if row:
                if (
                    row["account_id"],
                    row["account_revision"],
                    row["record"]["configuration"],
                ) != (account["account_id"], account["revision"], self.configuration):
                    raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
                return True
            original = c.execute(
                "SELECT d.record->'understanding' AS configuration FROM "
                "authorization_admin.task_delegations d JOIN "
                "authorization_admin.task_delegation_ledgers l USING(delegation_id) "
                "WHERE d.task_id='S5-V023-ARCH-323' AND d.subject_id=%s "
                "AND l.tenant_id=%s AND l.security_domain=%s "
                "AND l.ledger_id=%s AND l.purpose='understanding'",
                (SUBJECT, *SCOPE, self.configuration["ledger_id"]),
            ).fetchone()
            if not original or original["configuration"] != self.configuration:
                raise AuthorityError("CONTEXT_ADMISSION_ORIGINAL_BUDGET_MISMATCH")
            # Cannot adopt any pre-existing history or an already dispatched call.
            created = c.execute(
                "SELECT applied_at FROM authorization_admin.schema_migrations WHERE "
                "version=37"
            ).fetchone()
            history = c.execute(
                "SELECT record FROM draft_assistance.invocation_versions "
                "WHERE namespace=%s AND security_domain=%s AND record->>'contextId'=%s",
                (*SCOPE, invocation.context_id),
            ).fetchall()
            if (
                not history
                or invocation.created_at < created["applied_at"]
                or any(h["record"]["state"] != "AUTHORIZATION_PENDING" for h in history)
            ):
                raise AuthorityError("CONTEXT_ADMISSION_HISTORY_DENIED")
            record = {
                "task_id": "S5-V023-IMPL-324",
                "phase": "understanding",
                "synthetic_only": True,
                "context_id": invocation.context_id,
                "first_invocation_id": invocation.invocation_id,
                "subject_id": SUBJECT,
                "account_id": account["account_id"],
                "account_revision": account["revision"],
                "tenant_id": SCOPE[0],
                "security_domain": SCOPE[1],
                "configuration": self.configuration,
            }
            c.execute(
                "INSERT INTO authorization_admin.context_call_requests"
                "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,"
                "first_invocation_id,record,digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    invocation.context_id,
                    *SCOPE,
                    SUBJECT,
                    account["account_id"],
                    account["revision"],
                    invocation.invocation_id,
                    Jsonb(record),
                    digest(record),
                ),
            )

            return True

    def ready(self, context, invocation):
        with self.repository.connection_scope() as c:
            row = request_row(c, invocation.context_id)
            if row is None:
                return old_context(c, invocation.context_id)
            try:
                active(c, row, self.configuration)
            except AuthorityError as exc:
                if exc.reason_code == "CONTEXT_ADMISSION_REQUIRED":
                    return False
                raise
            return True

    def read(self, context, context_id):
        with self.repository.connection_scope() as c:
            row = request_row(c, context_id)
            if not row or (row["tenant_id"], row["security_domain"]) != (
                context.scope.tenant_id,
                context.scope.security_domain,
            ):
                raise AuthorityError("CONTEXT_ADMISSION_NOT_FOUND")
            if context.principal_id != row["subject_id"]:
                self.delegation._admin(context, c)
            try:
                active(c, row, self.configuration)
                status, reason = "ACTIVE", None
            except AuthorityError as exc:
                status, reason = "NOT_ADMITTED", exc.reason_code
            totals = c.execute(
                "SELECT count(*) AS calls,coalesce(sum(coalesce(s.actual_cost_microusd,"
                "r.worst_case_cost_microusd)),0) AS charged_or_reserved_microusd "
                "FROM draft_provider_budget.reservations r LEFT JOIN "
                "draft_provider_budget.settlements s "
                "USING(namespace,security_domain,ledger_id,reservation_id) "
                "WHERE r.namespace=%s AND r.security_domain=%s AND r.ledger_id=%s",
                (
                    row["tenant_id"],
                    row["security_domain"],
                    self.configuration["ledger_id"],
                ),
            ).fetchone()
            return {
                "budgetSummary": {k: int(v) for k, v in totals.items()},
                "request": row,
                "decision": latest(c, context_id),
                "status": status,
                "reasonCode": reason,
            }

    def approve(self, context, context_id, spec):
        self.delegation._admin(context)
        payload = spec.model_dump(mode="json")
        with self.repository.connection_scope() as c:
            row = request_row(c, context_id)
            if not row or (row["tenant_id"], row["security_domain"]) != (
                context.scope.tenant_id,
                context.scope.security_domain,
            ):
                raise AuthorityError("CONTEXT_ADMISSION_NOT_FOUND")
            if context.principal_id == row["subject_id"]:
                raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
            account = c.execute(
                "SELECT status,revision FROM browser_identity.local_accounts "
                "WHERE account_id=%s FOR SHARE",
                (row["account_id"],),
            ).fetchone()
            self.delegation._admin(context, c)
            lock(c, context_id)
            previous = c.execute(
                "SELECT * FROM authorization_admin.context_call_decisions "
                "WHERE issuer_id=%s AND idempotency_key=%s",
                (context.principal_id, spec.idempotency_key),
            ).fetchone()
            if previous:
                if previous["context_id"] != context_id or previous[
                    "payload_digest"
                ] != digest(payload):
                    raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
                return previous
            now = datetime.now(UTC)
            if (
                spec.expires_at.utcoffset() != timedelta(0)
                or not now < spec.expires_at <= now + timedelta(hours=8)
                or spec.request_digest != row["digest"]
                or row["record"]["configuration"] != self.configuration
                or account != {"status": "ENABLED", "revision": row["account_revision"]}
            ):
                raise AuthorityError("CONTEXT_ADMISSION_INVALID")
            prior = latest(c, context_id)
            record = {
                **payload,
                "request": row["record"],
                "predecessor_id": prior["admission_id"] if prior else None,
            }
            identity = "context-admission:" + uuid4().hex
            grants = self.delegation.grants
            c.execute(
                "INSERT INTO authorization_admin.context_call_decisions VALUES"
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    identity,
                    context_id,
                    prior["ordinal"] + 1 if prior else 1,
                    context.principal_id,
                    row["subject_id"],
                    grants.generation.generation,
                    grants.recovery_epoch,
                    spec.idempotency_key,
                    digest(payload),
                    Jsonb(record),
                    now,
                    spec.expires_at,
                ),
            )
            self.repository._audit(
                c,
                event_type="CONTEXT_CALL_ADMISSION",
                actor_id=context.principal_id,
                outcome="APPROVED",
                reason="D324_5_SYNTHETIC_CONTEXT",
                occurred_at=now,
                scope=context.scope,
                subject_id=context_id,
                generation=grants.generation.generation,
                recovery_epoch=grants.recovery_epoch,
            )
            return latest(c, context_id)

    def revoke(self, context, context_id, admission_id):
        self.delegation._admin(context)
        with self.repository.connection_scope() as c:
            self.delegation._admin(context, c)
            lock(c, context_id)
            row = request_row(c, context_id)
            if not row or (row["tenant_id"], row["security_domain"]) != (
                context.scope.tenant_id,
                context.scope.security_domain,
            ):
                raise AuthorityError("CONTEXT_ADMISSION_NOT_FOUND")
            if not c.execute(
                "SELECT 1 FROM authorization_admin.context_call_decisions "
                "WHERE context_id=%s AND admission_id=%s",
                (context_id, admission_id),
            ).fetchone():
                raise AuthorityError("CONTEXT_ADMISSION_NOT_FOUND")
            c.execute(
                "INSERT INTO "
                "authorization_admin.context_call_revocations(admission_id,actor_id) "
                "VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (admission_id, context.principal_id),
            )
            return {"revoked": True}


def guard(c, budget, invocation, quote):
    """Return True only when this new path owns admission, never quota bypass."""
    if not available(c):
        return False
    context_id = getattr(invocation, "context_id", None)
    if context_id is None:
        return False
    row = request_row(c, context_id)
    if row is None:
        return False
    if old_context(c, context_id) or (
        row["subject_id"] != invocation.initiating_principal_id
        or (row["tenant_id"], row["security_domain"])
        != (invocation.scope.namespace, invocation.scope.security_domain)
    ):
        raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
    configuration = getattr(budget, "delegation_configuration", None)
    active(c, row, configuration)
    lock(c, context_id)
    if (
        configuration["ledger_id"] != budget.ledger_id
        or not 1 <= quote.input_token_upper_bound <= configuration["input_tokens"]
        or quote.output_token_ceiling > configuration["output_tokens"]
    ):
        raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
    if c.execute(
        "SELECT 1 FROM draft_assistance.invocations i "
        "JOIN LATERAL (SELECT record FROM draft_assistance.invocation_versions v "
        "WHERE (v.namespace,v.security_domain,v.invocation_id)="
        "(i.namespace,i.security_domain,i.invocation_id) ORDER BY aggregate_version "
        "DESC "
        "LIMIT 1) v ON true "
        "WHERE i.namespace=%s AND i.security_domain=%s AND v.record->>'contextId'=%s "
        "AND (v.record->>'state' IN ('OUTCOME_UNKNOWN','CANCELLATION_REQUESTED') "
        "OR v.record->'localCleanup'->>'reason'='CLEANUP_FAILURE' OR "
        "(i.invocation_id<>%s AND EXISTS(SELECT 1 FROM "
        "draft_provider_budget.reservations r "
        "LEFT JOIN draft_provider_budget.settlements s "
        "USING(namespace,security_domain,ledger_id,reservation_id) WHERE "
        "r.namespace=i.namespace AND r.security_domain=i.security_domain "
        "AND r.invocation_id=i.invocation_id AND s.reservation_id IS NULL)))",
        (
            row["tenant_id"],
            row["security_domain"],
            context_id,
            invocation.invocation_id,
        ),
    ).fetchone():
        raise AuthorityError("CONTEXT_ADMISSION_OUTCOME_UNKNOWN")
    return True


def bind_problem(c, context, result, invocation_id):
    """Link a new Problem to its actual successful draft, never to old 323."""
    if not invocation_id or not available(c):
        return False
    invocation = c.execute(
        "SELECT v.record FROM draft_assistance.invocation_versions v WHERE "
        "namespace=%s AND security_domain=%s AND invocation_id=%s "
        "ORDER BY aggregate_version DESC LIMIT 1",
        (context.scope.tenant_id, context.scope.security_domain, invocation_id),
    ).fetchone()
    if not invocation:
        return False
    value = invocation["record"]
    row = request_row(c, value["contextId"])
    if row is None:
        return False
    if (
        row["subject_id"] != context.principal_id
        or value["initiatingPrincipalId"] != context.principal_id
        or value["state"] != "SUCCEEDED"
        or value["resultKind"] != "DRAFT_READY"
    ):
        raise AuthorityError("CONTEXT_ADMISSION_DRAFT_INVALID")
    active(c, row, row["record"]["configuration"])
    lock(c, row["context_id"])
    identity = result["revision"]["business_problem_id"]
    previous = c.execute(
        "SELECT resource_id,invocation_id FROM "
        "authorization_admin.context_call_objects "
        "WHERE context_id=%s AND owner='BUSINESS_PROBLEM'",
        (row["context_id"],),
    ).fetchone()
    if previous:
        if previous != {"resource_id": identity, "invocation_id": invocation_id}:
            raise AuthorityError("CONTEXT_ADMISSION_PROBLEM_ALREADY_BOUND")
        return True
    c.execute(
        "INSERT INTO authorization_admin.context_call_objects "
        "VALUES(%s,%s,%s,%s,%s,%s)",
        (
            row["tenant_id"],
            row["security_domain"],
            "BUSINESS_PROBLEM",
            identity,
            row["context_id"],
            invocation_id,
        ),
    )
    return True
