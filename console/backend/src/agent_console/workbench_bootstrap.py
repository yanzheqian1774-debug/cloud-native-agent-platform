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
    BusinessProblemCreateCoordinator,
)
from agent_console.digital_employee_application import DigitalEmployeeRepository
from agent_console.digital_employee_definition import EmployeeDefinitionRepository
from agent_console.draft_assistance import DraftAssistanceService
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    DraftAssistanceGrantTargetValidator,
    GrantAdministrationDraftAuthorization,
)
from agent_console.governed_execution_ownership import execution_database_fingerprint
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_api import install_planning_invocations
from agent_console.plan_suggestion_application import PlanningApplication
from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from agent_console.provider_usage import ProviderUsageGrantTargetValidator
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
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from agent_console.workbench_pagination import WorkbenchCursorCodec
from agent_console.workbench_plan_suggestion import (
    PlanningGrantTargetValidator,
    planning_operations,
)
from agent_console.workbench_workflow import workflow_operations
from agent_console.workflow_definition_service import WorkflowDefinitionService


@dataclass(slots=True)
class WorkbenchComposition:
    application: FastAPI
    foundation: AuthorityFoundation
    managed_closeables: tuple[object, ...] = ()

    def close(self) -> None:
        self.foundation.close()
        for value in reversed(self.managed_closeables):
            value.close()


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
    draft_assistance: DraftAssistanceService | None = None,
    model_grant_target_validator=None,
    planning_v2_enabled: bool = False,
    planning_invocations: PlanningInvocationDependencies | None = None,
    planning_unavailable_reason: str = "PLANNING_NOT_CONFIGURED",
    managed_closeables: tuple[object, ...] = (),
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
    if planning_invocations is not None and not planning_v2_enabled:
        raise AuthorityError("PLANNING_V2_DISABLED")
    planning = None
    if planning_v2_enabled:
        planning_repository = PostgresPlanningRepository(
            business_problems.problems.pool
        )
        planning_repository.migrate()
        planning = PlanningApplication(
            planning_repository, business_problems.problems, None
        )
    grant_targets = WorkbenchGrantTargetValidator(
        business_problems.problems,
        agent_definitions,
        employee_definitions,
        additional=(
            (
                DraftAssistanceGrantTargetValidator(
                    draft_assistance.repository,
                    model_target_validator=model_grant_target_validator,
                ),
            )
            if draft_assistance is not None
            else ()
        )
        + (
            (
                PlanningGrantTargetValidator(
                    planning_invocations.profile
                    if planning_invocations is not None
                    else None
                ),
            )
            if planning is not None
            else ()
        )
        + (
            ProviderUsageGrantTargetValidator(
                understanding=draft_assistance.repository
                if draft_assistance is not None
                else None,
                planning=PostgresPlanningInvocations(planning.repository)
                if planning_invocations is not None
                else None,
            ),
        ),
    )
    foundation = build_authority_foundation(
        runtime,
        BrowserSessionPolicy(
            login_nonce_lifetime=timedelta(minutes=5),
            idle_lifetime=timedelta(minutes=30),
            absolute_lifetime=timedelta(hours=8),
            csrf_lifetime=timedelta(minutes=10),
        ),
        target_validator=grant_targets,
    )
    try:
        authorizer = WorkbenchOwnerAuthorization(
            foundation.generation_controller,
            foundation.repository,
            foundation.grants.authorization,
        )
        if draft_assistance is not None:
            draft_assistance.authorization = GrantAdministrationDraftAuthorization(
                foundation.grants,
                authorizer,
                clock=foundation.grants.clock,
            )
        application = create_workbench_bff(
            foundation.sessions,
            authorizer,
            WorkbenchBffPolicy(allowed_host, allowed_origin),
            grant_administration=foundation.grants,
            operations=(
                *(
                    planning_operations(planning, employee_definitions)
                    if planning is not None
                    else ()
                ),
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
            **(
                {
                    "route_installers": (
                        (
                            (install_draft_assistance_routes(draft_assistance),)
                            if draft_assistance is not None
                            else ()
                        )
                        + (
                            (
                                install_planning_invocations(
                                    planning_invocations.bind(
                                        planning, foundation.grants.authorization
                                    )
                                    if planning_invocations is not None
                                    else None,
                                    planning_unavailable_reason,
                                ),
                            )
                            if planning_v2_enabled
                            else ()
                        )
                    )
                }
                if draft_assistance is not None or planning_v2_enabled
                else {}
            ),
        )
        return WorkbenchComposition(application, foundation, managed_closeables)
    except Exception:
        foundation.close()
        for value in reversed(managed_closeables):
            value.close()
        raise
