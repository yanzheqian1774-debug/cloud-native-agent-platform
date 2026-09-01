"""Storage-independent repository Port candidates for execution authority."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .execution_contract import (
    AgentInstanceId,
    AssignmentId,
    AttemptId,
    CommandId,
    EvidenceId,
    ExecutionIdentityAggregate,
    InterventionId,
    ObservationId,
    OutcomeId,
    PlacementDecision,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeDesiredState,
    RuntimeInstanceId,
    RuntimeObservation,
    ScopeIdentity,
    WorkflowRunId,
)


class AppendDisposition(StrEnum):
    APPENDED = "APPENDED"
    REPLAYED = "REPLAYED"


@dataclass(frozen=True, slots=True)
class PlacementResult:
    disposition: AppendDisposition
    decision: PlacementDecision


class ExecutionIdentityRepository(Protocol):
    def save(
        self, scope: ScopeIdentity, aggregate: ExecutionIdentityAggregate
    ) -> ExecutionIdentityAggregate: ...

    def get_attempt(
        self, scope: ScopeIdentity, attempt_id: AttemptId
    ) -> ExecutionIdentityAggregate | None: ...


class PlacementRepository(Protocol):
    def decide(
        self,
        scope: ScopeIdentity,
        request: PlacementRequest,
        decision: PlacementDecision,
    ) -> PlacementResult: ...

    def get(
        self, scope: ScopeIdentity, placement_id: PlacementId
    ) -> PlacementDecision | None: ...

    def get_by_request(
        self, scope: ScopeIdentity, request_id: PlacementRequestId
    ) -> PlacementDecision | None: ...


class RuntimeDesiredStateRepository(Protocol):
    def append(
        self, scope: ScopeIdentity, command: RuntimeDesiredState
    ) -> AppendDisposition: ...

    def get(
        self, scope: ScopeIdentity, command_id: CommandId
    ) -> RuntimeDesiredState | None: ...

    def read_runtime(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[RuntimeDesiredState, ...]: ...


class RuntimeObservationRepository(Protocol):
    def append(
        self, scope: ScopeIdentity, observation: RuntimeObservation
    ) -> AppendDisposition: ...

    def get(
        self, scope: ScopeIdentity, observation_id: ObservationId
    ) -> RuntimeObservation | None: ...

    def read_runtime(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[RuntimeObservation, ...]: ...


class ExecutionEvidencePort(Protocol):
    def read_attempt(
        self, scope: ScopeIdentity, attempt_id: AttemptId
    ) -> tuple[EvidenceId, ...]: ...


class OutcomePort(Protocol):
    def read_workflow(
        self, scope: ScopeIdentity, workflow_run_id: WorkflowRunId
    ) -> tuple[OutcomeId, ...]: ...


class InterventionPort(Protocol):
    def read_runtime(
        self, scope: ScopeIdentity, runtime_instance_id: RuntimeInstanceId
    ) -> tuple[InterventionId, ...]: ...

    def read_assignment(
        self, scope: ScopeIdentity, assignment_id: AssignmentId
    ) -> tuple[InterventionId, ...]: ...


class ExecutionRelationshipQueryPort(Protocol):
    def attempts_for_runtime_agent(
        self,
        scope: ScopeIdentity,
        runtime_instance_id: RuntimeInstanceId,
        agent_instance_id: AgentInstanceId,
    ) -> tuple[AttemptId, ...]: ...
