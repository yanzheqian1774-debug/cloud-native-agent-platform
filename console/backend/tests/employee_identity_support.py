"""Real, uniquely scoped identity-chain fixtures; no inherited database rows."""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DigitalEmployeeApplicationService,
)
from agent_console.digital_employee_definition import (
    PublishedEmployeeDefinitionAuthority,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.execution_application import (
    ApprovedPlanIdentity,
    ExecutionApplicationService,
    ScopedExecutionAuthorization,
    StartExecutionCommand,
    execution_plan_bytes,
)
from agent_console.execution_postgres import AssignmentId, DigitalEmployeeInstanceId
from agent_console.workflow_control_domain import (
    ApprovalDecision,
    PlanRecord,
    PlanStatus,
)
from agent_console.workflow_control_postgres import PostgresWorkflowControlRepository
from test_digital_employee_definition_postgres import Authorized, publish_employee

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def migrate(authority):
    with authority.pool.connection() as conn:
        for version in range(1, 13):
            conn.execute(next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text())
    PostgresEmployeeDefinitionRepository(authority).migrate(
        MIGRATIONS / "0014_digital_employee_identity.sql"
    )


def employee(authority, database_url, scope, *, instance_id=None, assignment_id=None):
    migrate(authority)
    revision, _, _ = publish_employee(
        PostgresEmployeeDefinitionRepository(authority), scope, database_url
    )
    service = DigitalEmployeeApplicationService(
        PostgresDigitalEmployeeRepository(authority),
        PublishedEmployeeDefinitionAuthority(
            PostgresEmployeeDefinitionRepository(authority), Authorized(scope)
        ),
    )
    suffix = uuid.uuid4().hex
    instance, _ = service.create_instance(
        scope=scope,
        instance_id=DigitalEmployeeInstanceId(instance_id or f"employee-{suffix}"),
        definition_id=revision.definition_id,
        definition_revision_id=revision.revision_id,
        owner_id="owner",
        organization_id=scope.namespace,
        command_id=f"create-{suffix}",
    )
    assignment = AssignmentRecord(
        scope,
        AssignmentId(assignment_id or f"assignment-{suffix}"),
        instance.instance_id,
        "owner",
        "operator",
        AssignmentLifecycle.ACTIVE,
        datetime.now(UTC),
        None,
        1,
        f"assign-{suffix}",
    )
    service.assign(assignment)
    return revision, instance, assignment


def authorize(scope, permissions=("START", "RETRY")):
    return ScopedExecutionAuthorization(
        scope, "owner", frozenset(permissions), "execution-decision"
    )


def approve_plan(authority, database_url, workflow, instance, assignment):
    suffix = uuid.uuid4().hex
    scope = instance.scope
    now = datetime.now(UTC)
    approval_id = workflow.approval_id
    content = execution_plan_bytes(
        workflow, assignment.assignment_id, instance.instance_id
    )
    digest = hashlib.sha256(content).hexdigest()
    workflow_member, _ = publish_workflow(database_url, scope)
    workflow_id = workflow_member.resource_id
    control = PostgresWorkflowControlRepository(
        database_url,
        migration_path=MIGRATIONS / "0011_workflow_control_plan_evidence_outcome.sql",
    )
    try:
        plan = PlanRecord(
            scope,
            f"durable-plan-{suffix}",
            1,
            workflow_id,
            workflow_member.revision_id,
            workflow_member.digest.removeprefix("sha256:"),
            PlanStatus.PENDING_APPROVAL,
            1,
            digest,
            content,
            now,
            now,
        )
        control.create_plan(plan)
        control.append_approval(
            scope,
            ApprovalDecision(
                approval_id,
                plan.plan_id,
                1,
                digest,
                1,
                "APPROVE",
                "reviewer",
                "HUMAN_REVIEW",
                "BUSINESS_APPROVAL",
                "d" * 64,
                now,
            ),
        )
    finally:
        control.pool.close()
    return ApprovedPlanIdentity(
        workflow.canonical_workflow_revision_id,
        workflow.approved_candidate_digest,
        approval_id,
        plan.plan_id,
        1,
        digest,
    )


def start_chain(
    authority, database_url, workflow, *, instance_id=None, assignment_id=None
):
    from agent_console.execution_postgres import ScopeIdentity

    scope = ScopeIdentity(workflow.tenant_id, workflow.security_domain)
    revision, instance, assignment = employee(
        authority,
        database_url,
        scope,
        instance_id=instance_id,
        assignment_id=assignment_id,
    )
    approved = approve_plan(authority, database_url, workflow, instance, assignment)
    command = StartExecutionCommand(
        scope,
        workflow,
        approved,
        assignment.assignment_id,
        instance.instance_id,
        workflow.ordered_task_ids[0],
        "start",
    )
    service = ExecutionApplicationService(authority, authorize(scope))
    return revision, instance, assignment, command, service.start(command)


def fail_attempt(authority, identity):
    # Model an observed Runtime failure, not a retry implementation shortcut.
    with authority.pool.connection() as conn:
        conn.execute(
            "UPDATE execution_authority.attempts SET "
            "control_state='FAILED' WHERE namespace=%s AND "
            "security_domain=%s AND attempt_id=%s",
            (
                identity.scope.namespace,
                identity.scope.security_domain,
                str(identity.attempt.attempt_id),
            ),
        )


def publish_workflow(database_url, scope):
    from agent_console.digital_employee_definition import CompositionMember, MemberKind
    from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
    from agent_console.runtime_profile_service import RuntimeProfileService
    from agent_console.workflow_definition_postgres import (
        PostgresWorkflowDefinitionRepository,
    )
    from agent_console.workflow_definition_service import WorkflowDefinitionService
    from test_runtime_profile_postgres import CONTENT

    migration = MIGRATIONS / "0007_workflow_runtime_profiles.sql"
    runtime_repo = PostgresRuntimeProfileRepository(
        database_url, migration_path=migration
    )
    workflow_repo = PostgresWorkflowDefinitionRepository(
        database_url, migration_path=migration
    )
    runtime_service = RuntimeProfileService(runtime_repo)
    runtime_scope = runtime_service.scope(scope.namespace, scope.security_domain)

    def publish(service, service_scope, key, content):
        row = service.create(
            service_scope, "owner", "Identity-chain reference", content
        )
        identity = row[key]
        service.validate(service_scope, identity, "owner", row["aggregateVersion"])
        row = service.repository.get(service_scope, identity)
        rev = row["revisions"][0]
        service.review(
            service_scope,
            identity,
            "reviewer",
            row["aggregateVersion"],
            rev["digest"],
            "APPROVE",
            "Exact review",
        )
        row = service.repository.get(service_scope, identity)
        service.publish(
            service_scope,
            identity,
            "publisher",
            row["aggregateVersion"],
            rev["digest"],
            row["reviews"][0]["reviewId"],
        )
        return identity, rev["revisionId"], rev["digest"]

    try:
        runtime = CompositionMember(
            MemberKind.RUNTIME_PROFILE,
            *publish(runtime_service, runtime_scope, "runtimeProfileId", CONTENT),
        )

        def resolve(wscope, ref):
            if (wscope.namespace, wscope.security_domain) != (
                scope.namespace,
                scope.security_domain,
            ):
                return False
            row = runtime_repo.get(runtime_scope, ref["resourceId"])
            return any(
                r["revisionId"] == ref["revisionId"]
                and r["digest"] == ref["digest"]
                and r["state"] == "PUBLISHED"
                for r in row["revisions"]
            )

        service = WorkflowDefinitionService(workflow_repo, reference_resolver=resolve)
        wscope = service.scope(scope.namespace, scope.security_domain)
        workflow = CompositionMember(
            MemberKind.WORKFLOW,
            *publish(
                service,
                wscope,
                "workflowDefinitionId",
                {
                    "description": "Identity-chain workflow",
                    "tasks": [
                        {"taskId": "collect", "name": "Collect", "dependsOn": []}
                    ],
                    "inputs": [],
                    "outputs": [],
                    "runtimeProfile": {
                        "kind": "RUNTIME_PROFILE",
                        "resourceId": runtime.resource_id,
                        "revisionId": runtime.revision_id,
                        "digest": runtime.digest,
                    },
                },
            ),
        )
        return workflow, runtime
    finally:
        runtime_repo.pool.close()
        workflow_repo.pool.close()
