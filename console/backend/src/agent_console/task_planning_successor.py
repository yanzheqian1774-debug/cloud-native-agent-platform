"""D324-7 exact successor linked to signed task and unchanged original ledger."""

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .bounded_task_authorization import current
from .bounded_task_policy import TaskAuthorizationRequest, require_configuration
from .context_call_admission import lock, request_row
from .task_delegation import digest


def prepare(service, c, context, request, record):
    """Only an installed, independently signed task can select the D7 path."""
    if not getattr(service, "bounded_tasks_enabled", False):
        return None
    rows = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE tenant_id=%s "
        "AND security_domain=%s AND subject_id=%s AND root_id=%s "
        "AND record->>'purpose'='SAME_CASE_DELIVERY' ORDER BY created_at DESC",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            request.target.problem.resource_id,
        ),
    ).fetchall()
    if not rows:
        return None
    row = rows[0]
    current(c, row)
    spec = TaskAuthorizationRequest.model_validate(row["record"])
    if spec.configuration is None or spec.root != request.target.problem:
        raise AuthorityError("TASK_AUTHORIZATION_CONFIGURATION_MISMATCH")
    require_configuration(
        spec.configuration, service.actual_configuration, cleanup_seconds=2
    )
    scope = (row["tenant_id"], row["security_domain"])
    lock(c, "d7-planning:" + spec.configuration.ledger_id)
    prior = c.execute(
        "SELECT s.*,i.record FROM authorization_admin.task_planning_successors s "
        "JOIN authorization_admin.planning_call_preparations i USING(context_id) "
        "WHERE s.tenant_id=%s AND s.security_domain=%s AND s.ledger_id=%s",
        (*scope, spec.configuration.ledger_id),
    ).fetchone()
    if prior:
        if (
            prior["task_request_id"] != row["request_id"]
            or prior["record"]["request"]["idempotency_key"] != request.idempotency_key
        ):
            raise AuthorityError("PLANNING_SINGLE_ALLOWANCE_ALREADY_BOUND")
        if (
            prior["record"]["target"]["input_commitment"]
            != record["target"]["input_commitment"]
        ):
            raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
        return service._projection(
            c, request_row(c, prior["context_id"]), prior["record"]
        )
    validate_recovery(c, spec, scope, service.configuration)
    configuration = service.configuration
    if configuration["calls"] != 8 or configuration["cost_microusd"] != 10000000:
        raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
    identity = record["target"]["suggestion_context_id"]
    payload = dict(
        task_id=spec.task_id,
        phase="planning",
        synthetic_only=True,
        context_id=identity,
        first_invocation_id=record["target"]["invocation_id"],
        source_context_id=identity,
        configuration=configuration,
        subject_id=row["subject_id"],
        account_id=row["account_id"],
        account_revision=row["account_revision"],
        target=record["target"],
        task_request_id=row["request_id"],
        cumulative_call_cap=21,
        maximum_new_calls=1,
    )
    c.execute(
        "INSERT INTO authorization_admin.context_call_requests "
        "(context_id,tenant_id,security_domain,subject_id,account_id,"
        "account_revision,first_invocation_id,record,digest) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            identity,
            *scope,
            row["subject_id"],
            row["account_id"],
            row["account_revision"],
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
        "INSERT INTO authorization_admin.planning_call_preparations VALUES(%s,%s,"
        "%s,%s,%s,%s,%s)",
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
        "INSERT INTO authorization_admin.task_planning_successors VALUES(%s,%s,"
        "%s,%s,%s,%s,8,20,21)",
        (
            row["request_id"],
            identity,
            spec.recovery_invocation_id,
            *scope,
            spec.configuration.ledger_id,
        ),
    )
    return service._projection(c, request_row(c, identity), saved)


def require_task(c, row, actual):
    identity = row["record"].get("task_request_id")
    if not identity:
        return False
    task = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE request_id=%s "
        "AND tenant_id=%s AND security_domain=%s AND subject_id=%s",
        (identity, row["tenant_id"], row["security_domain"], row["subject_id"]),
    ).fetchone()
    if not task:
        raise AuthorityError("TASK_AUTHORIZATION_SCOPE_DENIED")
    current(c, task)
    spec = TaskAuthorizationRequest.model_validate(task["record"])
    require_configuration(spec.configuration, actual, cleanup_seconds=2)
    return True


def cap(c, row, budget, original):
    if not row["record"].get("task_request_id"):
        return None
    require_task(c, row, getattr(budget, "task_actual_configuration", {}))
    extension = c.execute(
        "SELECT cumulative_call_cap FROM authorization_admin.task_planning_successors "
        "WHERE context_id=%s AND task_request_id=%s AND tenant_id=%s AND "
        "security_domain=%s AND ledger_id=%s",
        (
            row["context_id"],
            row["record"]["task_request_id"],
            row["tenant_id"],
            row["security_domain"],
            budget.ledger_id,
        ),
    ).fetchone()
    if original != 8 or not extension:
        raise AuthorityError("PLANNING_EXACT_ADMISSION_REQUIRED")
    return extension["cumulative_call_cap"]


def validate_recovery(c, spec, scope, configuration):
    predecessor = c.execute(
        "SELECT i.record->'target' AS target,r.record AS result, "
        "q.record->'configuration' AS original_config FROM "
        "workflow_planning.invocations i "
        "JOIN workflow_planning.invocation_results r USING(namespace,"
        "security_domain,invocation_id) "
        "JOIN authorization_admin.context_call_requests q ON "
        "q.first_invocation_id=i.invocation_id "
        "AND q.tenant_id=i.namespace AND q.security_domain=i.security_domain "
        "JOIN authorization_admin.planning_call_allowances a ON "
        "a.context_id=q.context_id "
        "WHERE i.namespace=%s AND i.security_domain=%s AND i.invocation_id=%s "
        "AND a.ledger_id=%s",
        (*scope, spec.recovery_invocation_id, spec.configuration.ledger_id),
    ).fetchone()
    if (
        not predecessor
        or predecessor["result"].get("technical_status") != "OUTCOME_UNKNOWN"
        or predecessor["target"]["problem"]["problem"]
        != spec.root.model_dump(mode="json")
    ):
        raise AuthorityError("TASK_AUTHORIZATION_RECOVERY_TARGET_DENIED")
    original = predecessor["original_config"]
    if original["configuration_digest"] != spec.configuration.predecessor_digest or {
        k: v for k, v in original.items() if k != "configuration_digest"
    } != {k: v for k, v in configuration.items() if k != "configuration_digest"}:
        raise AuthorityError("TASK_AUTHORIZATION_CONFIGURATION_MISMATCH")
