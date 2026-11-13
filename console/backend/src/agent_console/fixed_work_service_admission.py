# ruff: noqa: E501 -- Explicit scoped owner queries.
"""Service planning call preparation, using current grants and the original budget.

No browser accounts, approval decisions, provider transport, or execution owner.
"""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path

from psycopg.types.json import Jsonb

from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    ExactGrant,
    TrustedRequestContext,
)
from .digital_employee_definition import digest
from .fixed_work_authoring_postgres import read as read_work
from .fixed_work_service_policy import ServicePlanningPolicy
from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

MIGRATION = (
    Path(__file__).parents[2] / "migrations/0070_fixed_work_service_admission.sql"
)


STRUCTURE = (
    Table(
        "fixed_work_service.schema_migrations", LEDGER_COLUMNS, (primary("version"),)
    ),
    Table(
        "fixed_work_service.planning_preparations",
        columns(
            *(
                (key, "text")
                for key in (
                    "namespace",
                    "security_domain",
                    "subject_id",
                    "credential_id",
                    "work_id",
                    "revision_id",
                    "event_id",
                    "invocation_id",
                    "request_digest",
                    "record_digest",
                    "policy_digest",
                )
            ),
            ("expires_at", "timestamp with time zone"),
            ("record", "jsonb"),
            ("context", "jsonb"),
            ("policy", "jsonb"),
        ),
        (
            primary(
                "namespace", "security_domain", "subject_id", "work_id", "event_id"
            ),
            unique("namespace", "security_domain", "invocation_id"),
            unique("namespace", "security_domain", "work_id", "event_id"),
            foreign(
                ("namespace", "security_domain", "work_id", "revision_id"),
                "fixed_work_authoring.revisions",
                ("namespace", "security_domain", "work_id", "revision_id"),
            ),
        ),
        ("immutable_planning_preparations",),
    ),
)


def require(value, reason="FIXED_WORK_SERVICE_ADMISSION_INVALID"):
    if not value:
        raise AuthorityError(reason)


def migrate(c):
    c.execute("SELECT pg_advisory_xact_lock(3240070)")
    exists = c.execute(
        "SELECT to_regclass('fixed_work_service.schema_migrations') AS name"
    ).fetchone()["name"]
    checksum = sha256(MIGRATION.read_bytes()).hexdigest()
    if not exists:
        c.execute(MIGRATION.read_text())
        c.execute(
            "INSERT INTO fixed_work_service.schema_migrations VALUES(70,%s,'fixed-work-service-planning-v1')",
            (checksum,),
        )
    compatible(c)


def compatible(c):
    require(
        c.execute(
            "SELECT to_regclass('fixed_work_service.schema_migrations') AS name"
        ).fetchone()["name"]
        is not None,
        "FIXED_WORK_SERVICE_SCHEMA_UNAVAILABLE",
    )
    checksum = sha256(MIGRATION.read_bytes()).hexdigest()
    rows = c.execute(
        "SELECT version,checksum,adapter FROM fixed_work_service.schema_migrations ORDER BY version"
    ).fetchall()
    require(
        schema_is_compatible(c, STRUCTURE)
        and rows
        == [
            dict(
                version=70, checksum=checksum, adapter="fixed-work-service-planning-v1"
            )
        ],
        "FIXED_WORK_SERVICE_SCHEMA_INCOMPATIBLE",
    )


def event_key(work, event):
    require(
        isinstance(event, str)
        and 1 <= len(event) <= 200
        and not any(ch.isspace() for ch in event)
    )
    return "fixed-work-plan:" + digest([work.model_dump(mode="json"), event])


