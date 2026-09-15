"""Domain-owned exact targets used by the Employee Workbench grant journey."""

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
    TrustedRequestContext,
)
from agent_console.digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity


class WorkbenchGrantTargetValidator:
    """Compose only the Employee and Agent target owners required by IMPL-310."""

    def __init__(
        self,
        unused_problem_owner: object,
        agents: AgentDefinitionRepository,
        employees: EmployeeDefinitionRepository,
    ) -> None:
        del unused_problem_owner
        self.agents = agents
        self.employees = employees

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
            if grant.owner == "EMPLOYEE":
                return self.employees.is_known_grant_target_for_workbench(
                    connection,
                    ScopeIdentity(
                        context.scope.tenant_id, context.scope.security_domain
                    ),
                    grant.action,
                    grant.exact_resource,
                )
            if grant.owner == "AGENT":
                return self.agents.is_known_grant_target_for_workbench(
                    connection,
                    DefinitionScope(
                        context.scope.tenant_id, context.scope.security_domain
                    ),
                    grant.action,
                    grant.exact_resource,
                )
            return False
        except (AgentDefinitionRepositoryError, EmployeeDefinitionError) as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def validate_continuation(
        self, claim: ContinuationClaim, *, connection: object | None = None
    ) -> bool:
        del claim, connection
        return False

    def validate_offer(
        self,
        scope: AuthorityScope,
        members: Sequence[ExactGrant],
        canonical_resource_reference: str,
        owner_revision: str,
    ) -> bool:
        del scope, members, canonical_resource_reference, owner_revision
        return False
