"""Explicit internal composition, not an HTTP identity or automatic scheduler.

Construct only for an independently configured normal planning owner. No migration,
credential issuance, policy activation, or provider calls occur at construction.
"""

from copy import copy

from .fixed_work_service_admission import (
    ServicePlanningRegistry,
    compatible,
    event_key,
    require,
)
from .plan_suggestion_invocation import PlanningRequest
from .workbench_business_problem import OwnerPrincipal


class ServicePlanningRuntime:
    def __init__(self, service, authorization, policy_reader, *, enabled=False):
        self.enabled = enabled
        self.service = service
        self.registry = ServicePlanningRegistry(
            service.application.repository, authorization, policy_reader
        )
        if enabled:
            # Never replace another exact admission or another registry on a shared
            # budget. Dedicated service composition still uses the original ledger.
            require(service.exact_admission is None)
            from .draft_provider_budget_postgres import PostgresProviderCallBudget
            from .plan_suggestion_runtime import PlanningBudget

            require(isinstance(service.budget, PlanningBudget))
            ledger = service.budget.owner
            require(isinstance(ledger, PostgresProviderCallBudget))
            require(getattr(ledger, "service_planning_admission", None) is None)
            from psycopg.rows import dict_row

            with service.application.repository.pool.connection() as c:
                c.row_factory = dict_row
                compatible(c)
            ledger.service_planning_admission = self.registry

    def begin(self, context, event, *, prepare_only=False):
        require(self.enabled, "FIXED_WORK_SERVICE_DISABLED")
        policy = self.registry._policy()
        # Identity and policy are checked by the real owner and registry before
        # claim and again in the same transaction as the original budget guard.
        require(event in policy.allowedEventIds, "FIXED_WORK_SERVICE_EVENT_DENIED")
        owner = copy(self.service)
        owner.exact_admission = self.registry.bind(context, event)
        request = PlanningRequest(
            target=policy.target,
            policy=policy.planningPolicy,
            idempotency_key=event_key(policy.work, event),
        )
        principal = OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )
        return owner.begin(principal, request, prepare_only=prepare_only)

    def tick(self, context, *, now):
        """Explicit host callback, never installed or started by construction.

        Exact DB clock/identity/budget checks still occur in begin. No retry loop;
        one unknown/denial stops the caller rather than moving to another event.
        """
        from .fixed_work_service_schedule import due_events

        require(self.enabled, "FIXED_WORK_SERVICE_DISABLED")
        policy = self.registry._policy()
        return tuple(self.begin(context, event) for event in due_events(policy, now))
