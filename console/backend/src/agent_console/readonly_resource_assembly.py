"""Preflight existing exact bindings against a composition-owned executor allowlist.

This is a pure readiness check, not authorization, publication or dispatch.
"""

from .execution_preparation import TaskParticipation
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorRegistry


def check_readonly_assembly(
    participants: tuple[TaskParticipation, ...],
    *,
    registry: SkillExecutorRegistry,
    allowed_references: tuple[dict, ...],
    operations: tuple[str, ...],
):
    from .skill_invocation_domain import ExecutorRevision

    allowed = {canonical_digest(ref) for ref in allowed_references}
    if not participants or len({p.task_id for p in participants}) != len(participants):
        raise ValueError("ASSEMBLY_TASKS_INVALID")
    for participant in participants:
        registry.resolve(
            ExecutorRevision(
                participant.executor_id,
                participant.executor_revision,
                participant.executor_digest,
            )
        )
        if participant.skill.operation not in operations:
            raise ValueError("ASSEMBLY_OPERATION_UNAVAILABLE")
        for ref in (participant.definition, participant.profile):
            if canonical_digest(ref.model_dump(mode="json")) not in allowed:
                raise ValueError("ASSEMBLY_EXACT_RESOURCE_UNAVAILABLE")
        for binding in (participant.skill, *participant.resources):
            if (
                canonical_digest(binding.reference.model_dump(mode="json"))
                not in allowed
            ):
                raise ValueError("ASSEMBLY_EXACT_RESOURCE_UNAVAILABLE")
    return canonical_digest([p.model_dump(mode="json") for p in participants])
