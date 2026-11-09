"""Explicit bounded managed-Skill composition for the existing Native worker."""

from datetime import UTC, datetime

from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    ExactGrant,
    TrustedRequestContext,
)
from .ontology_execution import parse_preparation
from .prepared_execution_lineage import prepared_attempt
from .prepared_native_skill import PreparedNativeSkillCaller
from .resource_use_domain import canonical_digest
from .skill_executor import SkillExecutorRegistry
from .skill_invocation_application import FixedReadOnlyPolicyAuthority
from .skill_invocation_composition import compose_governed_skill_invocation
from .skill_invocation_domain import SideEffectClass, SideEffectPolicy
from .synthetic_cost_skill import SyntheticCostSkillExecutor

POLICY = SideEffectPolicy(
    "synthetic-cost-readonly",
    "1",
    canonical_digest(
        {
            "policyId": "synthetic-cost-readonly",
            "policyRevision": "1",
            "allowedClass": "READ_ONLY",
        }
    ),
    SideEffectClass.READ_ONLY,
)


def compose(
    pool,
    database_url,
    migrations,
    reader,
    generation,
    authorization_check,
    *,
    mode="synthetic-cost-v1",
    native_loop_path=None,
):
    if mode == "ontology-sales-v1":
        from .sales_ontology_executor import SalesOntologyExecutor

        executor = SalesOntologyExecutor()
    elif mode == "sales-gross-profit-v2-candidate":
        from .sales_gross_profit_skill import SalesGrossProfitSkillExecutor

        executor = SalesGrossProfitSkillExecutor()
    elif mode == "sales-diagnostic-v1":
        from .sales_diagnostic_skill import SalesDiagnosticSkillExecutor

        executor = SalesDiagnosticSkillExecutor()
    elif mode == "synthetic-delivery-v1":
        from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor

        executor = SyntheticDeliverySkillExecutor()
    elif mode in {"synthetic-cost-v1", "registered-readonly-v1"}:
        executor = SyntheticCostSkillExecutor()
    else:
        raise ValueError("PREPARED_SKILL_CONFIGURATION_INVALID")
    executors = (executor,)
    if mode in {"registered-readonly-v1", "sales-gross-profit-v2-candidate"}:
        from .sales_diagnostic_skill import SalesDiagnosticSkillExecutor
        from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor
        from .synthetic_delivery_skill_v2 import SyntheticDeliverySkillExecutorV2
        from .tabular_diagnostic_skill import TabularDiagnosticSkillExecutor

        executors = (
            TabularDiagnosticSkillExecutor(),
            SyntheticCostSkillExecutor(),
            SalesDiagnosticSkillExecutor(),
            SyntheticDeliverySkillExecutor(),
            SyntheticDeliverySkillExecutorV2(),
        )
        if mode == "sales-gross-profit-v2-candidate":
            executors += (executor,)
    from .native_document_skill import NativeDocumentSkillExecutor

    native_runtime = []
    if native_loop_path:
        from .native_loop_skill import (
            NativeLoopSkillExecutor,
            NativeValidatedLoopSkillExecutor,
        )

        executors += tuple(
            executor_type(
                lambda identity, output, timeout: native_runtime[0].run(
                    identity, output, timeout
                )
            )
            for executor_type in (
                NativeDocumentSkillExecutor,
                NativeLoopSkillExecutor,
                NativeValidatedLoopSkillExecutor,
            )
        )
    composition = compose_governed_skill_invocation(
        database_url,
        migrations,
        None,
        FixedReadOnlyPolicyAuthority(POLICY),
        SkillExecutorRegistry(executors),
    )

    def authorize(connection, command):
        if not authorization_check(connection, command):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        row = prepared_attempt(connection, command.scope, command.attempt_id)
        if row is None:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        p = parse_preparation(row["preparation"])
        resource = (
            f"skill-invocation:prepared:{p.digest}:"
            f"{row['task_id']}:{row['attempt_ordinal']}"
        )
        grant = ExactGrant("SKILL", "INVOKE_SKILL", resource)
        context = TrustedRequestContext(
            command.principal_id,
            AuthorityScope(command.scope.namespace, command.scope.security_domain),
            command.credential_id,
            AuthenticationSource(command.authentication_source),
            generation.policy_version,
        )
        grants = (grant,)
        binding = getattr(p, "business_semantics", None)
        if binding is not None:
            from .ontology_service import resource as ontology_resource

            grants += (
                ExactGrant(
                    "BUSINESS_ONTOLOGY",
                    "USE",
                    ontology_resource(
                        binding.ontology.resource_id, binding.ontology.revision_id
                    ),
                ),
            )
        if not all(
            reader.has_current_grants(
                context,
                grants,
                now=datetime.now(UTC),
                generation=command.authority_generation.value,
                recovery_epoch=command.recovery_epoch.value,
                connection=connection,
                configure_transaction=False,
            )
        ):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return "prepared-skill-authorization:" + canonical_digest(
            {
                "principal": command.principal_id,
                "credential": command.credential_id,
                "namespace": command.scope.namespace,
                "securityDomain": command.scope.security_domain,
                "resource": resource,
                "generation": command.authority_generation.value,
                "recoveryEpoch": command.recovery_epoch.value,
            }
        )

    if native_loop_path:
        from .native_loop_runtime import NativeLoopRuntime

        native_runtime.append(
            NativeLoopRuntime(
                native_loop_path,
                pool,
                database_url,
                migrations,
                reader,
                generation,
                authorize,
            )
        )
        composition.closeables = tuple(native_runtime)

    return PreparedNativeSkillCaller(
        pool,
        composition,
        authorize,
        sales_v2_candidate=mode == "sales-gross-profit-v2-candidate",
    ), composition


def owner_authority_factory(reader, generation, authorization_check):
    """Reconstruct only the original saved principal; every new grant is rechecked."""
    from types import SimpleNamespace

    def factory(connection, command):
        if not authorization_check(connection, command):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        context = TrustedRequestContext(
            command.principal_id,
            AuthorityScope(command.scope.namespace, command.scope.security_domain),
            command.credential_id,
            AuthenticationSource(command.authentication_source),
            generation.policy_version,
        )

        class CurrentAuthority:
            def require(self, principal, owner, action, resource):
                if (
                    principal.principal_id,
                    principal.tenant_id,
                    principal.security_domain,
                ) != (
                    context.principal_id,
                    context.scope.tenant_id,
                    context.scope.security_domain,
                ):
                    raise AuthorityError("AUTHORIZATION_NOT_FOUND")
                from .authority_configuration import validate_registered_grant

                grant = ExactGrant(owner, action, resource)
                validate_registered_grant(grant, allow_meta=False)
                if not reader.has_current_grants(
                    context,
                    (grant,),
                    now=datetime.now(UTC),
                    generation=command.authority_generation.value,
                    recovery_epoch=command.recovery_epoch.value,
                    connection=connection,
                    configure_transaction=False,
                )[0]:
                    raise AuthorityError("AUTHORIZATION_NOT_FOUND")
                return SimpleNamespace(
                    decision_id="prepared-native-owner:"
                    + canonical_digest(
                        {
                            "principal": context.principal_id,
                            "namespace": context.scope.tenant_id,
                            "securityDomain": context.scope.security_domain,
                            "owner": owner,
                            "action": action,
                            "resource": resource,
                            "generation": command.authority_generation.value,
                        }
                    )
                )

        return context, CurrentAuthority()

    return factory
