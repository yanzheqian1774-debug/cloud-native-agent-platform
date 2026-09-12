"""Fail-closed production composition for the trusted Workbench BFF."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI

from agent_console.agent_definition_repository import AgentDefinitionRepository
from agent_console.authority_configuration import AuthorityRuntimeConfiguration
from agent_console.authority_contracts import AuthorityError
from agent_console.authority_foundation import (
    AuthorityFoundation,
    build_authority_foundation,
)
from agent_console.browser_session_application import BrowserSessionPolicy
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_continuation import (
    BusinessProblemContinuationValidator,
    BusinessProblemCreateCoordinator,
)
from agent_console.digital_employee_application import DigitalEmployeeRepository
from agent_console.digital_employee_definition import EmployeeDefinitionRepository
from agent_console.governed_execution_ownership import execution_database_fingerprint
from agent_console.workbench_agent import agent_operations
from agent_console.workbench_bff import (
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_employee import (
    digital_employee_operations,
    employee_operations,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from agent_console.workbench_pagination import WorkbenchCursorCodec
from agent_console.workbench_workflow import workflow_operations
from agent_console.workflow_definition_service import WorkflowDefinitionService


@dataclass(slots=True)
class WorkbenchComposition:
    application: FastAPI
    foundation: AuthorityFoundation

    def close(self) -> None:
        self.foundation.close()


def build_workbench_composition(
    *,
    runtime_configuration_path: Path,
    allowed_host: str,
    allowed_origin: str,
    owner_database_url: str,
    agent_database_url: str,
    business_problems: BusinessProblemApplication,
    agent_definitions: AgentDefinitionRepository,
    employee_definitions: EmployeeDefinitionRepository,
    digital_employees: DigitalEmployeeRepository,
    workflow_database_url: str = "",
    workflows: WorkflowDefinitionService | None = None,
) -> WorkbenchComposition:
    """Build only after every external authority and owner dependency is present."""
    if not runtime_configuration_path.is_absolute():
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
    try:
        document = json.loads(runtime_configuration_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityError("AUTHORITY_CONFIGURATION_UNAVAILABLE") from exc
    if not isinstance(document, dict):
        raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
    runtime = AuthorityRuntimeConfiguration.from_mapping(document)
    authority_database = execution_database_fingerprint(runtime.database_url)
    if authority_database != execution_database_fingerprint(owner_database_url):
        raise AuthorityError("OWNER_TRANSACTION_UNAVAILABLE")
    if authority_database != execution_database_fingerprint(agent_database_url):
        raise AuthorityError("OWNER_TRANSACTION_UNAVAILABLE")
    workflow_enabled = bool(workflow_database_url or workflows)
    if workflow_enabled and not (workflow_database_url and workflows):
        raise AuthorityError("WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE")
    if workflow_enabled and authority_database != execution_database_fingerprint(
        workflow_database_url
    ):
        raise AuthorityError("OWNER_TRANSACTION_UNAVAILABLE")
    problem_continuations = BusinessProblemContinuationValidator(
        business_problems.problems
    )
    foundation = build_authority_foundation(
        runtime,
        BrowserSessionPolicy(
            login_nonce_lifetime=timedelta(minutes=5),
            idle_lifetime=timedelta(minutes=30),
            absolute_lifetime=timedelta(hours=8),
            csrf_lifetime=timedelta(minutes=10),
        ),
        target_validator=problem_continuations,
    )
    try:
        authorizer = WorkbenchOwnerAuthorization(
            foundation.generation_controller,
            foundation.repository,
            foundation.grants.authorization,
        )
        application = create_workbench_bff(
            foundation.sessions,
            authorizer,
            WorkbenchBffPolicy(allowed_host, allowed_origin),
            grant_administration=foundation.grants,
            operations=(
                *business_problem_operations(
                    business_problems,
                    BusinessProblemCreateCoordinator(
                        foundation.grants,
                        clock=foundation.grants.clock,
                        identity_factory=foundation.grants.identity_factory,
                    ),
                ),
                *agent_operations(
                    agent_definitions,
                    WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                ),
                *employee_operations(
                    employee_definitions,
                    WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                ),
                *digital_employee_operations(digital_employees),
                *(workflow_operations(workflows) if workflows is not None else ()),
            ),
        )
        return WorkbenchComposition(application, foundation)
    except Exception:
        foundation.close()
        raise
