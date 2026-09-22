"""D324-6 exact staged planning object; one additive count, never money bypass."""

import hashlib
from datetime import UTC, datetime

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .context_call_admission import (
    SCOPE,
    SUBJECT,
    ContextCallAdmission,
    active,
    lock,
    request_row,
)
from .task_delegation import digest


def available(c):
    return bool(
        c.execute(
            "SELECT "
            "to_regclass('authorization_admin.planning_call_preparations') AS name"
        ).fetchone()["name"]
    )


class PlanningCallAdmission(ContextCallAdmission):
    def migrate(self):
        path = (
            self.repository.migration_path.parent / "0038_planning_call_allowance.sql"
        )
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            previous = c.execute(
                "SELECT checksum FROM authorization_admin.schema_migrations "
                "WHERE version=38"
            ).fetchone()
            if previous:
                if previous["checksum"] != checksum:
                    raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
                return
            c.execute(path.read_text())
            c.execute(
                "INSERT INTO authorization_admin.schema_migrations "
                "(version,checksum,adapter) VALUES(38,%s,'planning-call-allowance-v1')",
                (checksum,),
            )

    def prepare_record(self, context, request, record):
        """Persist the actual generated object before signing or invocation claim."""
        scope = (context.scope.tenant_id, context.scope.security_domain)
        with self.repository.connection_scope() as c:
            source = c.execute(
                "SELECT context_id FROM authorization_admin.context_call_objects "
                "WHERE tenant_id=%s AND security_domain=%s AND "
                "owner='BUSINESS_PROBLEM' "
                "AND resource_id=%s",
                (*scope, request.target.problem.resource_id),
            ).fetchone()
            if source is None:
                return None  # Original 323 admission remains unchanged.
            if scope != SCOPE or context.principal_id != SUBJECT:
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            account = c.execute(
                "SELECT a.* FROM browser_identity.local_accounts a JOIN "
                "browser_identity.local_account_sessions s USING(account_id) "
                "WHERE s.session_id=%s AND a.revision=s.account_revision "
                "AND a.status='ENABLED' FOR SHARE OF a",
                (context.session_id_or_service_credential_id,),
            ).fetchone()
            if account is None or account["status"] != "ENABLED":
                raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
            source_row = request_row(c, source["context_id"])
            if source_row["subject_id"] != context.principal_id:
                raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
            key = (*scope, context.principal_id, request.idempotency_key)
            lock(c, "planning:" + digest(key))
            previous = c.execute(
                "SELECT * FROM authorization_admin.planning_call_preparations "
                "WHERE tenant_id=%s AND security_domain=%s "
                "AND subject_id=%s AND request_key=%s",
                key,
            ).fetchone()
            if previous:
                if previous["input_commitment"] != record["target"]["input_commitment"]:
                    raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
                row = request_row(c, previous["context_id"])
                if row["record"]["configuration"] != self.configuration:
                    raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
                return self._projection(c, row, previous["record"])
            original = c.execute(
                "SELECT d.record->'planning' AS config FROM "
                "authorization_admin.task_delegations d "
                "JOIN authorization_admin.task_delegation_ledgers l "
                "USING(delegation_id) "
                "WHERE l.tenant_id=%s AND l.security_domain=%s "
                "AND l.ledger_id=%s AND l.purpose='planning' "
                "AND d.task_id='S5-V023-ARCH-323' "
                "AND d.subject_id='human:demo323-requester'",
                (*scope, self.configuration["ledger_id"]),
            ).fetchone()
            if not original or original["config"] != self.configuration:
                raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
            record = {
                **record,
                "bounded_new_calls": 1,
                "request": record["request"]
                if "request" in record
                else request.model_dump(mode="json"),
                "submitted_at": record.get(
                    "submitted_at", datetime.now(UTC).isoformat()
                ),
            }
            identity = record["target"]["suggestion_context_id"]
            payload = dict(
                task_id="S5-V023-IMPL-324",
                phase="planning",
                synthetic_only=True,
                context_id=identity,
                first_invocation_id=record["target"]["invocation_id"],
                source_context_id=source["context_id"],
                configuration=self.configuration,
                subject_id=context.principal_id,
                account_id=account["account_id"],
                account_revision=account["revision"],
                target=record["target"],
                cumulative_call_cap=20,
                maximum_new_calls=1,
            )
            c.execute(
                "INSERT INTO authorization_admin.context_call_requests "
                "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,"
                "first_invocation_id,record,digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
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
            c.execute(
                "INSERT INTO authorization_admin.planning_call_preparations "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (*key, identity, record["target"]["input_commitment"], Jsonb(record)),
            )
            return self._projection(c, request_row(c, identity), record)

    def _projection(self, c, row, record):
        try:
            active(c, row, self.configuration)
            ready = True
        except AuthorityError as exc:
            if exc.reason_code != "CONTEXT_ADMISSION_REQUIRED":
                raise
            ready = False
        return {
            "invocation": record,
            "result": {
                "technical_status": "AUTHORIZATION_PENDING",
                "kind": None,
                "reason": "PLANNING_EXACT_ADMISSION_REQUIRED",
            },
            "admission": {
                "context_id": row["context_id"],
                "ready": ready,
                "maximum_new_calls": 1,
                "cumulative_call_cap": 20,
            },
        }

    def recover(self, context, key):
        with self.repository.connection_scope() as c:
            row = c.execute(
                "SELECT * FROM authorization_admin.planning_call_preparations "
                "WHERE tenant_id=%s AND security_domain=%s "
                "AND subject_id=%s AND request_key=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    context.principal_id,
                    key,
                ),
            ).fetchone()
            if row is None:
                return None
            return self._projection(c, request_row(c, row["context_id"]), row["record"])

    def before_approve(self, c, row):
        scope = (
            row["tenant_id"],
            row["security_domain"],
            self.configuration["ledger_id"],
        )
        policy = c.execute(
            "SELECT call_cap,total_cost_cap_microusd FROM "
            "draft_provider_budget.policies "
            "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s FOR UPDATE",
            scope,
        ).fetchone()
        if policy != {"call_cap": 8, "total_cost_cap_microusd": 10000000}:
            raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
        c.execute(
            "INSERT INTO authorization_admin.planning_call_allowances "
            "(tenant_id,security_domain,ledger_id,context_id,"
            "original_call_cap,cumulative_call_cap) "
            "VALUES(%s,%s,%s,%s,8,20) ON CONFLICT DO NOTHING",
            (*scope, row["context_id"]),
        )
        chosen = c.execute(
            "SELECT context_id FROM authorization_admin.planning_call_allowances "
            "WHERE tenant_id=%s AND security_domain=%s AND ledger_id=%s",
            scope,
        ).fetchone()
        if chosen["context_id"] != row["context_id"]:
            raise AuthorityError("PLANNING_SINGLE_ALLOWANCE_ALREADY_BOUND")


