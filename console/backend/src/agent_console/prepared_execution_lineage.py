# ruff: noqa: RUF001 -- Exact approved Chinese boundary text.
"""D324 exact source-owner and Task participant readbacks; no approval projection."""

from .execution_preparation import ExecutionPreparation, ExecutionPreparationError
from .plan_suggestion_domain import ConfirmedPlanRevision


def prepared_attempt(connection, scope, attempt_id):
    present = connection.execute(
        "SELECT to_regclass('execution_authority.prepared_task_bindings') AS name"
    ).fetchone()["name"]
    if present is None:
        return None
    return connection.execute(
        "SELECT b.*,p.record AS preparation,a.predecessor_attempt_id,a.attempt_ordinal,"
        "a.control_state AS attempt_state FROM execution_authority.attempts a "
        "JOIN execution_authority.prepared_task_bindings b "
        "USING(namespace,security_domain,task_run_id) "
        "JOIN execution_authority.run_preparations p "
        "USING(namespace,security_domain,workflow_run_id) "
        "WHERE a.namespace=%s AND a.security_domain=%s AND a.attempt_id=%s",
        (scope.namespace, scope.security_domain, str(attempt_id)),
    ).fetchone()


def validate_approved_preparation(connection, preparation):
    p = preparation
    row = connection.execute(
        "SELECT p.record,p.digest,a.record AS approval,a.decision_id "
        "FROM workflow_planning.plans p JOIN workflow_planning.approvals a "
        "USING(namespace,security_domain,plan_id,version) "
        "WHERE p.namespace=%s AND p.security_domain=%s AND p.plan_id=%s "
        "AND p.version=%s FOR SHARE OF p,a",
        (p.namespace, p.security_domain, p.plan_id, p.plan_version),
    ).fetchone()
    if row is None:
        raise ExecutionPreparationError("PREPARED_PLAN_APPROVAL_REQUIRED")
    plan = ConfirmedPlanRevision.model_validate(row["record"])
    if (
        plan.digest != p.plan_digest
        or row["digest"] != p.plan_digest
        or plan.semantics != p.semantics
        or row["decision_id"] != p.approval_id
        or row["approval"].get("decision") != "APPROVE"
        or row["approval"].get("plan_digest") != p.plan_digest
    ):
        raise ExecutionPreparationError("PREPARED_PLAN_APPROVAL_MISMATCH")
    from .cost_execution_revision import (
        DELIVERY_SYNTHETIC_ONLY,
        EXECUTION_ONLY,
        SYNTHETIC_ONLY,
    )
    from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor

    delivery = [
        t.executor_id == SyntheticDeliverySkillExecutor.revision.executor_id
        for t in p.participants
    ]
    if any(delivery) and not all(delivery):
        raise ExecutionPreparationError("PREPARED_EXECUTION_CASE_MIXED")
    boundary = DELIVERY_SYNTHETIC_ONLY if all(delivery) else SYNTHETIC_ONLY

    if (
        EXECUTION_ONLY not in plan.semantics.business_rules
        or boundary not in plan.semantics.boundaries
    ):
        raise ExecutionPreparationError("PREPARED_EXECUTION_SUCCESSOR_REQUIRED")
    requirements = {r.requirement_id: r for r in plan.semantics.requirements}
    if any(r.required and r.selected is None for r in requirements.values()):
        raise ExecutionPreparationError("PREPARED_REQUIRED_SELECTION_MISSING")
    participants = {t.task_id: t for t in p.participants}
    for task in plan.semantics.tasks:
        participant = participants[task.task_id]
        employee = requirements[task.employee_requirement_id]
        if employee.kind != "EMPLOYEE" or employee.selected != participant.definition:
            raise ExecutionPreparationError("PREPARED_EMPLOYEE_SELECTION_MISMATCH")
        for reference in task.requirement_ids:
            requirement = requirements[reference]
            if (
                requirement.kind == "KNOWLEDGE"
                and requirement.selected != p.source_snapshot
            ):
                raise ExecutionPreparationError("PREPARED_SOURCE_SELECTION_MISMATCH")
            if requirement.required and requirement.kind not in {
                "EMPLOYEE",
                "KNOWLEDGE",
                "SKILL",
            }:
                raise ExecutionPreparationError(
                    "PREPARED_REQUIREMENT_OWNER_NOT_CONFIGURED"
                )
            if requirement.kind == "SKILL" and (
                requirement.selected != participant.skill.reference
            ):
                raise ExecutionPreparationError("PREPARED_SKILL_SELECTION_MISMATCH")
    expected = f"执行准备映射SHA256：{p.mapping_digest}；"
    if not any(text.startswith(expected) for text in plan.semantics.boundaries):
        raise ExecutionPreparationError("PREPARED_MAPPING_NOT_APPROVED")
    return row


