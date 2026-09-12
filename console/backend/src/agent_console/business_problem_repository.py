"""Typed repository port for durable Business Problem authority."""

from typing import Protocol

from agent_console.business_problem_domain import (
    BusinessProblemAggregate,
    BusinessProblemCreatorReceipt,
    BusinessProblemLifecycleEvent,
    BusinessProblemRevision,
    BusinessProblemState,
    PlanProblemBinding,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
)
from agent_console.execution_domain import ScopeIdentity


class BusinessProblemRepository(Protocol):
    def create_problem(
        self,
        revision: BusinessProblemRevision,
        *,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
        connection=None,
        receipt_policy_generation: int | None = None,
        receipt_recovery_epoch: int | None = None,
    ) -> BusinessProblemRevision: ...
    def get_creator_receipt(
        self,
        scope: ScopeIdentity,
        creator_principal_id: str,
        originating_command_idempotency_key: str,
        *,
        authorized: bool,
        connection=None,
    ) -> BusinessProblemCreatorReceipt: ...
    def get_problem(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[BusinessProblemRevision, ...]: ...
    def list_problems(
        self, scope: ScopeIdentity, *, authorized: bool
    ) -> tuple[BusinessProblemRevision, ...]: ...
    def get_aggregate(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> BusinessProblemAggregate: ...
    def add_problem_revision(
        self,
        revision: BusinessProblemRevision,
        *,
        expected_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> BusinessProblemRevision: ...
    def add_criterion_revision(
        self,
        revision: SuccessCriterionRevision,
        *,
        expected_version: int | None,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> SuccessCriterionRevision: ...
    def get_criterion_revision(
        self, scope: ScopeIdentity, revision_id: str, *, authorized: bool
    ) -> SuccessCriterionRevision: ...
    def list_criterion_revisions(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[SuccessCriterionRevision, ...]: ...
    def add_criteria_set_revision(
        self,
        revision: SuccessCriteriaSetRevision,
        *,
        expected_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> SuccessCriteriaSetRevision: ...
    def get_criteria_set_revision(
        self, scope: ScopeIdentity, set_revision_id: str, *, authorized: bool
    ) -> SuccessCriteriaSetRevision: ...
    def list_criteria_set_revisions(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[SuccessCriteriaSetRevision, ...]: ...
    def transition(
        self,
        scope: ScopeIdentity,
        business_problem_id: str,
        to_state: BusinessProblemState,
        *,
        actor_id: str,
        expected_version: int,
        event_id: str,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> int: ...
    def get_lifecycle(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[BusinessProblemLifecycleEvent, ...]: ...
    def bind_plan(
        self,
        binding: PlanProblemBinding,
        *,
        expected_problem_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> PlanProblemBinding: ...
    def get_plan_binding(
        self, scope: ScopeIdentity, binding_id: str, *, authorized: bool
    ) -> PlanProblemBinding: ...


class BusinessProblemPlanRepository(Protocol):
    """Product-owned ports participating in a caller-owned transaction."""

    def validate_plan_target(
        self,
        connection,
        binding: PlanProblemBinding,
        expected_version: int,
        *,
        authorized: bool,
    ): ...
    def bind_prepared_plan(
        self,
        connection,
        binding: PlanProblemBinding,
        *,
        expected_problem_version: int,
        idempotency_key: str,
        payload_digest: str,
        authorized: bool,
    ) -> PlanProblemBinding: ...
    def validate_approval_binding(
        self,
        connection,
        binding: PlanProblemBinding,
        *,
        expected_problem_version: int,
        authorized: bool,
    ) -> PlanProblemBinding: ...
