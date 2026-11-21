"""Concrete standalone owner factory; never imports app or starts its API."""

import hashlib
import json
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from .fixed_work_bound_composition import (
    compose_bound_cycle_service,
    inspect_bound_cycle,
)
from .fixed_work_cycle_configuration import CycleConfiguration
from .fixed_work_service_admission import require


@dataclass
class CycleProcess:
    configuration: CycleConfiguration
    loop: object
    cleanup: ExitStack

    def close(self):
        self.cleanup.close()

    def check(self):
        self.configuration.verify()
        result = inspect_bound_cycle(self.loop)
        automation = self.loop.host.continuation.readonly_owner.automation
        context = self.loop.current_context()
        policy = self.loop.host.runtime.registry._policy()
        service = self.loop.host.runtime.service
        from datetime import UTC, datetime

        from .model_binding_resolution import (
            ExactModelBinding,
            ExactModelUse,
            ModelConsumptionScope,
            ModelUseAction,
            ModelUseSubject,
            resolve_authorized_model_binding,
        )
        from .workbench_business_problem import OwnerPrincipal

        principal = OwnerPrincipal(
            context.principal_id, policy.tenantId, policy.securityDomain
        )
        with service.application.repository.pool.connection() as c:
            service.application.validate_target(principal, policy.target, c)
        model = policy.model
        resolve_authorized_model_binding(
            ModelConsumptionScope(policy.tenantId, policy.securityDomain),
            ModelUseSubject(context.principal_id),
            ExactModelUse(
                ExactModelBinding(model.resource_id, model.revision_id, model.digest),
                ModelUseAction.INVOKE_MODEL,
                policy.model_target,
            ),
            authorizer=service.model_authorizer,
            resolver=service.model_resolver,
            evaluation_time=lambda: datetime.now(UTC),
        )
        # The independent issuer's current authority is checked without requesting
        # or deciding any grants. Missing runtime/START remains an owner gate.
        automation.authenticate(context)
        with automation.grants.repository.connection_scope() as c:
            now = automation.grants.clock()
            work = automation.work(context, policy.target.problem, now, connection=c)
            from .fixed_work_sources_postgres import read

            bound = read(
                c,
                (policy.tenantId, policy.securityDomain),
                "bindings",
                policy.work.resource_id,
                policy.work.revision_id,
            )
            from .plan_suggestion_domain import ExactReference

            require(
                ExactReference.model_validate(bound["record"]["inputSource"]["source"])
                == policy.resourceSnapshot,
                "FIXED_CYCLE_SINGLE_SOURCE_SNAPSHOT_REQUIRED",
            )
            source_digest = bound["record"]["inputSource"]["sourceContentDigest"]
            require(
                source_digest in work.sourceContentDigests,
                "FIXED_CYCLE_RESOURCE_SOURCE_DENIED",
            )
            self.loop.host.continuation.readonly_owner.policy.work(
                context, policy.target.problem, source_digest, now
            )
        return {
            **result,
            "resourceIssuer": "CURRENT_AUTHORITY_OBSERVED",
            "modelCalled": False,
            "grantWritten": False,
            "nativeStarted": False,
        }

    def run(self, stop, observe):
        self.check()
        original_step = self.loop.step

        def guarded_step():
            self.configuration.verify()
            return original_step()

        self.loop.step = guarded_step
        try:
            self.loop.run(stop, observe)
        finally:
            self.loop.step = original_step


def _schema(pool, migrations, table, versions):
    # Fixed code-owned table/path mapping, not user SQL. No migration execution.
    with pool.connection() as c:
        for version, filename in versions:
            row = c.execute(
                f"SELECT checksum FROM {table} WHERE version=%s", (version,)
            ).fetchone()
            require(
                row
                and row["checksum"]
                == hashlib.sha256((migrations / filename).read_bytes()).hexdigest(),
                "FIXED_CYCLE_SCHEMA_NOT_PREPARED",
            )


def _existing_schemas(pool, migrations):
    from .fixed_work_authoring_postgres import compatibility as authoring
    from .fixed_work_service_admission import compatible as service
    from .fixed_work_sources_postgres import compatible as source
    from .fixed_work_trigger_postgres import compatible as trigger

    _schema(
        pool,
        migrations,
        "business_problem_authority.schema_migrations",
        ((13, "0013_business_problem_authority.sql"),),
    )
    _schema(
        pool,
        migrations,
        "execution_authority.resource_policy_migrations",
        ((44, "0044_resource_automation.sql"),),
    )
    with pool.connection() as c:
        for check in (authoring, source, trigger, service):
            check(c)