def resource_lineage(connection, scope, attempt_id):
    """Shape-compatible source readback for Resource Use's existing owner checks."""
    row = prepared_attempt(connection, scope, attempt_id)
    if row is None:
        return None
    p = ExecutionPreparation.model_validate(row["preparation"])
    approved = validate_approved_preparation(connection, p)
    participant = row["participant"]
    lineage = connection.execute(
        "SELECT eb.*,ib.definition_id AS instance_definition_id,"
        "ib.revision_id AS instance_revision_id,"
        "ib.digest AS instance_definition_digest,"
        "a.digital_employee_instance_id AS assignment_instance_id "
        "FROM digital_employee_definition.execution_bindings eb "
        "JOIN digital_employee_definition.instance_bindings ib "
        "USING(namespace,security_domain,digital_employee_instance_id) "
        "JOIN execution_authority.assignments a ON a.namespace=eb.namespace "
        "AND a.security_domain=eb.security_domain AND a.assignment_id=%s "
        "WHERE eb.namespace=%s AND eb.security_domain=%s AND eb.attempt_id=%s",
        (row["assignment_id"], scope.namespace, scope.security_domain, str(attempt_id)),
    ).fetchone()
    if (
        lineage is None
        or lineage["assignment_instance_id"] != participant["instance_id"]
    ):
        raise ExecutionPreparationError("PREPARED_PARTICIPANT_MISMATCH")
    return {
        "task_run_id": row["task_run_id"],
        "workflow_run_id": p.run_id,
        "assignment_id": row["assignment_id"],
        "predecessor_attempt_id": row["predecessor_attempt_id"],
        "predecessor_workflow_run_id": None,
        "plan_id": p.plan_id,
        "plan_version": p.plan_version,
        "approved_plan_digest": p.plan_digest,
        "plan_digest": approved["digest"],
        "plan_status": "APPROVED",
        "digital_employee_instance_id": lineage["assignment_instance_id"],
        "employee_binding_instance_id": lineage["digital_employee_instance_id"],
        "definition_id": lineage["definition_id"],
        "revision_id": lineage["revision_id"],
        "definition_digest": lineage["digest"],
        "employee_plan_digest": lineage["plan_digest"],
        "approval_id": lineage["approval_id"],
        "instance_definition_id": lineage["instance_definition_id"],
        "instance_revision_id": lineage["instance_revision_id"],
        "instance_definition_digest": lineage["instance_definition_digest"],
        "approval_decision_id": approved["decision_id"],
        "approval_plan_digest": approved["approval"]["plan_digest"],
        "approval_decision": approved["approval"]["decision"],
    }


def validate_participant(connection, scope, participant):
    """Re-read exact, active employee/assignment before each new effect."""
    from datetime import UTC, datetime

    from .digital_employee_definition import EmployeeRevision
    from .digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )

    key = (scope.namespace, scope.security_domain)
    row = connection.execute(
        "SELECT i.record,b.definition_id,b.revision_id,b.digest,"
        "a.record AS assignment,a.digital_employee_instance_id AS assigned_instance "
        "FROM execution_authority.digital_employee_instances i "
        "JOIN digital_employee_definition.instance_bindings b "
        "USING(namespace,security_domain,digital_employee_instance_id) "
        "JOIN execution_authority.assignments a "
        "ON a.namespace=i.namespace AND a.security_domain=i.security_domain "
        "AND a.assignment_id=%s WHERE i.namespace=%s AND i.security_domain=%s "
        "AND i.digital_employee_instance_id=%s FOR SHARE OF i,a",
        (participant.assignment_id, *key, participant.instance_id),
    ).fetchone()
    ref = participant.definition
    if row is None or (
        row["definition_id"],
        row["revision_id"],
        row["digest"],
        row["assigned_instance"],
        row["record"].get("lifecycle"),
        row["record"].get("definition_authority"),
        row["record"].get("definition_id"),
        row["record"].get("definition_revision_id"),
        row["record"].get("definition_digest"),
    ) != (
        ref.resource_id,
        ref.revision_id,
        ref.digest,
        participant.instance_id,
        "ENABLED",
        "DIGITAL_EMPLOYEE_DEFINITION_V1",
        ref.resource_id,
        ref.revision_id,
        ref.digest,
    ):
        raise ExecutionPreparationError("PREPARED_PARTICIPANT_NOT_EXECUTABLE")
    a = row["assignment"]
    try:
        start = datetime.fromisoformat(a["effective_from"])
        end = (
            datetime.fromisoformat(a["effective_until"])
            if a["effective_until"]
            else None
        )
        valid = (
            a["lifecycle"] == "ACTIVE"
            and start <= datetime.now(UTC)
            and (end is None or datetime.now(UTC) < end)
        )
    except (KeyError, ValueError, TypeError):
        valid = False
    if not valid:
        raise ExecutionPreparationError("PREPARED_ASSIGNMENT_NOT_ACTIVE")
    definition = PostgresEmployeeDefinitionRepository._read(
        connection, scope, ref.resource_id, ref.revision_id
    )
    if not definition["published"] or definition["digest"] != ref.digest:
        raise ExecutionPreparationError("PREPARED_DEFINITION_NOT_PUBLISHED")
    revision = EmployeeRevision.from_record(definition["revision"])
    PostgresEmployeeDefinitionRepository.validate_members(connection, revision)
    skill = participant.skill.reference
    if not any(
        str(m.kind) == "SKILL"
        and (m.resource_id, m.revision_id, m.digest)
        == (skill.resource_id, skill.revision_id, skill.digest)
        for m in revision.members
    ):
        raise ExecutionPreparationError("PREPARED_SKILL_NOT_MEMBER")


