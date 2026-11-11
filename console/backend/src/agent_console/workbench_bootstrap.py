"""Fail-closed production composition for the trusted Workbench BFF."""

from __future__ import annotations

import json
import os
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
from agent_console.workbench_business_capability import capability_operations
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_employee import (
    digital_employee_operations,
    employee_operations,
)
from agent_console.workbench_employee_relations import (
    operations as employee_relation_operations,
)
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from agent_console.workbench_pagination import WorkbenchCursorCodec
from agent_console.workbench_plan_suggestion import (
    PlanningGrantTargetValidator,
    planning_operations,
)
from agent_console.workbench_team import team_operations
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
    model_repository=None,
    planning_v2_enabled: bool = False,
    prepared_execution_coordinator=None,
    prepared_resource_services=None,
    sales_v2_candidate: bool = False,
    sales_supplement_candidate: bool = False,
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
    if (
        model_repository is not None
        and authority_database
        != execution_database_fingerprint(model_repository.pool.conninfo)
    ):
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
            planning_repository,
            business_problems.problems,
            None,
            sales_supplement_candidate=sales_supplement_candidate,
        )
    from .workbench_prepared_execution import (
        PreparedExecutionGrantTargets,
        prepared_execution_operations,
    )

    if prepared_execution_coordinator is not None and not planning_v2_enabled:
        raise AuthorityError("PREPARED_EXECUTION_REQUIRES_PLANNING")
    if (
        prepared_execution_coordinator is not None
        and authority_database
        != execution_database_fingerprint(
            prepared_execution_coordinator.repository.pool.conninfo
        )
    ):
        raise AuthorityError("OWNER_TRANSACTION_UNAVAILABLE")
    if prepared_execution_coordinator is not None:
        from .prepared_execution_schema import migrate as migrate_prepared
        from .prepared_result_review import migrate as migrate_review
        from .resource_use_postgres import PostgresResourceUseRepository

        resource_use = PostgresResourceUseRepository(
            owner_database_url,
            migration_path=Path(__file__).parents[2]
            / "migrations/0015_resource_use_measurement.sql",
        )
        try:
            resource_use.migrate()
        finally:
            resource_use.close()

        with (
            business_problems.problems.pool.connection() as connection,
            connection.transaction(),
        ):
            migrate_prepared(connection)
            migrate_review(connection)
    from .workbench_prepared_resources import (
        PreparedResourceTargets,
        prepared_resource_operations,
    )

    if prepared_resource_services:
        prepared_resource_services = dict(prepared_resource_services)
        if "skill" in prepared_resource_services:
            prepared_resource_services.setdefault(
                "mcp", prepared_resource_services["skill"]
            )
        if prepared_execution_coordinator is None:
            raise AuthorityError("PREPARED_EXECUTION_DISABLED")
        for service in prepared_resource_services.values():
            if (
                execution_database_fingerprint(service.repository.pool.conninfo)
                != authority_database
            ):
                raise AuthorityError("OWNER_TRANSACTION_UNAVAILABLE")
    ontology_enabled = os.environ.get("BUSINESS_ONTOLOGY_ENABLED") == "1"
    ontology_operations = ()
    ontology_targets = ()
    if ontology_enabled:
        from .ontology_api import operations as build_ontology_operations
        from .ontology_authorization import OntologyPlanTargets, OntologyTargets
        from .ontology_postgres import migrate as migrate_ontology

        with (
            business_problems.problems.pool.connection() as connection,
            connection.transaction(),
        ):
            migrate_ontology(connection)
            if prepared_execution_coordinator is not None:
                from .ontology_execution import migrate as migrate_semantic_binding

                migrate_semantic_binding(connection)
        ontology_operations = build_ontology_operations(planning)
        ontology_targets = (
            OntologyPlanTargets(
                json.loads(os.environ.get("BUSINESS_ONTOLOGY_PLAN_TARGETS", "[]"))
            ),
            OntologyTargets(
                json.loads(os.environ.get("BUSINESS_ONTOLOGY_CREATION_TARGETS", "[]"))
            ),
        )
    # Explicit opt-in: deployment applies the migration separately; startup only
    # verifies it. The existing owner pool and authorization transaction are reused.
    team_repository = None
    team_targets = ()
    if os.environ.get("TEAM_DEFINITIONS_ENABLED") == "true":
        from .team_definition_postgres import PostgresTeamDefinitionRepository
        from .workbench_team import TeamTargets

        team_repository = PostgresTeamDefinitionRepository(
            business_problems.problems.pool
        )
        team_repository.compatibility(
            Path(__file__).parents[2] / "migrations/0051_team_definition.sql"
        )
        team_targets = (TeamTargets(),)

    capability_repository = None
    capability_targets = ()
    if os.environ.get("BUSINESS_CAPABILITIES_ENABLED") == "true":
        from .business_capability_postgres import PostgresBusinessCapabilityRepository
        from .workbench_business_capability import CapabilityTargets

        capability_repository = PostgresBusinessCapabilityRepository(
            business_problems.problems.pool
        )
        capability_repository.compatibility(
            Path(__file__).parents[2] / "migrations/0052_business_capability.sql"
        )
        from .business_capability_publication_postgres import (
            CapabilityPublicationRepository,
        )

        CapabilityPublicationRepository(business_problems.problems.pool).compatibility(
            Path(__file__).parents[2]
            / "migrations/0053_business_capability_publication.sql"
        )
        capability_targets = (CapabilityTargets(),)

    from .resource_definition_management import DefinitionTargets
    from .resource_management import ManagementTargets
    from .workbench_model_directory import ModelReadTargets

    grant_targets = WorkbenchGrantTargetValidator(
        business_problems.problems,
        agent_definitions,
        employee_definitions,
        additional=(ManagementTargets(), DefinitionTargets())
        + team_targets
        + capability_targets
        + (
            (ModelReadTargets(model_repository),)
            if model_repository is not None
            else ()
        )
        + ontology_targets
        + ((PreparedResourceTargets(),) if prepared_resource_services else ())
        + (
            (PreparedExecutionGrantTargets(),)
            if prepared_execution_coordinator is not None
            else ()
        )
        + (
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
        delegation_routes = ()
        task_binding = None
        delegation = planning_admission = None
        if (
            draft_assistance is not None
            and planning_invocations is not None
            and hasattr(draft_assistance.transport, "configuration")
            and hasattr(planning_invocations.provider, "configuration")
        ):
            from .task_delegation import TaskDelegationService, configured_limits
            from .task_delegation_api import install_task_delegation_routes

            configurations = {
                "understanding": configured_limits(
                    draft_assistance.profile,
                    draft_assistance.transport.configuration,
                    draft_assistance.budget,
                ),
                "planning": configured_limits(
                    planning_invocations.provider.transport_profile,
                    planning_invocations.provider.configuration,
                    planning_invocations.budget.owner,
                    planning=True,
                ),
            }
            draft_assistance.budget.delegation_configuration = configurations[
                "understanding"
            ]
            planning_invocations.budget.owner.delegation_configuration = configurations[
                "planning"
            ]
            delegation = TaskDelegationService(
                foundation.grants,
                configurations,
                timeout_source=(
                    planning_invocations.provider.transport_profile,
                    planning_invocations.provider.configuration,
                    planning_invocations.budget.owner,
                ),
            )
            delegation.migrate()
            from dataclasses import replace

            from .task_development import prepare_planning_admission

            planning_invocations = replace(
                planning_invocations,
                admission_factory=lambda context: (
                    lambda request: prepare_planning_admission(
                        delegation, context, request
                    )
                ),
            )
            from .task_delegation import record_created_object

            task_binding = record_created_object
            delegation_routes = (install_task_delegation_routes(delegation),)
            if os.environ.get("CONTEXT_CALL_ADMISSION_ENABLED") == "true":
                from .context_call_admission import ContextCallAdmission
                from .context_call_admission_api import install_context_call_admission

                admission = ContextCallAdmission(
                    delegation, configurations["understanding"]
                )
                admission.migrate()
                from .planning_call_admission import (
                    BoundPlanningAdmission,
                    PlanningCallAdmission,
                )

                planning_admission = PlanningCallAdmission(
                    delegation, configurations["planning"]
                )
                planning_admission.migrate()
                admission.planning = planning_admission
                planning_invocations = replace(
                    planning_invocations,
                    exact_admission_factory=lambda context: BoundPlanningAdmission(
                        planning_admission, context
                    ),
                )
                from .development_draft_admission import bind_created_object as bind_d12

                task_binding = bind_d12(admission, task_binding)
                draft_assistance.authorization.context_admission = admission
                draft_assistance.budget.context_admission = admission
                delegation_routes += (install_context_call_admission(admission),)

        roots_path = os.environ.get("BOUNDED_TASK_AUTHORIZATION_ROOTS")
        if roots_path:
            from .bounded_task_bootstrap import install_task_authorization
            from .task_delegation import TaskDelegationService

            if delegation is None:
                delegation = TaskDelegationService(foundation.grants, {})
                delegation.migrate()
            delegation_routes += (
                install_task_authorization(
                    roots_path, delegation, planning_admission, planning_invocations
                ),
            )

        if delegation is not None and task_binding is not None:
            creation = getattr(
                delegation.repository, "initial_case_creation_bindings", ()
            )
            if creation:
                from .initial_case_creation import bind_created_object

                task_binding = bind_created_object(
                    task_binding,
                    creation,
                    sales_supplement_enabled=sales_supplement_candidate
                    and sales_v2_candidate,
                )

        resource_automation = None
        resource_automation_routes = ()
        automation_path = os.environ.get("RESOURCE_PREPARATION_POLICY")
        if automation_path:
            if planning is None or not prepared_resource_services:
                raise AuthorityError("RESOURCE_POLICY_DEPENDENCIES_REQUIRED")
            from .resource_automation import (
                ResourceAutomation,
            )
            from .resource_automation import (
                migrate as migrate_automation,
            )
            from .resource_automation import (
                operations as resource_automation_operations,
            )
            from .resource_automation_policy import AutomationPolicy

            policy = AutomationPolicy.load(automation_path)
            resource_automation = ResourceAutomation(
                policy,
                foundation.grants,
                planning,
                prepared_resource_services,
                employee_definitions,
                sales_v2_candidate=sales_v2_candidate,
            )
            with foundation.repository.connection_scope() as c:
                migrate_automation(c)
            resource_automation_routes = resource_automation_operations(
                resource_automation
            )

        continuation_routes = ()
        continuation_path = os.environ.get("READONLY_CONTINUATION_POLICY")
        if continuation_path:
            if resource_automation is None or prepared_execution_coordinator is None:
                raise AuthorityError("READONLY_CONTINUATION_DEPENDENCIES_REQUIRED")
            from .readonly_continuation import ReadonlyContinuation
            from .readonly_continuation import operations as continuation_operations
            from .readonly_continuation_policy import ReadonlyContinuationPolicy

            continuation = ReadonlyContinuation(
                resource_automation,
                ReadonlyContinuationPolicy.load(continuation_path),
                prepared_execution_coordinator,
            )
            resource_automation.continuation = continuation
            continuation_routes = continuation_operations(continuation)

        current_work_routes = ()
        if os.environ.get("CURRENT_WORK_DIRECTORY_ENABLED") == "true":
            if prepared_execution_coordinator is None:
                raise AuthorityError("CURRENT_WORK_DIRECTORY_DEPENDENCIES_REQUIRED")
            from .workbench_current_work import operations as current_work_operations

            current_work_routes = current_work_operations(
                WorkbenchCursorCodec(foundation.continuation_owner.signing_key)
            )

        directory_routes = ()
        directory_installers = ()
        if prepared_resource_services:
            from .workbench_resource_directory import install_directory
            from .workbench_resource_directory import operations as directory_operations

            directory_installers = (
                install_directory(
                    prepared_resource_services,
                    WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                    authorizer,
                    workflows,
                ),
            )
            directory_routes = directory_operations(
                prepared_resource_services,
                WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                workflows,
            )

        definition_path = os.environ.get("RESOURCE_DEFINITION_MANAGEMENT_POLICY")
        if definition_path:
            if not prepared_resource_services or not all(
                k in prepared_resource_services for k in ("agent", "knowledge")
            ):
                raise AuthorityError("DEFINITION_MANAGEMENT_DEPENDENCIES_REQUIRED")
            from .resource_definition_management import (
                DefinitionManagement,
                DefinitionPolicy,
                install_definitions,
            )

            definition_policy = DefinitionPolicy.model_validate_json(
                Path(definition_path).read_text()
            )
            directory_installers += (
                install_definitions(
                    DefinitionManagement(
                        prepared_resource_services, definition_policy, foundation.grants
                    ),
                    authorizer,
                ),
            )

        management_path = os.environ.get("RESOURCE_MANAGEMENT_POLICY")
        if management_path and prepared_resource_services:
            from .resource_management import (
                ManagementPolicy,
                ResourceManagement,
                install_management,
            )

            management_policy = ManagementPolicy.model_validate_json(
                Path(management_path).read_text()
            )
            directory_installers += (
                install_management(
                    ResourceManagement(
                        prepared_resource_services,
                        management_policy,
                        foundation.grants,
                        sales_v2_candidate=sales_v2_candidate,
                        prepared_handoff_enabled=sales_supplement_candidate
                        and sales_v2_candidate,
                    ),
                    authorizer,
                ),
            )

        source_review_routes = ()
        if os.environ.get("EXECUTION_SOURCE_REVIEW_ENABLED") == "true":
            from .execution_source_review import ReviewPolicy
            from .execution_source_review import operations as source_review_operations

            if not prepared_resource_services or prepared_execution_coordinator is None:
                raise AuthorityError("SOURCE_REVIEW_DEPENDENCIES_REQUIRED")
            source_review_routes = source_review_operations(
                prepared_resource_services,
                prepared_execution_coordinator,
                ReviewPolicy.load(os.environ.get("EXECUTION_SOURCE_REVIEW_POLICY")),
                sales_v2_candidate=sales_v2_candidate,
            )

        runtime_trace_routes = ()
        if os.environ.get("EMPLOYEE_EXECUTION_TRACE_ENABLED") == "true":
            from .employee_execution_trace import ObservationConfiguration
            from .employee_execution_trace import operations as trace_operations

            runtime_trace_routes = trace_operations(
                digital_employees,
                prepared_execution_coordinator,
                definitions=employee_definitions,
                configuration=ObservationConfiguration.load(
                    os.environ["EXECUTION_RUNTIME_OBSERVATION_CONFIGURATION"]
                ),
                sales_v2_candidate=sales_v2_candidate,
            )

        from .sales_supplement_composition import operations as supplement_operations

        sales_supplement_routes = supplement_operations(
            planning,
            prepared_resource_services,
            enabled=sales_supplement_candidate,
            sales_v2_candidate=sales_v2_candidate,
        )

        from .workbench_model_directory import operations as model_directory_operations

        application = create_workbench_bff(
            foundation.sessions,
            authorizer,
            WorkbenchBffPolicy(
                allowed_host,
                allowed_origin,
                route_body_limits=tuple(
                    (
                        "/api/workbench/v1/resource-management/"
                        + kind
                        + "/import-preview",
                        10 * 1024 * 1024,
                    )
                    for kind in ("skill", "mcp")
                )
                if management_path
                else (),
            ),
            **(
                {"conversation_database_url": owner_database_url}
                if os.environ.get("PRIVATE_CONVERSATIONS_ENABLED") == "true"
                else {}
            ),
            grant_administration=foundation.grants,
            operations=(
                *(
                    model_directory_operations(
                        model_repository,
                        WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                    )
                    if model_repository is not None
                    else ()
                ),
                *sales_supplement_routes,
                *source_review_routes,
                *runtime_trace_routes,
                *resource_automation_routes,
                *continuation_routes,
                *directory_routes,
                *current_work_routes,
                *ontology_operations,
                *(
                    prepared_resource_operations(
                        prepared_resource_services,
                        skill_successor_enabled=sales_supplement_candidate
                        and sales_v2_candidate,
                    )
                    if prepared_resource_services
                    else ()
                ),
                *(
                    prepared_execution_operations(
                        prepared_execution_coordinator,
                        sales_v2_candidate=sales_v2_candidate,
                    )
                    if prepared_execution_coordinator is not None
                    else ()
                ),
                *(
                    planning_operations(
                        planning,
                        employee_definitions,
                        resource_automation=resource_automation,
                    )
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
                    task_binding=task_binding,
                ),
                *agent_operations(
                    agent_definitions,
                    WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                ),
                *employee_operations(
                    employee_definitions,
                    WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                    prepared_resource_reads=prepared_resource_services is not None,
                ),
                *(
                    team_operations(
                        team_repository,
                        employee_definitions,
                        WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                    )
                    if team_repository is not None
                    else ()
                ),
                *(
                    capability_operations(
                        capability_repository,
                        employee_definitions,
                        prepared_resource_services or {},
                        WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                        workflows,
                    )
                    if capability_repository is not None
                    else ()
                ),
                *digital_employee_operations(digital_employees),
                *employee_relation_operations(
                    employee_definitions,
                    digital_employees,
                    WorkbenchCursorCodec(foundation.continuation_owner.signing_key),
                ),
                *(workflow_operations(workflows) if workflows is not None else ()),
            ),
            **(
                {
                    "route_installers": (
                        directory_installers
                        + delegation_routes
                        + (
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
                if directory_installers
                or draft_assistance is not None
                or planning_v2_enabled
                else {}
            ),
        )
        if resource_automation is not None:
            resource_automation.capability_contract_reader = getattr(
                application.state, "capability_execution_contract_reader", None
            )
        if (
            planning_admission is not None
            and capability_repository is not None
            and resource_automation is not None
        ):
            from .capability_planning_admission import source_reader

            planning_admission.capability_source_reader = source_reader(
                resource_automation,
                application.state.capability_execution_contract_reader,
                authorizer,
            )
        if continuation_path:
            continuation.capability_contract_reader = getattr(
                application.state, "capability_execution_contract_reader", None
            )
        return WorkbenchComposition(application, foundation, managed_closeables)
    except Exception:
        foundation.close()
        for value in reversed(managed_closeables):
            value.close()
        raise
