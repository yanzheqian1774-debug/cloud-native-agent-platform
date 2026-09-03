"""Internal repository ports for the ARCH-208 persistence boundary."""

from typing import Protocol

from .workflow_control_domain import (
    ApprovalDecision,
    AtomicControlCommand,
    AtomicControlResult,
    InterventionRequest,
    InterventionTransition,
    PlanRecord,
    PlanStatus,
    ScopeIdentity,
)


class PlanRepository(Protocol):
    def create_plan(self, plan: PlanRecord) -> PlanRecord: ...
    def get_plan(
        self, scope: ScopeIdentity, plan_id: str, plan_version: int
    ) -> PlanRecord | None: ...
    def replace_plan_status(
        self,
        scope: ScopeIdentity,
        plan_id: str,
        plan_version: int,
        status: PlanStatus,
        *,
        expected_version: int,
    ) -> PlanRecord: ...
    def append_approval(
        self, scope: ScopeIdentity, decision: ApprovalDecision
    ) -> ApprovalDecision: ...
    def read_approvals(
        self, scope: ScopeIdentity, plan_id: str, plan_version: int
    ) -> tuple[ApprovalDecision, ...]: ...
    def read_successor_plans(
        self, scope: ScopeIdentity, plan_id: str, plan_version: int
    ) -> tuple[PlanRecord, ...]: ...


class InterventionRepository(Protocol):
    def request_intervention(
        self, scope: ScopeIdentity, request: InterventionRequest
    ) -> InterventionRequest: ...
    def append_transition(
        self,
        scope: ScopeIdentity,
        transition: InterventionTransition,
        *,
        expected_version: int,
    ) -> InterventionTransition: ...
    def read_transitions(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[InterventionTransition, ...]: ...


class ExecutionControlRepository(Protocol):
    def compare_and_swap_target(
        self,
        scope: ScopeIdentity,
        target_kind: str,
        target_id: str,
        target_state: str,
        *,
        expected_version: int,
    ) -> int: ...

    def read_successor_runs(
        self, scope: ScopeIdentity, workflow_run_id: str
    ) -> tuple[str, ...]: ...


class IdempotencyRepository(Protocol):
    def lookup_idempotency(
        self,
        scope: ScopeIdentity,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
    ) -> object | None: ...


class ControlCommandRepository(Protocol):
    def read_pending_commands(
        self, scope: ScopeIdentity
    ) -> tuple[dict[str, object], ...]: ...


class EvidenceOutcomeRepository(Protocol):
    def read_linked_evidence(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[str, ...]: ...

    def read_linked_outcomes(
        self, scope: ScopeIdentity, intervention_id: str
    ) -> tuple[str, ...]: ...


class WorkflowControlUnitOfWork(Protocol):
    def persist(
        self, command: AtomicControlCommand, *, authorized: bool
    ) -> AtomicControlResult: ...