def _planning_factory(runtime, application, authorization, policy_path):
    """Fresh dedicated service; never strip another service's exact_admission."""
    from .model_governance_authorization import ModelUseAuthorizationAdapter
    from .plan_invocation_postgres import PostgresPlanningInvocations
    from .plan_model_use_postgres import PostgresPlanModelUseOwner
    from .plan_suggestion_application import PlanningApplication
    from .plan_suggestion_authorization import PlanningCurrentAuthority
    from .plan_suggestion_service import PlanningSuggestionService

    d = runtime.dependencies
    require(
        d.exact_admission_factory is None and d.admission_factory is None,
        "FIXED_CYCLE_DEDICATED_PLANNING_REQUIRED",
    )

    def create(context):
        def source_snapshot(principal, target):
            from .fixed_work_service_admission import ServicePlanningRegistry
            from .fixed_work_service_policy import ServicePlanningPolicy
            from .fixed_work_sources_postgres import read
            from .plan_suggestion_domain import ExactReference

            registry = ServicePlanningRegistry(
                application.repository,
                authorization,
                lambda: ServicePlanningPolicy.load(policy_path),
            )
            policy = registry._policy()
            require(
                (principal.principal_id, principal.tenant_id, principal.security_domain)
                == (
                    context.principal_id,
                    context.scope.tenant_id,
                    context.scope.security_domain,
                )
                and target == policy.target,
                "FIXED_CYCLE_SOURCE_TARGET_CHANGED",
            )
            with application.repository.pool.connection() as c, c.transaction():
                registry._check(c, context, policy)
                bound = read(
                    c,
                    (policy.tenantId, policy.securityDomain),
                    "bindings",
                    policy.work.resource_id,
                    policy.work.revision_id,
                )
                selected = ExactReference.model_validate(
                    bound["record"]["inputSource"]["source"]
                )
                # This first deployable factory supports one published Knowledge
                # source as the original planning/execution snapshot. It does not
                # invent a catalogue snapshot or substitute another source.
                require(
                    selected == policy.resourceSnapshot,
                    "FIXED_CYCLE_SINGLE_SOURCE_SNAPSHOT_REQUIRED",
                )
                return selected

        return PlanningSuggestionService(
            PlanningApplication(
                application.repository,
                application.problems,
                PlanningCurrentAuthority(context, authorization),
            ),
            PostgresPlanningInvocations(application.repository),
            d.profile,
            model_authorizer=ModelUseAuthorizationAdapter(context, authorization),
            model_resolver=d.model_resolver,
            budget=d.budget,
            quote=d.quote,
            provider=d.provider,
            model_use_owner=PostgresPlanModelUseOwner(application.repository),
            commitment_key=d.commitment_key,
            prepare_resources=source_snapshot,
            identity_factory=d.identity_factory,
            adaptive_limits=d.adaptive_limits,
        )

    return create


