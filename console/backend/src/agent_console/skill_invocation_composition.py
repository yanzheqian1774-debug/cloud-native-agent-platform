"""Normal PostgreSQL composition root for governed Attempt Skill invocation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .resource_use_postgres import PostgresResourceUseRepository
from .skill_executor import SkillExecutorRegistry
from .skill_invocation_application import (
    GovernedAttemptSkillInvocationService,
    SkillInvocationAuthorization,
    SkillSideEffectPolicyAuthority,
)
from .skill_invocation_postgres import PostgresSkillInvocationRepository


@dataclass(slots=True)
class SkillInvocationComposition:
    """Owns application dependencies and their connection-pool lifetime."""

    application: GovernedAttemptSkillInvocationService
    invocation_repository: PostgresSkillInvocationRepository
    resource_use_repository: PostgresResourceUseRepository

    def close(self) -> None:
        self.invocation_repository.close()
        self.resource_use_repository.close()


def compose_governed_skill_invocation(
    database_url: str,
    migrations: Path,
    authorization: SkillInvocationAuthorization | None,
    policy_authority: SkillSideEffectPolicyAuthority,
    executors: SkillExecutorRegistry,
) -> SkillInvocationComposition:
    """Build the internal application entry and restart-recovery dependencies."""
    resource_use = PostgresResourceUseRepository(
        database_url,
        migration_path=migrations / "0015_resource_use_measurement.sql",
    )
    resource_use.migrate()
    invocation = PostgresSkillInvocationRepository(
        database_url,
        migration_path=migrations / "0016_skill_invocation.sql",
        resource_use_repository=resource_use,
    )
    invocation.migrate()
    return SkillInvocationComposition(
        GovernedAttemptSkillInvocationService(
            invocation, authorization, policy_authority, executors
        ),
        invocation,
        resource_use,
    )