def require_evidence_writer(connection):
    writer = connection.execute(
        "SELECT state,authoritative_writer FROM execution_authority.evidence_cutover "
        "WHERE singleton=true FOR SHARE"
    ).fetchone()
    if writer != {"state": "POSTGRES_ACTIVE", "authoritative_writer": "POSTGRES"}:
        raise ExecutionPreparationError("PREPARED_EVIDENCE_WRITER_NOT_READY")


def native_binding(connection, command):
    """Return a prepared binding only after locking/rechecking current Run state."""
    from .execution_preparation_postgres import PreparedExecutionStore

    row = prepared_attempt(connection, command.scope, command.attempt_id)
    if row is None:
        return None
    require_evidence_writer(connection)
    p, progress = PreparedExecutionStore(connection).read(
        command.scope.namespace,
        command.scope.security_domain,
        row["workflow_run_id"],
        lock=True,
    )
    validate_approved_preparation(connection, p)
    participant = next(x for x in p.participants if x.task_id == row["task_id"])
    task = next(x for x in progress.tasks if x.task_id == row["task_id"])
    if (
        row["participant"] != participant.model_dump(mode="json")
        or row["assignment_id"] != participant.assignment_id
        or task.attempt_id != str(command.attempt_id)
        or task.state != "QUEUED"
        or progress.state not in {"PENDING", "RUNNING"}
        or progress.cancellation_request_id
        or participant.agent_instance_id != str(command.agent_instance_id)
        or participant.runtime_instance_id != str(command.runtime_instance_id)
        or participant.runtime_generation != command.runtime_generation.value
    ):
        raise ExecutionPreparationError("PREPARED_DISPATCH_NOT_READY")
    validate_participant(connection, command.scope, participant)
    from .prepared_execution_resources import validate_resources

    validate_resources(connection, command.scope, p, participant)
    return connection.execute(
        "SELECT d.decision,d.digest AS placement_digest,d.runtime_instance_id,"
        "r.current_generation,q.attempt_id,q.agent_instance_id,b.assignment_id,"
        "w.approved_plan_revision_id,w.approved_plan_digest AS plan_digest,"
        "'APPROVED' AS status,a.control_state "
        "FROM execution_authority.placement_decisions d "
        "JOIN execution_authority.placement_requests q "
        "USING(namespace,security_domain,request_id) "
        "JOIN execution_authority.runtime_instances r "
        "USING(namespace,security_domain,runtime_instance_id) "
        "JOIN execution_authority.attempts a "
        "ON a.namespace=q.namespace AND a.security_domain=q.security_domain "
        "AND a.attempt_id=q.attempt_id "
        "JOIN execution_authority.prepared_task_bindings b "
        "ON b.namespace=a.namespace AND b.security_domain=a.security_domain "
        "AND b.task_run_id=a.task_run_id "
        "JOIN execution_authority.workflow_runs w "
        "ON w.namespace=b.namespace AND w.security_domain=b.security_domain "
        "AND w.workflow_run_id=b.workflow_run_id "
        "WHERE d.namespace=%s AND d.security_domain=%s AND d.placement_id=%s "
        "FOR SHARE OF d,q,r,a,w",
        (
            command.scope.namespace,
            command.scope.security_domain,
            str(command.placement_id),
        ),
    ).fetchone()


def dispatch_grants(connection, command):
    """Current root admission AND Task permission; neither substitutes for Skill use."""
    from .authority_contracts import ExactGrant

    original = ExactGrant(
        command.authorization_owner,
        command.authorization_action,
        command.authorization_resource,
    )
    row = prepared_attempt(connection, command.scope, command.attempt_id)
    if row is None:
        return (original,)
    p = ExecutionPreparation.model_validate(row["preparation"])
    required = ExactGrant(
        "EXECUTION", "START", "governed-execution:prepared:" + p.digest
    )
    if original != required:
        raise ExecutionPreparationError("PREPARED_ADMISSION_GRANT_MISMATCH")
    from .prepared_execution_resources import resource_read_grants

    participant = next(t for t in p.participants if t.task_id == row["task_id"])
    return (
        *resource_read_grants(p, participant),
        required,
        ExactGrant(
            "EXECUTION",
            "START",
            f"governed-execution:participant:{p.digest}:{row['task_id']}",
        ),
    )
