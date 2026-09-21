"""D324 exact preparation and bounded state rules owned by Execution Authority.

These records add no provider, scheduler thread or accounting ledger. The existing
Native dispatch worker remains the sole effect owner. Reducers consume durable
observations; preparation/readiness alone never starts an Attempt.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .plan_suggestion_domain import (
    Digest,
    ExactReference,
    FlexiblePlanSemantics,
    Identity,
    Immutable,
)
from .resource_use_domain import canonical_digest

MAX_TASK_ARTIFACTS = 16  # All Attempts, including failed/retried history.
MAX_ARTIFACT_BYTES = 256 * 1024
MAX_RUN_ARTIFACT_BYTES = 4 * 1024 * 1024


class ExecutionPreparationError(ValueError):
    pass


class ResourceBinding(Immutable):
    kind: Literal["SKILL", "MCP", "KNOWLEDGE", "EMPLOYEE", "RUNTIME"]
    reference: ExactReference
    owner_observation: Identity
    input_schema_digest: Digest
    output_schema_digest: Digest
    operation: Identity


class TaskParticipation(Immutable):
    task_id: Identity
    assignment_id: Identity
    instance_id: Identity
    definition: ExactReference
    skill: ResourceBinding
    resources: tuple[ResourceBinding, ...] = Field(default=(), max_length=32)
    executor_id: Identity
    executor_revision: Identity
    executor_digest: Digest
    agent_instance_id: Identity
    runtime_instance_id: Identity
    runtime_generation: int = Field(ge=1)
    profile: ExactReference
    max_attempts: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def skill_kind(self):
        if self.skill.kind != "SKILL":
            raise ValueError("PREPARATION_MANAGED_SKILL_REQUIRED")
        refs = [self.skill, *self.resources]
        keys = [(r.kind, r.reference.resource_id) for r in refs]
        if len(keys) != len(set(keys)):
            raise ValueError("PREPARATION_DUPLICATE_RESOURCE")
        return self


class ExecutionPreparation(Immutable):
    schema_version: Literal["execution-preparation.v1"] = "execution-preparation.v1"
    namespace: Identity
    security_domain: Identity
    plan_id: Identity
    plan_version: int = Field(ge=1)
    plan_digest: Digest
    approval_id: Identity
    root_assignment_id: Identity
    root_instance_id: Identity
    semantics: FlexiblePlanSemantics
    participants: tuple[TaskParticipation, ...] = Field(min_length=1, max_length=32)
    source_snapshot: ExactReference
    synthetic: Literal[True]
    execution_boundary: Literal["ISOLATED_SYNTHETIC_READ_ONLY"]

    @model_validator(mode="after")
    def exact_tasks(self):
        participants = {p.task_id: p for p in self.participants}
        tasks = {t.task_id: t for t in self.semantics.tasks}
        if (
            len(participants) != len(self.participants)
            or participants.keys() != tasks.keys()
        ):
            raise ValueError("PREPARATION_TASK_SET_MISMATCH")
        for task in self.semantics.tasks:
            if participants[task.task_id].skill.operation != task.operation:
                raise ValueError("PREPARATION_OPERATION_MISMATCH")
        # The persisted source plan must also carry this boundary at admission.
        return self

    @property
    def digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json"))

    @property
    def mapping_digest(self):
        # Known before successor confirmation; excludes Plan/Approval to avoid a cycle.
        return canonical_digest(
            {
                key: self.model_dump(mode="json")[key]
                for key in (
                    "namespace",
                    "security_domain",
                    "root_assignment_id",
                    "root_instance_id",
                    "participants",
                    "source_snapshot",
                    "synthetic",
                    "execution_boundary",
                )
            }
        )

    @property
    def run_id(self) -> str:
        # Request keys and individual Task IDs deliberately do not enter this ID.
        return "workflow-run:" + self.digest


class TaskState(StrEnum):
    WAITING = "WAITING"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FINAL_FAILED = "FINAL_FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


TASK_TERMINAL = frozenset(
    {
        TaskState.SUCCEEDED,
        TaskState.FINAL_FAILED,
        TaskState.SKIPPED,
        TaskState.CANCELLED,
    }
)
RUN_TERMINAL = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


class TaskProgress(Immutable):
    task_id: Identity
    state: TaskState = TaskState.WAITING
    attempt_ordinal: int = Field(default=0, ge=0, le=3)
    attempt_id: Identity | None = None
    stop_evidence: Identity | None = None
    output_artifact_ids: tuple[Identity, ...] = Field(default=(), max_length=16)
    reason: Identity | None = None


class RunProgress(Immutable):
    version: int = Field(default=1, ge=1)
    state: Literal[
        "PENDING",
        "RUNNING",
        "RECOVERY_REQUIRED",
        "CANCEL_REQUESTED",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ] = "PENDING"
    cancellation_request_id: Identity | None = None
    tasks: tuple[TaskProgress, ...]


def initial_progress(preparation: ExecutionPreparation) -> RunProgress:
    return advance(
        preparation,
        RunProgress(
            tasks=tuple(
                TaskProgress(task_id=t.task_id) for t in preparation.semantics.tasks
            )
        ),
    )


def advance(preparation: ExecutionPreparation, progress: RunProgress) -> RunProgress:
    """Dependency propagation occurs only after final failure, never retry-wait."""
    tasks = {t.task_id: t for t in progress.tasks}
    definitions = {t.task_id: t for t in preparation.semantics.tasks}
    if len(tasks) != len(progress.tasks) or tasks.keys() != definitions.keys():
        raise ExecutionPreparationError("EXECUTION_TASK_SET_MISMATCH")
    if progress.state in RUN_TERMINAL:
        return progress
    if progress.cancellation_request_id:
        for key, task in tuple(tasks.items()):
            if task.state in {TaskState.WAITING, TaskState.READY, TaskState.RETRY_WAIT}:
                # No queued/running effect is inferred to have stopped.
                tasks[key] = task.model_copy(
                    update={
                        "state": TaskState.CANCELLED,
                        "stop_evidence": task.stop_evidence
                        or progress.cancellation_request_id,
                        "reason": "CANCELLED_BEFORE_DISPATCH",
                    }
                )
        state = "CANCEL_REQUESTED"
        if all(t.state in TASK_TERMINAL for t in tasks.values()):
            state = "CANCELLED"
    elif any(t.state == TaskState.UNKNOWN for t in tasks.values()):
        state = "RECOVERY_REQUIRED"
    else:
        changed = True
        while changed:
            changed = False
            for key, task in tuple(tasks.items()):
                if task.state not in {TaskState.WAITING, TaskState.READY}:
                    continue
                dependencies = [tasks[d] for d in definitions[key].depends_on]
                if any(
                    d.state in {TaskState.FINAL_FAILED, TaskState.SKIPPED}
                    for d in dependencies
                ):
                    tasks[key] = task.model_copy(
                        update={
                            "state": TaskState.SKIPPED,
                            "reason": "DEPENDENCY_FINAL_FAILED",
                        }
                    )
                    changed = True
                elif all(d.state == TaskState.SUCCEEDED for d in dependencies):
                    if task.state != TaskState.READY:
                        tasks[key] = task.model_copy(update={"state": TaskState.READY})
                        changed = True
        state = (
            "RUNNING" if any(t.attempt_ordinal for t in tasks.values()) else "PENDING"
        )
        if all(t.state == TaskState.SUCCEEDED for t in tasks.values()):
            state = "SUCCEEDED"
        elif all(t.state in TASK_TERMINAL for t in tasks.values()):
            state = "FAILED"
    return progress.model_copy(update={"state": state, "tasks": tuple(tasks.values())})


class ProgressEvent(Immutable):
    action: Literal[
        "QUEUE",
        "STARTED",
        "SUCCEEDED",
        "FAILED",
        "UNKNOWN",
        "RETRY",
        "FINALIZE_FAILURE",
        "REQUEST_CANCEL",
        "STOP_CONFIRMED",
    ]
    evidence_id: Identity
    task_id: Identity | None = None
    attempt_id: Identity | None = None
    artifact_ids: tuple[Identity, ...] = Field(default=(), max_length=16)


def transition(
    preparation: ExecutionPreparation, progress: RunProgress, event: ProgressEvent
) -> RunProgress:
    """Authorization, artifact integrity and CAS are enforced by the owner UoW."""
    if progress.state in RUN_TERMINAL:
        raise ExecutionPreparationError("EXECUTION_TERMINAL_IMMUTABLE")
    if len(set(event.artifact_ids)) != len(event.artifact_ids):
        raise ExecutionPreparationError("EXECUTION_DUPLICATE_ARTIFACT")
    if event.action == "REQUEST_CANCEL":
        if progress.cancellation_request_id:
            raise ExecutionPreparationError("EXECUTION_CANCEL_ALREADY_REQUESTED")
        return advance(
            preparation,
            progress.model_copy(
                update={
                    "version": progress.version + 1,
                    "cancellation_request_id": event.evidence_id,
                }
            ),
        )
    task = next((t for t in progress.tasks if t.task_id == event.task_id), None)
    if task is None or task.state in TASK_TERMINAL:
        raise ExecutionPreparationError("EXECUTION_TASK_TERMINAL_OR_MISSING")
    participant = next(p for p in preparation.participants if p.task_id == task.task_id)
    action = event.action
    patch = {}
    if action in {"QUEUE", "RETRY"}:
        expected = TaskState.READY if action == "QUEUE" else TaskState.RETRY_WAIT
        if (
            task.state != expected
            or progress.cancellation_request_id
            or progress.state == "RECOVERY_REQUIRED"
            or not event.attempt_id
            or event.attempt_id == task.attempt_id
            or task.attempt_ordinal >= participant.max_attempts
        ):
            raise ExecutionPreparationError("EXECUTION_DISPATCH_NOT_READY")
        patch = {
            "state": TaskState.QUEUED,
            "attempt_id": event.attempt_id,
            "attempt_ordinal": task.attempt_ordinal + 1,
            "stop_evidence": None,
            "output_artifact_ids": (),
            "reason": None,
        }
    elif action == "FINALIZE_FAILURE":
        if task.state != TaskState.RETRY_WAIT or not task.stop_evidence:
            raise ExecutionPreparationError("EXECUTION_FINAL_FAILURE_NOT_READY")
        patch = {"state": TaskState.FINAL_FAILED, "reason": "RETRY_DECLINED"}
    else:
        if not event.attempt_id or event.attempt_id != task.attempt_id:
            raise ExecutionPreparationError("EXECUTION_ATTEMPT_MISMATCH")
        if action == "STARTED" and task.state == TaskState.QUEUED:
            patch = {"state": TaskState.RUNNING}
        elif action == "UNKNOWN" and task.state in {
            TaskState.QUEUED,
            TaskState.RUNNING,
        }:
            patch = {"state": TaskState.UNKNOWN, "reason": "EFFECT_OUTCOME_UNKNOWN"}
        elif (
            action == "STOP_CONFIRMED"
            and progress.cancellation_request_id
            and task.state in {TaskState.QUEUED, TaskState.RUNNING, TaskState.UNKNOWN}
        ):
            patch = {"state": TaskState.CANCELLED, "stop_evidence": event.evidence_id}
        elif (
            action == "SUCCEEDED"
            and task.state == TaskState.RUNNING
            and event.artifact_ids
        ):
            patch = {
                "state": TaskState.SUCCEEDED,
                "stop_evidence": event.evidence_id,
                "output_artifact_ids": event.artifact_ids,
            }
        elif action == "FAILED" and task.state in {TaskState.QUEUED, TaskState.RUNNING}:
            patch = {
                "state": TaskState.FINAL_FAILED
                if task.attempt_ordinal >= participant.max_attempts
                else TaskState.RETRY_WAIT,
                "stop_evidence": event.evidence_id,
                "reason": "ATTEMPT_FAILED",
            }
        else:
            raise ExecutionPreparationError("EXECUTION_TRANSITION_REJECTED")
    updated = task.model_copy(update=patch)
    return advance(
        preparation,
        progress.model_copy(
            update={
                "version": progress.version + 1,
                "tasks": tuple(
                    updated if t.task_id == task.task_id else t for t in progress.tasks
                ),
            }
        ),
    )


class ArtifactDocument(Immutable):
    artifact_id: Identity
    task_id: Identity
    attempt_id: Identity
    kind: Identity
    schema_version: Identity
    content: Annotated[str, Field(max_length=MAX_ARTIFACT_BYTES)]
    digest: Digest

    @model_validator(mode="after")
    def bounded_bytes(self):
        import hashlib

        data = self.content.encode("utf-8")
        if (
            len(data) > MAX_ARTIFACT_BYTES
            or hashlib.sha256(data).hexdigest() != self.digest
        ):
            raise ValueError("ARTIFACT_SIZE_OR_DIGEST_INVALID")
        return self
