"""Typed values and persistence ports owned by Model Governance.

This internal domain boundary owns Platform Model identity and immutable
revision metadata.  Provider calls, credentials, connection observations,
Resource Use, Evidence, and public API schemas are intentionally outside it.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class ModelGovernanceError(RuntimeError):
    """Stable domain failure without storage or protected-object disclosure."""


class ModelGovernanceConflict(ModelGovernanceError):
    pass


class ModelGovernanceNotFound(ModelGovernanceError):
    pass


_SHA256_DIGEST = re.compile(r"[0-9a-f]{64}")


def _required(value: object, reason: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelGovernanceError(reason)


def _digest(value: object, reason: str) -> None:
    if not isinstance(value, str) or _SHA256_DIGEST.fullmatch(value) is None:
        raise ModelGovernanceError(reason)


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ModelGovernanceError("MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        return value.isoformat()
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ModelGovernanceError("MODEL_CANONICAL_KEY_INVALID")
            canonical_key = unicodedata.normalize("NFC", key)
            if canonical_key in normalized:
                raise ModelGovernanceError("MODEL_CANONICAL_KEY_CONFLICT")
            normalized[canonical_key] = _canonical(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ModelGovernanceError("MODEL_CANONICAL_NUMBER_INVALID")
    return value


def canonical_payload(value: Any) -> bytes:
    """Return deterministic, NFC-normalized canonical JSON bytes."""

    return json.dumps(
        _canonical(value),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_payload(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelScope:
    namespace: str
    security_domain: str

    def __post_init__(self) -> None:
        _required(self.namespace, "MODEL_SCOPE_REQUIRED")
        _required(self.security_domain, "MODEL_SCOPE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ModelRevisionIdentity:
    model_id: str
    revision_id: str
    digest: str

    def __post_init__(self) -> None:
        _required(self.model_id, "MODEL_ID_REQUIRED")
        _required(self.revision_id, "MODEL_REVISION_ID_REQUIRED")
        _digest(self.digest, "MODEL_REVISION_DIGEST_INVALID")


@dataclass(frozen=True, slots=True)
class ProviderRevisionIdentity:
    provider_id: str
    revision_id: str
    digest: str

    def __post_init__(self) -> None:
        _required(self.provider_id, "MODEL_PROVIDER_ID_REQUIRED")
        _required(self.revision_id, "MODEL_PROVIDER_REVISION_ID_REQUIRED")
        _digest(self.digest, "MODEL_PROVIDER_DIGEST_INVALID")


@dataclass(frozen=True, slots=True)
class EndpointRevisionIdentity:
    endpoint_id: str
    revision_id: str
    digest: str

    def __post_init__(self) -> None:
        _required(self.endpoint_id, "MODEL_ENDPOINT_ID_REQUIRED")
        _required(self.revision_id, "MODEL_ENDPOINT_REVISION_ID_REQUIRED")
        _digest(self.digest, "MODEL_ENDPOINT_DIGEST_INVALID")


@dataclass(frozen=True, slots=True)
class ConnectionProfileRevisionIdentity:
    profile_id: str
    revision_id: str
    digest: str

    def __post_init__(self) -> None:
        _required(self.profile_id, "MODEL_CONNECTION_PROFILE_ID_REQUIRED")
        _required(self.revision_id, "MODEL_CONNECTION_PROFILE_REVISION_ID_REQUIRED")
        _digest(self.digest, "MODEL_CONNECTION_PROFILE_DIGEST_INVALID")


def _timestamp(value: object, reason: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ModelGovernanceError(reason)


def _string_values(values: object, reason: str) -> None:
    if not isinstance(values, tuple):
        raise ModelGovernanceError(reason)
    for value in values:
        _required(value, reason)
    if len(values) != len(set(values)):
        raise ModelGovernanceError(reason)


def _computed_digest(record: Any, payload: dict[str, Any], reason: str) -> None:
    expected = canonical_digest(payload)
    supplied = record.digest
    if supplied != "" and supplied != expected:
        raise ModelGovernanceError(reason)
    object.__setattr__(record, "digest", expected)


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    scope: ModelScope
    model_id: str
    owner_id: str
    created_by: str
    created_at: datetime
    aggregate_version: int = 1
    current_revision_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        for value, reason in (
            (self.model_id, "MODEL_ID_REQUIRED"),
            (self.owner_id, "MODEL_OWNER_REQUIRED"),
            (self.created_by, "MODEL_CREATED_BY_REQUIRED"),
        ):
            _required(value, reason)
        _timestamp(self.created_at, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        if (
            isinstance(self.aggregate_version, bool)
            or not isinstance(self.aggregate_version, int)
            or self.aggregate_version < 1
        ):
            raise ModelGovernanceError("MODEL_AGGREGATE_VERSION_INVALID")
        if self.current_revision_id is not None:
            _required(self.current_revision_id, "MODEL_REVISION_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class SecretReference:
    reference_id: str
    version: str

    def __post_init__(self) -> None:
        _required(self.reference_id, "MODEL_SECRET_REFERENCE_REQUIRED")
        _required(self.version, "MODEL_SECRET_REFERENCE_VERSION_REQUIRED")


@dataclass(frozen=True, slots=True)
class InvocationLimit:
    name: str
    value: int | float
    unit: str

    def __post_init__(self) -> None:
        _required(self.name, "MODEL_INVOCATION_LIMIT_INVALID")
        _required(self.unit, "MODEL_INVOCATION_LIMIT_INVALID")
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or not math.isfinite(self.value)
            or self.value < 0
        ):
            raise ModelGovernanceError("MODEL_INVOCATION_LIMIT_INVALID")


@dataclass(frozen=True, slots=True)
class ModelProviderRevision:
    scope: ModelScope
    provider_id: str
    revision_id: str
    adapter_contract_id: str
    adapter_contract_revision_id: str
    supported_operation_classes: tuple[str, ...]
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        for value, reason in (
            (self.provider_id, "MODEL_PROVIDER_ID_REQUIRED"),
            (self.revision_id, "MODEL_PROVIDER_REVISION_ID_REQUIRED"),
            (self.adapter_contract_id, "MODEL_ADAPTER_CONTRACT_ID_REQUIRED"),
            (
                self.adapter_contract_revision_id,
                "MODEL_ADAPTER_CONTRACT_REVISION_ID_REQUIRED",
            ),
            (self.created_by, "MODEL_CREATED_BY_REQUIRED"),
        ):
            _required(value, reason)
        _string_values(
            self.supported_operation_classes, "MODEL_PROVIDER_OPERATIONS_INVALID"
        )
        if not self.supported_operation_classes:
            raise ModelGovernanceError("MODEL_PROVIDER_OPERATIONS_INVALID")
        _timestamp(self.created_at, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        _computed_digest(
            self,
            self.digest_contract(),
            "MODEL_PROVIDER_REVISION_DIGEST_MISMATCH",
        )

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "model-provider-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "provider_id": self.provider_id,
            "revision_id": self.revision_id,
            "adapter_contract_id": self.adapter_contract_id,
            "adapter_contract_revision_id": self.adapter_contract_revision_id,
            "supported_operation_classes": sorted(self.supported_operation_classes),
        }

    @property
    def identity(self) -> ProviderRevisionIdentity:
        return ProviderRevisionIdentity(self.provider_id, self.revision_id, self.digest)


@dataclass(frozen=True, slots=True)
class ModelEndpointRevision:
    scope: ModelScope
    endpoint_id: str
    revision_id: str
    normalized_address_reference: str
    region: str
    transport_constraints: tuple[str, ...]
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        for value, reason in (
            (self.endpoint_id, "MODEL_ENDPOINT_ID_REQUIRED"),
            (self.revision_id, "MODEL_ENDPOINT_REVISION_ID_REQUIRED"),
            (
                self.normalized_address_reference,
                "MODEL_ENDPOINT_ADDRESS_REFERENCE_REQUIRED",
            ),
            (self.region, "MODEL_ENDPOINT_REGION_REQUIRED"),
            (self.created_by, "MODEL_CREATED_BY_REQUIRED"),
        ):
            _required(value, reason)
        _string_values(self.transport_constraints, "MODEL_ENDPOINT_TRANSPORT_INVALID")
        _timestamp(self.created_at, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        _computed_digest(
            self,
            self.digest_contract(),
            "MODEL_ENDPOINT_REVISION_DIGEST_MISMATCH",
        )

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "model-endpoint-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "endpoint_id": self.endpoint_id,
            "revision_id": self.revision_id,
            "normalized_address_reference": self.normalized_address_reference,
            "region": self.region,
            "transport_constraints": sorted(self.transport_constraints),
        }

    @property
    def identity(self) -> EndpointRevisionIdentity:
        return EndpointRevisionIdentity(self.endpoint_id, self.revision_id, self.digest)


@dataclass(frozen=True, slots=True)
class ModelConnectionProfileRevision:
    scope: ModelScope
    profile_id: str
    revision_id: str
    endpoint: EndpointRevisionIdentity
    secret_reference: SecretReference
    connect_timeout_seconds: int
    request_timeout_seconds: int
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        for value, reason in (
            (self.profile_id, "MODEL_CONNECTION_PROFILE_ID_REQUIRED"),
            (self.revision_id, "MODEL_CONNECTION_PROFILE_REVISION_ID_REQUIRED"),
            (self.created_by, "MODEL_CREATED_BY_REQUIRED"),
        ):
            _required(value, reason)
        if not isinstance(self.endpoint, EndpointRevisionIdentity):
            raise ModelGovernanceError("MODEL_ENDPOINT_IDENTITY_REQUIRED")
        if not isinstance(self.secret_reference, SecretReference):
            raise ModelGovernanceError("MODEL_SECRET_REFERENCE_REQUIRED")
        for timeout in (self.connect_timeout_seconds, self.request_timeout_seconds):
            if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
                raise ModelGovernanceError("MODEL_CONNECTION_TIMEOUT_INVALID")
        _timestamp(self.created_at, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        _computed_digest(
            self,
            self.digest_contract(),
            "MODEL_CONNECTION_PROFILE_REVISION_DIGEST_MISMATCH",
        )

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "model-connection-profile-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "profile_id": self.profile_id,
            "revision_id": self.revision_id,
            "endpoint": self.endpoint,
            "secret_reference": self.secret_reference,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "request_timeout_seconds": self.request_timeout_seconds,
        }

    @property
    def identity(self) -> ConnectionProfileRevisionIdentity:
        return ConnectionProfileRevisionIdentity(
            self.profile_id, self.revision_id, self.digest
        )


@dataclass(frozen=True, slots=True)
class ModelRevision:
    scope: ModelScope
    model_id: str
    revision_id: str
    revision: int
    predecessor_revision_id: str | None
    provider: ProviderRevisionIdentity
    endpoint: EndpointRevisionIdentity
    connection_profile: ConnectionProfileRevisionIdentity
    provider_native_model_id: str
    compatibility: tuple[str, ...]
    capabilities: tuple[str, ...]
    invocation_limits: tuple[InvocationLimit, ...]
    created_by: str
    created_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        for value, reason in (
            (self.model_id, "MODEL_ID_REQUIRED"),
            (self.revision_id, "MODEL_REVISION_ID_REQUIRED"),
            (self.provider_native_model_id, "MODEL_PROVIDER_NATIVE_ID_REQUIRED"),
            (self.created_by, "MODEL_CREATED_BY_REQUIRED"),
        ):
            _required(value, reason)
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ModelGovernanceError("MODEL_REVISION_NUMBER_INVALID")
        if (self.revision == 1) != (self.predecessor_revision_id is None):
            raise ModelGovernanceError("MODEL_PREDECESSOR_INVALID")
        if self.predecessor_revision_id is not None:
            _required(self.predecessor_revision_id, "MODEL_PREDECESSOR_INVALID")
        for value, expected, reason in (
            (
                self.provider,
                ProviderRevisionIdentity,
                "MODEL_PROVIDER_IDENTITY_REQUIRED",
            ),
            (
                self.endpoint,
                EndpointRevisionIdentity,
                "MODEL_ENDPOINT_IDENTITY_REQUIRED",
            ),
            (
                self.connection_profile,
                ConnectionProfileRevisionIdentity,
                "MODEL_CONNECTION_PROFILE_IDENTITY_REQUIRED",
            ),
        ):
            if not isinstance(value, expected):
                raise ModelGovernanceError(reason)
        _string_values(self.compatibility, "MODEL_COMPATIBILITY_INVALID")
        _string_values(self.capabilities, "MODEL_CAPABILITIES_INVALID")
        if not isinstance(self.invocation_limits, tuple) or any(
            not isinstance(item, InvocationLimit) for item in self.invocation_limits
        ):
            raise ModelGovernanceError("MODEL_INVOCATION_LIMIT_INVALID")
        limit_names = [item.name for item in self.invocation_limits]
        if len(limit_names) != len(set(limit_names)):
            raise ModelGovernanceError("MODEL_INVOCATION_LIMIT_INVALID")
        _timestamp(self.created_at, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        _computed_digest(self, self.digest_contract(), "MODEL_REVISION_DIGEST_MISMATCH")

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "model-revision.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "model_id": self.model_id,
            "revision_id": self.revision_id,
            "revision": self.revision,
            "predecessor_revision_id": self.predecessor_revision_id,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "connection_profile": self.connection_profile,
            "provider_native_model_id": self.provider_native_model_id,
            "compatibility": sorted(self.compatibility),
            "capabilities": sorted(self.capabilities),
            "invocation_limits": sorted(
                self.invocation_limits, key=lambda item: item.name
            ),
        }

    @property
    def identity(self) -> ModelRevisionIdentity:
        return ModelRevisionIdentity(self.model_id, self.revision_id, self.digest)


@dataclass(frozen=True, slots=True)
class ExactProviderConfiguration:
    scope: ModelScope
    provider: ModelProviderRevision
    endpoint: ModelEndpointRevision
    connection_profile: ModelConnectionProfileRevision

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope) or not all(
            isinstance(record, expected)
            for record, expected in (
                (self.provider, ModelProviderRevision),
                (self.endpoint, ModelEndpointRevision),
                (self.connection_profile, ModelConnectionProfileRevision),
            )
        ):
            raise ModelGovernanceError("MODEL_CONFIGURATION_INVALID")
        if any(
            record.scope != self.scope
            for record in (self.provider, self.endpoint, self.connection_profile)
        ):
            raise ModelGovernanceError("MODEL_CONFIGURATION_SCOPE_MISMATCH")
        if self.connection_profile.endpoint != self.endpoint.identity:
            raise ModelGovernanceError("MODEL_CONFIGURATION_REFERENCE_MISMATCH")


class ModelLifecycleAction(StrEnum):
    VALIDATED = "VALIDATED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    PUBLISHED = "PUBLISHED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    DEPRECATED = "DEPRECATED"
    REVOKED = "REVOKED"
    SUCCESSOR_CREATED = "SUCCESSOR_CREATED"


@dataclass(frozen=True, slots=True)
class ModelLifecycleFact:
    scope: ModelScope
    fact_id: str
    model: ModelRevisionIdentity
    ordinal: int
    action: ModelLifecycleAction
    actor_id: str
    decision_id: str
    occurred_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        _required(self.fact_id, "MODEL_LIFECYCLE_FACT_ID_REQUIRED")
        if not isinstance(self.model, ModelRevisionIdentity):
            raise ModelGovernanceError("MODEL_REVISION_IDENTITY_REQUIRED")
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal < 1
        ):
            raise ModelGovernanceError("MODEL_LIFECYCLE_ORDINAL_INVALID")
        if not isinstance(self.action, ModelLifecycleAction):
            raise ModelGovernanceError("MODEL_LIFECYCLE_ACTION_INVALID")
        _required(self.actor_id, "MODEL_LIFECYCLE_ACTOR_REQUIRED")
        _required(self.decision_id, "MODEL_LIFECYCLE_DECISION_REQUIRED")
        _timestamp(self.occurred_at, "MODEL_TIMESTAMP_TIMEZONE_REQUIRED")
        _computed_digest(
            self, self.digest_contract(), "MODEL_LIFECYCLE_FACT_DIGEST_MISMATCH"
        )

    def digest_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "model-lifecycle-fact.v1",
            "namespace": self.scope.namespace,
            "security_domain": self.scope.security_domain,
            "fact_id": self.fact_id,
            "model": self.model,
            "ordinal": self.ordinal,
            "action": self.action,
            "actor_id": self.actor_id,
            "decision_id": self.decision_id,
            "occurred_at": self.occurred_at,
        }


class ModelEligibilityState(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    PUBLISHED_ENABLED = "PUBLISHED_ENABLED"
    PUBLISHED_DISABLED = "PUBLISHED_DISABLED"
    DEPRECATED = "DEPRECATED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class ModelLifecycleHighWater:
    ordinal: int
    fact_id: str
    fact_digest: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal < 1
        ):
            raise ModelGovernanceError("MODEL_LIFECYCLE_ORDINAL_INVALID")
        _required(self.fact_id, "MODEL_LIFECYCLE_FACT_ID_REQUIRED")
        _digest(self.fact_digest, "MODEL_LIFECYCLE_FACT_DIGEST_INVALID")


@dataclass(frozen=True, slots=True)
class ModelEligibility:
    scope: ModelScope
    model: ModelRevisionIdentity
    state: ModelEligibilityState
    high_water: ModelLifecycleHighWater

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ModelScope):
            raise ModelGovernanceError("MODEL_SCOPE_REQUIRED")
        if not isinstance(self.model, ModelRevisionIdentity):
            raise ModelGovernanceError("MODEL_REVISION_IDENTITY_REQUIRED")
        if not isinstance(self.state, ModelEligibilityState):
            raise ModelGovernanceError("MODEL_ELIGIBILITY_STATE_INVALID")
        if not isinstance(self.high_water, ModelLifecycleHighWater):
            raise ModelGovernanceError("MODEL_LIFECYCLE_HIGH_WATER_REQUIRED")

    @property
    def allows_new_use(self) -> bool:
        return self.state is ModelEligibilityState.PUBLISHED_ENABLED


class ModelDefinitionRepository(Protocol):
    """Scoped stable-root persistence; implementations fail closed."""

    def compatibility(self) -> None: ...

    def get(self, scope: ModelScope, model_id: str) -> ModelDefinition: ...

    def list(self, scope: ModelScope) -> tuple[ModelDefinition, ...]: ...

    def create(self, definition: ModelDefinition) -> ModelDefinition: ...


class ModelRevisionRepository(Protocol):
    """Exact immutable revisions plus append-only lifecycle history."""

    def compatibility(self) -> None: ...

    def get_revision(
        self, scope: ModelScope, model_id: str, revision_id: str
    ) -> ModelRevision: ...

    def add_revision(self, revision: ModelRevision) -> ModelRevision: ...

    def append_fact(self, fact: ModelLifecycleFact) -> ModelLifecycleFact: ...

    def read_lifecycle(
        self,
        scope: ModelScope,
        model_id: str,
        revision_id: str,
        *,
        through_ordinal: int | None = None,
    ) -> ModelEligibility: ...

    def advance_head(
        self,
        scope: ModelScope,
        model_id: str,
        successor_revision_id: str,
        *,
        expected_aggregate_version: int,
    ) -> ModelDefinition: ...


class ModelProviderConfigurationRepository(Protocol):
    """Exact, secret-free Provider/Endpoint/Profile revision persistence."""

    def compatibility(self) -> None: ...

    def add_provider_revision(
        self, revision: ModelProviderRevision
    ) -> ModelProviderRevision: ...

    def add_endpoint_revision(
        self, revision: ModelEndpointRevision
    ) -> ModelEndpointRevision: ...

    def add_connection_profile_revision(
        self, revision: ModelConnectionProfileRevision
    ) -> ModelConnectionProfileRevision: ...

    def resolve_exact(
        self,
        scope: ModelScope,
        provider: ProviderRevisionIdentity,
        endpoint: EndpointRevisionIdentity,
        connection_profile: ConnectionProfileRevisionIdentity,
    ) -> ExactProviderConfiguration: ...
