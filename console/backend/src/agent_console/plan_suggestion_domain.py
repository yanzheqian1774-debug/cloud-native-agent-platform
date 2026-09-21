"""Planning v2 immutable semantics; no execution or resource lifecycle authority."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .business_problem_domain import canonical_digest
from .planning_contracts import (
    ArtifactKind,
    Operation,
    PlanningPolicy,
    validate_semantics,
)

Text = Annotated[str, Field(min_length=1, max_length=500)]
Identity = Annotated[str, Field(min_length=1, max_length=200)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class PlanningError(RuntimeError):
    """Disclosure-safe planning failure."""


class PlanningConflict(PlanningError):
    pass


class Immutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExactReference(Immutable):
    resource_id: Identity
    revision_id: Identity
    digest: Digest


class ProblemTarget(Immutable):
    problem: ExactReference
    criteria: ExactReference
    criterion_revision_ids: tuple[Identity, ...] = Field(min_length=1, max_length=64)
    expected_problem_version: int = Field(ge=1)


class ResourceRequirement(Immutable):
    requirement_id: Identity
    kind: Literal["EMPLOYEE", "SKILL", "MCP", "KNOWLEDGE", "WORKFLOW"]
    name: Text
    purpose: Text
    required: bool
    selected: ExactReference | None = None
    operation: Text | None = None
    preparation: Text


class PlanningTask(Immutable):
    task_id: Identity
    title: Text
    responsibility: Text
    employee_requirement_id: Identity
    depends_on: tuple[Identity, ...] = Field(max_length=32)
    inputs: tuple[Text, ...] = Field(min_length=1, max_length=32)
    outputs: tuple[Text, ...] = Field(min_length=1, max_length=32)
    requirement_ids: tuple[Identity, ...] = Field(max_length=32)
    criterion_revision_ids: tuple[Identity, ...] = Field(min_length=1, max_length=64)


class PlanningStage(Immutable):
    stage_id: Identity
    title: Text
    task_ids: tuple[Identity, ...] = Field(min_length=1, max_length=32)


class PlanSemantics(Immutable):
    schema_version: Literal["planning.v2"] = "planning.v2"
    scenario: Literal["GENERAL_READ_ONLY", "OVERDUE_PURCHASE_ORDERS"]
    target: ProblemTarget
    title: Text
    business_rules: tuple[Text, ...] = Field(min_length=1, max_length=32)
    boundaries: tuple[Text, ...] = Field(min_length=1, max_length=16)
    effect: Literal["READ_ONLY"] = "READ_ONLY"
    stages: tuple[PlanningStage, ...] = Field(min_length=1, max_length=32)
    tasks: tuple[PlanningTask, ...] = Field(min_length=1, max_length=32)
    requirements: tuple[ResourceRequirement, ...] = Field(max_length=128)

    @model_validator(mode="after")
    def validate_graph(self):
        tasks = {t.task_id: t for t in self.tasks}
        resources = {r.requirement_id: r for r in self.requirements}
        members = [t for stage in self.stages for t in stage.task_ids]
        if (
            len(tasks) != len(self.tasks)
            or len(resources) != len(self.requirements)
            or len({s.stage_id for s in self.stages}) != len(self.stages)
            or len(members) != len(tasks)
            or set(members) != set(tasks)
            or sum(len(t.depends_on) for t in self.tasks) > 128
        ):
            raise ValueError("PLAN_STRUCTURE_INVALID")
        for task in self.tasks:
            employee = resources.get(task.employee_requirement_id)
            if (
                employee is None
                or employee.kind != "EMPLOYEE"
                or not set(task.requirement_ids) <= resources.keys()
                or not set(task.criterion_revision_ids)
                <= set(self.target.criterion_revision_ids)
                or not set(task.depends_on) <= tasks.keys()
                or len(set(task.depends_on)) != len(task.depends_on)
                or task.task_id in task.depends_on
            ):
                raise ValueError("PLAN_REFERENCE_INVALID")
        pending = dict(tasks)
        completed = set()
        while pending:
            ready = {
                key for key, t in pending.items() if set(t.depends_on) <= completed
            }
            if not ready:
                raise ValueError("PLAN_DEPENDENCY_CYCLE")
            completed.update(ready)
            pending = {key: t for key, t in pending.items() if key not in ready}
        if (
            self.schema_version == "planning.v2"
            and self.scenario == "OVERDUE_PURCHASE_ORDERS"
        ):
            expected = (("T1",), ("T2a", "T2b"), ("T3a", "T3b"))
            if tuple(s.task_ids for s in self.stages) != expected:
                raise ValueError("PROCUREMENT_STAGE_TASK_CONTRACT")
            ids = ("T1", "T2a", "T2b", "T3a", "T3b")
            for index, identity in enumerate(ids):
                deps = () if index == 0 else (ids[index - 1],)
                if tasks[identity].depends_on != deps:
                    raise ValueError("PROCUREMENT_DEPENDENCY_CONTRACT")
        return self

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))


class FlexiblePlanningTask(PlanningTask):
    operation: Operation
    input_kinds: tuple[ArtifactKind, ...] = Field(min_length=1, max_length=8)
    output_kind: ArtifactKind


class FlexiblePlanSemantics(PlanSemantics):
    schema_version: Literal["planning.v3"] = "planning.v3"
    policy: PlanningPolicy
    tasks: tuple[FlexiblePlanningTask, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def declared_contract(self):
        validate_semantics(self)
        return self


VersionedSemantics = Annotated[
    PlanSemantics | FlexiblePlanSemantics, Field(discriminator="schema_version")
]


class ProposalRevision(Immutable):
    proposal_id: Identity
    revision: int = Field(ge=1)
    predecessor_digest: Digest | None
    invocation_id: Identity
    semantics: VersionedSemantics

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))


class ResourceObservation(Immutable):
    requirement_id: Identity
    status: Literal[
        "MATCHED",
        "MISSING",
        "UNKNOWN",
        "UNREADABLE",
        "VERSION_MISMATCH",
        "UNAVAILABLE",
        "NOT_REQUIRED",
    ]
    reason: Text
    owner_high_water: Text | None = None
    exact_reference: ExactReference | None = None
    publication_checked: bool = False
    permission_checked: bool = False
    io_status: Literal["UNKNOWN", "DECLARED"] = "UNKNOWN"
    availability_status: Literal["UNKNOWN", "UNAVAILABLE"] = "UNKNOWN"
    discovery_status: Literal["NOT_REQUESTED", "OWNER_PORT_REQUIRED"] = "NOT_REQUESTED"


class ResourceSnapshot(Immutable):
    snapshot_id: Identity
    proposal_digest: Digest
    checked_at: Text
    observations: tuple[ResourceObservation, ...] = Field(max_length=128)
    preparation_contract: Literal[
        "TYPED_DECLARATIONS_VALID", "LEGACY_SUCCESSOR_REQUIRED"
    ] = "LEGACY_SUCCESSOR_REQUIRED"
    execution_eligible: Literal[False] = False

    def pending_required(self, proposal: ProposalRevision):
        if self.proposal_digest != proposal.digest:
            raise PlanningConflict("RESOURCE_SNAPSHOT_TARGET_MISMATCH")
        observations = {o.requirement_id: o for o in self.observations}
        return tuple(
            r.requirement_id
            for r in proposal.semantics.requirements
            if r.required
            and (
                r.requirement_id not in observations
                or observations[r.requirement_id].status != "MATCHED"
            )
        )


class ConfirmedPlanRevision(Immutable):
    schema_version: Literal["plan.v2"] = "plan.v2"
    plan_id: Identity
    version: int = Field(ge=1)
    source_proposal_id: Identity
    source_proposal_revision: int = Field(ge=1)
    source_proposal_digest: Digest
    predecessor_digest: Digest | None
    semantics: VersionedSemantics

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))
