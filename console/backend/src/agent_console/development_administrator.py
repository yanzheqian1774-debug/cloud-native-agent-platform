"""D12 explicitly enabled local-development role, never a browser claim."""

from datetime import UTC, datetime

from .authority_contracts import AuthenticationSource, ExactGrant

PRINCIPAL = "human:development-admin"
ACCOUNT = "local-account:devadmin"
SCOPE = ("s5-323-demo", "isolated-real-demo")
GRANT = ExactGrant("DEVELOPMENT_ADMIN", "USE", "development-administrator:local")


def configured(generation, context, credential):
    return bool(
        getattr(generation, "development_administrator", False)
        and context.authentication_source is AuthenticationSource.BROWSER_SESSION
        and context.principal_id == PRINCIPAL
        and (context.scope.tenant_id, context.scope.security_domain) == SCOPE
        and credential is not None
        and credential.credential_id == ACCOUNT
        and credential.principal_id == PRINCIPAL
        and credential.scope == context.scope
    )


def authorized(reader, context, *, generation, recovery_epoch, connection=None):
    if (
        context.principal_id != PRINCIPAL
        or (context.scope.tenant_id, context.scope.security_domain) != SCOPE
    ):
        return False
    return reader.has_current_grants(
        context,
        (GRANT,),
        now=datetime.now(UTC),
        generation=generation,
        recovery_epoch=recovery_epoch,
        connection=connection,
        configure_transaction=connection is None,
    )[0]


def for_service(service, context, connection=None):
    if context.principal_id != PRINCIPAL:
        return False
    return authorized(
        service.authorization,
        context,
        generation=service.generation.generation,
        recovery_epoch=service.recovery_epoch,
        connection=connection,
    )


def for_call(call):
    if call.context.principal_id != PRINCIPAL:
        return False
    adapter = getattr(call.authority, "adapter", None)
    if adapter is None:
        return False
    return authorized(
        adapter.authorization,
        call.context,
        generation=call.policy_generation,
        recovery_epoch=adapter.controller.readiness.recovery_epoch,
        connection=call.connection,
    )
