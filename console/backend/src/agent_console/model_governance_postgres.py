# ruff: noqa: E501
"""PostgreSQL primary adapter for authoritative Model Governance continuity."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    NotNullViolation,
    UniqueViolation,
)
from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    ExactProviderConfiguration,
    InvocationLimit,
    ModelConnectionProfileRevision,
    ModelDefinition,
    ModelEligibility,
    ModelEligibilityState,
    ModelEndpointRevision,
    ModelGovernanceConflict,
    ModelGovernanceError,
    ModelGovernanceNotFound,
    ModelLifecycleAction,
    ModelLifecycleFact,
    ModelLifecycleHighWater,
    ModelProviderRevision,
    ModelRevision,
    ModelRevisionIdentity,
    ModelScope,
    ProviderRevisionIdentity,
    SecretReference,
    canonical_payload,
)
from agent_console.postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

ADAPTER = "model-governance-postgresql-v1"
MIGRATION_VERSION = 19

MODEL_GOVERNANCE_STRUCTURE = (
    Table(
        "model_governance.schema_migrations",
        LEDGER_COLUMNS,
        (primary("version"),),
    ),
    Table(
        "model_governance.definitions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("model_id", "text"),
            ("owner_id", "text"),
            ("created_by", "text"),
            ("created_at", "timestamp with time zone"),
            ("aggregate_version", "bigint"),
            ("record", "jsonb"),
        ),
        (
            primary("namespace", "security_domain", "model_id"),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "model_id",
                    "current_revision_id",
                ),
                "model_governance.model_revisions",
                ("namespace", "security_domain", "model_id", "revision_id"),
            ),
        ),
    ),
    Table(
        "model_governance.provider_revisions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("provider_id", "text"),
            ("revision_id", "text"),
            ("digest", "text"),
            ("adapter_contract_id", "text"),
            ("adapter_contract_revision_id", "text"),
            ("created_by", "text"),
            ("created_at", "timestamp with time zone"),
            ("record", "jsonb"),
        ),
        (
            primary("namespace", "security_domain", "provider_id", "revision_id"),
            unique(
                "namespace",
                "security_domain",
                "provider_id",
                "revision_id",
                "digest",
            ),
        ),
        ("immutable_model_governance_provider_revisions",),
    ),
    Table(
        "model_governance.endpoint_revisions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("endpoint_id", "text"),
            ("revision_id", "text"),
            ("digest", "text"),
            ("normalized_address_reference", "text"),
            ("region", "text"),
            ("created_by", "text"),
            ("created_at", "timestamp with time zone"),
            ("record", "jsonb"),
        ),
        (
            primary("namespace", "security_domain", "endpoint_id", "revision_id"),
            unique(
                "namespace",
                "security_domain",
                "endpoint_id",
                "revision_id",
                "digest",
            ),
        ),
        ("immutable_model_governance_endpoint_revisions",),
    ),
    Table(
        "model_governance.connection_profile_revisions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("profile_id", "text"),
            ("revision_id", "text"),
            ("digest", "text"),
            ("endpoint_id", "text"),
            ("endpoint_revision_id", "text"),
            ("endpoint_digest", "text"),
            ("secret_reference_id", "text"),
            ("secret_reference_version", "text"),
            ("connect_timeout_seconds", "integer"),
            ("request_timeout_seconds", "integer"),
            ("created_by", "text"),
            ("created_at", "timestamp with time zone"),
            ("record", "jsonb"),
        ),
        (
            primary("namespace", "security_domain", "profile_id", "revision_id"),
            unique(
                "namespace",
                "security_domain",
                "profile_id",
                "revision_id",
                "digest",
            ),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "endpoint_id",
                    "endpoint_revision_id",
                    "endpoint_digest",
                ),
                "model_governance.endpoint_revisions",
                (
                    "namespace",
                    "security_domain",
                    "endpoint_id",
                    "revision_id",
                    "digest",
                ),
            ),
        ),
        ("immutable_model_governance_connection_profile_revisions",),
    ),
    Table(
        "model_governance.model_revisions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("model_id", "text"),
            ("revision_id", "text"),
            ("revision", "bigint"),
            ("digest", "text"),
            ("provider_id", "text"),
            ("provider_revision_id", "text"),
            ("provider_digest", "text"),
            ("endpoint_id", "text"),
            ("endpoint_revision_id", "text"),
            ("endpoint_digest", "text"),
            ("profile_id", "text"),
            ("profile_revision_id", "text"),
            ("profile_digest", "text"),
            ("provider_native_model_id", "text"),
            ("created_by", "text"),
            ("created_at", "timestamp with time zone"),
            ("record", "jsonb"),
        ),
        (
            primary("namespace", "security_domain", "model_id", "revision_id"),
            unique("namespace", "security_domain", "model_id", "revision"),
            unique(
                "namespace",
                "security_domain",
                "model_id",
                "revision_id",
                "digest",
            ),
            foreign(
                ("namespace", "security_domain", "model_id"),
                "model_governance.definitions",
                ("namespace", "security_domain", "model_id"),
            ),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "model_id",
                    "predecessor_revision_id",
                ),
                "model_governance.model_revisions",
                ("namespace", "security_domain", "model_id", "revision_id"),
            ),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "provider_id",
                    "provider_revision_id",
                    "provider_digest",
                ),
                "model_governance.provider_revisions",
                (
                    "namespace",
                    "security_domain",
                    "provider_id",
                    "revision_id",
                    "digest",
                ),
            ),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "endpoint_id",
                    "endpoint_revision_id",
                    "endpoint_digest",
                ),
                "model_governance.endpoint_revisions",
                (
                    "namespace",
                    "security_domain",
                    "endpoint_id",
                    "revision_id",
                    "digest",
                ),
            ),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "profile_id",
                    "profile_revision_id",
                    "profile_digest",
                ),
                "model_governance.connection_profile_revisions",
                (
                    "namespace",
                    "security_domain",
                    "profile_id",
                    "revision_id",
                    "digest",
                ),
            ),
        ),
        ("immutable_model_governance_model_revisions",),
    ),
    Table(
        "model_governance.lifecycle_facts",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("model_id", "text"),
            ("revision_id", "text"),
            ("model_digest", "text"),
            ("ordinal", "bigint"),
            ("fact_id", "text"),
            ("action", "text"),
            ("actor_id", "text"),
            ("decision_id", "text"),
            ("occurred_at", "timestamp with time zone"),
            ("digest", "text"),
            ("record", "jsonb"),
        ),
        (
            primary(
                "namespace",
                "security_domain",
                "model_id",
                "revision_id",
                "ordinal",
            ),
            unique("namespace", "security_domain", "fact_id"),
            foreign(
                (
                    "namespace",
                    "security_domain",
                    "model_id",
                    "revision_id",
                    "model_digest",
                ),
                "model_governance.model_revisions",
                (
                    "namespace",
                    "security_domain",
                    "model_id",
                    "revision_id",
                    "digest",
                ),
            ),
        ),
        ("immutable_model_governance_lifecycle_facts",),
    ),
)

_CONFLICTS = (CheckViolation, ForeignKeyViolation, NotNullViolation, UniqueViolation)


class PostgresModelGovernanceRepository:
    """One PostgreSQL adapter implementing the three narrow owner ports."""

    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout: float = 5.0,
    ) -> None:
        if not database_url:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE")
        if migration_path.name != "0019_model_governance.sql":
            raise ModelGovernanceError("MODEL_GOVERNANCE_SCHEMA_INCOMPATIBLE")
        self.migration_path = migration_path
        try:
            self.pool = ConnectionPool(
                database_url,
                min_size=min_pool_size,
                max_size=max_pool_size,
                timeout=timeout,
                kwargs={"row_factory": dict_row, "autocommit": False},
                open=True,
            )
            self.pool.wait(timeout=timeout)
        except Exception as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def close(self) -> None:
        self.pool.close()

    def migrate(self) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='10s'")
                connection.execute("SET LOCAL lock_timeout='5s'")
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 308))",
                    ("model-governance-migration-v19",),
                )
                relation = connection.execute(
                    "SELECT to_regclass('model_governance.schema_migrations') AS relation"
                ).fetchone()["relation"]
                row = None
                if relation is not None:
                    row = connection.execute(
                        "SELECT checksum,adapter FROM model_governance.schema_migrations WHERE version=%s",
                        (MIGRATION_VERSION,),
                    ).fetchone()
                if row is None:
                    connection.execute(self.migration_path.read_text())
                    connection.execute(
                        "INSERT INTO model_governance.schema_migrations(version,checksum,adapter) VALUES(%s,%s,%s)",
                        (MIGRATION_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif row != {
                    "checksum": self.migration_checksum,
                    "adapter": ADAPTER,
                }:
                    raise ModelGovernanceError("MODEL_GOVERNANCE_SCHEMA_INCOMPATIBLE")
                if not schema_is_compatible(connection, MODEL_GOVERNANCE_STRUCTURE):
                    raise ModelGovernanceError("MODEL_GOVERNANCE_SCHEMA_INCOMPATIBLE")
        except ModelGovernanceError:
            raise
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc

    def compatibility(self) -> None:
        try:
            with self.pool.connection() as connection:
                relation = connection.execute(
                    "SELECT to_regclass('model_governance.schema_migrations') AS relation"
                ).fetchone()["relation"]
                if relation is None:
                    raise ModelGovernanceError("MODEL_GOVERNANCE_SCHEMA_INCOMPATIBLE")
                row = connection.execute(
                    "SELECT checksum,adapter FROM model_governance.schema_migrations WHERE version=%s",
                    (MIGRATION_VERSION,),
                ).fetchone()
                if row != {
                    "checksum": self.migration_checksum,
                    "adapter": ADAPTER,
                } or not schema_is_compatible(connection, MODEL_GOVERNANCE_STRUCTURE):
                    raise ModelGovernanceError("MODEL_GOVERNANCE_SCHEMA_INCOMPATIBLE")
        except ModelGovernanceError:
            raise
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _scope(scope: ModelScope) -> tuple[str, str]:
        return scope.namespace, scope.security_domain

    @staticmethod
    def _record(value: Any) -> dict[str, Any]:
        return json.loads(canonical_payload(value))

    @staticmethod
    def _datetime(value: object) -> datetime:
        if not isinstance(value, str):
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
        return datetime.fromisoformat(value)

    @staticmethod
    def _stored_scope(record: dict[str, Any]) -> ModelScope:
        return ModelScope(**record["scope"])

    @classmethod
    def _definition(cls, row: dict[str, Any]) -> ModelDefinition:
        try:
            record = row["record"]
            result = ModelDefinition(
                scope=cls._stored_scope(record),
                model_id=record["model_id"],
                owner_id=record["owner_id"],
                created_by=record["created_by"],
                created_at=cls._datetime(record["created_at"]),
                aggregate_version=record["aggregate_version"],
                current_revision_id=record["current_revision_id"],
            )
            expected = {
                "namespace": result.scope.namespace,
                "security_domain": result.scope.security_domain,
                "model_id": result.model_id,
                "owner_id": result.owner_id,
                "created_by": result.created_by,
                "aggregate_version": result.aggregate_version,
                "current_revision_id": result.current_revision_id,
                "created_at": result.created_at,
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
            return result
        except (KeyError, ModelGovernanceError, TypeError, ValueError) as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT") from exc

    @classmethod
    def _provider(cls, row: dict[str, Any]) -> ModelProviderRevision:
        try:
            record = row["record"]
            result = ModelProviderRevision(
                scope=cls._stored_scope(record),
                provider_id=record["provider_id"],
                revision_id=record["revision_id"],
                adapter_contract_id=record["adapter_contract_id"],
                adapter_contract_revision_id=record["adapter_contract_revision_id"],
                supported_operation_classes=tuple(
                    record["supported_operation_classes"]
                ),
                created_by=record["created_by"],
                created_at=cls._datetime(record["created_at"]),
                digest=record["digest"],
            )
            expected = {
                "namespace": result.scope.namespace,
                "security_domain": result.scope.security_domain,
                "provider_id": result.provider_id,
                "revision_id": result.revision_id,
                "digest": result.digest,
                "adapter_contract_id": result.adapter_contract_id,
                "adapter_contract_revision_id": result.adapter_contract_revision_id,
                "created_by": result.created_by,
                "created_at": result.created_at,
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
            return result
        except (KeyError, ModelGovernanceError, TypeError, ValueError) as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT") from exc

    @classmethod
    def _endpoint(cls, row: dict[str, Any]) -> ModelEndpointRevision:
        try:
            record = row["record"]
            result = ModelEndpointRevision(
                scope=cls._stored_scope(record),
                endpoint_id=record["endpoint_id"],
                revision_id=record["revision_id"],
                normalized_address_reference=record["normalized_address_reference"],
                region=record["region"],
                transport_constraints=tuple(record["transport_constraints"]),
                created_by=record["created_by"],
                created_at=cls._datetime(record["created_at"]),
                digest=record["digest"],
            )
            expected = {
                "namespace": result.scope.namespace,
                "security_domain": result.scope.security_domain,
                "endpoint_id": result.endpoint_id,
                "revision_id": result.revision_id,
                "digest": result.digest,
                "normalized_address_reference": result.normalized_address_reference,
                "region": result.region,
                "created_by": result.created_by,
                "created_at": result.created_at,
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
            return result
        except (KeyError, ModelGovernanceError, TypeError, ValueError) as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT") from exc

    @classmethod
    def _profile(cls, row: dict[str, Any]) -> ModelConnectionProfileRevision:
        try:
            record = row["record"]
            result = ModelConnectionProfileRevision(
                scope=cls._stored_scope(record),
                profile_id=record["profile_id"],
                revision_id=record["revision_id"],
                endpoint=EndpointRevisionIdentity(**record["endpoint"]),
                secret_reference=SecretReference(**record["secret_reference"]),
                connect_timeout_seconds=record["connect_timeout_seconds"],
                request_timeout_seconds=record["request_timeout_seconds"],
                created_by=record["created_by"],
                created_at=cls._datetime(record["created_at"]),
                digest=record["digest"],
            )
            expected = {
                "namespace": result.scope.namespace,
                "security_domain": result.scope.security_domain,
                "profile_id": result.profile_id,
                "revision_id": result.revision_id,
                "digest": result.digest,
                "endpoint_id": result.endpoint.endpoint_id,
                "endpoint_revision_id": result.endpoint.revision_id,
                "endpoint_digest": result.endpoint.digest,
                "secret_reference_id": result.secret_reference.reference_id,
                "secret_reference_version": result.secret_reference.version,
                "connect_timeout_seconds": result.connect_timeout_seconds,
                "request_timeout_seconds": result.request_timeout_seconds,
                "created_by": result.created_by,
                "created_at": result.created_at,
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
            return result
        except (KeyError, ModelGovernanceError, TypeError, ValueError) as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT") from exc

    @classmethod
    def _revision(cls, row: dict[str, Any]) -> ModelRevision:
        try:
            record = row["record"]
            result = ModelRevision(
                scope=cls._stored_scope(record),
                model_id=record["model_id"],
                revision_id=record["revision_id"],
                revision=record["revision"],
                predecessor_revision_id=record["predecessor_revision_id"],
                provider=ProviderRevisionIdentity(**record["provider"]),
                endpoint=EndpointRevisionIdentity(**record["endpoint"]),
                connection_profile=ConnectionProfileRevisionIdentity(
                    **record["connection_profile"]
                ),
                provider_native_model_id=record["provider_native_model_id"],
                compatibility=tuple(record["compatibility"]),
                capabilities=tuple(record["capabilities"]),
                invocation_limits=tuple(
                    InvocationLimit(**item) for item in record["invocation_limits"]
                ),
                created_by=record["created_by"],
                created_at=cls._datetime(record["created_at"]),
                digest=record["digest"],
            )
            expected = {
                "namespace": result.scope.namespace,
                "security_domain": result.scope.security_domain,
                "model_id": result.model_id,
                "revision_id": result.revision_id,
                "revision": result.revision,
                "predecessor_revision_id": result.predecessor_revision_id,
                "digest": result.digest,
                "provider_id": result.provider.provider_id,
                "provider_revision_id": result.provider.revision_id,
                "provider_digest": result.provider.digest,
                "endpoint_id": result.endpoint.endpoint_id,
                "endpoint_revision_id": result.endpoint.revision_id,
                "endpoint_digest": result.endpoint.digest,
                "profile_id": result.connection_profile.profile_id,
                "profile_revision_id": result.connection_profile.revision_id,
                "profile_digest": result.connection_profile.digest,
                "provider_native_model_id": result.provider_native_model_id,
                "created_by": result.created_by,
                "created_at": result.created_at,
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
            return result
        except (KeyError, ModelGovernanceError, TypeError, ValueError) as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT") from exc

    @classmethod
    def _fact(cls, row: dict[str, Any]) -> ModelLifecycleFact:
        try:
            record = row["record"]
            result = ModelLifecycleFact(
                scope=cls._stored_scope(record),
                fact_id=record["fact_id"],
                model=ModelRevisionIdentity(**record["model"]),
                ordinal=record["ordinal"],
                action=ModelLifecycleAction(record["action"]),
                actor_id=record["actor_id"],
                decision_id=record["decision_id"],
                occurred_at=cls._datetime(record["occurred_at"]),
                digest=record["digest"],
            )
            expected = {
                "namespace": result.scope.namespace,
                "security_domain": result.scope.security_domain,
                "model_id": result.model.model_id,
                "revision_id": result.model.revision_id,
                "model_digest": result.model.digest,
                "ordinal": result.ordinal,
                "fact_id": result.fact_id,
                "action": result.action.value,
                "actor_id": result.actor_id,
                "decision_id": result.decision_id,
                "digest": result.digest,
                "occurred_at": result.occurred_at,
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
            return result
        except (KeyError, ModelGovernanceError, TypeError, ValueError) as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT") from exc

    def get(self, scope: ModelScope, model_id: str) -> ModelDefinition:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT * FROM model_governance.definitions WHERE namespace=%s AND security_domain=%s AND model_id=%s",
                    (*self._scope(scope), model_id),
                ).fetchone()
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        if row is None:
            raise ModelGovernanceNotFound("MODEL_DEFINITION_NOT_FOUND")
        return self._definition(row)

    def list(self, scope: ModelScope) -> tuple[ModelDefinition, ...]:
        try:
            with self.pool.connection() as connection:
                rows = connection.execute(
                    "SELECT * FROM model_governance.definitions WHERE namespace=%s AND security_domain=%s ORDER BY model_id LIMIT 200",
                    self._scope(scope),
                ).fetchall()
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return tuple(self._definition(row) for row in rows)

    def create(self, definition: ModelDefinition) -> ModelDefinition:
        record = self._record(definition)
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute(
                    "INSERT INTO model_governance.definitions(namespace,security_domain,model_id,owner_id,created_by,created_at,aggregate_version,current_revision_id,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        *self._scope(definition.scope),
                        definition.model_id,
                        definition.owner_id,
                        definition.created_by,
                        definition.created_at,
                        definition.aggregate_version,
                        definition.current_revision_id,
                        json.dumps(record),
                    ),
                )
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict("MODEL_DEFINITION_CONFLICT") from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return definition

    def add_provider_revision(
        self, revision: ModelProviderRevision
    ) -> ModelProviderRevision:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute(
                    "INSERT INTO model_governance.provider_revisions(namespace,security_domain,provider_id,revision_id,digest,adapter_contract_id,adapter_contract_revision_id,created_by,created_at,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        *self._scope(revision.scope),
                        revision.provider_id,
                        revision.revision_id,
                        revision.digest,
                        revision.adapter_contract_id,
                        revision.adapter_contract_revision_id,
                        revision.created_by,
                        revision.created_at,
                        json.dumps(self._record(revision)),
                    ),
                )
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict("MODEL_PROVIDER_REVISION_CONFLICT") from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return revision

    def add_endpoint_revision(
        self, revision: ModelEndpointRevision
    ) -> ModelEndpointRevision:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute(
                    "INSERT INTO model_governance.endpoint_revisions(namespace,security_domain,endpoint_id,revision_id,digest,normalized_address_reference,region,created_by,created_at,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        *self._scope(revision.scope),
                        revision.endpoint_id,
                        revision.revision_id,
                        revision.digest,
                        revision.normalized_address_reference,
                        revision.region,
                        revision.created_by,
                        revision.created_at,
                        json.dumps(self._record(revision)),
                    ),
                )
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict("MODEL_ENDPOINT_REVISION_CONFLICT") from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return revision

    def add_connection_profile_revision(
        self, revision: ModelConnectionProfileRevision
    ) -> ModelConnectionProfileRevision:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute(
                    "INSERT INTO model_governance.connection_profile_revisions(namespace,security_domain,profile_id,revision_id,digest,endpoint_id,endpoint_revision_id,endpoint_digest,secret_reference_id,secret_reference_version,connect_timeout_seconds,request_timeout_seconds,created_by,created_at,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        *self._scope(revision.scope),
                        revision.profile_id,
                        revision.revision_id,
                        revision.digest,
                        revision.endpoint.endpoint_id,
                        revision.endpoint.revision_id,
                        revision.endpoint.digest,
                        revision.secret_reference.reference_id,
                        revision.secret_reference.version,
                        revision.connect_timeout_seconds,
                        revision.request_timeout_seconds,
                        revision.created_by,
                        revision.created_at,
                        json.dumps(self._record(revision)),
                    ),
                )
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict(
                "MODEL_CONNECTION_PROFILE_REVISION_CONFLICT"
            ) from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return revision

    def resolve_exact(
        self,
        scope: ModelScope,
        provider: ProviderRevisionIdentity,
        endpoint: EndpointRevisionIdentity,
        connection_profile: ConnectionProfileRevisionIdentity,
    ) -> ExactProviderConfiguration:
        try:
            with self.pool.connection() as connection:
                provider_row = connection.execute(
                    "SELECT * FROM model_governance.provider_revisions WHERE namespace=%s AND security_domain=%s AND provider_id=%s AND revision_id=%s AND digest=%s",
                    (
                        *self._scope(scope),
                        provider.provider_id,
                        provider.revision_id,
                        provider.digest,
                    ),
                ).fetchone()
                endpoint_row = connection.execute(
                    "SELECT * FROM model_governance.endpoint_revisions WHERE namespace=%s AND security_domain=%s AND endpoint_id=%s AND revision_id=%s AND digest=%s",
                    (
                        *self._scope(scope),
                        endpoint.endpoint_id,
                        endpoint.revision_id,
                        endpoint.digest,
                    ),
                ).fetchone()
                profile_row = connection.execute(
                    "SELECT * FROM model_governance.connection_profile_revisions WHERE namespace=%s AND security_domain=%s AND profile_id=%s AND revision_id=%s AND digest=%s",
                    (
                        *self._scope(scope),
                        connection_profile.profile_id,
                        connection_profile.revision_id,
                        connection_profile.digest,
                    ),
                ).fetchone()
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        if provider_row is None or endpoint_row is None or profile_row is None:
            raise ModelGovernanceNotFound("MODEL_CONFIGURATION_NOT_FOUND")
        return ExactProviderConfiguration(
            scope,
            self._provider(provider_row),
            self._endpoint(endpoint_row),
            self._profile(profile_row),
        )

    def add_revision(self, revision: ModelRevision) -> ModelRevision:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute(
                    "INSERT INTO model_governance.model_revisions(namespace,security_domain,model_id,revision_id,revision,predecessor_revision_id,digest,provider_id,provider_revision_id,provider_digest,endpoint_id,endpoint_revision_id,endpoint_digest,profile_id,profile_revision_id,profile_digest,provider_native_model_id,created_by,created_at,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        *self._scope(revision.scope),
                        revision.model_id,
                        revision.revision_id,
                        revision.revision,
                        revision.predecessor_revision_id,
                        revision.digest,
                        revision.provider.provider_id,
                        revision.provider.revision_id,
                        revision.provider.digest,
                        revision.endpoint.endpoint_id,
                        revision.endpoint.revision_id,
                        revision.endpoint.digest,
                        revision.connection_profile.profile_id,
                        revision.connection_profile.revision_id,
                        revision.connection_profile.digest,
                        revision.provider_native_model_id,
                        revision.created_by,
                        revision.created_at,
                        json.dumps(self._record(revision)),
                    ),
                )
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict("MODEL_REVISION_CONFLICT") from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return revision

    def get_revision(
        self, scope: ModelScope, model_id: str, revision_id: str
    ) -> ModelRevision:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT * FROM model_governance.model_revisions WHERE namespace=%s AND security_domain=%s AND model_id=%s AND revision_id=%s",
                    (*self._scope(scope), model_id, revision_id),
                ).fetchone()
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        if row is None:
            raise ModelGovernanceNotFound("MODEL_REVISION_NOT_FOUND")
        return self._revision(row)

    @staticmethod
    def _reduce_lifecycle(
        facts: Sequence[ModelLifecycleFact], *, corrupt: bool
    ) -> ModelEligibilityState:
        state = ModelEligibilityState.DRAFT
        transitions = {
            (
                ModelEligibilityState.DRAFT,
                ModelLifecycleAction.VALIDATED,
            ): ModelEligibilityState.VALIDATED,
            (
                ModelEligibilityState.VALIDATED,
                ModelLifecycleAction.HUMAN_REVIEWED,
            ): ModelEligibilityState.HUMAN_REVIEWED,
            (
                ModelEligibilityState.HUMAN_REVIEWED,
                ModelLifecycleAction.PUBLISHED,
            ): ModelEligibilityState.PUBLISHED_ENABLED,
            (
                ModelEligibilityState.PUBLISHED_ENABLED,
                ModelLifecycleAction.DISABLED,
            ): ModelEligibilityState.PUBLISHED_DISABLED,
            (
                ModelEligibilityState.PUBLISHED_DISABLED,
                ModelLifecycleAction.ENABLED,
            ): ModelEligibilityState.PUBLISHED_ENABLED,
            (
                ModelEligibilityState.PUBLISHED_ENABLED,
                ModelLifecycleAction.DEPRECATED,
            ): ModelEligibilityState.DEPRECATED,
            (
                ModelEligibilityState.PUBLISHED_DISABLED,
                ModelLifecycleAction.DEPRECATED,
            ): ModelEligibilityState.DEPRECATED,
            (
                ModelEligibilityState.PUBLISHED_ENABLED,
                ModelLifecycleAction.REVOKED,
            ): ModelEligibilityState.REVOKED,
            (
                ModelEligibilityState.PUBLISHED_DISABLED,
                ModelLifecycleAction.REVOKED,
            ): ModelEligibilityState.REVOKED,
            (
                ModelEligibilityState.DEPRECATED,
                ModelLifecycleAction.REVOKED,
            ): ModelEligibilityState.REVOKED,
        }
        for fact in facts:
            if fact.action is ModelLifecycleAction.SUCCESSOR_CREATED and state in {
                ModelEligibilityState.PUBLISHED_ENABLED,
                ModelEligibilityState.PUBLISHED_DISABLED,
            }:
                continue
            next_state = transitions.get((state, fact.action))
            if next_state is None:
                reason = (
                    "MODEL_GOVERNANCE_STORAGE_CORRUPT"
                    if corrupt
                    else "MODEL_LIFECYCLE_CONFLICT"
                )
                raise ModelGovernanceError(reason)
            state = next_state
        return state

    def append_fact(self, fact: ModelLifecycleFact) -> ModelLifecycleFact:
        try:
            with self.pool.connection() as connection, connection.transaction():
                lock_key = json.dumps(
                    [
                        fact.scope.namespace,
                        fact.scope.security_domain,
                        fact.model.model_id,
                        fact.model.revision_id,
                    ]
                )
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 308))",
                    (lock_key,),
                )
                rows = connection.execute(
                    "SELECT * FROM model_governance.lifecycle_facts WHERE namespace=%s AND security_domain=%s AND model_id=%s AND revision_id=%s ORDER BY ordinal",
                    (
                        *self._scope(fact.scope),
                        fact.model.model_id,
                        fact.model.revision_id,
                    ),
                ).fetchall()
                existing = tuple(self._fact(row) for row in rows)
                expected_ordinal = len(existing) + 1
                if fact.ordinal != expected_ordinal:
                    raise ModelGovernanceConflict("MODEL_LIFECYCLE_CONFLICT")
                try:
                    self._reduce_lifecycle((*existing, fact), corrupt=False)
                except ModelGovernanceError as exc:
                    raise ModelGovernanceConflict("MODEL_LIFECYCLE_CONFLICT") from exc
                connection.execute(
                    "INSERT INTO model_governance.lifecycle_facts(namespace,security_domain,model_id,revision_id,model_digest,ordinal,fact_id,action,actor_id,decision_id,occurred_at,digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        *self._scope(fact.scope),
                        fact.model.model_id,
                        fact.model.revision_id,
                        fact.model.digest,
                        fact.ordinal,
                        fact.fact_id,
                        fact.action.value,
                        fact.actor_id,
                        fact.decision_id,
                        fact.occurred_at,
                        fact.digest,
                        json.dumps(self._record(fact)),
                    ),
                )
        except ModelGovernanceConflict:
            raise
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict("MODEL_LIFECYCLE_CONFLICT") from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        return fact

    def read_lifecycle(
        self,
        scope: ModelScope,
        model_id: str,
        revision_id: str,
        *,
        through_ordinal: int | None = None,
    ) -> ModelEligibility:
        if through_ordinal is not None and (
            isinstance(through_ordinal, bool)
            or not isinstance(through_ordinal, int)
            or through_ordinal < 1
        ):
            raise ModelGovernanceError("MODEL_LIFECYCLE_ORDINAL_INVALID")
        try:
            with self.pool.connection() as connection:
                revision_row = connection.execute(
                    "SELECT * FROM model_governance.model_revisions WHERE namespace=%s AND security_domain=%s AND model_id=%s AND revision_id=%s",
                    (*self._scope(scope), model_id, revision_id),
                ).fetchone()
                if revision_row is None:
                    raise ModelGovernanceNotFound("MODEL_REVISION_NOT_FOUND")
                parameters: tuple[Any, ...] = (
                    *self._scope(scope),
                    model_id,
                    revision_id,
                )
                ordinal_filter = ""
                if through_ordinal is not None:
                    ordinal_filter = " AND ordinal<=%s"
                    parameters = (*parameters, through_ordinal)
                rows = connection.execute(
                    "SELECT * FROM model_governance.lifecycle_facts WHERE namespace=%s AND security_domain=%s AND model_id=%s AND revision_id=%s"
                    + ordinal_filter
                    + " ORDER BY ordinal",
                    parameters,
                ).fetchall()
        except ModelGovernanceNotFound:
            raise
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
        if not rows:
            raise ModelGovernanceNotFound("MODEL_LIFECYCLE_NOT_FOUND")
        revision = self._revision(revision_row)
        facts = tuple(self._fact(row) for row in rows)
        if any(
            fact.ordinal != expected
            or fact.scope != scope
            or fact.model != revision.identity
            for expected, fact in enumerate(facts, 1)
        ):
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_CORRUPT")
        state = self._reduce_lifecycle(facts, corrupt=True)
        latest = facts[-1]
        return ModelEligibility(
            scope,
            revision.identity,
            state,
            ModelLifecycleHighWater(latest.ordinal, latest.fact_id, latest.digest),
        )

    def advance_head(
        self,
        scope: ModelScope,
        model_id: str,
        successor_revision_id: str,
        *,
        expected_aggregate_version: int,
    ) -> ModelDefinition:
        try:
            with self.pool.connection() as connection, connection.transaction():
                definition_row = connection.execute(
                    "SELECT * FROM model_governance.definitions WHERE namespace=%s AND security_domain=%s AND model_id=%s FOR UPDATE",
                    (*self._scope(scope), model_id),
                ).fetchone()
                if definition_row is None:
                    raise ModelGovernanceNotFound("MODEL_DEFINITION_NOT_FOUND")
                definition = self._definition(definition_row)
                if definition.aggregate_version != expected_aggregate_version:
                    raise ModelGovernanceConflict("MODEL_DEFINITION_STALE")
                revision_row = connection.execute(
                    "SELECT * FROM model_governance.model_revisions WHERE namespace=%s AND security_domain=%s AND model_id=%s AND revision_id=%s",
                    (*self._scope(scope), model_id, successor_revision_id),
                ).fetchone()
                if revision_row is None:
                    raise ModelGovernanceNotFound("MODEL_REVISION_NOT_FOUND")
                successor = self._revision(revision_row)
                if successor.predecessor_revision_id != definition.current_revision_id:
                    raise ModelGovernanceConflict("MODEL_REVISION_HEAD_CONFLICT")
                advanced = ModelDefinition(
                    scope=definition.scope,
                    model_id=definition.model_id,
                    owner_id=definition.owner_id,
                    created_by=definition.created_by,
                    created_at=definition.created_at,
                    aggregate_version=definition.aggregate_version + 1,
                    current_revision_id=successor.revision_id,
                )
                connection.execute(
                    "UPDATE model_governance.definitions SET aggregate_version=%s,current_revision_id=%s,record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND model_id=%s AND aggregate_version=%s",
                    (
                        advanced.aggregate_version,
                        advanced.current_revision_id,
                        json.dumps(self._record(advanced)),
                        *self._scope(scope),
                        model_id,
                        expected_aggregate_version,
                    ),
                )
                return advanced
        except (ModelGovernanceConflict, ModelGovernanceNotFound):
            raise
        except _CONFLICTS as exc:
            raise ModelGovernanceConflict("MODEL_DEFINITION_CONFLICT") from exc
        except PsycopgError as exc:
            raise ModelGovernanceError("MODEL_GOVERNANCE_STORAGE_UNAVAILABLE") from exc
