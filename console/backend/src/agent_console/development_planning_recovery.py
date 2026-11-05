"""D8 append-only observations and independently signed fresh development calls.

Observations describe evidence, never adjudicate usage or change old UNKNOWNs.
Each signed task admits one new exact invocation, with all history under100/USD50.
"""

from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field

from .authority_contracts import AuthorityError
from .bounded_task_authorization import current
from .bounded_task_policy import TaskAuthorizationRequest, require_configuration
from .context_call_admission import SCOPE, SUBJECT, lock, request_row
from .plan_suggestion_domain import Digest, ExactReference, Identity, Immutable
from .task_delegation import digest


class RecoveryObservation(Immutable):
    root: ExactReference
    invocation_id: Identity
    evidence_digest: Digest
    evidence_summary: str = Field(min_length=1, max_length=2000)
    idempotency_key: Identity
    # LOCAL_ONLY cannot be promoted to supplier outcome/usage by this API.
    provenance: Literal["LOCAL_ONLY"]
    local_cleanup_confirmed: Literal[True]


def available(c):
    return bool(
        c.execute(
            "SELECT "
            "to_regclass('authorization_admin.development_planning_followups') AS name"
        ).fetchone()["name"]
    )


def source(c, scope, root, invocation_id, subject):
    row = c.execute(
        "SELECT i.record->'target' AS target,i.actor_id,p.created_by,"
        "r.digest AS root_digest FROM workflow_planning.invocations i "
        "JOIN business_problem_authority.problems p ON p.namespace=i.namespace "
        "AND p.security_domain=i.security_domain AND p.business_problem_id=%s "
        "JOIN business_problem_authority.problem_revisions r ON "
        "r.namespace=p.namespace "
        "AND r.security_domain=p.security_domain AND "
        "r.business_problem_id=p.business_problem_id "
        "WHERE i.namespace=%s "
        "AND i.security_domain=%s AND i.invocation_id=%s AND r.revision_id=%s",
        (root.resource_id, *scope, invocation_id, root.revision_id),
    ).fetchone()
    if (
        not row
        or row["actor_id"] != subject
        or row["created_by"] != subject
        or row["root_digest"] != root.digest
        or row["target"]["problem"]["problem"] != root.model_dump(mode="json")
    ):
        raise AuthorityError("DEVELOPMENT_RECOVERY_TARGET_DENIED")
    return row


def observe(service, context, spec):
    scope = (context.scope.tenant_id, context.scope.security_domain)
    if scope != SCOPE or context.principal_id != SUBJECT:
        raise AuthorityError("DEVELOPMENT_RECOVERY_SCOPE_DENIED")
    root = spec.root.model_dump(mode="json")
    legacy_root = service.root_bindings.get(("SAME_CASE_DELIVERY", *scope))
    sales_root = service.root_bindings.get(
        ("SALES_DIAGNOSTIC", *scope, spec.root.resource_id)
    )
    if root not in (legacy_root, sales_root):
        raise AuthorityError("DEVELOPMENT_RECOVERY_TARGET_DENIED")
    from .local_accounts import current_session_account

    with service.repository.connection_scope() as c:
        if not current_session_account(
            c, session_id=context.session_id_or_service_credential_id
        ):
            raise AuthorityError("CONTEXT_ADMISSION_ACCOUNT_INACTIVE")
        source(c, scope, spec.root, spec.invocation_id, context.principal_id)
        payload = spec.model_dump(mode="json")
        key = (*scope, context.principal_id, spec.idempotency_key)
        lock(c, "d8-observation:" + digest(key))
        prior = c.execute(
            "SELECT * FROM authorization_admin.planning_recovery_observations "
            "WHERE tenant_id=%s AND security_domain=%s AND subject_id=%s AND "
            "request_key=%s",
            key,
        ).fetchone()
        if prior:
            if prior["digest"] != digest(payload):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return prior
        identity = "planning-recovery-observation:" + uuid4().hex
        return c.execute(
            "INSERT INTO authorization_admin.planning_recovery_observations "
            "(observation_id,tenant_id,security_domain,subject_id,root_id,invocation_id,"
            "request_key,digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                identity,
                *scope,
                context.principal_id,
                spec.root.resource_id,
                spec.invocation_id,
                spec.idempotency_key,
                digest(payload),
                Jsonb(payload),
            ),
        ).fetchone()


