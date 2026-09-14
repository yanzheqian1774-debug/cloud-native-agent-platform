"""Domain-owned exact-target composition for the Business Workbench."""

from __future__ import annotations

from collections.abc import Sequence

from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    ContinuationClaim,
    ExactGrant,
    TrustedRequestContext,
)
from agent_console.business_problem_continuation import (
    BusinessProblemContinuationValidator,
)
from agent_console.business_problem_domain import BusinessProblemError
from agent_console.business_problem_repository import BusinessProblemRepository
from agent_console.execution_domain import ScopeIdentity


class WorkbenchGrantTargetValidator:
    """Keep canonical target validation with the Business Problem owner."""

    def __init__(self, problems: BusinessProblemRepository) -> None:
        self.problems = problems
        self.problem_continuations = BusinessProblemContinuationValidator(problems)

    @staticmethod
    def _scope(context: TrustedRequestContext) -> ScopeIdentity:
        return ScopeIdentity(context.scope.tenant_id, context.scope.security_domain)

    def is_known_exact_target(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool:
        if connection is None:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")
        if grant.owner not in {"SUCCESS_CRITERION", "SUCCESS_CRITERIA_SET"}:
            return False
        try:
            return self.problems.is_known_grant_target_for_workbench(
                connection,
                self._scope(context),
                grant.owner,
                grant.action,
                grant.exact_resource,
            )
        except BusinessProblemError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def validate_continuation(
        self, claim: ContinuationClaim, *, connection: object | None = None
    ) -> bool:
        return self.problem_continuations.validate_continuation(
            claim, connection=connection
        )

    def validate_offer(
        self,
        scope: AuthorityScope,
        members: Sequence[ExactGrant],
        canonical_resource_reference: str,
        owner_revision: str,
    ) -> bool:
        return self.problem_continuations.validate_offer(
            scope,
            members,
            canonical_resource_reference,
            owner_revision,
        )