class ServicePlanningRegistry:
    def __init__(self, repository, authorization, policy_reader):
        self.repository, self.authorization, self.policy_reader = (
            repository,
            authorization,
            policy_reader,
        )

    def bind(self, context, event):
        return BoundServicePlanningAdmission(self, context, event)

    def _policy(self):
        value = self.policy_reader()
        require(isinstance(value, ServicePlanningPolicy))
        return value

    def _check(self, c, context, policy):
        now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        policy.require(context, now)
        authority = self.authorization
        saved = read_work(
            c,
            (policy.tenantId, policy.securityDomain),
            policy.work.resource_id,
            policy.work.revision_id,
        )
        require(
            saved["digest"] == policy.work.digest, "FIXED_WORK_SERVICE_WORK_CHANGED"
        )
        team = saved["record"]["team"]
        grants = (
            ExactGrant("TEAM", "READ", f"team:{team['teamId']}:{team['revisionId']}"),
            ExactGrant(
                "PLAN", "PREPARE", "plan:prepare:" + policy.target.problem.resource_id
            ),
            ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", policy.model_target),
        )
        kwargs = dict(
            now=now,
            generation=authority.generation.generation,
            recovery_epoch=authority.recovery_epoch,
            connection=c,
        )
        authority.require_current_context(context, grants, **kwargs)
        require(
            authority.has_current_grants(
                context, grants, configure_transaction=False, **kwargs
            )
            == (True,) * len(grants),
            "FIXED_WORK_SERVICE_GRANTS_REQUIRED",
        )
        return now

    @staticmethod
    def _lock(c, policy):
        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                "fixed-work-service:"
                + digest(
                    [
                        policy.tenantId,
                        policy.securityDomain,
                        policy.work.resource_id,
                    ]
                ),
            ),
        )

    @staticmethod
    def _pending(c, policy, own):
        if c.execute(
            "SELECT to_regclass('fixed_work_triggers.receipts') AS name"
        ).fetchone()["name"]:
            unresolved = c.execute(
                "SELECT 1 FROM fixed_work_triggers.receipts r LEFT JOIN execution_authority.prepared_run_progress p "
                "ON p.namespace=r.namespace AND p.security_domain=r.security_domain AND p.workflow_run_id=r.workflow_run_id "
                "WHERE r.namespace=%s AND r.security_domain=%s AND r.work_id=%s "
                "AND (p.record->>'state' IS NULL OR p.record->>'state' NOT IN ('SUCCEEDED','FAILED','CANCELLED')) LIMIT 1",
                (policy.tenantId, policy.securityDomain, policy.work.resource_id),
            ).fetchone()
            require(unresolved is None, "FIXED_WORK_SERVICE_PREVIOUS_RUN_UNRESOLVED")
        rows = c.execute(
            "SELECT p.invocation_id,p.event_id,p.subject_id,r.record AS result FROM fixed_work_service.planning_preparations p LEFT JOIN workflow_planning.invocation_results r USING(namespace,security_domain,invocation_id) WHERE p.namespace=%s AND p.security_domain=%s AND p.work_id=%s AND p.invocation_id<>%s",
            (
                policy.tenantId,
                policy.securityDomain,
                policy.work.resource_id,
                own,
            ),
        ).fetchall()
        for row in rows:
            result = row["result"] or {}
            require(
                result.get("technical_status") in {"SUCCEEDED", "FAILED"},
                "FIXED_WORK_SERVICE_PREVIOUS_OUTCOME_UNRESOLVED",
            )
            pending = c.execute(
                "SELECT 1 FROM draft_provider_budget.reservations r LEFT JOIN draft_provider_budget.settlements s USING(namespace,security_domain,ledger_id,reservation_id) WHERE r.namespace=%s AND r.security_domain=%s AND r.ledger_id=%s AND r.invocation_id=%s AND s.reservation_id IS NULL LIMIT 1",
                (
                    policy.tenantId,
                    policy.securityDomain,
                    policy.ledgerId,
                    row["invocation_id"],
                ),
            ).fetchone()
            require(pending is None, "FIXED_WORK_SERVICE_PREVIOUS_BUDGET_UNRESOLVED")
            if result.get("technical_status") == "SUCCEEDED":
                available = c.execute(
                    "SELECT to_regclass('fixed_work_triggers.receipts') AS name"
                ).fetchone()["name"]
                receipt = (
                    c.execute(
                        "SELECT 1 FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND work_id=%s AND event_id=%s",
                        (
                            policy.tenantId,
                            policy.securityDomain,
                            row["subject_id"],
                            policy.work.resource_id,
                            row["event_id"],
                        ),
                    ).fetchone()
                    if available
                    else None
                )
                require(
                    receipt is not None,
                    "FIXED_WORK_SERVICE_PREVIOUS_CYCLE_AWAITS_CONTINUATION",
                )

    def prepare(self, context, event, request, record):
        policy = self._policy()
        require(event in policy.allowedEventIds, "FIXED_WORK_SERVICE_EVENT_DENIED")
        require(request.idempotency_key == event_key(policy.work, event))
        target = record["target"]
        require(
            (target["namespace"], target["security_domain"])
            == (policy.tenantId, policy.securityDomain)
            and target["problem"] == policy.target.model_dump(mode="json")
            and target["resource_snapshot"]
            == policy.resourceSnapshot.model_dump(mode="json"),
            "FIXED_WORK_SERVICE_SOURCE_CHANGED",
        )
        require(
            request.target == policy.target
            and request.source_proposal is None
            and request.predecessor_invocation_id is None
            and not request.answers
            and request.policy == policy.planningPolicy
            and request.output_language is None
        )
        require(
            record["profile"]["profile_revision_id"] == policy.profileRevisionId
            and record["profile"]["profile_digest"] == policy.profileDigest
            and record["profile"]["model"] == policy.model.model_dump(mode="json")
        )
        request_digest = digest(request.model_dump(mode="json"))
        with self.repository.pool.connection() as c, c.transaction():
            from psycopg.rows import dict_row

            c.row_factory = dict_row
            now = self._check(c, context, policy)
            policy.require_event(event, now)
            self._lock(c, policy)
            old = c.execute(
                "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s AND work_id=%s AND event_id=%s",
                (
                    policy.tenantId,
                    policy.securityDomain,
                    policy.work.resource_id,
                    event,
                ),
            ).fetchone()
            if old:
                require(
                    old["subject_id"] == context.principal_id
                    and old["request_digest"] == request_digest
                    and old["policy"] == policy.model_dump(mode="json")
                    and old["policy_digest"] == policy.digest
                    and old["record_digest"] == digest(old["record"])
                    and old["credential_id"]
                    == context.session_id_or_service_credential_id,
                    "FIXED_WORK_SERVICE_EVENT_CONFLICT",
                )
                return {"invocation": old["record"], "admission": {"ready": True}}
            invocation = record["target"]["invocation_id"]
            self._pending(c, policy, invocation)
            saved = read_work(
                c,
                (policy.tenantId, policy.securityDomain),
                policy.work.resource_id,
                policy.work.revision_id,
            )
            require(
                saved["digest"] == policy.work.digest, "FIXED_WORK_SERVICE_WORK_CHANGED"
            )
            ctx = dict(
                principal=context.principal_id,
                credential=context.session_id_or_service_credential_id,
                policyVersion=context.authentication_policy_version,
                generation=self.authorization.generation.generation,
                recoveryEpoch=self.authorization.recovery_epoch,
            )
            c.execute(
                "INSERT INTO fixed_work_service.planning_preparations VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    policy.tenantId,
                    policy.securityDomain,
                    context.principal_id,
                    context.session_id_or_service_credential_id,
                    policy.work.resource_id,
                    policy.work.revision_id,
                    event,
                    invocation,
                    request_digest,
                    digest(record),
                    policy.digest,
                    policy.expiresAt,
                    Jsonb(record),
                    Jsonb(ctx),
                    Jsonb(policy.model_dump(mode="json")),
                ),
            )
        return {"invocation": record, "admission": {"ready": True}}

    def guard(self, c, budget, invocation, quote):
        row = c.execute(
            "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
            (
                invocation.scope.namespace,
                invocation.scope.security_domain,
                invocation.invocation_id,
            ),
        ).fetchone()
        if row is None:
            return False
        policy = self._verify(c, row)
        require(
            budget.ledger_id == policy.ledgerId
            and invocation.profile_revision_id == policy.profileRevisionId,
            "FIXED_WORK_SERVICE_LEDGER_MISMATCH",
        )
        require(
            1 <= quote.input_token_upper_bound <= policy.maximumInputTokens
            and quote.output_token_ceiling <= policy.maximumOutputTokens,
            "FIXED_WORK_SERVICE_QUOTE_LIMIT",
        )
        actual = c.execute(
            "SELECT actor_id,record FROM workflow_planning.invocations WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
            (row["namespace"], row["security_domain"], row["invocation_id"]),
        ).fetchone()
        require(
            actual is not None
            and actual["actor_id"] == row["subject_id"]
            and actual["record"] == row["record"],
            "FIXED_WORK_SERVICE_INVOCATION_CHANGED",
        )
        terminal = c.execute(
            "SELECT 1 FROM workflow_planning.invocation_results WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
            (row["namespace"], row["security_domain"], row["invocation_id"]),
        ).fetchone()
        require(terminal is None, "FIXED_WORK_SERVICE_INVOCATION_ALREADY_TERMINAL")
        return True

    def _verify(self, c, row, *, dispatch=True):
        policy = self._policy()
        context = TrustedRequestContext(
            row["subject_id"],
            AuthorityScope(row["namespace"], row["security_domain"]),
            row["credential_id"],
            AuthenticationSource.SERVICE_CREDENTIAL,
            row["context"]["policyVersion"],
        )
        now = self._check(c, context, policy)
        if dispatch:
            policy.require_event(row["event_id"], now)
        self._lock(c, policy)
        require(
            row["policy_digest"] == policy.digest
            and row["policy"] == policy.model_dump(mode="json")
            and row["record_digest"] == digest(row["record"])
            and now < row["expires_at"]
        )
        self._pending(c, policy, row["invocation_id"])
        return policy

    def authorize_confirmed_plan(self, c, context, event, plan):
        """Verify original model proposal, before the EXISTING readonly owner.

        Model output remains planning-only. Existing readonly continuation alone
        creates its policy preparation successor, approves/prepares and STARTs.
        """
        from .plan_suggestion_domain import ProposalRevision

        policy = self._policy()
        self._check(c, context, policy)
        self._lock(c, policy)
        require(event in policy.allowedEventIds)
        require(plan.semantics.target == policy.target)
        row = c.execute(
            "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND work_id=%s AND event_id=%s",
            (
                policy.tenantId,
                policy.securityDomain,
                context.principal_id,
                policy.work.resource_id,
                event,
            ),
        ).fetchone()
        require(
            row is not None
            and row["credential_id"] == context.session_id_or_service_credential_id,
            "FIXED_WORK_SERVICE_PLANNING_PROOF_REQUIRED",
        )
        self._verify(c, row, dispatch=False)
        source = c.execute(
            "SELECT record,digest FROM workflow_planning.proposals WHERE namespace=%s AND security_domain=%s AND proposal_id=%s AND revision=%s",
            (
                policy.tenantId,
                policy.securityDomain,
                plan.source_proposal_id,
                plan.source_proposal_revision,
            ),
        ).fetchone()
        require(source is not None)
        proposal = ProposalRevision.model_validate(source["record"])
        require(
            proposal.digest == source["digest"] == plan.source_proposal_digest
            and proposal.origin is None
            and proposal.invocation_id == row["invocation_id"],
            "FIXED_WORK_SERVICE_PROPOSAL_LINEAGE_CHANGED",
        )
        observed = c.execute(
            "SELECT record FROM workflow_planning.invocation_results WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
            (policy.tenantId, policy.securityDomain, row["invocation_id"]),
        ).fetchone()
        require(
            observed is not None
            and observed["record"].get("technical_status") == "SUCCEEDED"
            and observed["record"].get("kind") == "VALID_SUGGESTION"
            and observed["record"].get("proposal_digest") == proposal.digest,
            "FIXED_WORK_SERVICE_PLANNING_RESULT_REQUIRED",
        )
        metering = c.execute(
            "SELECT r.reservation_id,s.reservation_id settled,p.record receipt "
            "FROM draft_provider_budget.reservations r LEFT JOIN draft_provider_budget.settlements s USING(namespace,security_domain,ledger_id,reservation_id) "
            "LEFT JOIN workflow_planning.provider_receipts p USING(namespace,security_domain,invocation_id) "
            "WHERE r.namespace=%s AND r.security_domain=%s AND r.ledger_id=%s AND r.invocation_id=%s",
            (
                policy.tenantId,
                policy.securityDomain,
                policy.ledgerId,
                row["invocation_id"],
            ),
        ).fetchall()
        require(
            len(metering) == 1
            and metering[0]["settled"] == metering[0]["reservation_id"]
            and isinstance(metering[0]["receipt"], dict)
            and metering[0]["receipt"].get("reservation_id")
            == metering[0]["reservation_id"],
            "FIXED_WORK_SERVICE_BUDGET_RECEIPT_REQUIRED",
        )
        return row

    @contextmanager
    def dispatch_guard(self, context, record):
        with self.repository.pool.connection() as c, c.transaction():
            from psycopg.rows import dict_row

            c.row_factory = dict_row
            row = c.execute(
                "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s AND security_domain=%s AND invocation_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    record["target"]["invocation_id"],
                ),
            ).fetchone()
            require(
                row is not None
                and row["subject_id"] == context.principal_id
                and row["credential_id"] == context.session_id_or_service_credential_id
                and row["record"] == record
            )
            self._verify(c, row)
            yield c


class BoundServicePlanningAdmission:
    def __init__(self, registry, context, event):
        self.registry, self.context, self.event = registry, context, event

    def prepare(self, request, record):
        return self.registry.prepare(self.context, self.event, request, record)

    def dispatch_guard(self, record):
        return self.registry.dispatch_guard(self.context, record)
