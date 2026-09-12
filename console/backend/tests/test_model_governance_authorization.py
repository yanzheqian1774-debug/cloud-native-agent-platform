from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import validate_registered_grant
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    ExactGrant,
    TrustedRequestContext,
)
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ModelConsumptionScope,
    ModelUseSubject,
)
from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    ModelDefinition,
    ModelEligibility,
    ModelEligibilityState,
    ModelGovernanceNotFound,
    ModelLifecycleHighWater,
    ModelRevisionIdentity,
    ModelScope,
    ProviderRevisionIdentity,
)
from agent_console.model_governance_authorization import (
    CurrentExactGrantDecision,
    ModelCreatorContinuationAdapter,
    ModelCreatorGrantTargetValidator,
    ModelGovernanceExactResolver,
    ModelManagementOperation,
    ModelUseAuthorizationAdapter,
    PostgresModelGrantTargetLookup,
    bind_model_use,
    create_model_grant,
    invoke_model_use,
    model_catalog_grant,
    model_definition_owner_revision,
    model_definition_reference,
    model_management_grant,
    model_revision_grant,
)

NOW = datetime(2026, 9, 12, 9, tzinfo=UTC)
AUTHORITY_SCOPE = AuthorityScope("tenant-a", "quality")
MODEL_SCOPE = ModelScope("tenant-a", "quality")
CONSUMPTION_SCOPE = ModelConsumptionScope("tenant-a", "quality")
CONTEXT = TrustedRequestContext(
    "principal:creator",
    AUTHORITY_SCOPE,
    "session:1",
    AuthenticationSource.BROWSER_SESSION,
    "authentication-policy:7",
)
BINDING = ExactModelBinding("model:reviewer", "model-revision:7", "a" * 64)


def use():
    return bind_model_use(
        consumer_kind="AGENT",
        consumer_id="agent:quality",
        consumer_revision_id="agent-revision:4",
        binding=BINDING,
    )


def definition(*, version=1, revision_id=None, creator="principal:creator"):
    return ModelDefinition(
        MODEL_SCOPE,
        BINDING.resource_id,
        "team:model-governance",
        creator,
        NOW,
        version,
        revision_id,
    )


def eligibility():
    return ModelEligibility(
        MODEL_SCOPE,
        ModelRevisionIdentity(BINDING.resource_id, BINDING.revision_id, BINDING.digest),
        ModelEligibilityState.PUBLISHED_ENABLED,
        ModelLifecycleHighWater(3, "fact:3", "f" * 64),
    )


def test_closed_model_grant_mapping_is_registered_without_select_model() -> None:
    grants = (
        create_model_grant(),
        model_catalog_grant(),
        model_revision_grant(BINDING),
        ExactGrant("MODEL_GOVERNANCE", use().action.value, use().exact_resource),
        ExactGrant(
            "MODEL_GOVERNANCE",
            invoke_model_use(
                attempt_id="attempt:9",
                binding_snapshot_id="binding-snapshot:2",
                binding=BINDING,
            ).action.value,
            invoke_model_use(
                attempt_id="attempt:9",
                binding_snapshot_id="binding-snapshot:2",
                binding=BINDING,
            ).exact_resource,
        ),
        model_management_grant(
            ModelManagementOperation.PUBLISH,
            BINDING.resource_id,
            BINDING.revision_id,
        ),
    )
    for grant in grants:
        validate_registered_grant(grant, allow_meta=False)

    with pytest.raises(ValueError, match="UNKNOWN_AUTHORITY_OPERATION"):
        validate_registered_grant(
            ExactGrant("MODEL_GOVERNANCE", "SELECT_MODEL", "model:catalog"),
            allow_meta=False,
        )


class DecisionReader:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def authorize_current(self, context, grant, *, now):
        self.calls.append((context, grant, now))
        if not self.result:
            return None
        if isinstance(self.result, CurrentExactGrantDecision):
            return self.result
        return CurrentExactGrantDecision(
            "decision:current",
            context,
            grant,
            7,
            "policy:7",
            now - timedelta(seconds=1),
            now + timedelta(minutes=1),
        )