def guarded_row(c, budget, invocation):
    if not available(c):
        return None
    row = c.execute(
        "SELECT r.* FROM authorization_admin.context_call_requests r "
        "WHERE r.record->>'phase'='planning' AND r.first_invocation_id=%s "
        "AND r.tenant_id=%s AND r.security_domain=%s",
        (
            invocation.invocation_id,
            invocation.scope.namespace,
            invocation.scope.security_domain,
        ),
    ).fetchone()
    if row is None:
        return None
    active(c, row, getattr(budget, "delegation_configuration", None))
    lock(c, row["context_id"])
    actual = c.execute(
        "SELECT actor_id,record FROM workflow_planning.invocations "
        "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
        (row["tenant_id"], row["security_domain"], invocation.invocation_id),
    ).fetchone()
    if (
        not actual
        or actual["actor_id"] != row["subject_id"]
        or actual["record"]["target"] != row["record"]["target"]
    ):
        raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
    if c.execute(
        "SELECT 1 FROM draft_assistance.invocations i JOIN LATERAL "
        "(SELECT record FROM draft_assistance.invocation_versions v WHERE "
        "(v.namespace,v.security_domain,v.invocation_id)="
        "(i.namespace,i.security_domain,i.invocation_id) "
        "ORDER BY aggregate_version DESC LIMIT 1) v ON true "
        "WHERE i.namespace=%s AND i.security_domain=%s "
        "AND v.record->>'contextId'=%s AND "
        "(v.record->>'state' IN ('OUTCOME_UNKNOWN','CANCELLATION_REQUESTED') "
        "OR v.record->'localCleanup'->>'reason'='CLEANUP_FAILURE' "
        "OR EXISTS(SELECT 1 FROM draft_provider_budget.reservations r "
        "LEFT JOIN draft_provider_budget.settlements s "
        "USING(namespace,security_domain,ledger_id,reservation_id) "
        "WHERE r.namespace=i.namespace AND r.security_domain=i.security_domain "
        "AND r.invocation_id=i.invocation_id AND s.reservation_id IS NULL))",
        (row["tenant_id"], row["security_domain"], row["record"]["source_context_id"]),
    ).fetchone():
        raise AuthorityError("CONTEXT_ADMISSION_OUTCOME_UNKNOWN")
    terminal = c.execute(
        "SELECT 1 FROM workflow_planning.invocation_results "
        "WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
        (row["tenant_id"], row["security_domain"], invocation.invocation_id),
    ).fetchone()
    if terminal:
        raise AuthorityError("CONTEXT_ADMISSION_OUTCOME_UNKNOWN")
    return row


