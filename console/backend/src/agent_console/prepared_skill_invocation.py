"""Build the existing Skill owner's exact request from a prepared Task binding."""

from .execution_preparation import ExecutionPreparation
from .prepared_execution_lineage import prepared_attempt
from .prepared_execution_resources import validate_resources
from .resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    canonical_digest,
    stable_id,
)
from .skill_invocation_domain import (
    ExecutorRevision,
    SideEffectClass,
    SideEffectPolicy,
    SkillInvocationError,
    SkillInvocationRequest,
    SkillIOLimits,
)


def build_request(connection, scope, attempt_id, authorization_decision_id):
    row = prepared_attempt(connection, scope, attempt_id)
    if row is None:
        raise SkillInvocationError("PREPARED_SKILL_ATTEMPT_NOT_FOUND")
    p = ExecutionPreparation.model_validate(row["preparation"])
    t = next(t for t in p.participants if t.task_id == row["task_id"])
    operation = validate_resources(connection, scope, p, t)
    skill, employee = t.skill.reference, t.definition
    binding_id = stable_id(
        "skill-binding",
        employee.resource_id,
        employee.revision_id,
        skill.resource_id,
        skill.revision_id,
    )
    binding_digest = canonical_digest(
        {
            "bindingId": binding_id,
            "employeeDefinitionId": employee.resource_id,
            "employeeRevisionId": employee.revision_id,
            "skillId": skill.resource_id,
            "skillRevisionId": skill.revision_id,
            "skillDigest": skill.digest,
            "operation": t.skill.operation,
        }
    )
    use = ResourceUseBinding(
        scope=scope,
        resource_use_id=stable_id(
            "resource-use",
            scope.namespace,
            scope.security_domain,
            str(attempt_id),
            "SKILL",
            "skill:primary",
            "1",
        ),
        attempt_id=str(attempt_id),
        resource_kind=ResourceKind.SKILL,
        slot_key="skill:primary",
        occurrence_ordinal=1,
        resource_id=skill.resource_id,
        resource_revision_id=skill.revision_id,
        resource_digest=skill.digest,
        binding_id=binding_id,
        binding_digest=binding_digest,
        plan_id=p.plan_id,
        plan_version=p.plan_version,
        plan_digest=p.plan_digest,
        workflow_run_id=p.run_id,
        task_run_id=row["task_run_id"],
        digital_employee_definition_id=employee.resource_id,
        digital_employee_definition_revision_id=employee.revision_id,
        digital_employee_definition_digest=employee.digest,
        digital_employee_instance_id=t.instance_id,
        agent_instance_id=t.agent_instance_id,
        runtime_instance_id=t.runtime_instance_id,
        executor_id=t.executor_id,
        executor_revision=t.executor_revision,
        provider_id=None,
        provider_revision=None,
        authorization_decision_id=authorization_decision_id,
        predecessor_attempt_id=row["predecessor_attempt_id"],
    )
    policy, limits = operation["sideEffectPolicy"], operation["ioLimits"]
    return SkillInvocationRequest(
        scope=scope,
        idempotency_key="prepared-skill:" + str(attempt_id),
        attempt_id=str(attempt_id),
        workflow_run_id=p.run_id,
        task_run_id=row["task_run_id"],
        plan_id=p.plan_id,
        plan_version=p.plan_version,
        plan_digest=p.plan_digest,
        approval_id=p.approval_id,
        assignment_id=t.assignment_id,
        digital_employee_definition_id=employee.resource_id,
        digital_employee_definition_revision_id=employee.revision_id,
        digital_employee_definition_digest=employee.digest,
        digital_employee_instance_id=t.instance_id,
        agent_instance_id=t.agent_instance_id,
        runtime_instance_id=t.runtime_instance_id,
        skill_id=skill.resource_id,
        skill_revision_id=skill.revision_id,
        skill_digest=skill.digest,
        operation=t.skill.operation,
        input_schema_digest=t.skill.input_schema_digest,
        output_schema_digest=t.skill.output_schema_digest,
        binding_id=binding_id,
        binding_digest=binding_digest,
        executor=ExecutorRevision(
            t.executor_id, t.executor_revision, t.executor_digest
        ),
        side_effect_class=SideEffectClass.READ_ONLY,
        policy=SideEffectPolicy(
            policy["policyId"],
            policy["policyRevision"],
            policy["policyDigest"],
            SideEffectClass.READ_ONLY,
        ),
        io_limits=SkillIOLimits(
            limits["policyId"],
            limits["policyRevision"],
            limits["maxInputBytes"],
            limits["maxOutputBytes"],
            limits["maxObjectDepth"],
            limits["maxProperties"],
            limits["timeoutMs"],
        ),
        authorization_decision_id=authorization_decision_id,
        resource_use=use,
    )


def planned_outputs(preparation, progress=None):
    """Exact prospective read targets; permission creates no execution/evidence fact."""
    p = preparation
    ordinals = (
        {t.task_id: t.attempt_ordinal for t in progress.tasks}
        if progress
        else {t.task_id: t.max_attempts for t in p.participants}
    )
    result = []
    for task in p.participants:
        for ordinal in range(1, ordinals[task.task_id] + 1):
            attempt = stable_id(
                "prepared-attempt", p.run_id, task.task_id, str(ordinal)
            )
            invocation = stable_id(
                "skill-invocation",
                p.namespace,
                p.security_domain,
                attempt,
                "prepared-skill:" + attempt,
            )
            artifact = stable_id("native-skill-artifact", invocation)
            use = stable_id(
                "resource-use",
                p.namespace,
                p.security_domain,
                attempt,
                "SKILL",
                "skill:primary",
                "1",
            )
            result.append(
                {
                    "artifactId": artifact,
                    "resourceUseId": use,
                    "evidenceGrant": "evidence-reference:prepared:"
                    + f"{p.digest}:{artifact}",
                    "resourceGrant": f"resource-use:prepared:{p.digest}:{use}",
                }
            )
    return result
