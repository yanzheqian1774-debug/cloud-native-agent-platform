import dataclasses
import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta
from typing import get_type_hints

import pytest
from agent_console import model_governance
from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    ExactProviderConfiguration,
    InvocationLimit,
    ModelConnectionProfileRevision,
    ModelDefinition,
    ModelDefinitionRepository,
    ModelEligibility,
    ModelEligibilityState,
    ModelEndpointRevision,
    ModelGovernanceError,
    ModelLifecycleAction,
    ModelLifecycleFact,
    ModelLifecycleHighWater,
    ModelProviderConfigurationRepository,
    ModelProviderRevision,
    ModelRevision,
    ModelRevisionIdentity,
    ModelRevisionRepository,
    ModelScope,
    ProviderRevisionIdentity,
    SecretReference,
    canonical_digest,
    canonical_payload,
)

SCOPE = ModelScope("tenant-a", "quality")
NOW = datetime(2026, 9, 12, 8, 30, tzinfo=UTC)


def provider_revision(
    *, scope: ModelScope = SCOPE, operations: tuple[str, ...] = ("CHAT", "EMBED")
) -> ModelProviderRevision:
    return ModelProviderRevision(
        scope=scope,
        provider_id="provider:approved",
        revision_id="provider-revision:3",
        adapter_contract_id="adapter:openai-compatible",
        adapter_contract_revision_id="adapter-revision:2",
        supported_operation_classes=operations,
        created_by="principal:operator",
        created_at=NOW,
    )


def endpoint_revision(*, scope: ModelScope = SCOPE) -> ModelEndpointRevision:
    return ModelEndpointRevision(
        scope=scope,
        endpoint_id="endpoint:eu-primary",
        revision_id="endpoint-revision:4",
        normalized_address_reference="https://models.example.invalid/v1",
        region="eu-west",
        transport_constraints=("HTTPS", "TLS_1_3"),
        created_by="principal:operator",
        created_at=NOW,
    )


def connection_profile_revision(
    *,
    scope: ModelScope = SCOPE,
    endpoint: EndpointRevisionIdentity | None = None,
    secret_version: str = "7",
) -> ModelConnectionProfileRevision:
    endpoint = endpoint or endpoint_revision(scope=scope).identity
    return ModelConnectionProfileRevision(
        scope=scope,
        profile_id="profile:regulated",
        revision_id="profile-revision:6",
        endpoint=endpoint,
        secret_reference=SecretReference("secret:model-provider", secret_version),
        connect_timeout_seconds=10,
        request_timeout_seconds=60,
        created_by="principal:operator",
        created_at=NOW,
    )


def model_revision(**changes: object) -> ModelRevision:
    values: dict[str, object] = {
        "scope": SCOPE,
        "model_id": "model:reviewer",
        "revision_id": "model-revision:7",
        "revision": 1,
        "predecessor_revision_id": None,
        "provider": provider_revision().identity,
        "endpoint": endpoint_revision().identity,
        "connection_profile": connection_profile_revision().identity,
        "provider_native_model_id": "reviewer-2026-08",
        "compatibility": ("JSON_SCHEMA", "TOOLS"),
        "capabilities": ("CHAT", "STRUCTURED_OUTPUT"),
        "invocation_limits": (
            InvocationLimit("max_input_tokens", 32_000, "TOKEN"),
            InvocationLimit("max_output_tokens", 4_096, "TOKEN"),
        ),
        "created_by": "principal:operator",
        "created_at": NOW,
    }
    values.update(changes)
    return ModelRevision(**values)  # type: ignore[arg-type]


