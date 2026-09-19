"""Real owner resolution stays read-only for exact, denied and mismatched refs."""

import os
from types import SimpleNamespace

from agent_console.authority_contracts import AuthorityError
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.plan_suggestion_domain import PlanSemantics, ProposalRevision
from agent_console.plan_suggestion_resources import (
    EmployeePlanningReader,
    PlanningResourceResolver,
)
from psycopg import sql
from s5_v023_arch_323_fixture import MIGRATIONS, SCOPE, seed
from test_plan_suggestion_v2 import repository  # noqa: F401


def test_real_employee_reference_gaps_denial_and_no_writes(repository):  # noqa: F811
    authority = PostgresAuthorityRepository(
        os.environ["PLANNING323_TEST_DATABASE_URL"],
        migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql",
    )
    authority.migrate()
    try:
        case = seed(os.environ["PLANNING323_TEST_DATABASE_URL"], authority)
        proposal = ProposalRevision(
            proposal_id="323-owner-test",
            revision=1,
            predecessor_digest=None,
            invocation_id="323-owner-invocation",
            semantics=PlanSemantics.model_validate(case.semantics),
        )
        principal = SimpleNamespace(principal_id="human:323")

        class Authorization:
            deny = False

            def require(self, *args):
                if self.deny:
                    raise AuthorityError("AUTHORIZATION_NOT_FOUND")

        authorization = Authorization()
        reader = EmployeePlanningReader(
            PostgresEmployeeDefinitionRepository(authority),
            authorization,
            lambda _: SCOPE,
        )
        resolver = PlanningResourceResolver({"EMPLOYEE": reader})

        def counts():
            with repository.pool.connection() as conn:
                tables = conn.execute(
                    "SELECT schemaname,tablename FROM pg_tables WHERE schemaname "
                    "NOT IN ('pg_catalog','information_schema')"
                ).fetchall()
                return {
                    (schema, table): conn.execute(
                        sql.SQL("SELECT count(*) FROM {}.{}").format(
                            sql.Identifier(schema), sql.Identifier(table)
                        )
                    ).fetchone()[0]
                    for schema, table in tables
                }

        before = counts()
        result = resolver.resolve(principal, proposal)
        assert result.observations[0].status == "MATCHED"
        assert len(result.pending_required(proposal)) == 6
        assert result.observations[-1].status == "NOT_REQUIRED"
        authorization.deny = True
        assert (
            resolver.resolve(principal, proposal).observations[0].status == "UNREADABLE"
        )
        authorization.deny = False
        invalid = proposal.model_dump(mode="json")
        invalid["semantics"]["requirements"][0]["selected"]["digest"] = "0" * 64
        assert (
            resolver.resolve(principal, ProposalRevision.model_validate(invalid))
            .observations[0]
            .status
            == "UNAVAILABLE"
        )
        assert counts() == before
    finally:
        authority.close()
