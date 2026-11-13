# ruff: noqa: E501 -- Exact existing owner and receipt keys.
"""Service event wrapper around the EXISTING readonly continuation transaction.

No Plan origin, approval, preparation, Run or execution command is manufactured here.
"""

from dataclasses import replace

from .digital_employee_definition import digest
from .fixed_work_service_admission import require
from .fixed_work_trigger_postgres import compatible
from .plan_suggestion_domain import ConfirmedPlanRevision
from .readonly_continuation import ReadonlyContinuation, command_key
from .workbench_business_problem import OwnerPrincipal
from .workbench_fixed_work_trigger import FixedWorkTriggerOwner


class ServiceCycleContinuation:
    def __init__(self, registry, readonly_owner, *, enabled=False):
        self.registry, self.readonly_owner, self.enabled = (
            registry,
            readonly_owner,
            enabled,
        )
        require(isinstance(readonly_owner, ReadonlyContinuation))

    def continue_once(self, call, event):
        require(self.enabled, "FIXED_WORK_SERVICE_CONTINUATION_DISABLED")
        policy = self.registry._policy()
        require(event in policy.allowedEventIds, "FIXED_WORK_SERVICE_EVENT_DENIED")
        c, context = call.connection, call.context
        principal = OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )
        call.authority.require(
            principal, "PLAN", "READ", "plan:v2:" + call.path["proposal_id"]
        )
        app = self.readonly_owner.automation.bound_app(call)
        scope = app.scope(principal)
        # Original Plan lock first, exactly as readonly continuation; all work uses
        # caller-owned transaction and must roll back together on any failure.
        with app.repository.transaction(
            scope, call.path["proposal_id"], authorized=True
        ) as cur:
            require(cur.connection is c, "FIXED_WORK_SERVICE_TRANSACTION_REQUIRED")
            original = app.repository.read_plan(
                cur, scope, call.path["proposal_id"], call.payload["version"]
            )
            plan = ConfirmedPlanRevision.model_validate(original["plan"])
            require(original["digest"] == plan.digest)
            compatible(c)
            self.registry._check(c, context, policy)
            self.registry._lock(c, policy)
            identity = (
                scope.namespace,
                scope.security_domain,
                context.principal_id,
                event,
            )
            # Same lock family as the explicit trigger owner, before receipt read.
            for item in sorted(
                (
                    digest([*identity]),
                    digest(
                        [
                            scope.namespace,
                            scope.security_domain,
                            "work",
                            policy.work.resource_id,
                        ]
                    ),
                )
            ):
                c.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    ("fixed-work-trigger:" + item,),
                )
            payload_digest = digest(
                dict(
                    work=policy.work.model_dump(mode="json"),
                    event=event,
                    plan=plan.digest,
                )
            )
            prior = c.execute(
                "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND event_id=%s",
                identity,
            ).fetchone()
            if prior:
                require(
                    prior["payload_digest"] == payload_digest
                    and prior["work_id"] == policy.work.resource_id
                    and prior["revision_id"] == policy.work.revision_id,
                    "FIXED_WORK_SERVICE_EVENT_CONFLICT",
                )
                call.authority.require(
                    principal,
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:" + prior["preparation_digest"],
                )
                return FixedWorkTriggerOwner.receipt(prior)
            self.registry.authorize_confirmed_plan(c, context, event, plan)
            key = command_key(plan)
            existing = c.execute(
                "SELECT 1 FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
                (*identity[:3], key),
            ).fetchone()
            require(
                existing is None,
                "FIXED_WORK_SERVICE_EXISTING_CONTINUATION_REQUIRES_REVIEW",
            )
            result = self.readonly_owner(
                replace(
                    call,
                    operation="CONTINUE_READONLY_WORK",
                    payload={"version": plan.version},
                    query={},
                )
            )
            receipt = result["receipt"]
            require(
                receipt["sourcePlanDigest"] == plan.digest
                and receipt["subject"] == context.principal_id
                and receipt["executionStarted"] is True
            )
            actual = c.execute(
                "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
                (*identity[:3], key),
            ).fetchone()
            require(
                actual is not None and actual["result"] == receipt,
                "FIXED_WORK_SERVICE_CONTINUATION_RECEIPT_CHANGED",
            )
            row = c.execute(
                "INSERT INTO fixed_work_triggers.receipts VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp()) RETURNING *",
                (
                    *identity,
                    policy.work.resource_id,
                    policy.work.revision_id,
                    policy.work.digest,
                    receipt["preparationDigest"],
                    payload_digest,
                    policy.digest,
                    receipt["runId"],
                    key + ":start",
                ),
            ).fetchone()
            return FixedWorkTriggerOwner.receipt(row)