def test_canonical_payload_is_sorted_compact_utf8_and_nfc_normalized() -> None:
    left = {"z": "Cafe\u0301", "a": {"re\u0301gion": "e\u0301u"}}
    right = {"a": {"région": "éu"}, "z": "Café"}

    expected = '{"a":{"région":"éu"},"z":"Café"}'.encode()
    assert canonical_payload(left) == expected
    assert canonical_payload(right) == expected
    assert canonical_digest(left) == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize(
    "value,reason",
    [
        ({1: "not-a-string-key"}, "MODEL_CANONICAL_KEY_INVALID"),
        ({"value": float("nan")}, "MODEL_CANONICAL_NUMBER_INVALID"),
        ({"when": datetime(2026, 1, 1)}, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED"),
        (
            {"é": 1, "e\u0301": 2},
            "MODEL_CANONICAL_KEY_CONFLICT",
        ),
    ],
)
def test_canonical_payload_rejects_ambiguous_or_nonportable_values(
    value: object, reason: str
) -> None:
    with pytest.raises(ModelGovernanceError, match=reason):
        canonical_payload(value)


@pytest.mark.parametrize(
    "factory,args,reason",
    [
        (ModelRevisionIdentity, ("", "revision:1", "a" * 64), "MODEL_ID_REQUIRED"),
        (
            ProviderRevisionIdentity,
            ("provider:1", "", "a" * 64),
            "MODEL_PROVIDER_REVISION_ID_REQUIRED",
        ),
        (
            EndpointRevisionIdentity,
            ("endpoint:1", "revision:1", "SHA256:a"),
            "MODEL_ENDPOINT_DIGEST_INVALID",
        ),
        (
            ConnectionProfileRevisionIdentity,
            ("profile:1", "revision:1", "A" * 64),
            "MODEL_CONNECTION_PROFILE_DIGEST_INVALID",
        ),
    ],
)
def test_exact_revision_identities_reject_missing_or_noncanonical_parts(
    factory: object, args: tuple[str, str, str], reason: str
) -> None:
    with pytest.raises(ModelGovernanceError, match=reason):
        factory(*args)  # type: ignore[operator]


def test_definition_preserves_owner_generated_platform_identity() -> None:
    definition = ModelDefinition(
        scope=SCOPE,
        model_id="model:owner-generated",
        owner_id="team:risk",
        created_by="principal:creator",
        created_at=NOW,
    )

    assert definition.model_id == "model:owner-generated"
    assert definition.aggregate_version == 1
    assert definition.current_revision_id is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.model_id = "provider-native-name"  # type: ignore[misc]


def test_configuration_revisions_compute_exact_stable_digests() -> None:
    provider = provider_revision()
    reordered = ModelProviderRevision(
        scope=SCOPE,
        provider_id=provider.provider_id,
        revision_id=provider.revision_id,
        adapter_contract_id=provider.adapter_contract_id,
        adapter_contract_revision_id=provider.adapter_contract_revision_id,
        supported_operation_classes=("EMBED", "CHAT"),
        created_by="principal:other-provenance",
        created_at=NOW + timedelta(days=1),
    )

    assert provider.identity == ProviderRevisionIdentity(
        provider.provider_id, provider.revision_id, provider.digest
    )
    assert provider.digest == reordered.digest
    assert len(provider.digest) == 64


def test_connection_profile_contains_only_typed_secret_reference_metadata() -> None:
    profile = connection_profile_revision()
    payload = canonical_payload(profile.digest_contract())

    assert profile.secret_reference == SecretReference("secret:model-provider", "7")
    assert b"secret:model-provider" in payload
    assert not hasattr(profile, "secret_value")
    assert not hasattr(profile, "credentials")
    assert connection_profile_revision(secret_version="8").digest != profile.digest


def test_model_revision_digest_covers_only_the_accepted_canonical_contract() -> None:
    revision = model_revision()
    same_contract = model_revision(
        compatibility=("TOOLS", "JSON_SCHEMA"),
        capabilities=("STRUCTURED_OUTPUT", "CHAT"),
        invocation_limits=tuple(reversed(revision.invocation_limits)),
        created_by="principal:later-import",
        created_at=NOW + timedelta(days=2),
    )
    payload = revision.digest_contract()
    independently_encoded = json.dumps(
        model_governance._canonical(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert revision.digest == hashlib.sha256(independently_encoded).hexdigest()
    assert revision.digest == same_contract.digest
    assert revision.identity == ModelRevisionIdentity(
        revision.model_id, revision.revision_id, revision.digest
    )
    assert "created_by" not in payload
    assert "created_at" not in payload


@pytest.mark.parametrize(
    "changes",
    [
        {"provider_native_model_id": "reviewer-2026-09"},
        {"provider": ProviderRevisionIdentity("provider:other", "rev:1", "b" * 64)},
        {"capabilities": ("CHAT",)},
        {"compatibility": ("JSON_SCHEMA",)},
        {"invocation_limits": (InvocationLimit("max_output_tokens", 8192, "TOKEN"),)},
    ],
)
def test_invocation_affecting_changes_create_a_new_model_digest(
    changes: dict[str, object],
) -> None:
    assert model_revision(**changes).digest != model_revision().digest


def test_supplied_model_digest_must_match_owner_canonical_digest() -> None:
    with pytest.raises(ModelGovernanceError, match="MODEL_REVISION_DIGEST_MISMATCH"):
        model_revision(digest="f" * 64)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"revision": 0}, "MODEL_REVISION_NUMBER_INVALID"),
        (
            {"revision": 2, "predecessor_revision_id": None},
            "MODEL_PREDECESSOR_INVALID",
        ),
        (
            {"revision": 1, "predecessor_revision_id": "model-revision:6"},
            "MODEL_PREDECESSOR_INVALID",
        ),
        ({"capabilities": ("CHAT", "CHAT")}, "MODEL_CAPABILITIES_INVALID"),
        (
            {
                "invocation_limits": (
                    InvocationLimit("max_tokens", 1, "TOKEN"),
                    InvocationLimit("max_tokens", 2, "TOKEN"),
                )
            },
            "MODEL_INVOCATION_LIMIT_INVALID",
        ),
    ],
)
def test_model_revision_rejects_invalid_contract_values(
    changes: dict[str, object], reason: str
) -> None:
    with pytest.raises(ModelGovernanceError, match=reason):
        model_revision(**changes)