def guard(c, budget, invocation, quote):
    row = guarded_row(c, budget, invocation)
    if row is None:
        return False
    limits = row["record"]["configuration"]
    if (
        limits["ledger_id"] != budget.ledger_id
        or not 1 <= quote.input_token_upper_bound <= limits["input_tokens"]
        or quote.output_token_ceiling > limits["output_tokens"]
    ):
        raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
    effective_cap(c, budget, invocation, 8)
    return True


def effective_cap(c, budget, invocation, original):
    row = guarded_row(c, budget, invocation)
    if row is None:
        return original
    allowance = c.execute(
        "SELECT cumulative_call_cap FROM authorization_admin.planning_call_allowances "
        "WHERE tenant_id=%s AND security_domain=%s AND ledger_id=%s AND context_id=%s",
        (row["tenant_id"], row["security_domain"], budget.ledger_id, row["context_id"]),
    ).fetchone()
    if allowance is None or original != 8:
        raise AuthorityError("PLANNING_EXACT_ADMISSION_REQUIRED")
    return allowance["cumulative_call_cap"]


class BoundPlanningAdmission:
    def __init__(self, service, context):
        self.service, self.context = service, context

    def prepare(self, request, record):
        return self.service.prepare_record(self.context, request, record)

    def recover(self, key):
        prepared = self.service.recover(self.context, key)
        if prepared and prepared["admission"]["ready"]:
            try:
                with self.dispatch_guard(prepared["invocation"]):
                    pass
            except AuthorityError as exc:
                prepared["admission"]["ready"] = False
                prepared["admission"]["reasonCode"] = exc.reason_code
        return prepared

    def dispatch_guard(self, record):
        from contextlib import contextmanager

        from .authority_contracts import ExactGrant
        from .local_accounts import current_session_account

        @contextmanager
        def guarded():
            with self.service.repository.connection_scope() as c:
                if not current_session_account(
                    c, session_id=self.context.session_id_or_service_credential_id
                ):
                    raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
                row = request_row(c, record["target"]["suggestion_context_id"])
                if row is None:
                    yield
                    return
                if (row["subject_id"], row["tenant_id"], row["security_domain"]) != (
                    self.context.principal_id,
                    self.context.scope.tenant_id,
                    self.context.scope.security_domain,
                ):
                    raise AuthorityError("CONTEXT_ADMISSION_SCOPE_DENIED")
                active(c, row, self.service.configuration)
                grants = self.service.delegation.grants
                problem = record["target"]["problem"]["problem"]["resource_id"]
                exacts = (
                    ExactGrant("PLAN", "PREPARE", "plan:prepare:" + problem),
                    ExactGrant(
                        "MODEL_GOVERNANCE",
                        "INVOKE_MODEL",
                        self.service.configuration["model_target"],
                    ),
                )
                if not all(
                    grants.authorization.has_current_grants(
                        self.context,
                        exacts,
                        now=datetime.now(UTC),
                        generation=grants.generation.generation,
                        recovery_epoch=grants.recovery_epoch,
                        connection=c,
                        configure_transaction=False,
                    )
                ):
                    raise AuthorityError("CONTEXT_ADMISSION_GRANTS_REQUIRED")
                yield

        return guarded()
