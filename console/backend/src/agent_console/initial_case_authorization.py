"""D9 one independently signed exact sales call on the original aggregate ledger."""

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .bounded_task_authorization import current
from .bounded_task_policy import TaskAuthorizationRequest, require_configuration
from .context_call_admission import lock, request_row
from .task_delegation import digest


def validate_initial_case(c, spec, scope):
    if spec.purpose != "SALES_DIAGNOSTIC" or spec.initial_case_revision is None:
        raise AuthorityError("INITIAL_CASE_AUTHORIZATION_REQUIRED")
    policy = c.execute(
        "SELECT call_cap,total_cost_cap_microusd FROM draft_provider_budget.policies "
        "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s FOR SHARE",
        (*scope, spec.configuration.ledger_id),
    ).fetchone()
    if policy != {"call_cap": 8, "total_cost_cap_microusd": 10000000}:
        raise AuthorityError("INITIAL_CASE_LEDGER_DENIED")
    # A successor is not an initial-case bypass around a previously unknown call.
    unknown = c.execute(
        "SELECT 1 FROM workflow_planning.invocations i LEFT JOIN "
        "workflow_planning.invocation_results r "
        "USING(namespace,security_domain,invocation_id) "
        "WHERE i.namespace=%s AND i.security_domain=%s "
        "AND i.record->'target'->'problem'->'problem'->>'resource_id'=%s "
        "AND (r.record IS NULL OR r.record->>'technical_status'='OUTCOME_UNKNOWN')",
        (*scope, spec.root.resource_id),
    ).fetchone()
    if unknown:
        raise AuthorityError("INITIAL_CASE_RECOVERY_REQUIRED")


def prepare(service, c, context, request, record):
    if not getattr(service, "bounded_tasks_enabled", False):
        return None
    rows = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE tenant_id=%s "
        "AND security_domain=%s AND subject_id=%s AND root_id=%s "
        "AND record->>'purpose'='SALES_DIAGNOSTIC' ORDER BY created_at DESC",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            request.target.problem.resource_id,
        ),
    ).fetchall()
    if not rows:
        return None
    task = rows[0]
    current(c, task)
    spec = TaskAuthorizationRequest.model_validate(task["record"])
    require_configuration(
        spec.configuration, service.actual_configuration, cleanup_seconds=2
    )
    if (
        spec.root != request.target.problem
        or spec.initial_case_revision.criteria_set != request.target.criteria
    ):
        raise AuthorityError("INITIAL_CASE_TARGET_MISMATCH")
    scope = (task["tenant_id"], task["security_domain"])
    lock(c, "initial-case:" + spec.configuration.ledger_id)
    old = c.execute(
        "SELECT d.*,p.record FROM authorization_admin.initial_case_planning_calls d "
        "JOIN authorization_admin.planning_call_preparations p USING(context_id) "
        "WHERE d.task_request_id=%s",
        (task["request_id"],),
    ).fetchone()
    if old:
        if old["record"]["request"]["idempotency_key"] != request.idempotency_key:
            raise AuthorityError("INITIAL_CASE_SINGLE_CALL_ALREADY_BOUND")
        if (
            old["record"]["target"]["input_commitment"]
            != record["target"]["input_commitment"]
        ):
            raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
        return service._projection(c, request_row(c, old["context_id"]), old["record"])
    validate_initial_case(c, spec, scope)
    if (
        service.configuration["calls"] != 8
        or service.configuration["cost_microusd"] != 10000000
    ):
        raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
    identity = record["target"]["suggestion_context_id"]
    revision = spec.initial_case_revision.model_dump(mode="json")
    payload = dict(
        task_id=spec.task_id,
        phase="planning",
        synthetic_only=True,
        context_id=identity,
        first_invocation_id=record["target"]["invocation_id"],
        source_context_id=identity,
        configuration=service.configuration,
        subject_id=task["subject_id"],
        account_id=task["account_id"],
        account_revision=task["account_revision"],
        target=record["target"],
        task_request_id=task["request_id"],
        cumulative_call_cap=100,
        total_cost_cap_microusd=50000000,
        maximum_new_calls=1,
        initial_case_revision=revision,
    )
    c.execute(
        "INSERT INTO authorization_admin.context_call_requests "
        "(context_id,tenant_id,security_domain,subject_id,account_id,account_revision,first_invocation_id,record,digest)"
        " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
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
        "INSERT INTO authorization_admin.initial_case_planning_calls "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,100,50000000)",
        (
            task["request_id"],
            identity,
            *scope,
            context.principal_id,
            spec.root.resource_id,
            spec.configuration.ledger_id,
        ),
    )
    return service._projection(c, request_row(c, identity), saved)


def require_link(c, row, task, spec):
    link = c.execute(
        "SELECT * FROM authorization_admin.initial_case_planning_calls WHERE "
        "context_id=%s AND task_request_id=%s AND tenant_id=%s AND "
        "security_domain=%s AND subject_id=%s AND root_id=%s AND ledger_id=%s",
        (
            row["context_id"],
            task["request_id"],
            row["tenant_id"],
            row["security_domain"],
            row["subject_id"],
            spec.root.resource_id,
            spec.configuration.ledger_id,
        ),
    ).fetchone()
    if (
        not link
        or row["record"].get("initial_case_revision")
        != spec.initial_case_revision.model_dump(mode="json")
        or row["record"]["target"]["problem"]["criteria"]
        != spec.initial_case_revision.criteria_set.model_dump(mode="json")
        or row["record"]["target"]["problem"]["problem"]
        != spec.root.model_dump(mode="json")
    ):
        raise AuthorityError("INITIAL_CASE_TARGET_MISMATCH")
    return link


def limits(c, row, budget, original):
    if not row["record"].get("initial_case_revision"):
        return None
    task = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE "
        "request_id=%s AND tenant_id=%s AND security_domain=%s AND "
        "subject_id=%s",
        (
            row["record"]["task_request_id"],
            row["tenant_id"],
            row["security_domain"],
            row["subject_id"],
        ),
    ).fetchone()
    if not task:
        raise AuthorityError("INITIAL_CASE_AUTHORIZATION_REQUIRED")
    current(c, task)
    spec = TaskAuthorizationRequest.model_validate(task["record"])
    require_configuration(
        spec.configuration,
        getattr(budget, "task_actual_configuration", {}),
        cleanup_seconds=2,
    )
    link = require_link(c, row, task, spec)
    if (
        original != 8
        or link["ledger_id"] != budget.ledger_id
        or link["cumulative_call_cap"] != 100
        or link["total_cost_cap_microusd"] != 50000000
    ):
        raise AuthorityError("INITIAL_CASE_LEDGER_DENIED")
    return 100, 50000000