def test_exact_provider_configuration_requires_one_scope_and_profile_endpoint() -> None:
    provider = provider_revision()
    endpoint = endpoint_revision()
    profile = connection_profile_revision(endpoint=endpoint.identity)

    resolved = ExactProviderConfiguration(SCOPE, provider, endpoint, profile)
    assert resolved.provider.identity == provider.identity
    assert resolved.endpoint.identity == profile.endpoint

    foreign_scope = ModelScope("tenant-b", "quality")
    with pytest.raises(
        ModelGovernanceError, match="MODEL_CONFIGURATION_SCOPE_MISMATCH"
    ):
        ExactProviderConfiguration(
            SCOPE, provider_revision(scope=foreign_scope), endpoint, profile
        )
    with pytest.raises(
        ModelGovernanceError, match="MODEL_CONFIGURATION_REFERENCE_MISMATCH"
    ):
        ExactProviderConfiguration(
            SCOPE,
            provider,
            endpoint,
            connection_profile_revision(
                endpoint=EndpointRevisionIdentity("endpoint:other", "rev:1", "a" * 64)
            ),
        )


def test_lifecycle_fact_and_eligibility_are_exact_and_high_water_bound() -> None:
    revision = model_revision()
    fact = ModelLifecycleFact(
        scope=SCOPE,
        fact_id="model-fact:4",
        model=revision.identity,
        ordinal=4,
        action=ModelLifecycleAction.PUBLISHED,
        actor_id="principal:reviewer",
        decision_id="decision:publish-4",
        occurred_at=NOW,
    )
    high_water = ModelLifecycleHighWater(fact.ordinal, fact.fact_id, fact.digest)

    eligible = ModelEligibility(
        SCOPE, revision.identity, ModelEligibilityState.PUBLISHED_ENABLED, high_water
    )
    disabled = ModelEligibility(
        SCOPE, revision.identity, ModelEligibilityState.PUBLISHED_DISABLED, high_water
    )

    assert eligible.allows_new_use is True
    assert disabled.allows_new_use is False
    assert fact.digest == canonical_digest(fact.digest_contract())


def test_repository_ports_are_exact_typed_owner_boundaries() -> None:
    assert set(vars(ModelDefinitionRepository)) >= {"get", "list", "create"}
    assert set(vars(ModelRevisionRepository)) >= {
        "get_revision",
        "add_revision",
        "append_fact",
        "read_lifecycle",
        "advance_head",
    }
    assert set(vars(ModelProviderConfigurationRepository)) >= {
        "add_provider_revision",
        "add_endpoint_revision",
        "add_connection_profile_revision",
        "resolve_exact",
    }
    resolve_hints = get_type_hints(ModelProviderConfigurationRepository.resolve_exact)
    assert resolve_hints == {
        "scope": ModelScope,
        "provider": ProviderRevisionIdentity,
        "endpoint": EndpointRevisionIdentity,
        "connection_profile": ConnectionProfileRevisionIdentity,
        "return": ExactProviderConfiguration,
    }
    assert (
        "through_ordinal"
        in inspect.signature(ModelRevisionRepository.read_lifecycle).parameters
    )


def test_unaccepted_extension_ports_are_not_part_of_the_domain_batch() -> None:
    assert not hasattr(model_governance, "ModelConnectionObservationRepository")
    assert not hasattr(model_governance, "ModelInvocationPort")
    assert not hasattr(model_governance, "ModelEvidence")
