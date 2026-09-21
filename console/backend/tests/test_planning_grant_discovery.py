"""Canonical owner discovery for the permissions already required by planning."""

import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace as NS

from agent_console.authority_contracts import AuthorityScope, ExactGrant
from agent_console.business_problem_domain import BusinessProblemRevision
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.execution_domain import ScopeIdentity
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_plan_suggestion import PlanningGrantTargetValidator
from test_model_governance_postgres import records
from test_plan_suggestion_v2 import repository as repository


def test_canonical_discovery_rejects_forged_scope_and_digest(repository):
    migrations = Path(__file__).parents[1] / "migrations"
    url = os.environ["PLANNING323_TEST_DATABASE_URL"]
    problems = PostgresBusinessProblemRepository(
        url, migration_path=migrations / "0013_business_problem_authority.sql"
    )
    models = PostgresModelGovernanceRepository(
        url, migration_path=migrations / "0019_model_governance.sql"
    )
    try:
        problems.migrate()
        models.migrate()
        scope, definition, provider, endpoint, connection, model = records("323")
        models.create(definition)
        models.add_provider_revision(provider)
        models.add_endpoint_revision(endpoint)
        models.add_connection_profile_revision(connection)
        models.add_revision(model)
        revision = BusinessProblemRevision(
            ScopeIdentity(scope.namespace, scope.security_domain),
            "problem-323",
            "problem-323:1",
            1,
            None,
            "Synthetic",
            "Read-only procurement",
            "team:test",
            "human:test",
            datetime.now(UTC),
        )
        problems.create_problem(
            revision,
            idempotency_key="test-create",
            payload_digest=revision.digest,
            authorized=True,
        )
        binding = NS(
            resource_id=model.model_id,
            revision_id=model.revision_id,
            digest=model.digest,
        )
        validator = WorkbenchGrantTargetValidator(
            problems, additional=(PlanningGrantTargetValidator(NS(model=binding)),)
        )
        context = NS(scope=AuthorityScope(scope.namespace, scope.security_domain))
        foreign = NS(scope=AuthorityScope("foreign", scope.security_domain))
        targets = [
            ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-323"),
            ExactGrant("BUSINESS_PROBLEM", "REVISE", "business-problem:problem-323"),
            ExactGrant(
                "BUSINESS_PROBLEM", "TRANSITION", "business-problem:problem-323"
            ),
            ExactGrant("PLAN", "PREPARE", "plan:prepare:problem-323"),
            ExactGrant("PLAN", "READ", "plan:prepared:problem-323"),
            ExactGrant(
                "MODEL_GOVERNANCE",
                "INVOKE_MODEL",
                f"model:invocation:plan-suggestion:{model.model_id}:{model.revision_id}:{model.digest}",
            ),
        ]
        with problems.pool.connection() as current:
            for target in targets:
                assert validator.is_known_exact_target(
                    context, target, connection=current
                )
                assert not validator.is_known_exact_target(
                    foreign, target, connection=current
                )
                assert not validator.is_known_exact_target(
                    context,
                    ExactGrant(
                        target.owner, target.action, target.exact_resource + "-forged"
                    ),
                    connection=current,
                )
            # Discovery only identifies owner-backed targets; it grants no action.
            assert not validator.is_known_exact_target(
                context,
                ExactGrant("PLAN", "APPROVE", "plan:prepare:problem-323"),
                connection=current,
            )
            assert not validator.is_known_exact_target(
                context,
                ExactGrant(
                    "MODEL_GOVERNANCE",
                    "INVOKE_MODEL",
                    targets[-1].exact_resource.replace(
                        "plan-suggestion", "other-purpose"
                    ),
                ),
                connection=current,
            )
    finally:
        problems.pool.close()
        models.close()
