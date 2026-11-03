"""Explicit bounded managed-Skill composition for the existing Native worker."""

from datetime import UTC, datetime

from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    ExactGrant,
    TrustedRequestContext,
)
from .execution_preparation import ExecutionPreparation
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
):
    if mode == "synthetic-delivery-v1":
        from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor

        executor = SyntheticDeliverySkillExecutor()
    elif mode == "synthetic-cost-v1":
        executor = SyntheticCostSkillExecutor()
    else:
        raise ValueError("PREPARED_SKILL_CONFIGURATION_INVALID")
    composition = compose_governed_skill_invocation(
        database_url,
        migrations,
        None,
        FixedReadOnlyPolicyAuthority(POLICY),
        SkillExecutorRegistry((executor,)),
    )

    def authorize(connection, command):
        if not authorization_check(connection, command):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        row = prepared_attempt(connection, command.scope, command.attempt_id)
        if row is None:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        p = ExecutionPreparation.model_validate(row["preparation"])
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

    return PreparedNativeSkillCaller(pool, composition, authorize), composition


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