def test_authorization_adapter_binds_trusted_context_and_complete_exact_target() -> (
    None
):
    reader = DecisionReader()
    adapter = ModelUseAuthorizationAdapter(CONTEXT, reader, clock=lambda: NOW)

    decision = adapter.authorize_use(
        CONSUMPTION_SCOPE, ModelUseSubject(CONTEXT.principal_id), use()
    )

    assert decision is not None
    assert decision.use == use()
    assert reader.calls[0][1] == ExactGrant(
        "MODEL_GOVERNANCE", "BIND_MODEL", use().exact_resource
    )
    assert (
        adapter.authorize_use(
            ModelConsumptionScope("tenant-b", "quality"),
            ModelUseSubject(CONTEXT.principal_id),
            use(),
        )
        is None
    )
    assert len(reader.calls) == 1


def test_authorization_adapter_rejects_mismatched_or_expired_authority_result() -> None:
    grant = ExactGrant("MODEL_GOVERNANCE", "BIND_MODEL", use().exact_resource)
    expired = CurrentExactGrantDecision(
        "decision:expired",
        CONTEXT,
        grant,
        7,
        "policy:7",
        NOW - timedelta(minutes=2),
        NOW,
    )
    adapter = ModelUseAuthorizationAdapter(
        CONTEXT, DecisionReader(expired), clock=lambda: NOW
    )
    assert (
        adapter.authorize_use(
            CONSUMPTION_SCOPE, ModelUseSubject(CONTEXT.principal_id), use()
        )
        is None
    )


class DefinitionRepository:
    def get(self, scope, model_id):
        assert (scope, model_id) == (MODEL_SCOPE, BINDING.resource_id)
        return definition(version=2, revision_id=BINDING.revision_id)


class RevisionRepository:
    def __init__(self, lifecycle=None):
        self.lifecycle = lifecycle or eligibility()

    def get_revision(self, scope, model_id, revision_id):
        assert (scope, model_id, revision_id) == (
            MODEL_SCOPE,
            BINDING.resource_id,
            BINDING.revision_id,
        )
        return SimpleNamespace(
            digest=BINDING.digest,
            provider=ProviderRevisionIdentity("provider:1", "revision:1", "b" * 64),
            endpoint=EndpointRevisionIdentity("endpoint:1", "revision:1", "c" * 64),
            connection_profile=ConnectionProfileRevisionIdentity(
                "profile:1", "revision:1", "d" * 64
            ),
        )

    def read_lifecycle(self, scope, model_id, revision_id):
        if isinstance(self.lifecycle, Exception):
            raise self.lifecycle
        return self.lifecycle


class ConfigurationRepository:
    def resolve_exact(self, scope, provider, endpoint, connection_profile):
        return SimpleNamespace(
            provider=SimpleNamespace(identity=provider),
            endpoint=SimpleNamespace(identity=endpoint),
            connection_profile=SimpleNamespace(identity=connection_profile),
        )


def test_owner_resolver_returns_exact_typed_graph_and_preserves_high_water() -> None:
    resolver = ModelGovernanceExactResolver(
        DefinitionRepository(), RevisionRepository(), ConfigurationRepository()
    )
    resolved = resolver.resolve_exact(CONSUMPTION_SCOPE, BINDING)
    assert resolved is not None
    assert resolved.binding == BINDING
    assert resolved.eligibility.high_water.ordinal == 3
    assert resolved.provider.digest == "b" * 64


def test_zero_lifecycle_fact_preserves_current_not_found() -> None:
    resolver = ModelGovernanceExactResolver(
        DefinitionRepository(),
        RevisionRepository(ModelGovernanceNotFound("MODEL_LIFECYCLE_NOT_FOUND")),
        ConfigurationRepository(),
    )
    with pytest.raises(ModelGovernanceNotFound, match="MODEL_LIFECYCLE_NOT_FOUND"):
        resolver.resolve_exact(CONSUMPTION_SCOPE, BINDING)


class ContinuationPort:
    def __init__(self):
        self.call = None

    def mint_owner_continuation(self, context, claim, *, originating_command_key):
        self.call = (context, claim, originating_command_key)
        return "opaque:model-creator"


