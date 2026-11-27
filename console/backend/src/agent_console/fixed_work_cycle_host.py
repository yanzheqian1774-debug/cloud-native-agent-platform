"""Bounded host step over existing owners; no implicit daemon or new authority.

The composition supplies a transaction-scoped AuthorizedOwnerCall factory using
its real service credential. The local process is not an approval authority.
"""

from dataclasses import replace

from psycopg.rows import dict_row

from .digital_employee_definition import digest
from .fixed_work_service_admission import require
from .fixed_work_service_continuation import ServiceCycleContinuation
from .fixed_work_service_runtime import ServicePlanningRuntime
from .workbench_business_problem import OwnerPrincipal
from .workbench_fixed_work_trigger import FixedWorkTriggerOwner


class FixedWorkCycleHost:
    def __init__(
        self, runtime, continuation, call_scope, *, enabled=False, plan_approval=None
    ):
        require(isinstance(runtime, ServicePlanningRuntime))
        require(isinstance(continuation, ServiceCycleContinuation))
        require(continuation.registry is runtime.registry)
        self.runtime, self.continuation = runtime, continuation
        self.call_scope, self.enabled = call_scope, enabled
        self.plan_approval = plan_approval

    def step(self, context, event):
        """One event, no automatic repair, no second provider call after claim.

        Every write below remains an existing owner command. If a process dies
        between those owners, the next step reads/replays their exact saved keys.
        """
        require(self.enabled, "FIXED_WORK_CYCLE_HOST_DISABLED")
        registry = self.runtime.registry
        policy = registry._policy()
        require(event in policy.allowedEventIds, "FIXED_WORK_SERVICE_EVENT_DENIED")
        principal = OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )
        identity = (
            policy.tenantId,
            policy.securityDomain,
            policy.work.resource_id,
            event,
        )
        with registry.repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            registry._check(c, context, policy)
            # Observe only; release this transaction before any model invocation.
            prepared = c.execute(
                "SELECT * FROM fixed_work_service.planning_preparations "
                "WHERE namespace=%s AND security_domain=%s "
                "AND work_id=%s AND event_id=%s",
                identity,
            ).fetchone()
            if prepared:
                require(
                    prepared["subject_id"] == context.principal_id
                    and prepared["credential_id"]
                    == context.session_id_or_service_credential_id
                    and prepared["policy_digest"] == policy.digest,
                    "FIXED_WORK_SERVICE_EVENT_CONFLICT",
                )
            receipt = c.execute(
                "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s "
                "AND security_domain=%s AND work_id=%s AND event_id=%s",
                identity,
            ).fetchall()
            require(len(receipt) <= 1, "FIXED_WORK_SERVICE_RECEIPT_CONFLICT")
            if receipt:
                require(
                    prepared and receipt[0]["actor_id"] == context.principal_id,
                    "FIXED_WORK_SERVICE_RECEIPT_CONFLICT",
                )
        if receipt:
            # The observation transaction above must finish before call_scope
            # opens a new connection and acquires the same governance lock.
            # Reauthenticate and recheck the exact immutable receipt/current
            # authority inside that original owner transaction.
            with self.call_scope(context) as call:
                current_receipt = call.connection.execute(
                    "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s "
                    "AND security_domain=%s AND work_id=%s AND event_id=%s",
                    identity,
                ).fetchall()
                require(
                    len(current_receipt) == 1 and current_receipt[0] == receipt[0],
                    "FIXED_WORK_SERVICE_RECEIPT_CONFLICT",
                )
                call.authority.require(
                    principal,
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:"
                    + current_receipt[0]["preparation_digest"],
                )
                return {
                    "stage": "START_COMMITTED",
                    "receipt": FixedWorkTriggerOwner.receipt(current_receipt[0]),
                }
        if prepared is None:
            saved = self.runtime.begin(context, event)
        else:
            # Missing result is UNKNOWN, missing invocation raises. Neither path
            # falls back to begin or fabricates a new event/claim.
            saved = self.runtime.service.read(
                principal, prepared["invocation_id"], settle_receipt=False
            )
        result = saved["result"]
        if result["technical_status"] != "SUCCEEDED":
            return {"stage": "PLANNING_OBSERVATION", "result": result}
        if result.get("kind") != "VALID_SUGGESTION":
            return {"stage": "PLANNING_INPUT_REQUIRED", "result": result}
        proposal = result["proposal"]
        command = "fixed-cycle:" + digest([policy.work.model_dump(mode="json"), event])
        # Recheck the narrow service policy in each original owner transaction;
        # a model finishing does not retain approval or resource-write authority.
        with self.call_scope(context) as call:
            self._stage(call, policy)
            if self.plan_approval is not None:
                self.plan_approval.review(call, event, result, command + ":approval")
            app = self.continuation.readonly_owner.automation.bound_app(call)
            confirmed = app.confirm(
                principal,
                proposal["proposal_id"],
                proposal["revision"],
                result["proposal_digest"],
                expected_plan_version=0,
                key=command + ":confirm",
            )
        version = confirmed["plan"]["version"]
        with self.call_scope(context) as call:
            self._stage(call, policy)
            call = replace(
                call,
                path={"proposal_id": proposal["proposal_id"]},
                query={},
                payload={"version": version, "idempotencyKey": command + ":resources"},
                operation="PREPARE_RESOURCE_AUTOMATION",
            )
            call.authority.require(
                principal, "PLAN", "APPROVE", "plan:v2:" + proposal["proposal_id"]
            )
            resources = self.continuation.readonly_owner.automation(call)
        if resources["state"] != "READY":
            return {"stage": "RESOURCES_PENDING", "resources": resources}
        with self.call_scope(context) as call:
            receipt = self.continuation.continue_once(
                replace(
                    call,
                    path={"proposal_id": proposal["proposal_id"]},
                    payload={"version": version},
                    query={},
                ),
                event,
            )
        return {"stage": "START_COMMITTED", "receipt": receipt}

    def _stage(self, call, expected_policy):
        current = self.runtime.registry._policy()
        require(
            current.digest == expected_policy.digest,
            "FIXED_WORK_CYCLE_CONFIGURATION_CHANGED",
        )
        self.runtime.registry._check(call.connection, call.context, current)
