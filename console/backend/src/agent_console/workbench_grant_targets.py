"""Owner-dispatched exact-target composition for the combined Workbench."""

from __future__ import annotations

from collections.abc import Sequence

from agent_console.agent_definition_repository import (
    AgentDefinitionRepository,
    AgentDefinitionRepositoryError,
    DefinitionScope,
)
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    ContinuationClaim,
    ExactGrant,
    GrantTargetValidator,
    TrustedRequestContext,
)
from agent_console.business_problem_continuation import (
    BusinessProblemContinuationValidator,
)
from agent_console.business_problem_domain import BusinessProblemError
from agent_console.business_problem_repository import BusinessProblemRepository
from agent_console.digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeDefinitionRepository,
)
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.execution_domain import ScopeIdentity


class WorkbenchGrantTargetValidator:
    """Dispatch validation to the canonical owner and fail closed otherwise."""

    def __init__(
        self,
        problems: BusinessProblemRepository | None,
        agents: AgentDefinitionRepository | None = None,
        employees: EmployeeDefinitionRepository | None = None,
        additional: Sequence[GrantTargetValidator] = (),
    ) -> None:
        self.problems = problems
        self.problem_continuations = (
            BusinessProblemContinuationValidator(problems)
            if problems is not None
            else None
        )
        self.agents = agents
        self.employees = employees
        self.additional = tuple(additional)

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
        try:
            if grant.owner in {"SUCCESS_CRITERION", "SUCCESS_CRITERIA_SET"} or (
                grant.owner == "BUSINESS_PROBLEM"
                and grant.action in {"READ", "REVISE", "TRANSITION"}
            ):
                if self.problems is None:
                    return False
                return self.problems.is_known_grant_target_for_workbench(
                    connection,
                    self._scope(context),
                    grant.owner,
                    grant.action,
                    grant.exact_resource,
                )
            if grant.owner == "EMPLOYEE":
                if self.employees is None:
                    return False
                return self.employees.is_known_grant_target_for_workbench(
                    connection,
                    self._scope(context),
                    grant.action,
                    grant.exact_resource,
                )
            if grant.owner == "AGENT" and grant.action in {"LIST", "READ"}:
                if self.agents is None:
                    return False
                return self.agents.is_known_grant_target_for_workbench(
                    connection,
                    DefinitionScope(
                        context.scope.tenant_id, context.scope.security_domain
                    ),
                    grant.action,
                    grant.exact_resource,
                )
            return any(
                validator.is_known_exact_target(context, grant, connection=connection)
                for validator in self.additional
            )
        except (
            AgentDefinitionRepositoryError,
            BusinessProblemError,
            DraftAssistanceError,
            EmployeeDefinitionError,
        ) as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def validate_continuation(
        self, claim: ContinuationClaim, *, connection: object | None = None
    ) -> bool:
        if self.problem_continuations is None:
            return False
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
        if self.problem_continuations is None:
            return False
        return self.problem_continuations.validate_offer(
            scope,
            members,
            canonical_resource_reference,
            owner_revision,
        )
