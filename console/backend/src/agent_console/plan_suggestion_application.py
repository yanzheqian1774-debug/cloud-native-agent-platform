"""Confirmed Problem planning and Workflow Control confirmation coordinator."""

from .business_problem_authorization import (
    criteria_resource,
    criterion_revision_resource,
    problem_resource,
)
from .business_problem_domain import BusinessProblemState
from .execution_domain import ScopeIdentity
from .plan_suggestion_domain import PlanningConflict, PlanningError


class PlanningApplication:
    def __init__(self, repository, problems, authority):
        self.repository = repository
        self.problems = problems
        self.authority = authority

    @staticmethod
    def scope(principal):
        return ScopeIdentity(principal.tenant_id, principal.security_domain)

    def require(self, principal, action, proposal_id):
        return self.authority.require(
            principal, "PLAN", action, f"plan:v2:{proposal_id}"
        )

    def validate_target(self, principal, target, connection, *, current=True):
        self.authority.require(
            principal,
            "BUSINESS_PROBLEM",
            "READ",
            problem_resource(target.problem.resource_id),
        )
        self.authority.require(
            principal,
            "SUCCESS_CRITERIA_SET",
            "READ",
            criteria_resource(target.problem.resource_id),
        )
        scope = self.scope(principal)
        aggregate = self.problems.get_aggregate(
            scope, target.problem.resource_id, authorized=True, connection=connection
        )
        revisions = self.problems.get_problem(
            scope, target.problem.resource_id, authorized=True, connection=connection
        )
        revision = next(
            (r for r in revisions if r.revision_id == target.problem.revision_id), None
        )
        criteria = self.problems.get_criteria_set_revision(
            scope,
            target.criteria.revision_id,
            authorized=True,
            connection=connection,
            business_problem_id=target.problem.resource_id,
        )
        for identity in criteria.ordered_criterion_revision_ids:
            self.authority.require(
                principal,
                "SUCCESS_CRITERION",
                "READ",
                criterion_revision_resource(identity),
            )
        if (
            target.criteria.resource_id != target.problem.resource_id
            or revision is None
            or revision.digest != target.problem.digest
            or criteria.digest != target.criteria.digest
            or criteria.problem_revision_id != target.problem.revision_id
            or criteria.ordered_criterion_revision_ids != target.criterion_revision_ids
        ):
            raise PlanningConflict("PLANNING_TARGET_MISMATCH")
        if current:
            sets = self.problems.list_criteria_set_revisions(
                scope,
                target.problem.resource_id,
                authorized=True,
                connection=connection,
            )
            if (
                aggregate.aggregate_version != target.expected_problem_version
                or aggregate.current_revision_id != target.problem.revision_id
                or aggregate.current_state != BusinessProblemState.ACTIVE
                or not sets
                or sets[-1].set_revision_id != target.criteria.revision_id
            ):
                raise PlanningConflict("PLANNING_TARGET_STALE")

    def save_suggestion(self, principal, proposal):
        # This entry is called by the governed invocation owner, never model HTTP.
        self.require(principal, "PREPARE", proposal.proposal_id)
        scope = self.scope(principal)
        with self.repository.transaction(
            scope, proposal.proposal_id, authorized=True
        ) as cursor:
            self.validate_target(
                principal, proposal.semantics.target, cursor.connection
            )
            return self.repository.add_proposal(cursor, scope, proposal)

    def confirm(
        self, principal, proposal_id, revision, digest, *, expected_plan_version, key
    ):
        if not key or len(key) > 200 or expected_plan_version < 0:
            raise PlanningError("PLANNING_COMMAND_INVALID")
        self.require(principal, "APPROVE", proposal_id)
        scope = self.scope(principal)
        with self.repository.transaction(scope, proposal_id, authorized=True) as cursor:
            proposal = self.repository.proposal(cursor, scope, proposal_id, revision)
            if proposal.digest != digest:
                raise PlanningConflict("PROPOSAL_DIGEST_CONFLICT")
            self.validate_target(
                principal, proposal.semantics.target, cursor.connection, current=False
            )
            return self.repository.confirmation(
                cursor,
                scope,
                proposal,
                actor=principal.principal_id,
                key=key,
                expected_plan_version=expected_plan_version,
                authority_basis="TRUSTED_EXACT_PLAN_APPROVAL",
                validate_current=lambda: self.validate_target(
                    principal, proposal.semantics.target, cursor.connection
                ),
            )

    def read(self, principal, plan_id, version):
        self.require(principal, "READ", plan_id)
        scope = self.scope(principal)
        with self.repository.transaction(scope, plan_id, authorized=True) as cursor:
            result = self.repository.read_plan(cursor, scope, plan_id, version)
            from .plan_suggestion_domain import ConfirmedPlanRevision

            plan = ConfirmedPlanRevision.model_validate(result["plan"])
            self.validate_target(
                principal, plan.semantics.target, cursor.connection, current=False
            )
            return result