def validate_followup(c, spec, scope, subject):
    if not available(c) or scope != SCOPE or subject != SUBJECT:
        raise AuthorityError("DEVELOPMENT_RECOVERY_SCOPE_DENIED")
    source(c, scope, spec.root, spec.recovery_invocation_id, subject)
    ids = spec.development_revision.recovery_observation_ids
    if len(ids) != len(set(ids)):
        raise AuthorityError("DEVELOPMENT_RECOVERY_OBSERVATION_REQUIRED")
    found_predecessor = False
    for identity in ids:
        obs = c.execute(
            "SELECT * FROM authorization_admin.planning_recovery_observations "
            "WHERE observation_id=%s AND tenant_id=%s AND security_domain=%s "
            "AND subject_id=%s AND root_id=%s",
            (identity, *scope, subject, spec.root.resource_id),
        ).fetchone()
        if (
            not obs
            or digest(obs["record"]) != obs["digest"]
            or obs["record"]["root"] != spec.root.model_dump(mode="json")
        ):
            raise AuthorityError("DEVELOPMENT_RECOVERY_OBSERVATION_REQUIRED")
        found_predecessor |= obs["invocation_id"] == spec.recovery_invocation_id
    if not found_predecessor:
        raise AuthorityError("DEVELOPMENT_RECOVERY_OBSERVATION_REQUIRED")
    # A new branch cannot escape the original D7 or an earlier D8 ledger chain.
    prior = c.execute(
        "SELECT q.context_id FROM authorization_admin.context_call_requests q "
        "JOIN draft_provider_budget.reservations r ON r.namespace=q.tenant_id "
        "AND r.security_domain=q.security_domain AND "
        "r.invocation_id=q.first_invocation_id "
        "WHERE q.tenant_id=%s AND q.security_domain=%s AND q.subject_id=%s "
        "AND q.first_invocation_id=%s AND r.ledger_id=%s AND (EXISTS(SELECT 1 FROM "
        "authorization_admin.task_planning_successors s WHERE "
        "s.context_id=q.context_id "
        "AND s.ledger_id=r.ledger_id) OR EXISTS(SELECT 1 FROM "
        "authorization_admin.development_planning_followups d WHERE "
        "d.context_id=q.context_id "
        "AND d.ledger_id=r.ledger_id))",
        (*scope, subject, spec.recovery_invocation_id, spec.configuration.ledger_id),
    ).fetchone()
    if not prior:
        raise AuthorityError("DEVELOPMENT_RECOVERY_LEDGER_DENIED")


