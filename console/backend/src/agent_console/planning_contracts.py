"""Versioned, finite planning contracts. Never a natural-language truth oracle."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Operation = Literal[
    "READ_DATA",
    "VALIDATE_DATA",
    "CLASSIFY_OVERDUE",
    "SUMMARIZE",
    "ANALYZE_DATA",
    "RECOMMEND",
    "RENDER_REPORT",
]
ArtifactKind = Literal[
    "CONTEXT",
    "SOURCE_SNAPSHOT",
    "VALIDATED_DATA",
    "CLASSIFICATION",
    "SUMMARY",
    "ANALYSIS",
    "RECOMMENDATIONS",
    "REPORT",
]
PROCUREMENT = (
    "READ_DATA",
    "VALIDATE_DATA",
    "CLASSIFY_OVERDUE",
    "SUMMARIZE",
    "RENDER_REPORT",
)
OUTPUTS = dict(
    zip(
        PROCUREMENT,
        ("SOURCE_SNAPSHOT", "VALIDATED_DATA", "CLASSIFICATION", "SUMMARY", "REPORT"),
        strict=True,
    )
) | {"ANALYZE_DATA": "ANALYSIS", "RECOMMEND": "RECOMMENDATIONS"}
INPUTS = {
    "READ_DATA": {"CONTEXT"},
    "VALIDATE_DATA": {"SOURCE_SNAPSHOT"},
    "CLASSIFY_OVERDUE": {"VALIDATED_DATA"},
    "SUMMARIZE": {"SOURCE_SNAPSHOT", "VALIDATED_DATA", "CLASSIFICATION"},
    "ANALYZE_DATA": {"VALIDATED_DATA", "SUMMARY", "CLASSIFICATION"},
    "RECOMMEND": {"ANALYSIS", "SUMMARY"},
    "RENDER_REPORT": set(OUTPUTS.values()),
}


class PlanningPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["planning-policy.v2"] = "planning-policy.v2"
    mode: Literal["FREE", "TEMPLATE_ASSISTED", "STRICT_WORKFLOW"] = "FREE"
    template: Literal["procurement-overdue.v1"] | None = None
    required_operations: tuple[Operation, ...] = Field(default=(), max_length=7)
    prohibited_operations: tuple[Operation, ...] = Field(default=(), max_length=7)
    business_acceptance_as_task: bool = False

    @model_validator(mode="after")
    def consistent(self):
        if (self.mode == "FREE") != (self.template is None):
            raise ValueError("PLANNING_MODE_TEMPLATE_CONFLICT")
        required, prohibited = (
            set(self.required_operations),
            set(self.prohibited_operations),
        )
        if self.mode == "STRICT_WORKFLOW":
            required |= set(PROCUREMENT)
            if not set(self.required_operations) <= set(PROCUREMENT):
                raise ValueError("PLANNING_TEMPLATE_OPERATION_CONFLICT")
        if required & prohibited:
            raise ValueError("PLANNING_OPERATION_CONFLICT")
        if self.business_acceptance_as_task:
            raise ValueError("BUSINESS_ACCEPTANCE_IS_NOT_A_PLANNING_TASK")
        return self


def validate_semantics(plan):
    """Validate declared operations/data flow/coverage, not prose equivalence."""
    policy = plan.policy
    operations = {t.operation for t in plan.tasks}
    if not set(policy.required_operations) <= operations or operations & set(
        policy.prohibited_operations
    ):
        raise ValueError("PLANNING_OPERATION_CONFLICT")
    covered = {c for t in plan.tasks for c in t.criterion_revision_ids}
    if covered != set(plan.target.criterion_revision_ids):
        raise ValueError("PLANNING_CRITERION_COVERAGE_MISSING")
    tasks = {t.task_id: t for t in plan.tasks}
    for task in plan.tasks:
        if task.output_kind != OUTPUTS[task.operation]:
            raise ValueError("PLANNING_OPERATION_OUTPUT_CONFLICT")
        incoming = set(task.input_kinds)
        produced = {tasks[dep].output_kind for dep in task.depends_on}
        if task.operation == "READ_DATA":
            valid = incoming == {"CONTEXT"} and not task.depends_on
        else:
            valid = (
                bool(produced)
                and incoming == produced
                and bool(incoming & INPUTS[task.operation])
            )
        if not valid:
            raise ValueError("PLANNING_OPERATION_INPUT_CONFLICT")
    if policy.mode == "STRICT_WORKFLOW":
        # Compare typed responsibilities and exact producer/consumer links, not
        # titles, task IDs or the coincidence of having five nodes.
        if len(plan.tasks) != len(PROCUREMENT) or len(
            {t.operation for t in plan.tasks}
        ) != len(PROCUREMENT):
            raise ValueError("PLANNING_STRICT_OPERATION_CONFLICT")
        by_operation = {t.operation: t for t in plan.tasks}
        previous = None
        for operation in PROCUREMENT:
            task = by_operation.get(operation)
            if task is None or task.depends_on != (
                () if previous is None else (previous.task_id,)
            ):
                raise ValueError("PLANNING_STRICT_DEPENDENCY_CONFLICT")
            previous = task
        groups = tuple(
            tuple(tasks[identity].operation for identity in stage.task_ids)
            for stage in plan.stages
        )
        if groups != (
            ("READ_DATA",),
            ("VALIDATE_DATA", "CLASSIFY_OVERDUE"),
            ("SUMMARIZE", "RENDER_REPORT"),
        ):
            raise ValueError("PLANNING_STRICT_STAGE_CONFLICT")


def validation_report(plan):
    if plan.schema_version == "planning.v2":
        return {
            "policy_version": "planning-suggestion.v1",
            "status": "LEGACY_STRUCTURE_ONLY",
            "natural_language_coverage": "NOT_DETERMINISTICALLY_VERIFIED",
        }
    validate_semantics(plan)
    return {
        "policy_version": "planning-suggestion.v2",
        "status": "DECLARED_CONTRACT_VALID",
        "checks": [
            "SUPPORTED_OPERATIONS",
            "TYPED_DATA_FLOW",
            "ALL_CRITERION_REFERENCES",
            "EXPLICIT_POLICY_CONSTRAINTS",
        ],
        "natural_language_coverage": "REQUIRES_HUMAN_REVIEW",
        "execution_eligible": False,
    }
