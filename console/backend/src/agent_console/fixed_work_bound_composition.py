"""Explicit runnable composition over real authority/planning/readonly owners.

No dynamic import, migration, credential creation, implicit thread or HTTP start.
The installer owns dependency lifetime and supplies its private credential reader.
"""

from contextlib import contextmanager
from datetime import UTC, datetime

from .authority_contracts import (
    AuthenticationSource,
    GrantSource,
    TrustedRequestContext,
)
from .browser_session_application import StaticGenerationAuthenticator
from .fixed_work_bound_policy import BoundServicePlanningPolicy
from .fixed_work_cycle_composition import compose_cycle_service
from .fixed_work_service_admission import require
from .fixed_work_service_policy import ServicePlanningPolicy
from .workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerAuthorization,
)


def compose_bound_cycle_service(
    *,
    foundation,
    planning_factory,
    readonly_owner,
    policy_path,
    credential_reader,
    enabled=False,
    poll_seconds=30,
    policy_plan_approval_enabled=False,
):
    if not enabled:
        return None
    policy = ServicePlanningPolicy.load(policy_path)
    require(
        isinstance(policy, BoundServicePlanningPolicy),
        "FIXED_WORK_CONFIRMED_SOURCE_POLICY_REQUIRED",
    )
    controller = foundation.generation_controller
    authorization = foundation.grants.authorization
    adapter = WorkbenchOwnerAuthorization(
        controller, foundation.repository, authorization
    )

    def current_context():
        with controller.protected_request() as generation:
            verified = StaticGenerationAuthenticator(
                generation, source=GrantSource.SERVICE_ONLY
            ).authenticate(credential_reader(), now=datetime.now(UTC))
            context = TrustedRequestContext(
                verified.principal_id,
                verified.scope,
                verified.credential_id,
                AuthenticationSource.SERVICE_CREDENTIAL,
                verified.policy_version,
            )
            policy.require(context, datetime.now(UTC))
            return context

    initial = current_context()

    @contextmanager
    def call_scope(context):
        # Reauthenticate from the actual credential before opening an effect unit;
        # never trust a context passed by a model or browser payload.
        require(current_context() == context, "FIXED_WORK_SERVICE_IDENTITY_DENIED")
        with (
            controller.protected_request() as generation,
            foundation.repository.connection_scope() as c,
        ):
            c.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            current = ServicePlanningPolicy.load(policy_path)
            require(
                current.digest == policy.digest,
                "FIXED_WORK_CYCLE_CONFIGURATION_CHANGED",
            )
            # The same original registry checks all source/current credential/grant
            # gates inside this transaction before the original owners can write.
            loop.host.runtime.registry._check(c, context, current)
            yield AuthorizedOwnerCall(
                "FIXED_WORK_SERVICE_CYCLE",
                context,
                c,
                {},
                {},
                {},
                (),
                AuthorizedOwnerAuthority(
                    adapter, context, c, generation.generation, ()
                ),
                generation.generation,
                controller.readiness.recovery_epoch,
            )

    loop = compose_cycle_service(
        planning_service=planning_factory(initial),
        authorization=authorization,
        policy_path=policy_path,
        readonly_owner=readonly_owner,
        current_context=current_context,
        authorized_call_scope=call_scope,
        database_fingerprint=controller.readiness.database_fingerprint,
        enabled=True,
        poll_seconds=poll_seconds,
        policy_plan_approval_enabled=policy_plan_approval_enabled,
    )
    # Construction never dispatches. These are the actual owners the explicit
    # caller later runs with loop.run(stop_event, observer).
    return loop


def inspect_bound_cycle(loop):
    """Read current gates only; never reserve a budget or dispatch a due event."""
    from psycopg.rows import dict_row

    from .fixed_work_service_schedule import due_events

    require(loop is not None and loop.enabled, "FIXED_WORK_CYCLE_SERVICE_DISABLED")
    context = loop.current_context()
    registry = loop.host.runtime.registry
    policy = registry._policy()
    require(
        isinstance(policy, BoundServicePlanningPolicy),
        "FIXED_WORK_CONFIRMED_SOURCE_POLICY_REQUIRED",
    )
    with registry.repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        now = registry._check(c, context, policy)
    return {
        "work": policy.work.model_dump(mode="json"),
        "sourceBindingDigest": policy.sourceBindingDigest,
        "sourceAndCurrentServiceAuthority": "VERIFIED_AT_OBSERVATION",
        "schedule": "BOUNDED_WINDOWS_VALIDATED",
        "dueEventCount": len(due_events(policy, now)),
        "budget": "ORIGINAL_LEDGER_CHECKED_AT_EACH_RESERVATION",
        "execution": "ORIGINAL_OWNERS_REQUIRED_FOR_EACH_PLAN_AND_START",
        "humanAnswerDelegation": "NOT_CONFIGURED",
        "executionStartedByObservation": False,
    }
