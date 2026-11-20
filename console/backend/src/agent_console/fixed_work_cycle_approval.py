# ruff: noqa: E501 -- Same-connection exact owner proof queries.
"""Optional exact service-plan approval through the existing independent issuer.

This adapter never creates grants itself. Real saved model provenance, metering,
current work/credential and the original resource policy precede GrantAdmin.
"""

from contextlib import nullcontext
from copy import copy

from .authority_contracts import ExactGrant
from .fixed_work_service_admission import require
from .plan_suggestion_domain import ProposalRevision
from .workbench_business_problem import OwnerPrincipal


class ServiceCyclePlanApproval:
    def __init__(self, registry, budget, automation, *, enabled=False):
        self.registry, self.budget, self.automation = registry, budget, automation
        self.enabled = enabled

    def review(self, call, event, result, command_key):
        require(self.enabled, "FIXED_WORK_CYCLE_APPROVAL_DISABLED")
        proposal = ProposalRevision.model_validate(result["proposal"])
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        app = self.automation.bound_app(call)
        # Same order as continuation/resources: Plan first, then work admission.
        with app.repository.transaction(
            app.scope(principal), proposal.proposal_id, authorized=True
        ) as cur:
            require(
                cur.connection is call.connection,
                "FIXED_WORK_SERVICE_TRANSACTION_REQUIRED",
            )
            return self._review_locked(call, event, result, command_key)

    def _review_locked(self, call, event, result, command_key):
        c, context = call.connection, call.context
        policy = self.registry._policy()
        self.registry._check(c, context, policy)
        self.registry._lock(c, policy)
        require(event in policy.allowedEventIds)
        principal = OwnerPrincipal(
            context.principal_id, policy.tenantId, policy.securityDomain
        )
        call.authority.require(
            principal,
            "PLAN",
            "READ",
            "plan:prepared:" + policy.target.problem.resource_id,
        )
        row = c.execute(
            "SELECT * FROM fixed_work_service.planning_preparations WHERE namespace=%s "
            "AND security_domain=%s AND work_id=%s AND event_id=%s",
            (policy.tenantId, policy.securityDomain, policy.work.resource_id, event),
        ).fetchone()
        require(
            row is not None
            and row["subject_id"] == context.principal_id
            and row["credential_id"] == context.session_id_or_service_credential_id,
            "FIXED_WORK_SERVICE_PLANNING_PROOF_REQUIRED",
        )
        self.registry._verify(c, row, dispatch=False)
        observed = c.execute(
            "SELECT record FROM workflow_planning.invocation_results WHERE namespace=%s "
            "AND security_domain=%s AND invocation_id=%s",
            (policy.tenantId, policy.securityDomain, row["invocation_id"]),
        ).fetchone()
        require(
            observed is not None
            and observed["record"] == result
            and result.get("technical_status") == "SUCCEEDED"
            and result.get("kind") == "VALID_SUGGESTION",
            "FIXED_WORK_SERVICE_PLANNING_RESULT_REQUIRED",
        )
        proposal = ProposalRevision.model_validate(result["proposal"])
        app = self.automation.bound_app(call)
        with app.repository.transaction(
            app.scope(principal), proposal.proposal_id, authorized=True
        ) as cur:
            require(cur.connection is c, "FIXED_WORK_SERVICE_TRANSACTION_REQUIRED")
            actual = app.repository.proposal(
                cur, app.scope(principal), proposal.proposal_id, proposal.revision
            )
            require(
                actual == proposal
                and proposal.origin is None
                and proposal.invocation_id == row["invocation_id"]
                and proposal.digest == result["proposal_digest"]
                and proposal.semantics.target == policy.target,
                "FIXED_WORK_SERVICE_PROPOSAL_LINEAGE_CHANGED",
            )
        receipt = c.execute(
            "SELECT p.record,r.reservation_id FROM workflow_planning.provider_receipts p "
            "JOIN draft_provider_budget.reservations r USING(namespace,security_domain,invocation_id) "
            "WHERE p.namespace=%s AND p.security_domain=%s AND p.invocation_id=%s AND r.ledger_id=%s",
            (
                policy.tenantId,
                policy.securityDomain,
                row["invocation_id"],
                policy.ledgerId,
            ),
        ).fetchall()
        require(
            len(receipt) == 1
            and receipt[0]["record"].get("reservation_id")
            == receipt[0]["reservation_id"]
            and self.budget.ledger_id == policy.ledgerId,
            "FIXED_WORK_SERVICE_BUDGET_RECEIPT_REQUIRED",
        )
        # Same connection and original pricing/reservation validator; no reserve,
        # settle, repricing or alternate ledger is introduced here.
        budget = copy(self.budget)
        budget._connection = lambda: nullcontext(c)
        require(
            budget.read_settlement(receipt[0]["reservation_id"])["status"]
            == "ESTIMATE_SETTLED",
            "FIXED_WORK_SERVICE_BUDGET_RECEIPT_REQUIRED",
        )
        issuer = self.automation.authenticate(context)
        work = self.automation.work(
            context, policy.target.problem, self.automation.grants.clock(), connection=c
        )
        from .resource_automation_policy import AdministratorWorkScope

        require(
            not isinstance(work, AdministratorWorkScope)
            and issuer.principal_id != context.principal_id,
            "FIXED_WORK_INDEPENDENT_POLICY_ISSUER_REQUIRED",
        )
        work = work.model_copy(
            update={"expiresAt": min(work.expiresAt, policy.expiresAt)}
        )
        return self.automation.decide(
            call,
            tuple(
                ExactGrant("PLAN", action, "plan:v2:" + proposal.proposal_id)
                for action in ("READ", "PREPARE", "APPROVE")
            ),
            command_key,
            work,
            issuer,
        )
