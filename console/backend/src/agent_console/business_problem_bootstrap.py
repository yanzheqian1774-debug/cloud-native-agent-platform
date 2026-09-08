"""Production-only durable Product assembly on the existing execution database."""

from pathlib import Path

from .business_plan_postgres import PostgresProblemPlanUnitOfWork
from .business_problem_application import BusinessProblemApplication
from .business_problem_postgres import PostgresBusinessProblemRepository
from .workflow_control_postgres import PostgresWorkflowControlRepository
from .workflow_definition_postgres import PostgresWorkflowDefinitionRepository


def build_business_problem_application(database_url, employees):
    migrations = Path(__file__).parents[2] / "migrations"
    opened = []
    try:
        control = PostgresWorkflowControlRepository(
            database_url,
            migration_path=migrations
            / "0011_workflow_control_plan_evidence_outcome.sql",
        )
        opened.append(control)
        control.migrate()
        problems = PostgresBusinessProblemRepository(
            database_url,
            migration_path=migrations / "0013_business_problem_authority.sql",
        )
        opened.append(problems)
        problems.migrate()
        workflows = PostgresWorkflowDefinitionRepository(
            database_url,
            migration_path=migrations / "0007_workflow_runtime_profiles.sql",
        )
        opened.append(workflows)
        workflows.compatibility()
        return BusinessProblemApplication(
            PostgresProblemPlanUnitOfWork(problems, control),
            None,
            workflows,
            employees.employee_definitions,
            employees.repository,
        )
    except Exception:
        for repository in opened:
            repository.pool.close()
        raise
