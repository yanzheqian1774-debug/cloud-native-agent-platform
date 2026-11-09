"""D11 confirmation of an existing qualified proposal, without execution."""

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import ExactGrant
from .business_problem_domain import BusinessProblemError
from .plan_suggestion_domain import (
    ExactReference,
    PlanningConflict,
    PlanningError,
    SyntheticValidationOrigin,
)
from .planning_candidates import read_published, require_read
from .planning_contracts import validation_report
from .planning_source_change import approved_source, validate_confirmation
from .resource_automation_validation import validate
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class ConfirmPolicyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem: ExactReference
    revision: int = Field(ge=1)
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    expectedPlanVersion: int = Field(ge=0)
    idempotencyKey: str = Field(min_length=1, max_length=120)


def entry_grants(context, path, payload, query):
    return (
        ExactGrant(
            "PLAN", "READ", "plan:prepared:" + payload["problem"]["resource_id"]
        ),
    )


class PolicyPlanConfirmation:
    def __init__(self, automation):
        self.automation = automation

    def __call__(self, call):
        try:
            return self.confirm(call)
        except PlanningError as exc:
            raise WorkbenchOwnerError(
                str(exc), 409 if isinstance(exc, PlanningConflict) else 404
            ) from exc

    def confirm(self, call):
        a = self.automation
        request = ConfirmPolicyPlan.model_validate(call.payload)
        issuer = a.authenticate(call.context)
        work = a.work(call.context, request.problem, a.grants.clock())
        p = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        app = a.bound_app(call)
        scope = app.scope(p)
        # Enforce the entry authority for direct owner callers as well as BFF.
        call.authority.require(
            p, "PLAN", "READ", "plan:prepared:" + request.problem.resource_id
        )
        identity = call.path["proposal_id"]
        with app.repository.transaction(scope, identity, authorized=True) as cur:
            proposal = app.repository.proposal(cur, scope, identity, request.revision)
            if (
                proposal.digest != request.digest
                or proposal.semantics.target.problem != request.problem
            ):
                raise WorkbenchOwnerError("POLICY_CONFIRMATION_PROPOSAL_CONFLICT", 409)
            if proposal.origin is not None and not isinstance(
                proposal.origin, SyntheticValidationOrigin
            ):
                raise WorkbenchOwnerError(
                    "POLICY_CONFIRMATION_SPECIALIZED_OWNER_REQUIRED", 409
                )
            validation_report(proposal.semantics)

            def validate_current():
                try:
                    app.validate_target(p, proposal.semantics.target, cur.connection)
                except BusinessProblemError as exc:
                    raise WorkbenchOwnerError(
                        "POLICY_CONFIRMATION_TARGET_STALE", 409
                    ) from exc

            validate_current()
            validate_confirmation(app, p, cur.connection, proposal)
            source = approved_source(proposal.semantics)
            require_read(call.authority, p, "KNOWLEDGE", source)
            content, _ = read_published(cur.connection, scope, "KNOWLEDGE", source)
            validate("knowledge", content, work)
            actions = [
                ExactGrant("PLAN", action, "plan:v2:" + identity)
                for action in ("READ", "PREPARE", "APPROVE")
            ]
            proof = a.decide(
                call, actions, "confirm:" + request.idempotencyKey, work, issuer
            )
            a.proof_grants(call, actions)
            confirmation = app.repository.confirmation(
                cur,
                scope,
                proposal,
                actor=issuer.principal_id,
                key="policy-plan-confirm:" + request.idempotencyKey,
                expected_plan_version=request.expectedPlanVersion,
                authority_basis="POLICY:"
                + proof.decision_id
                + ":"
                + proof.policy_digest,
                approval_kind="RESOURCE_POLICY_APPROVAL",
                validate_current=validate_current,
            )
            return {
                "confirmation": confirmation,
                "policyBasis": proof.record(issuer.principal_id),
                "executionStarted": False,
            }