def build_cycle_process(configuration):
    """Only fixed production classes; disabled mode performs no dependency IO."""
    if not configuration.enabled:
        return None
    configuration.verify()
    from .agent_definition_postgres import PostgresAgentDefinitionRepository
    from .agent_definition_service import AgentDefinitionService
    from .authority_configuration import AuthorityRuntimeConfiguration
    from .authority_foundation import build_authority_foundation
    from .browser_session_application import BrowserSessionPolicy
    from .business_problem_postgres import PostgresBusinessProblemRepository
    from .digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from .execution_postgres import PostgresExecutionAuthorityRepository
    from .fixed_work_existing_planning import build_existing_planning
    from .governed_execution_ownership import execution_database_fingerprint
    from .knowledge_lifecycle_service import KnowledgeLifecycleService
    from .knowledge_postgres import PostgresKnowledgeRepository
    from .plan_suggestion_application import PlanningApplication
    from .plan_suggestion_postgres import PostgresPlanningRepository
    from .prepared_native_coordinator import PreparedNativeCoordinator
    from .readonly_continuation import ReadonlyContinuation
    from .readonly_continuation_policy import ReadonlyContinuationPolicy
    from .resource_automation import ResourceAutomation
    from .resource_automation_policy import AutomationPolicy
    from .runtime_profile_postgres import PostgresRuntimeProfileRepository
    from .runtime_profile_service import RuntimeProfileService
    from .skill_mcp_postgres import PostgresSkillMcpRepository
    from .skill_mcp_service import SkillMcpService
    from .workbench_grant_targets import WorkbenchGrantTargetValidator
    from .workbench_plan_suggestion import PlanningGrantTargetValidator
    from .workbench_prepared_execution import PreparedExecutionGrantTargets
    from .workbench_prepared_resources import PreparedResourceTargets

    runtime = AuthorityRuntimeConfiguration.from_mapping(
        json.loads(configuration.authorityRuntime.path.read_text())
    )
    db = runtime.database_url
    migrations = Path(__file__).parents[2] / "migrations"
    require(
        runtime.migration_path.resolve()
        == (migrations / "0018_browser_session_grant_authority.sql").resolve()
        and runtime.database_fingerprint == execution_database_fingerprint(db),
        "FIXED_CYCLE_AUTHORITY_BINDING_MISMATCH",
    )
    stack = ExitStack()
    try:

        def owned(repo):
            close = getattr(repo, "close", None)
            stack.callback(close if close is not None else repo.pool.close)
            return repo

        problems = owned(
            PostgresBusinessProblemRepository(
                db, migration_path=migrations / "0013_business_problem_authority.sql"
            )
        )
        _existing_schemas(problems.pool, migrations)
        execution = owned(
            PostgresExecutionAuthorityRepository(
                db, migration_path=migrations / "0008_execution_runtime_authority.sql"
            )
        )
        execution.compatibility()
        execution.native_dispatch_compatibility(
            migrations / "0022_native_execution_dispatch.sql"
        )
        employees = PostgresEmployeeDefinitionRepository(execution)
        employees.compatibility(migrations / "0014_digital_employee_identity.sql")
        agents = owned(
            PostgresAgentDefinitionRepository(
                db,
                migration_path=migrations / "0001_agent_definition_lifecycle.sql",
                governed_bindings_migration_path=migrations
                / "0006_agent_governed_bindings.sql",
            )
        )
        skills = owned(
            PostgresSkillMcpRepository(
                db, migration_path=migrations / "0002_skill_mcp_lifecycle.sql"
            )
        )
        runtimes = owned(
            PostgresRuntimeProfileRepository(
                db, migration_path=migrations / "0007_workflow_runtime_profiles.sql"
            )
        )
        runtimes.compatibility()
        knowledge = owned(
            PostgresKnowledgeRepository(
                db, migration_path=migrations / "0003_knowledge_operations.sql"
            )
        )
        knowledge.compatibility()
        services = {
            "agent": AgentDefinitionService(agents),
            "skill": SkillMcpService(skills),
            "runtime": RuntimeProfileService(runtimes),
            "knowledge": KnowledgeLifecycleService(knowledge),
        }
        services["mcp"] = services["skill"]
        planning_runtime = owned(
            build_existing_planning(
                db,
                configuration.planningRuntime.path,
                migrations,
                **(
                    {"budget_extension_path": configuration.budgetExtension.path}
                    if configuration.budgetExtension is not None
                    else {}
                ),
            )
        )
        _schema(
            problems.pool,
            migrations,
            "workflow_planning.schema_migrations",
            (
                (25, "0025_plan_suggestion.sql"),
                (26, "0026_plan_suggestion_invocation.sql"),
                (27, "0027_planning_provider_receipt.sql"),
                (43, "0043_planning_source_change.sql"),
            ),
        )
        planning = PlanningApplication(
            PostgresPlanningRepository(problems.pool), problems, None
        )
        targets = WorkbenchGrantTargetValidator(
            problems,
            agents,
            employees,
            additional=(
                PreparedResourceTargets(),
                PreparedExecutionGrantTargets(),
                PlanningGrantTargetValidator(planning_runtime.dependencies.profile),
            ),
        )
        foundation = owned(
            build_authority_foundation(
                runtime,
                BrowserSessionPolicy(
                    login_nonce_lifetime=timedelta(minutes=5),
                    idle_lifetime=timedelta(minutes=30),
                    absolute_lifetime=timedelta(hours=8),
                    csrf_lifetime=timedelta(minutes=10),
                ),
                target_validator=targets,
                existing_only=True,
            )
        )
        require(
            execution_database_fingerprint(db)
            == foundation.generation_controller.readiness.database_fingerprint,
            "FIXED_CYCLE_DATABASE_MISMATCH",
        )
        automation = ResourceAutomation(
            AutomationPolicy.load(configuration.resourcePolicy.path),
            foundation.grants,
            planning,
            services,
            employees,
        )
        readonly = ReadonlyContinuation(
            automation,
            ReadonlyContinuationPolicy.load(configuration.readonlyPolicy.path),
            PreparedNativeCoordinator(execution),
        )
        automation.continuation = readonly
        loop = compose_bound_cycle_service(
            foundation=foundation,
            planning_factory=_planning_factory(
                planning_runtime,
                planning,
                foundation.grants.authorization,
                configuration.servicePolicy.path,
            ),
            readonly_owner=readonly,
            policy_path=configuration.servicePolicy.path,
            credential_reader=lambda: (
                configuration.serviceCredential.verify().read_text().strip()
            ),
            enabled=True,
            poll_seconds=configuration.pollSeconds,
            policy_plan_approval_enabled=configuration.policyPlanApprovalEnabled,
        )
        policy = loop.host.runtime.registry._policy()
        profile = planning_runtime.dependencies.profile
        require(
            (
                profile.profile_revision_id,
                profile.profile_digest,
                profile.model,
                planning_runtime.budget.ledger_id,
            )
            == (
                policy.profileRevisionId,
                policy.profileDigest,
                policy.model,
                policy.ledgerId,
            ),
            "FIXED_CYCLE_PROFILE_LEDGER_MISMATCH",
        )
        process = CycleProcess(configuration, loop, stack)
        process.check()
        return process
    except BaseException:
        stack.close()
        raise