def test_creator_continuation_is_minted_only_after_owner_generated_create() -> None:
    port = ContinuationPort()
    adapter = ModelCreatorContinuationAdapter(
        port,
        policy_generation=7,
        clock=lambda: NOW,
        identity_factory=lambda: "continuation:model:create:1",
    )
    created = definition()

    opaque = adapter.mint_after_create(
        CONTEXT,
        created,
        request_purpose="MODEL_CREATOR_MANAGEMENT",
        originating_command_key="create-model:command:1",
        expires_at=NOW + timedelta(minutes=10),
    )

    assert opaque == "opaque:model-creator"
    _, claim, command_key = port.call
    assert command_key == "create-model:command:1"
    assert claim.subject_principal_id == CONTEXT.principal_id
    assert claim.scope == CONTEXT.scope
    assert claim.canonical_resource_reference == model_definition_reference(
        created.model_id
    )
    assert claim.owner_revision == model_definition_owner_revision(created)
    assert claim.members == (
        model_management_grant(
            ModelManagementOperation.REVISE, created.model_id, "new"
        ),
    )


@pytest.mark.parametrize(
    "created,expires",
    [
        (definition(creator="principal:other"), NOW + timedelta(minutes=1)),
        (
            definition(version=2, revision_id=BINDING.revision_id),
            NOW + timedelta(minutes=1),
        ),
        (definition(), NOW + timedelta(minutes=10, seconds=1)),
    ],
)
def test_creator_continuation_rejects_wrong_creator_advanced_head_or_long_ttl(
    created, expires
) -> None:
    adapter = ModelCreatorContinuationAdapter(
        ContinuationPort(), policy_generation=7, clock=lambda: NOW
    )
    with pytest.raises(ValueError, match="MODEL_CREATOR_CONTINUATION_INVALID"):
        adapter.mint_after_create(
            CONTEXT,
            created,
            request_purpose="MODEL_CREATOR_MANAGEMENT",
            originating_command_key="create-model:command:1",
            expires_at=expires,
        )


class Lookup:
    def __init__(self):
        self.calls = []
        self.current = True

    def is_known_exact_target(self, scope, grant, *, connection=None):
        self.calls.append(("target", scope, grant, connection))
        return True

    def is_current_creator_definition(
        self,
        scope,
        *,
        principal_id,
        canonical_resource_reference,
        owner_revision,
        connection=None,
    ):
        self.calls.append(
            (
                "creator",
                scope,
                principal_id,
                canonical_resource_reference,
                owner_revision,
                connection,
            )
        )
        return self.current


def test_creator_validator_rechecks_owner_fact_on_consumption_connection() -> None:
    created = definition()
    port = ContinuationPort()
    adapter = ModelCreatorContinuationAdapter(
        port, policy_generation=7, clock=lambda: NOW
    )
    adapter.mint_after_create(
        CONTEXT,
        created,
        request_purpose="MODEL_CREATOR_MANAGEMENT",
        originating_command_key="create-model:command:1",
        expires_at=NOW + timedelta(minutes=1),
    )
    claim = port.call[1]
    lookup = Lookup()
    validator = ModelCreatorGrantTargetValidator(lookup)
    transaction = object()

    assert validator.validate_continuation(claim, connection=transaction)
    assert all(call[-1] is transaction for call in lookup.calls)
    lookup.current = False
    assert not validator.validate_continuation(claim, connection=transaction)
    assert not validator.validate_offer(
        CONTEXT.scope,
        claim.members,
        claim.canonical_resource_reference,
        claim.owner_revision,
    )


class Connection:
    def __init__(self, known=True):
        self.known = known
        self.calls = []

    def execute(self, query, parameters):
        self.calls.append((query, parameters))
        return self

    def fetchone(self):
        return {"known": self.known}


def test_postgres_lookup_uses_grant_administration_caller_connection() -> None:
    repository = SimpleNamespace(pool=None)
    lookup = PostgresModelGrantTargetLookup(repository)
    connection = Connection()
    grant = model_management_grant(
        ModelManagementOperation.REVISE, BINDING.resource_id, "new"
    )

    assert lookup.is_known_exact_target(MODEL_SCOPE, grant, connection=connection)
    assert connection.calls[0][1] == (
        MODEL_SCOPE.namespace,
        MODEL_SCOPE.security_domain,
        grant.exact_resource,
        MODEL_SCOPE.namespace,
        MODEL_SCOPE.security_domain,
        grant.exact_resource,
        MODEL_SCOPE.namespace,
        MODEL_SCOPE.security_domain,
        grant.exact_resource,
        MODEL_SCOPE.namespace,
        MODEL_SCOPE.security_domain,
        grant.exact_resource,
        MODEL_SCOPE.namespace,
        MODEL_SCOPE.security_domain,
        grant.exact_resource,
        MODEL_SCOPE.namespace,
        MODEL_SCOPE.security_domain,
        grant.exact_resource,
    )
