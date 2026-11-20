"""Explicit composition of existing service owners into the bounded cycle loop.

The caller owns normal model/authority/resource services and their closeables.
There is no environment auto-start, dynamic Python import path, credential
creation or migration. Deployment supplies those existing dependencies once.
"""

from .fixed_work_cycle_host import FixedWorkCycleHost
from .fixed_work_service_admission import require
from .fixed_work_service_continuation import ServiceCycleContinuation
from .fixed_work_service_policy import ServicePlanningPolicy
from .fixed_work_service_runtime import ServicePlanningRuntime


def compose_cycle_service(
    *,
    planning_service,
    authorization,
    policy_path,
    readonly_owner,
    current_context,
    authorized_call_scope,
    database_fingerprint,
    enabled=False,
    poll_seconds=30,
    policy_plan_approval_enabled=False,
):
    """Return an unstarted loop, or None with no dependency reads when disabled.

    authorized_call_scope(context) is the existing service composition's
    transaction/authentication boundary, not a browser-provided grant callback.
    Every actual command additionally checks its original owner authority.
    """
    if not enabled:
        return None
    require(callable(current_context) and callable(authorized_call_scope))
    # Import only on explicit opt-in; web-only deployment has no loop dependency.
    from agent_operator.fixed_work_cycle_service import FixedWorkCycleService

    from .readonly_continuation import ReadonlyContinuation

    require(isinstance(readonly_owner, ReadonlyContinuation))
    loop = FixedWorkCycleService(
        None,
        current_context,
        database_fingerprint,
        enabled=False,
        poll_seconds=poll_seconds,
    )
    runtime = ServicePlanningRuntime(
        planning_service,
        authorization,
        lambda: ServicePlanningPolicy.load(policy_path),
        enabled=True,
    )
    continuation = ServiceCycleContinuation(
        runtime.registry, readonly_owner, enabled=True
    )
    approval = None
    if policy_plan_approval_enabled:
        from .fixed_work_cycle_approval import ServiceCyclePlanApproval

        approval = ServiceCyclePlanApproval(
            runtime.registry,
            planning_service.budget.owner,
            readonly_owner.automation,
            enabled=True,
        )
    host = FixedWorkCycleHost(
        runtime,
        continuation,
        authorized_call_scope,
        enabled=True,
        plan_approval=approval,
    )
    loop.host = host
    loop.enabled = True
    return loop