def prepare(service, c, context, request, record, task, spec):
    scope = (task["tenant_id"], task["security_domain"])
    require_configuration(
        spec.configuration, service.actual_configuration, cleanup_seconds=2
    )
    validate_followup(c, spec, scope, context.principal_id)
    lock(c, "d8-planning:" + spec.configuration.ledger_id)
    old = c.execute(
        "SELECT d.*,p.record FROM authorization_admin.development_planning_followups d "
        "JOIN authorization_admin.planning_call_preparations p USING(context_id) "
        "WHERE d.tenant_id=%s AND d.security_domain=%s AND d.ledger_id=%s "
        "AND (d.predecessor_invocation_id=%s OR d.task_request_id=%s)",
        (
            *scope,
            spec.configuration.ledger_id,
            spec.recovery_invocation_id,
            task["request_id"],
        ),
    ).fetchone()
    if old:
        if (
            old["task_request_id"] != task["request_id"]
            or old["record"]["request"]["idempotency_key"] != request.idempotency_key
        ):
            raise AuthorityError("DEVELOPMENT_FOLLOWUP_ALREADY_BOUND")
        if (
            old["record"]["target"]["input_commitment"]
            != record["target"]["input_commitment"]
        ):
            raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
        return service._projection(c, request_row(c, old["context_id"]), old["record"])
    if (
        service.configuration["calls"] != 8
        or service.configuration["cost_microusd"] != 10000000
    ):
        raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
    source_context = record["target"]["suggestion_context_id"]
    identity = (
        record["target"]["invocation_id"]
        if getattr(request, "predecessor_invocation_id", None)
        else source_context
    )
    payload = dict(
        task_id=spec.task_id,
        phase="planning",
        synthetic_only=True,
        context_id=identity,
        first_invocation_id=record["target"]["invocation_id"],
        source_context_id=source_context,
        configuration=service.configuration,
        subject_id=task["subject_id"],
        account_id=task["account_id"],
        account_revision=task["account_revision"],
        target=record["target"],
        task_request_id=task["request_id"],
        cumulative_call_cap=100,
        total_cost_cap_microusd=50000000,
        maximum_new_calls=1,
        development_revision=spec.development_revision.model_dump(mode="json"),
    )
    c.execute(
        "INSERT INTO authorization_admin.context_call_requests "
        "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,"
        "first_invocation_id,record,digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            identity,
            *scope,
            task["subject_id"],
            task["account_id"],
            task["account_revision"],
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
        "INSERT INTO authorization_admin.planning_call_preparations "
        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (
            *scope,
            context.principal_id,
            request.idempotency_key,
            identity,
            record["target"]["input_commitment"],
            Jsonb(saved),
        ),
    )
    c.execute(
        "INSERT INTO authorization_admin.development_planning_followups "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,100,50000000)",
        (
            task["request_id"],
            identity,
            spec.recovery_invocation_id,
            *scope,
            context.principal_id,
            spec.root.resource_id,
            spec.configuration.ledger_id,
        ),
    )
    return service._projection(c, request_row(c, identity), saved)


def limits(c, row, budget, original):
    if not row["record"].get("development_revision"):
        return None
    task = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE "
        "request_id=%s AND tenant_id=%s AND security_domain=%s AND subject_id=%s",
        (
            row["record"]["task_request_id"],
            row["tenant_id"],
            row["security_domain"],
            row["subject_id"],
        ),
    ).fetchone()
    if not task:
        raise AuthorityError("TASK_AUTHORIZATION_SCOPE_DENIED")
    current(c, task)
    spec = TaskAuthorizationRequest.model_validate(task["record"])
    require_configuration(
        spec.configuration,
        getattr(budget, "task_actual_configuration", {}),
        cleanup_seconds=2,
    )
    ext = c.execute(
        "SELECT * FROM authorization_admin.development_planning_followups "
        "WHERE context_id=%s AND task_request_id=%s AND tenant_id=%s AND "
        "security_domain=%s AND ledger_id=%s",
        (
            row["context_id"],
            task["request_id"],
            row["tenant_id"],
            row["security_domain"],
            budget.ledger_id,
        ),
    ).fetchone()
    if (
        original != 8
        or not ext
        or spec.development_revision is None
        or row["record"]["development_revision"]
        != spec.development_revision.model_dump(mode="json")
        or ext["cumulative_call_cap"] != spec.development_revision.cumulative_call_cap
        or ext["total_cost_cap_microusd"]
        != spec.development_revision.total_cost_cap_microusd
    ):
        raise AuthorityError("DEVELOPMENT_PLANNING_REVISION_MISMATCH")
    return ext["cumulative_call_cap"], ext["total_cost_cap_microusd"]


def read_observation(service, context, identity):
    """Exact GET under the original subject or existing independent admin rights."""
    with service.repository.connection_scope() as c:
        row = c.execute(
            "SELECT * FROM authorization_admin.planning_recovery_observations "
            "WHERE observation_id=%s AND tenant_id=%s AND security_domain=%s",
            (identity, context.scope.tenant_id, context.scope.security_domain),
        ).fetchone()
        if not row:
            raise AuthorityError("DEVELOPMENT_RECOVERY_NOT_FOUND")
        if row["subject_id"] != context.principal_id:
            service.delegation._admin(context, c)
        if digest(row["record"]) != row["digest"]:
            raise AuthorityError("DEVELOPMENT_RECOVERY_RECORD_INVALID")
        return row
