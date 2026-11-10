"""Exact saved association for an already-authorized ResourceUse read."""

from .execution_domain import ScopeIdentity
from .prepared_execution_lineage import prepared_attempt
from .resource_use_domain import canonical_digest, stable_id


def read_saved_use_binding(connection, preparation, use_id):
    """Caller must enforce the exact RESOURCE_USE READ grant before calling."""
    p = preparation
    row = connection.execute(
        "SELECT record FROM resource_use.uses WHERE namespace=%s "
        "AND security_domain=%s AND resource_use_id=%s",
        (p.namespace, p.security_domain, use_id),
    ).fetchone()
    if not row or not isinstance(row["record"], dict):
        return None
    b = row["record"]
    expected = {
        "resource_use_id": use_id,
        "scope": {"namespace": p.namespace, "security_domain": p.security_domain},
        "workflow_run_id": p.run_id,
        "plan_id": p.plan_id,
        "plan_version": p.plan_version,
        "plan_digest": p.plan_digest,
        "resource_kind": "SKILL",
        "slot_key": "skill:primary",
        "occurrence_ordinal": 1,
    }
    if any(b.get(k) != value for k, value in expected.items()):
        return None
    attempt_id = b.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        return None
    scope = ScopeIdentity(p.namespace, p.security_domain)
    attempt = prepared_attempt(connection, scope, attempt_id)
    if not attempt or attempt["workflow_run_id"] != p.run_id:
        return None
    task = next((t for t in p.participants if t.task_id == attempt["task_id"]), None)
    ordinal = attempt["attempt_ordinal"]
    if task is None or not isinstance(ordinal, int) or ordinal < 1:
        return None
    if attempt_id != stable_id(
        "prepared-attempt", p.run_id, task.task_id, str(ordinal)
    ):
        return None
    if use_id != stable_id(
        "resource-use",
        p.namespace,
        p.security_domain,
        attempt_id,
        "SKILL",
        "skill:primary",
        "1",
    ):
        return None
    reference, employee = task.skill.reference, task.definition
    binding_id = stable_id(
        "skill-binding",
        employee.resource_id,
        employee.revision_id,
        reference.resource_id,
        reference.revision_id,
    )
    binding_digest = canonical_digest(
        {
            "bindingId": binding_id,
            "employeeDefinitionId": employee.resource_id,
            "employeeRevisionId": employee.revision_id,
            "skillId": reference.resource_id,
            "skillRevisionId": reference.revision_id,
            "skillDigest": reference.digest,
            "operation": task.skill.operation,
        }
    )
    exact = {
        "binding_id": binding_id,
        "binding_digest": binding_digest,
        "task_run_id": attempt["task_run_id"],
        "resource_id": reference.resource_id,
        "resource_revision_id": reference.revision_id,
        "resource_digest": reference.digest,
        "digital_employee_definition_id": employee.resource_id,
        "digital_employee_definition_revision_id": employee.revision_id,
        "digital_employee_definition_digest": employee.digest,
        "digital_employee_instance_id": task.instance_id,
    }
    if any(b.get(k) != value for k, value in exact.items()):
        return None
    return {
        "taskId": task.task_id,
        "attemptId": attempt_id,
        "attemptOrdinal": ordinal,
        "operation": task.skill.operation,
        "kind": "SKILL",
        "resource": {
            "resource_id": reference.resource_id,
            "revision_id": reference.revision_id,
            "digest": reference.digest,
        },
    }
