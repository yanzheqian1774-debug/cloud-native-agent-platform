# ruff: noqa: E501
"""Exact employee/assignment/approval validation within the Execution transaction."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .digital_employee_definition import EmployeeRevision
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .execution_domain import ExecutionConflict


def validate_lineage(
    conn,
    aggregate,
    approved_plan,
    authorization_decision_id,
    workflow=None,
    task_id=None,
):
    if not authorization_decision_id:
        raise ExecutionConflict("EXECUTION_NOT_FOUND")
    scope = aggregate.scope
    key = (scope.namespace, scope.security_domain)
    employee_id = str(aggregate.assignment.digital_employee_instance_id)
    assignment_id = str(aggregate.assignment.assignment_id)
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (json.dumps((*key, str(aggregate.task_run.task_run_id))),),
    )
    employee = conn.execute(
        "SELECT i.record,b.definition_id,b.revision_id,b.digest FROM execution_authority.digital_employee_instances i JOIN digital_employee_definition.instance_bindings b USING(namespace,security_domain,digital_employee_instance_id) WHERE i.namespace=%s AND i.security_domain=%s AND i.digital_employee_instance_id=%s FOR SHARE OF i",
        (*key, employee_id),
    ).fetchone()
    if employee is None:
        raise ExecutionConflict("EXACT_EMPLOYEE_LINEAGE_REQUIRED")
    record = employee["record"]
    if record.get("definition_authority") != "DIGITAL_EMPLOYEE_DEFINITION_V1" or (
        record.get("definition_id"),
        record.get("definition_revision_id"),
        record.get("definition_digest"),
    ) != (employee["definition_id"], employee["revision_id"], employee["digest"]):
        raise ExecutionConflict("EMPLOYEE_LINEAGE_CORRUPT")
    definition = PostgresEmployeeDefinitionRepository._read(
        conn, scope, employee["definition_id"], employee["revision_id"]
    )
    if (
        definition["digest"] != employee["digest"]
        or not definition["published"]
        or record.get("lifecycle") != "ENABLED"
    ):
        raise ExecutionConflict("EMPLOYEE_NOT_EXECUTABLE")
    PostgresEmployeeDefinitionRepository.validate_members(
        conn, EmployeeRevision.from_record(definition["revision"])
    )
    assignment = conn.execute(
        "SELECT digital_employee_instance_id,record FROM execution_authority.assignments WHERE namespace=%s AND security_domain=%s AND assignment_id=%s FOR SHARE",
        (*key, assignment_id),
    ).fetchone()
    if assignment is None or assignment["digital_employee_instance_id"] != employee_id:
        raise ExecutionConflict("ASSIGNMENT_NOT_FOUND")
    try:
        a = assignment["record"]
        start = datetime.fromisoformat(a["effective_from"])
        end = (
            None
            if a["effective_until"] is None
            else datetime.fromisoformat(a["effective_until"])
        )
        if (
            start.tzinfo is None
            or (end is not None and end.tzinfo is None)
            or a["lifecycle"] != "ACTIVE"
            or not start <= datetime.now(UTC)
            or (end is not None and datetime.now(UTC) >= end)
        ):
            raise ExecutionConflict("ASSIGNMENT_NOT_ACTIVE")
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionConflict("EXACT_ASSIGNMENT_REQUIRED") from exc
    predecessor = aggregate.attempt.predecessor_attempt_id
    ordinal = 1
    if predecessor is not None:
        previous = conn.execute(
            "SELECT a.task_run_id,a.control_state,a.attempt_ordinal,b.* FROM execution_authority.attempts a JOIN digital_employee_definition.execution_bindings b USING(namespace,security_domain,attempt_id) WHERE a.namespace=%s AND a.security_domain=%s AND a.attempt_id=%s FOR UPDATE OF a",
            (*key, str(predecessor)),
        ).fetchone()
        if (
            previous is None
            or previous["task_run_id"] != str(aggregate.task_run.task_run_id)
            or previous["control_state"] != "FAILED"
        ):
            raise ExecutionConflict("RETRY_REQUIRES_FAILED_ATTEMPT")
        if (
            previous["digital_employee_instance_id"],
            previous["definition_id"],
            previous["revision_id"],
            previous["digest"],
        ) != (
            employee_id,
            employee["definition_id"],
            employee["revision_id"],
            employee["digest"],
        ):
            raise ExecutionConflict("RETRY_LINEAGE_MISMATCH")
        successor = conn.execute(
            "SELECT attempt_id FROM execution_authority.attempts WHERE namespace=%s AND security_domain=%s AND predecessor_attempt_id=%s",
            (*key, str(predecessor)),
        ).fetchone()
        if successor is not None and successor["attempt_id"] != str(
            aggregate.attempt.attempt_id
        ):
            raise ExecutionConflict("ATTEMPT_SUCCESSOR_CONFLICT")
        ordinal = previous["attempt_ordinal"] + 1
        approval_id = previous["approval_id"]
        wanted_digest = previous["plan_digest"]
    else:
        if approved_plan is None:
            raise ExecutionConflict("EXACT_PLAN_APPROVAL_REQUIRED")
        approval_id, wanted_digest = (
            approved_plan.approval_id,
            approved_plan.plan_digest,
        )
    plan = conn.execute(
        "SELECT p.plan_id,p.plan_version,p.plan_digest,p.canonical_bytes,p.status,d.decision FROM execution_authority.plan_approval_decisions d JOIN execution_authority.plans p USING(namespace,security_domain,plan_id,plan_version) WHERE d.namespace=%s AND d.security_domain=%s AND d.approval_decision_id=%s AND d.plan_digest=p.plan_digest FOR SHARE OF p",
        (*key, approval_id),
    ).fetchone()
    if (
        plan is None
        or plan["status"] != "APPROVED"
        or plan["decision"] != "APPROVE"
        or plan["plan_digest"] != wanted_digest
    ):
        raise ExecutionConflict("EXACT_PLAN_APPROVAL_REQUIRED")
    if predecessor is None and (approved_plan.plan_id, approved_plan.plan_version) != (
        plan["plan_id"],
        plan["plan_version"],
    ):
        raise ExecutionConflict("PLAN_IDENTITY_MISMATCH")
    raw = bytes(plan["canonical_bytes"])
    if hashlib.sha256(raw).hexdigest() != plan["plan_digest"]:
        raise ExecutionConflict("PLAN_CONTENT_CORRUPT")
    try:
        content = json.loads(raw)
        valid = (
            content["schemaVersion"] == "employee-execution-plan.v1"
            and content["assignmentId"] == assignment_id
            and content["instanceId"] == employee_id
            and content["workflow"]["canonical_workflow_revision_id"]
            == aggregate.workflow_run.approved_plan_revision_id
            and content["workflow"]["tenant_id"] == scope.namespace
            and content["workflow"]["security_domain"] == scope.security_domain
        )
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise ExecutionConflict("PLAN_RELATIONSHIP_MISMATCH")
    if predecessor is None:
        from .execution_application import execution_plan_bytes

        if (
            workflow is None
            or task_id not in workflow.ordered_task_ids
            or raw != execution_plan_bytes(workflow, assignment_id, employee_id)
        ):
            raise ExecutionConflict("PLAN_CONTENT_MISMATCH")
    else:
        run = conn.execute(
            "SELECT assignment_id,plan_id,plan_version,approved_plan_digest,approved_plan_revision_id FROM execution_authority.workflow_runs WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s FOR SHARE",
            (*key, str(aggregate.workflow_run.workflow_run_id)),
        ).fetchone()
        if run is None or tuple(run.values()) != (
            assignment_id,
            plan["plan_id"],
            plan["plan_version"],
            plan["plan_digest"],
            aggregate.workflow_run.approved_plan_revision_id,
        ):
            raise ExecutionConflict("RETRY_PLAN_MISMATCH")
    if predecessor is None:
        plan["task_id"] = task_id
    else:
        task = conn.execute(
            "SELECT workflow_node_id,workflow_run_id FROM execution_authority.task_runs WHERE namespace=%s AND security_domain=%s AND task_run_id=%s FOR SHARE",
            (*key, str(aggregate.task_run.task_run_id)),
        ).fetchone()
        if (
            task is None
            or task["workflow_run_id"] != str(aggregate.workflow_run.workflow_run_id)
            or task["workflow_node_id"] not in content["workflow"]["ordered_task_ids"]
        ):
            raise ExecutionConflict("RETRY_TASK_MISMATCH")
        plan["task_id"] = task["workflow_node_id"]
    return employee, plan, approval_id, ordinal


def append_lineage(
    conn, aggregate, employee, plan, approval_id, authorization_decision_id
):
    key = (
        aggregate.scope.namespace,
        aggregate.scope.security_domain,
        str(aggregate.attempt.attempt_id),
    )
    values = (
        *key,
        str(aggregate.assignment.digital_employee_instance_id),
        employee["definition_id"],
        employee["revision_id"],
        employee["digest"],
        plan["plan_digest"],
        approval_id,
        authorization_decision_id,
    )
    conn.execute(
        "INSERT INTO digital_employee_definition.execution_bindings VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        values,
    )
    stored = conn.execute(
        "SELECT digital_employee_instance_id,definition_id,revision_id,digest,plan_digest,approval_id,authorization_decision_id FROM digital_employee_definition.execution_bindings WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
        key,
    ).fetchone()
    if tuple(stored.values()) != values[3:]:
        raise ExecutionConflict("EXECUTION_LINEAGE_CONFLICT")


def validate_placement(conn, scope, request, decision, *, required=False):
    """Check new lineage and Agent identity under the same placement transaction."""
    present = conn.execute(
        "SELECT to_regclass('digital_employee_definition.execution_bindings') AS name"
    ).fetchone()["name"]
    if present is None:
        if required:
            raise ExecutionConflict("EXACT_EMPLOYEE_LINEAGE_REQUIRED")
        return
    key = (scope.namespace, scope.security_domain)
    binding = conn.execute(
        "SELECT b.*,a.task_run_id,t.workflow_run_id FROM digital_employee_definition.execution_bindings b JOIN execution_authority.attempts a USING(namespace,security_domain,attempt_id) JOIN execution_authority.task_runs t USING(namespace,security_domain,task_run_id) WHERE b.namespace=%s AND b.security_domain=%s AND b.attempt_id=%s FOR SHARE OF a",
        (*key, str(request.attempt_id)),
    ).fetchone()
    if binding is None:
        if required:
            raise ExecutionConflict("EXACT_EMPLOYEE_LINEAGE_REQUIRED")
        return
    if (binding["task_run_id"], binding["workflow_run_id"]) != (
        str(request.task_run_id),
        str(request.workflow_run_id),
    ):
        raise ExecutionConflict("PLACEMENT_EXECUTION_MISMATCH")
    definition = PostgresEmployeeDefinitionRepository._read(
        conn, scope, binding["definition_id"], binding["revision_id"]
    )
    revision = EmployeeRevision.from_record(definition["revision"])
    agent = next(m for m in revision.members if m.kind == "AGENT")
    stored = conn.execute(
        "SELECT record FROM execution_authority.agent_instances WHERE namespace=%s AND security_domain=%s AND agent_instance_id=%s FOR SHARE",
        (*key, str(request.agent_instance_id)),
    ).fetchone()
    if (
        stored is None
        or definition["digest"] != binding["digest"]
        or request.agent_revision_id != agent.revision_id
        or (
            stored["record"].get("agent_definition_id"),
            stored["record"].get("agent_revision_id"),
            stored["record"].get("agent_digest"),
        )
        != (agent.resource_id, agent.revision_id, agent.digest)
        or (
            decision.runtime_instance_id is not None
            and stored["record"].get("runtime_instance_id")
            != str(decision.runtime_instance_id)
        )
    ):
        raise ExecutionConflict("PLACEMENT_PRIMARY_AGENT_MISMATCH")


def prepare_control_retry(conn, operation, target):
    """Adapt an existing governed retry UoW without changing legacy records."""
    if (
        conn.execute(
            "SELECT to_regclass('digital_employee_definition.execution_bindings') AS name"
        ).fetchone()["name"]
        is None
    ):
        return None
    bound = conn.execute(
        "SELECT 1 FROM digital_employee_definition.execution_bindings WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
        (
            operation.scope.namespace,
            operation.scope.security_domain,
            operation.target.attempt_id,
        ),
    ).fetchone()
    if bound is None:
        return None
    from dataclasses import replace

    from .execution_postgres import (
        AttemptId,
        AttemptIdentity,
        PostgresExecutionAuthorityRepository,
        canonical_bytes,
        canonical_digest,
    )

    previous = PostgresExecutionAuthorityRepository.identity_from_record(
        operation.scope, target["record"]
    )
    successor = replace(
        previous,
        attempt=AttemptIdentity(
            AttemptId(operation.successor_id),
            previous.task_run.task_run_id,
            previous.attempt.attempt_id,
        ),
    )
    employee, plan, approval_id, ordinal = validate_lineage(
        conn, successor, None, operation.control_command_id
    )
    return (
        successor,
        employee,
        plan,
        approval_id,
        ordinal,
        json.loads(canonical_bytes(successor))["payload"],
        canonical_digest(successor),
    )
