"""Typed repository port for durable Business Problem authority."""

from typing import Protocol

from agent_console.business_problem_domain import (
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
    ) -> BusinessProblemRevision: ...
    def get_problem(
        self, scope: ScopeIdentity, business_problem_id: str, *, authorized: bool
    ) -> tuple[BusinessProblemRevision, ...]: ...
    def list_problems(
        self, scope: ScopeIdentity, *, authorized: bool
    ) -> tuple[BusinessProblemRevision, ...]: ...
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
