from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import psycopg
import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    BrowserSession,
    CredentialId,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequest,
    GrantRequestStatus,
    GrantSource,
    SessionId,
    TrustedRequestContext,
    VerifiedPrincipal,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
)
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ModelBindingResolutionFailure,
    ModelConsumptionScope,
    ModelUseSubject,
    resolve_authorized_model_binding,
)
from agent_console.model_governance import (
    InvocationLimit,
    ModelConnectionProfileRevision,
    ModelDefinition,
    ModelEndpointRevision,
    ModelLifecycleAction,
    ModelLifecycleFact,
    ModelProviderRevision,
    ModelRevision,
    ModelScope,
    SecretReference,
)
from agent_console.model_governance_authorization import (
    MODEL_OWNER,
    bind_caller_owned_model_use,
    bind_model_use,
    invoke_model_use,
)
from agent_console.model_governance_postgres import (
    PostgresModelGovernanceRepository,
)

DATABASE_URL = os.environ.get("MODEL_AUTHORIZATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="308 exclusive real PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def isolated_database() -> str:
    original = DATABASE_URL or ""
    database_name = f"impl308_authorization_{uuid.uuid4().hex}"
    admin = psycopg.connect(original, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = original.rsplit("/", 1)[0] + f"/{database_name}"
    try:
        yield database_url
    finally:
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


def persist_model(
    repository: PostgresModelGovernanceRepository,
    scope: ModelScope,
    *,
    now: datetime,
) -> ExactModelBinding:
    suffix = uuid.uuid4().hex
    definition = ModelDefinition(
        scope,
        f"model:{suffix}",
        "team:model-governance",
        "human:alice",
        now,
    )
    provider = ModelProviderRevision(
        scope,
        f"provider:{suffix}",
        f"provider-revision:{suffix}",
        "adapter:openai-compatible",
        "adapter-revision:1",
        ("CHAT",),
        "human:operator",
        now,
    )
    endpoint = ModelEndpointRevision(
        scope,
        f"endpoint:{suffix}",
        f"endpoint-revision:{suffix}",
        "https://models.example.invalid/v1",
        "eu-west",
        ("HTTPS",),
        "human:operator",
        now,
    )
    profile = ModelConnectionProfileRevision(
        scope,
        f"profile:{suffix}",
        f"profile-revision:{suffix}",
        endpoint.identity,
        SecretReference(f"secret:model:{suffix}", "1"),
        10,
        60,
        "human:operator",
        now,
    )
    revision = ModelRevision(
        scope,
        definition.model_id,
        f"model-revision:{suffix}",
        1,
        None,
        provider.identity,
        endpoint.identity,
        profile.identity,
        "reviewer-model",
        (),
        ("CHAT",),
        (InvocationLimit("max_output_tokens", 4096, "TOKEN"),),
        "human:operator",
        now,
    )
    repository.create(definition)
    repository.add_provider_revision(provider)
    repository.add_endpoint_revision(endpoint)
    repository.add_connection_profile_revision(profile)
    repository.add_revision(revision)
    repository.advance_head(
        scope,
        definition.model_id,
        revision.revision_id,
        expected_aggregate_version=1,
    )
    for ordinal, action in enumerate(
        (
            ModelLifecycleAction.VALIDATED,
            ModelLifecycleAction.HUMAN_REVIEWED,
            ModelLifecycleAction.PUBLISHED,
        ),
        1,
    ):
        repository.append_fact(
            ModelLifecycleFact(
                scope,
                f"model-fact:{ordinal}:{suffix}",
                revision.identity,
                ordinal,
                action,
                "human:reviewer",
                f"model-lifecycle-decision:{ordinal}:{suffix}",
                now + timedelta(milliseconds=ordinal),
            )
        )
    return ExactModelBinding(revision.model_id, revision.revision_id, revision.digest)


def activate_authority(
    repository: PostgresAuthorityRepository,
    scope: AuthorityScope,
    static_grant: ExactGrant,
    *,
    now: datetime,
) -> tuple[StaticAuthorityGeneration, TrustedRequestContext]:
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "policy-current",
        "test",
        (
            CredentialConfiguration(
                CredentialId("credential-browser-alice"),
                "7" * 64,
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.BROWSER_BOOTSTRAP,
                (),
            ),
            CredentialConfiguration(
                CredentialId("credential-service-alice"),
                "8" * 64,
                "human:alice",
                scope,
                now + timedelta(days=1),
                GrantSource.SERVICE_ONLY,
                (StaticGrant(static_grant, GrantSource.SERVICE_ONLY),),
            ),
        ),
        (),
        frozenset(),
    )
    repository.activate_generation(
        1,
        generation.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=now,
    )
    principal = VerifiedPrincipal(
        "human:alice",
        scope,
        CredentialId("credential-browser-alice"),
        now + timedelta(days=1),
        "policy-current",
    )
    repository.create_session(
        BrowserSession(
            SessionId("session-alice"),
            principal,
            now,
            now,
            now + timedelta(minutes=30),
            now + timedelta(hours=8),
            1,
            1,
        ),
        "9" * 64,
    )
    return generation, TrustedRequestContext(
        "human:alice",
        scope,
        "session-alice",
        AuthenticationSource.BROWSER_SESSION,
        "policy-current",
    )


def add_dynamic_grant(
    repository: PostgresAuthorityRepository,
    scope: AuthorityScope,
    grant: ExactGrant,
    *,
    now: datetime,
) -> tuple[GrantId, datetime, datetime]:
    request = GrantRequest(
        "model-bind-request",
        "human:alice",
        scope,
        (grant,),
        "MODEL_BINDING",
        GrantRequestStatus.PENDING,
        now,
    )
    repository.submit_request(
        request,
        actor_id="human:alice",
        idempotency_key="model-bind-request",
        payload_digest="1" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    issued_at = now + timedelta(seconds=1)
    expires_at = now + timedelta(hours=1)
    grant_id = GrantId("model-bind-grant")
    repository.decide_request(
        GrantDecision(
            "model-bind-decision",
            request.request_id,
            "human:admin",
            "meta-admin",
            True,
            "ASSIGNED_DUTY",
            "TICKET",
            "2" * 64,
            "policy-issued",
            "test",
            issued_at,
        ),
        grants=((grant_id, grant, issued_at, expires_at),),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="model-bind-decision",
        payload_digest="3" * 64,
        recovery_epoch=1,
    )
    return grant_id, issued_at, expires_at


def test_model_use_composes_current_decision_and_owner_read_on_one_transaction(
    isolated_database: str,
) -> None:
    authority = PostgresAuthorityRepository(
        isolated_database,
        migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql",
    )
    models = PostgresModelGovernanceRepository(
        isolated_database,
        migration_path=MIGRATIONS / "0019_model_governance.sql",
    )
    authority.migrate()
    models.migrate()
    now = datetime.now(UTC)
    model_scope = ModelScope(f"model-authorization-{uuid.uuid4().hex}", "quality")
    scope = AuthorityScope(model_scope.namespace, model_scope.security_domain)
    binding = persist_model(models, model_scope, now=now)
    bind_use = bind_model_use(
        consumer_kind="AGENT",
        consumer_id="agent:quality",
        consumer_revision_id="agent-revision:4",
        binding=binding,
    )
    bind_grant = ExactGrant(MODEL_OWNER, bind_use.action.value, bind_use.exact_resource)
    static_use = invoke_model_use(
        attempt_id="attempt:static",
        binding_snapshot_id="binding-snapshot:static",
        binding=binding,
    )
    static_grant = ExactGrant(
        MODEL_OWNER, static_use.action.value, static_use.exact_resource
    )
    generation, context = activate_authority(authority, scope, static_grant, now=now)
    grant_id, issued_at, expires_at = add_dynamic_grant(
        authority, scope, bind_grant, now=now
    )
    reader = GenerationAuthorizationReader(
        generation, authority, authority, recovery_epoch=1
    )
    effective_at = issued_at + timedelta(seconds=1)

    service_context = TrustedRequestContext(
        "human:alice",
        scope,
        "credential-service-alice",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-current",
    )
    assert (
        reader.authorize_current(service_context, static_grant, now=effective_at)
        is None
    )
    assert reader.authorize_current(context, bind_grant, now=expires_at) is None
    denied_use = bind_model_use(
        consumer_kind="AGENT",
        consumer_id="agent:other",
        consumer_revision_id="agent-revision:4",
        binding=binding,
    )
    with authority.connection_scope() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        denied = bind_caller_owned_model_use(
            context,
            reader,
            models,
            connection,
            generation=1,
            clock=lambda: effective_at,
        )
        with pytest.raises(
            ModelBindingResolutionFailure, match="MODEL_BINDING_NOT_FOUND"
        ):
            resolve_authorized_model_binding(
                ModelConsumptionScope(scope.tenant_id, scope.security_domain),
                ModelUseSubject(context.principal_id),
                denied_use,
                authorizer=denied.authorizer,
                resolver=denied.resolver,
                evaluation_time=effective_at,
            )

    revoke_started = Event()
    revoke_finished = Event()
    session_revoke_started = Event()
    session_revoke_finished = Event()

    def revoke() -> bool:
        revoke_started.set()
        result = authority.revoke_grant(
            grant_id,
            actor_id="human:admin",
            reason="DUTY_ENDED",
            idempotency_key="model-bind-revoke",
            payload_digest="4" * 64,
            now=effective_at + timedelta(seconds=1),
        )
        revoke_finished.set()
        return result

    def revoke_session() -> bool:
        session_revoke_started.set()
        result = authority.revoke_session(
            SessionId("session-alice"),
            reason="SESSION_ENDED",
            actor_id="human:admin",
            now=effective_at + timedelta(seconds=1),
        )
        session_revoke_finished.set()
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        with authority.connection_scope() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            adapters = bind_caller_owned_model_use(
                context,
                reader,
                models,
                connection,
                generation=1,
                clock=lambda: effective_at,
            )
            assert adapters.resolver.definitions.connection is connection
            resolved = resolve_authorized_model_binding(
                ModelConsumptionScope(scope.tenant_id, scope.security_domain),
                ModelUseSubject(context.principal_id),
                bind_use,
                authorizer=adapters.authorizer,
                resolver=adapters.resolver,
                evaluation_time=effective_at,
            )
            assert resolved.binding == binding
            assert resolved.eligibility.high_water.ordinal == 3
            future = executor.submit(revoke)
            session_future = executor.submit(revoke_session)
            assert revoke_started.wait(timeout=10)
            assert session_revoke_started.wait(timeout=10)
            assert not revoke_finished.wait(timeout=0.2)
            assert not session_revoke_finished.wait(timeout=0.2)
        assert future.result(timeout=10)
        assert session_future.result(timeout=10)

    with authority.connection_scope() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        adapters = bind_caller_owned_model_use(
            context,
            reader,
            models,
            connection,
            generation=1,
            clock=lambda: effective_at + timedelta(seconds=2),
        )
        with pytest.raises(
            ModelBindingResolutionFailure, match="MODEL_BINDING_NOT_FOUND"
        ):
            resolve_authorized_model_binding(
                ModelConsumptionScope(scope.tenant_id, scope.security_domain),
                ModelUseSubject(context.principal_id),
                bind_use,
                authorizer=adapters.authorizer,
                resolver=adapters.resolver,
                evaluation_time=effective_at + timedelta(seconds=2),
            )

    authority.close()
    models.close()
